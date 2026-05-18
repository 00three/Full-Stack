"""
LLM 모듈: 1차 JSON 추출 + 2차 기사 생성 + 3차 사실검증

Provider:
- openai: gpt-4o / gpt-4o-mini 등
- anthropic: claude-sonnet-4-6 / claude-haiku-4-5 등
설정은 rag/config.py LLMConfig 또는 환경변수 LLM_PROVIDER로 결정.
함수 인자로 provider/model을 넘기면 그 호출에 한해 override (compare 스크립트용).
"""

import json

from anthropic import Anthropic
from openai import OpenAI

from .config import llm_config


# ──────────────────────────────────────────────
# Provider 추상화
# ──────────────────────────────────────────────

_openai_client: OpenAI | None = None
_anthropic_client: Anthropic | None = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=llm_config.openai_api_key)
    return _openai_client


def _get_anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=llm_config.anthropic_api_key)
    return _anthropic_client


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """LLM 호출 (재시도 3회). provider/model 미지정시 config 기본값 사용."""
    provider = provider or llm_config.provider
    if model is None:
        model = (
            llm_config.anthropic_model if provider == "anthropic" else llm_config.openai_model
        )

    last_error = None
    for _ in range(3):
        try:
            if provider == "anthropic":
                resp = _get_anthropic().messages.create(
                    model=model,
                    max_tokens=llm_config.max_tokens,
                    temperature=llm_config.temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return resp.content[0].text
            else:
                resp = _get_openai().chat.completions.create(
                    model=model,
                    temperature=llm_config.temperature,
                    max_tokens=llm_config.max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return resp.choices[0].message.content
        except Exception as e:
            last_error = e

    raise RuntimeError(f"LLM 호출 3회 실패 ({provider}/{model}): {last_error}")


# ──────────────────────────────────────────────
# 1차: JSON 구조화 추출
# ──────────────────────────────────────────────

EXTRACT_SYSTEM = """You are an expert at extracting key facts from Korean press releases.
Extract information from the given text and output ONLY in valid JSON format.
Do not speculate. Mark missing information as null."""

EXTRACT_SCHEMA = """{
  "who": "기관/단체명",
  "policy": "정책/사업명",
  "decision": "결정/조치 내용",
  "target": "대상",
  "numbers": "수치 정보",
  "origin": "배경/기원",
  "effect": "효과/영향"
}"""


def extract_json(
    chunks: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """선택된 chunk들에서 핵심 팩트를 JSON으로 추출 (1차 LLM)"""
    texts = "\n\n---\n\n".join(
        f"[{c.get('source', '')} | {c.get('date', '')}] {c['original_text']}"
        for c in chunks
    )

    user_prompt = f"""Extract information from the text below and output as JSON.

Schema:
{EXTRACT_SCHEMA}

Text:
{texts}"""

    result = _call_llm(EXTRACT_SYSTEM, user_prompt, provider=provider, model=model)

    # JSON 파싱 (재시도 포함)
    for attempt in range(3):
        try:
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt < 2:
                result = _call_llm(
                    EXTRACT_SYSTEM,
                    user_prompt + "\n\nThe previous response failed JSON parsing. Output ONLY valid JSON.",
                    provider=provider,
                    model=model,
                )

    raise RuntimeError("JSON 파싱 3회 실패")


# ──────────────────────────────────────────────
# 2차: 기사 생성
# ──────────────────────────────────────────────

ARTICLE_SYSTEM = """You are a professional Korean news reporter writing breaking news articles in 한국어.

WRITING APPROACH:
- Center the article on the core facts from the extracted JSON
- Enrich with background, context, and concrete details from the reference sources
- Length: 600-900 Korean characters in body, 3-5 paragraphs

PARAGRAPH STRUCTURE:
- Paragraph 1 (lead): Compress 5W1H into 1-2 sentences (around 80 chars each)
- Paragraphs 2-3: Specific numbers, details, background. Each paragraph should cite at least one reference with [n] marker when possible
- Final paragraph: Significance or impact, written as established facts (no speculation)

MAIN DOMINANCE (preferred, NOT a quota to pad):
- Prefer for the MAIN press release to occupy at least 60% of the body.
- Reference articles fill background and context only.
- BAD: a paragraph entirely about "the World Bank's commodity report" or
  "the IMF's economic outlook" with no connection to the main decision.
- GOOD: a paragraph about the main decision, mentioning World Bank/IMF
  findings in 1-2 sentences as supporting context.

CRITICAL — when MAIN material is insufficient:
- If the MAIN source does not provide enough material for a 600-character body,
  WRITE A SHORTER BODY. 400-500 chars is acceptable.
- 3-4 paragraphs is acceptable if MAIN cannot support 5.
- PADDING WITH INVENTED DETAILS TO REACH 60% OR 600 CHARS IS THE WORST
  POSSIBLE ERROR. A shorter, honest article is always better than a longer
  article with invented padding.
- The 600-character minimum and the 60% dominance rule BOTH bend before
  fabrication. Never invent to satisfy either.

SOURCE ROLES (critical):
- Main press release = source of CORE FACTS (decisions, policies, figures, dates)
- Reference articles = source of BACKGROUND, CONTEXT, and connections to related events
- When citing facts from reference articles, append [n] markers at the END of the sentence
- The main press release's conclusion must remain the central axis of the article

KOREAN NEWS STYLE (strict):
- Short sentences (around 80 Korean characters each)
- Use ONLY declarative endings. NO speculation, prediction, expectation, or hope expressions.
  Forbidden patterns (zero tolerance):
    ~것으로 보인다, ~할 수 있다, ~될 전망이다, ~예상된다,
    ~기여할 것이다, ~기대된다, ~예측된다, ~할 것으로 분석된다,
    ~가능성이 높다, ~가능성도 있다, ~검토할 수 있다, ~열어뒀다,
    ~열어두었다, ~검토 중이다 (when source states decision is firm),
    ~예고된다, ~할 것으로 보인다, ~전망된다
- Self-check before output: scan draft for "가능성", "전망", "예상", "기대".
  If any of these appear AND are not direct quotes from sources, rewrite the
  sentence as a present-tense factual statement.
- Prioritize numbers, proper nouns, and dates in placement
- Minimize adjectives and adverbs; stick to objective facts

TITLE RULES (strict):
- Write a SINGLE noun phrase ending with one key action verb-noun
  (e.g., "동결", "추진", "제출", "결정", "발표").
- NO comma-separated dual topics. Pick the strongest single fact.
- NO parentheses, NO subtitle, NO em-dash, NO middle dot lists at end.
- GOOD: "미 연준 4월 FOMC 기준금리 3.50~3.75% 3회 연속 동결"
- BAD:  "미 연준 기준금리 동결, 찬성 8·반대 4 1992년 이후 최다 이견"
        (two topics joined by comma)
- BAD:  "여야 6당 187명 개헌안 국회 제출, KBS 계엄 생방송 의혹 동시 부상"
        (two unrelated events)
- If two facts seem equally important, embed the secondary one as a
  modifier in a single noun phrase, not as a second clause.

NO INVENTED DETAILS (zero tolerance — strictest rule):
- Do NOT add specific job-term dates, percentages, named clauses, treaty
  terms, regulatory provisions, organizational positions, or named multi-step
  proposals that do not appear VERBATIM in the JSON or reference text.
- Do NOT supplement with general world knowledge even if factually plausible.
  Forbidden inventions include patterns like:
    "이사직은 N년까지 유지된다" (when source only states 의장직 임기)
    "반도체 수출 호조" (when source doesn't mention semiconductors)
    "우라늄 농축 규제와 해협 통제권" (when source doesn't list these)
    "1단계 ~ 2단계 ~ 3단계 ~" (named stage proposals)
    "1,743억 달러로 줄어" (specific monetary figures from nowhere)
    "~에 따른 ~ 효과" (chains of cause not stated in sources)
- If a connection seems "obvious" but isn't stated in any source, OMIT it.
- When uncertain whether a detail came from a source, OMIT it.
- ABSOLUTE RULE: every named entity, percentage, date, monetary figure,
  named multi-step proposal, and quoted position MUST be traceable to a
  specific sentence in either the JSON or the reference chunks. If you
  cannot point to that sentence, the detail is invalid and must be removed.

PRE-OUTPUT TRACEABILITY CHECK (mandatory — run silently before final output):
Before writing 제목/리드/본문, perform this internal scan on every sentence
you intend to include:
1. List each specific number in the sentence (e.g., "3,250만 명", "1,743억 달러")
2. List each named clause/proposal/policy (e.g., "단계적 협상안",
   "에너지 자립도 제고", "현금 지원")
3. List each specific date and named individual
4. For each item, ask: "Which JSON field or which reference chunk contains
   this exact item?"
5. If you cannot answer for any item, DELETE the sentence (do not soften it,
   do not paraphrase it — delete it entirely).
6. If deletion shortens the body below 600 chars, that is acceptable. Refer
   to the MAIN DOMINANCE section above — shorter is always better than invented.

OUTPUT FORMAT (write the content in Korean, keep these Korean labels exactly):
제목: ...
리드: ...
본문: ..."""


def _truncate_ref_body(text: str, max_chars: int | None) -> str:
    """참고기사 본문을 max_chars로 자름. None이면 원본 유지."""
    if not text or max_chars is None or max_chars <= 0:
        return text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def generate_article(
    extracted_json: dict,
    chunks: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
    ref_body_max_chars: int | None = 300,
) -> dict:
    """JSON + 참고 chunk로 속보기사 생성 (2차 LLM).

    ref_body_max_chars:
        참고기사 본문을 LLM 프롬프트에 넣을 때 자르는 길이 (기본 300자).
        참고가 메인을 정보량으로 압도하는 현상 완화 목적.
        None 또는 0 이하면 자르지 않음 (구버전 동작).
    """
    chunk_refs = "\n\n".join(
        f"[{i+1}] [{c.get('source', '')} | {c.get('date', '')}] {c.get('title', '')}\n"
        f"Body: {_truncate_ref_body(c.get('original_text', ''), ref_body_max_chars)}"
        for i, c in enumerate(chunks)
    )

    user_prompt = f"""Write a Korean breaking news article based on the JSON below.

Extracted JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

Reference sources:
{chunk_refs}"""

    result = _call_llm(ARTICLE_SYSTEM, user_prompt, provider=provider, model=model)

    article = {"title": "", "lead": "", "body": ""}
    lines = result.strip().split("\n")
    current = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("제목:"):
            current = "title"
            article["title"] = stripped.replace("제목:", "").strip()
        elif stripped.startswith("리드:"):
            current = "lead"
            article["lead"] = stripped.replace("리드:", "").strip()
        elif stripped.startswith("본문:"):
            current = "body"
            article["body"] = stripped.replace("본문:", "").strip()
        elif current == "body" and stripped:
            article["body"] += "\n" + stripped

    return article


# ──────────────────────────────────────────────
# 3차: 사실검증
# ──────────────────────────────────────────────

VERIFY_SYSTEM = """You are a strict fact-checking expert for Korean news.
You receive: (1) the extracted JSON from main press release(s),
(2) the reference chunks that were used, and (3) the generated article.

Your job: identify EVERY specific claim in the generated article that is
NOT directly supported by either the JSON or one of the reference chunks.

WHAT COUNTS AS A SPECIFIC CLAIM (be paranoid — flag liberally):
1. Named entities: institutions, persons, places, programs, reports
   (verify exact spelling and identity)
2. Numerical values: amounts, counts, percentages, monetary figures
   (e.g., "1,743억 달러", "3,250만 명") — same number must appear in source
3. Specific dates and time periods
4. Named multi-step proposals (e.g., "1단계 ~ 2단계 ~ 3단계 ~")
5. Specific clauses, terms, regulatory provisions, treaty conditions
   (e.g., "에너지 자립도 제고", "우라늄 농축 규제")
6. Direct or indirect attributions of position to a person or institution
7. Causal claims ("A로 인해 B가 발생했다") — both A and B must be in source

VERIFICATION STANCE:
- Better to flag a false positive than miss real hallucination.
- "Plausible world knowledge" does NOT count as support. Only the JSON
  or reference chunks count.
- Near-paraphrase counts as support; pure invention does not.

OUTPUT FORMAT (JSON only — no markdown fence):
{
  "passed": boolean,
  "unsupported_count": integer,
  "issues": [
    {
      "sentence": "<the offending sentence, ≤80 chars>",
      "unsupported_item": "<the specific claim that is not in sources>",
      "reason": "<one short clause: e.g., 'no chunk mentions 1,743억 달러'>"
    }
  ]
}

passed = true ONLY if unsupported_count == 0."""


def verify_article(
    extracted_json: dict,
    article: dict,
    chunks: list[dict] | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """생성된 기사를 JSON + 참고 chunks와 비교하여 사실검증 (3차 LLM).

    chunks:
        2차 생성에 사용된 참고 chunks. None이면 구버전 동작(JSON만 비교).
        환각 검증 정확도를 위해 가능하면 전달할 것.
    """
    chunk_block = ""
    if chunks:
        chunk_block = "\n\nReference chunks used:\n" + "\n\n".join(
            f"[{i+1}] {c.get('source', '')} | {c.get('date', '')} | "
            f"{c.get('title', '')}\n{c.get('original_text', '')[:500]}"
            for i, c in enumerate(chunks)
        )

    user_prompt = f"""Step 1 extracted JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}
{chunk_block}

Generated article:
Title: {article['title']}
Lead: {article['lead']}
Body: {article['body']}"""

    result = _call_llm(VERIFY_SYSTEM, user_prompt, provider=provider, model=model)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = json.loads(cleaned)
        # 호환성: 구버전 키 보존 (이미 string list로 issues 반환하는 호출자 대비)
        if isinstance(parsed.get("issues"), list) and parsed["issues"] and isinstance(parsed["issues"][0], dict):
            # 새 구조에서 string 요약도 같이 노출
            parsed["issues_summary"] = [
                f"{it.get('unsupported_item', '?')} — {it.get('reason', '')}"
                for it in parsed["issues"]
            ]
        return parsed
    except json.JSONDecodeError:
        return {"passed": False, "unsupported_count": -1, "issues": [], "issues_summary": ["검증 결과 파싱 실패"]}
