"""
LLM 모듈: 1차 JSON 추출 + 2차 기사 생성 + 3차 사실검증

Provider:
- openai: gpt-4o / gpt-4o-mini 등
- anthropic: claude-sonnet-4-6 / claude-haiku-4-5 등
- bedrock: Amazon Bedrock Converse / ConverseStream 호환 모델
설정은 rag/config.py LLMConfig 또는 환경변수 LLM_PROVIDER로 결정.
함수 인자로 provider/model을 넘기면 그 호출에 한해 override (compare 스크립트용).
"""

import json
import re
from collections.abc import Iterator

import boto3
from anthropic import Anthropic
from openai import OpenAI

from .config import llm_config


# ──────────────────────────────────────────────
# Provider 추상화
# ──────────────────────────────────────────────

_openai_client: OpenAI | None = None
_anthropic_client: Anthropic | None = None
_bedrock_client = None


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


# 단계별 권장 temperature
# - 추출(1차): 결정적이어야 함 (같은 입력 → 같은 JSON)
# - 생성(2차): 자연스러운 문장 위해 약간의 변동
# - 검증(3차): 같은 환각을 일관되게 catch (결정적)
EXTRACT_TEMP = 0.0
GENERATE_TEMP = 0.4
VERIFY_TEMP = 0.0


def _get_bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=llm_config.bedrock_region)
    return _bedrock_client


def _resolve_provider_model(provider: str | None, model: str | None) -> tuple[str, str]:
    resolved_provider = provider or llm_config.provider
    if model:
        return resolved_provider, model
    if resolved_provider == "anthropic":
        return resolved_provider, llm_config.anthropic_model
    if resolved_provider == "bedrock":
        if not llm_config.bedrock_model_id:
            raise RuntimeError("BEDROCK_MODEL_ID가 설정되지 않았습니다.")
        return resolved_provider, llm_config.bedrock_model_id
    return resolved_provider, llm_config.openai_model


def _bedrock_request(
    system_prompt: str,
    user_prompt: str,
    model: str,
    *,
    temperature: float,
    max_tokens: int | None = None,
) -> dict:
    inference_config = {"maxTokens": max_tokens or llm_config.max_tokens}
    if "claude-opus-4-7" not in model:
        inference_config["temperature"] = temperature

    return {
        "modelId": model,
        "system": [{"text": system_prompt}],
        "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
        "inferenceConfig": inference_config,
    }


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """LLM 호출 (재시도 3회). provider/model 미지정시 config 기본값 사용.

    temperature: None이면 config 기본값 사용. 단계별로 다르게 호출할 때 override.
    """
    provider, model = _resolve_provider_model(provider, model)
    if temperature is None:
        temperature = llm_config.temperature
    effective_max_tokens = max_tokens or llm_config.max_tokens

    last_error = None
    for _ in range(3):
        try:
            if provider == "anthropic":
                resp = _get_anthropic().messages.create(
                    model=model,
                    max_tokens=effective_max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return resp.content[0].text
            if provider == "bedrock":
                resp = _get_bedrock().converse(
                    **_bedrock_request(
                        system_prompt,
                        user_prompt,
                        model,
                        temperature=temperature,
                        max_tokens=effective_max_tokens,
                    )
                )
                return "".join(
                    block.get("text", "")
                    for block in resp["output"]["message"]["content"]
                    if block.get("text")
                )
            else:
                resp = _get_openai().chat.completions.create(
                    model=model,
                    temperature=temperature,
                    max_tokens=effective_max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return resp.choices[0].message.content
        except Exception as e:
            last_error = e

    raise RuntimeError(f"LLM 호출 3회 실패 ({provider}/{model}): {last_error}")


def _stream_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Iterator[str]:
    """LLM 응답 텍스트를 delta 단위로 yield."""
    provider, model = _resolve_provider_model(provider, model)
    if temperature is None:
        temperature = llm_config.temperature
    effective_max_tokens = max_tokens or llm_config.generate_max_tokens

    if provider == "bedrock":
        response = _get_bedrock().converse_stream(
            **_bedrock_request(
                system_prompt,
                user_prompt,
                model,
                temperature=temperature,
                max_tokens=effective_max_tokens,
            )
        )
        for event in response["stream"]:
            delta = event.get("contentBlockDelta", {}).get("delta", {}).get("text")
            if delta:
                yield delta
        return

    if provider == "openai":
        stream = _get_openai().chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=effective_max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta
        return

    # Anthropic direct SDK는 현재 동기 경로만 유지합니다. 스트림 API가 필요하면 provider 레이어에서 확장합니다.
    yield _call_llm(
        system_prompt,
        user_prompt,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=effective_max_tokens,
    )


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
        f"[{c.get('source', '')} | {c.get('date', '')}] {c.get('title', '')}\n"
        f"{_truncate_ref_body(c.get('original_text', ''), _extract_limit_for(i))}"
        for i, c in enumerate(chunks)
    )

    user_prompt = f"""Extract information from the text below and output as JSON.

Schema:
{EXTRACT_SCHEMA}

Text:
{texts}"""

    result = _call_llm(
        EXTRACT_SYSTEM, user_prompt,
        provider=provider,
        model=model,
        temperature=EXTRACT_TEMP,
        max_tokens=llm_config.extract_max_tokens,
    )

    # JSON 파싱 (재시도 포함)
    for attempt in range(3):
        try:
            return _parse_json_object(result)
        except json.JSONDecodeError:
            if attempt < 2:
                result = _call_llm(
                    EXTRACT_SYSTEM,
                    user_prompt + "\n\nThe previous response failed JSON parsing. Output ONLY valid JSON.",
                    provider=provider,
                    model=model,
                    temperature=EXTRACT_TEMP,
                    max_tokens=llm_config.extract_max_tokens,
                )

    fallback = _fallback_extracted_json(chunks)
    fallback["_warning"] = "LLM JSON 파싱 실패로 로컬 fallback 사용"
    return fallback


def _parse_json_object(result: str) -> dict:
    cleaned = result.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("JSON object expected", cleaned, 0)
    return parsed


def _fallback_extracted_json(chunks: list[dict]) -> dict:
    main = chunks[0] if chunks else {}
    text = main.get("original_text", "") or ""
    numbers = ", ".join(re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:명|건|%|원|억원|조원|일|년|월|회|개|곳)?", text)[:8])
    return {
        "who": main.get("source") or None,
        "policy": main.get("title") or None,
        "decision": (text[:220].rstrip() + "...") if len(text) > 220 else text,
        "target": None,
        "numbers": numbers or None,
        "origin": None,
        "effect": None,
    }


# ──────────────────────────────────────────────
# 2차: 기사 생성
# ──────────────────────────────────────────────

ARTICLE_SYSTEM = """You are a professional Korean news reporter writing breaking news articles in 한국어.

WRITING APPROACH:
- Center the article on the core facts from the extracted JSON
- Enrich with background, context, and concrete details from the reference sources
- Length: 1,400-2,200 Korean characters in body when the supplied sources
  contain enough factual material. Write 6-8 paragraphs for normal policy,
  institution, labor, and analysis articles.

GENRE IDENTIFICATION (run FIRST, before composing):
Identify the genre of the MAIN press release and write accordingly. Mixing
genres produces awkward results.
- 정세·정책 보도자료 → analytical news article (사실 단언체, 배경 분석 권장)
- 기관 발표·결정 → straight news (사실·인용 중심, 분석은 절제)
- 편성·행사 안내 → 안내성 단신 (방송일·출연자 위주, 분석 톤 금지)
- 뉴스레터·복수 사건 묶음 → SINGLE 사건만 선택해 단일 기사로 작성, 나머지는 폐기
- 비평·논평 칼럼 → 분석 톤 자체가 본질. 객관 사실 보도처럼 바꾸지 않는다.
If the genre is unclear, default to straight news.

PARAGRAPH STRUCTURE:
- Paragraph 1 (lead, MANDATORY): A headline-style noun-phrase line implicit
  in 제목, then a lead containing 누가·언제·무엇 compressed into 1-2 sentences
  (around 80 chars each). Every article MUST start with a clear lead before
  any other content. No exceptions.
- Paragraphs 2-6: Specific numbers, details, quotations, background, and
  stakeholder context. Each paragraph MUST end with at least one [n] marker
  indicating the source used for that paragraph.
- Final paragraph: Significance or impact, written as established facts
  with a source marker. No speculation.

NAMING CONVENTIONS (mandatory):
- On first mention, write each institution and person in FULL formal name.
  e.g., "방송미디어통신위원회(방미통위)", "유엔개발계획(UNDP)",
       "안규백 국방부 장관"
- After the first mention, short form (약칭) is allowed and preferred for
  flow. e.g., "방미통위", "UNDP", "안 장관"
- Do NOT use ambiguous abbreviations (e.g., "위원회", "장관") without first
  establishing what they refer to.

NO REFERENCES SCENARIO (when 참고기사 is empty or near-empty):
- If reference chunks are empty or contain no usable content, build the
  article ONLY from facts in the MAIN press release / JSON.
- DO NOT supplement with external world knowledge, historical context, or
  general facts not in the MAIN source.
- A shorter article based purely on the MAIN is correct. Inventing background
  to fill space is forbidden in this scenario.

MAIN DOMINANCE (preferred, NOT a quota to pad):
- Prefer for the MAIN press release to occupy at least 60% of the body.
- Reference articles fill background and context only.
- BAD: a paragraph entirely about "the World Bank's commodity report" or
  "the IMF's economic outlook" with no connection to the main decision.
- GOOD: a paragraph about the main decision, mentioning World Bank/IMF
  findings in 1-2 sentences as supporting context.

CRITICAL — when MAIN material is insufficient:
- If the MAIN source and references do not provide enough material for a
  1,400-character body, WRITE A SHORTER BODY. 700-1,000 chars is acceptable.
- 4-5 paragraphs is acceptable if the sources cannot support 6-8.
- PADDING WITH INVENTED DETAILS TO REACH 60% OR THE TARGET LENGTH IS THE WORST
  POSSIBLE ERROR. A shorter, honest article is always better than a longer
  article with invented padding.
- The target length and the 60% dominance rule BOTH bend before
  fabrication. Never invent to satisfy either.

SOURCE ROLES (critical):
- Main press release = source of CORE FACTS (decisions, policies, figures, dates)
- Reference articles = source of BACKGROUND, CONTEXT, and connections to related events
- When citing facts from any source, append [n] markers at the END of the
  sentence or paragraph. Use [1] for the main press release and [2], [3]...
  for reference articles in the order listed below.
- Every body paragraph must contain at least one [n] marker so the frontend
  can show the source tooltip.
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
6. If deletion shortens the body below the target length, that is acceptable. Refer
   to the MAIN DOMINANCE section above — shorter is always better than invented.

OUTPUT FORMAT (write the content in Korean, keep these Korean labels exactly):
장르: [정세보도|기관발표|편성안내|뉴스레터|칼럼|기타]  ← GENRE IDENTIFICATION에서 식별한 결과 명시
제목: ...
리드: ...
본문: ..."""


# ──────────────────────────────────────────────
# 미디어스 스타일 모드 (옵션)
# ──────────────────────────────────────────────
#
# 송창한·고성욱 기자 패턴 + 외부 칼럼 분석 기반.
# 사용: generate_article(..., style="mediaus") 또는 ARTICLE_STYLE=mediaus 환경변수
#
# 핵심 차이점 (vs default):
# - 제목: 단일 명사구 강제 X → "주체, '핵심 키워드' 발언/행동" 콤마 패턴 권장
# - 종결체: 단언체 + 존댓말 혼용 (인용 후 존댓말, 사실은 단언)
# - 비평 동사 자연스럽게 허용 (지적했다, 비판했다, 은폐했다, 규정했다)
# - 단체·노조·기관 성명 직접 인용 강화
# - 메인이 정책/방송/노동/언론 영역일 때 자연스럽게 적용됨

ARTICLE_SYSTEM_MEDIAUS = """You are a Korean reporter writing in the editorial
voice of 미디어스 (mediaus.co.kr), an online publication focused on media
policy, public broadcasting governance, labor-rights journalism, and press
criticism. Your writing should be indistinguishable from articles by reporters
송창한 and 고성욱.

WRITING APPROACH:
- Center the article on the core facts from the extracted JSON
- Enrich with direct quotes from named institutions, unions, and civic groups
- Length: 1,400-2,200 Korean characters in body when the supplied sources
  contain enough factual material. Write 6-8 paragraphs for normal policy,
  public broadcasting, labor, and analysis articles.
- If MAIN material and references are insufficient for the target length,
  write a SHORTER body. Never pad.

GENRE IDENTIFICATION (run FIRST, before composing):
Identify the genre of the MAIN press release. Even in 미디어스 voice, genre
dictates structure.
- 정책·기관 결정 보도자료 → 단언체 사실 보도 + 비평적 맥락
- 노조·시민단체 성명 → 직접 인용 중심, 단체명 정식 → 약칭
- 분석·논평 칼럼 → 분석 톤 자체가 본질, 객관 사실 보도로 바꾸지 않는다
- 편성·행사 안내 → 안내성 단신, 분석 톤 강요 금지
- 뉴스레터·복수 사건 묶음 → SINGLE 가장 중요한 사건만 골라 단일 기사로

EVERY ARTICLE MUST START with a clear lead containing 누가·언제·무엇 압축
into 1-2 sentences. No exceptions.

NAMING CONVENTIONS (mandatory):
- 첫 언급: 정식 명칭 + (약칭) 형태로 명시
  예: "방송미디어통신위원회(방미통위)", "전국언론노동조합(언론노조)",
       "박찬욱 KBS 감사", "이호찬 언론노조 위원장"
- 이후 언급: 약칭 사용 가능. "위원회", "장관" 같은 비특정 단어 단독 사용 금지.

NO REFERENCES SCENARIO:
- 참고기사가 비어있거나 무관하면, MAIN 보도자료 사실만으로 작성.
- 외부 일반 상식 보충 금지. 짧은 기사가 환각 있는 긴 기사보다 백배 낫다.

DOMAIN PRIORITIES (미디어스 areas):
- 공영방송·미디어 거버넌스 (방미통위·방미심위·KBS·MBC·YTN 등)
- 노동·인권 (대기업 노조, 비정규직, 플랫폼 노동, 언론노조)
- 언론 비평·메타 보도 (다른 매체 보도를 분석·비평)
- 미디어 정책·법령

TITLE STYLE (mediaus-specific — different from default mode):
- Preferred pattern: "[주체], [인용/행위 핵심]"
  · 예: "방미통위, 18일 공영방송 이사 추천단체 공모"
  · 예: "KBS 감사, '2인 방통위 적법' 1심 판결에 \"법리 왜곡\""
  · 예: "이 대통령, 조선일보 '순부채비율 착시' 보도에 \"아쉽다\""
- Comma after subject is REQUIRED when followed by a direct/indirect quote
  or a critical action.
- Quotation marks for key phrases ARE encouraged:
  · 큰따옴표 "..." for verbatim quotes or provocative critique keywords
  · 작은따옴표 '...' for nested keywords or formal terms
- End with action verb or noun-ization: "공모", "손본다", "돌입", "의결", "확정"
- Critical adjectives/verbs ALLOWED: 무색한, 쫓아간, 외면한, 손본다
- Avoid: 단일 명사구만으로 끝나서 비평 각도를 잃는 제목

LEAD (1-2 sentences):
- Pattern: "[주체]가/이 [핵심 행동/결정]을 했다. [배경 또는 맥락 한 문장]."
- 단언체로 끝맺음 ("결정했다", "나선다", "밝혔다")
- 1-2번째 문장에 핵심 수치/날짜 포함

ENDING STYLE (mediaus signature — mixed sentence endings):
- Sentences stating facts, dates, numbers → 단언체
  · 예: "방미통위는 15일 전체회의를 열고 추천단체 선정 계획안을 의결했다."
  · 예: "한국 순부채비율은 10.3%로 G20 평균 89.6%를 크게 밑돌고 있다."
- Sentences after direct/indirect quotes → 존댓말체
  · 예: "그는 '법리 왜곡'이라고 강조했습니다."
  · 예: "위원장은 '공정하고 투명한 절차'를 당부했습니다."
- Mixing within an article is normal and expected.
- Do NOT use single ending consistently — alternate based on context.

BODY STRUCTURE (recommended):
1. 첫 단락: 핵심 사실 + 5W1H (단언체)
2. 둘째 단락: 직접·간접 인용 (존댓말체 종결)
3. 셋째 단락: 배경·수치·맥락 (단언체)
4. 넷째 단락: 추가 인용 또는 진영별 입장 정리
5. 다섯째: 참고기사에서 확인한 관련 사건·유사 사례
6. 여섯째 이후: 평가·관전 포인트 또는 제도적 쟁점

SOURCE MARKERS:
- Every body paragraph MUST end with at least one [n] marker.
- Use [1] for the main press release and [2], [3]... for reference articles
  in the order listed below.
- If a paragraph combines main and reference facts, use multiple markers
  such as [1][3].

QUOTATION EMPHASIS (very important):
- Direct quotes from named entities are CENTRAL to mediaus style.
- Preferred sources to quote: 노동조합·시민단체 성명, 기관장 발언, 판결문, 보도자료
- Format: '..."[원문 인용]"라고 [밝혔습니다/지적했습니다/비판했습니다/촉구했습니다]'
- For multi-source pieces (송창한 patterns), organize by stance:
  · "진보 매체 ㅇㅇ은 '...'라고 평가했다"
  · "보수 매체 △△은 '...'라며 반대 입장을 보였다"

CRITICAL VOCABULARY (encouraged when supported by facts):
- 비판 동사: 지적했다, 비판했다, 규정했다, 촉구했다, 항의했다
- 분석적 어휘: 프레임, 구조적, 거버넌스, 자의적, 위축, 은폐, 공모한 셈
- These are mediaus's natural register. Don't sanitize.

NUMERIC SPECIFICITY (mediaus signature):
- 모든 수치를 정확히 인용 (억원, 명, %, 일자, 건수)
- 예: "13억 긴축", "467억 적자", "471억 악화", "100건 심의 중 40% 법정제재"
- Approximate numbers are weaker than verbatim. Always prefer exact.

NO INVENTED DETAILS (zero tolerance — same as default mode):
- 출처에 verbatim 없는 디테일 절대 금지. 짧게 쓰는 게 환각보다 백배 낫다.
- Pre-output traceability check: 모든 수치·발언자 직책·인용문이 JSON/chunks에 있는지 확인.
- 추측 어미 금지: ~가능성이 높다, ~전망된다, ~예상된다 등 default 모드와 동일.

OUTPUT FORMAT (한국어로 작성, 라벨은 그대로):
장르: [정세보도|기관발표|편성안내|뉴스레터|칼럼|기타]  ← GENRE IDENTIFICATION에서 식별한 결과 명시
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


def _extract_limit_for(index: int) -> int:
    """Use more main-source context and shorter reference context for fast extraction."""
    return llm_config.extract_main_max_chars if index == 0 else llm_config.extract_ref_max_chars


def _generate_limit_for(index: int, override: int | None) -> int:
    if override is not None:
        return override
    return llm_config.generate_main_max_chars if index == 0 else llm_config.generate_ref_max_chars


ARTICLE_TONE_INSTRUCTIONS = {
    "default": "기본 말투: 중립적이고 자연스러운 한국어 뉴스 문체를 유지한다.",
    "professional": (
        "전문적 말투: 정제되고 정확한 표현을 사용한다. 행정·정책·법률 용어는 "
        "필요할 때만 풀어 쓰고, 단정적이되 과장하지 않는다."
    ),
    "friendly": (
        "친근한 말투: 독자가 쉽게 따라올 수 있게 문장을 부드럽게 쓴다. "
        "뉴스 형식과 사실 정확성은 유지하고, 지나친 구어체는 피한다."
    ),
    "direct": (
        "솔직한 말투: 핵심을 앞에 두고 직설적으로 쓴다. 우회적 표현을 줄이되 "
        "비난이나 단정적 해석은 출처가 있을 때만 사용한다."
    ),
    "distinctive": (
        "독특한 말투: 제목과 리드에 약간의 리듬감과 신선한 표현을 허용한다. "
        "본문은 기사 문체를 유지하고, 장식적 표현 때문에 사실이 흐려지지 않게 한다."
    ),
    "efficient": (
        "효율적 말투: 문장을 짧게 끊고 중복 설명을 줄인다. 독자가 빠르게 핵심을 "
        "파악하도록 수치·주체·결과를 선명하게 배치한다."
    ),
    "critical": (
        "냉소적 말투: 비판적 관점을 허용하되, 근거가 있는 표현만 사용한다. "
        "조롱·비아냥·인신공격은 금지하고 제도적 쟁점 중심으로 쓴다."
    ),
    "mz": (
        "MZ 뉴스레터/숏폼형 말투: 전형적인 보도자료 문장처럼 쓰지 말고, 20·30대가 "
        "모바일에서 빠르게 읽는 설명형 기사처럼 쓴다. 핵심을 먼저 던지고, 쉬운 말로 "
        "배경과 영향을 풀어준다. 리드는 2-3문장으로 짧게 쓰며 '핵심은 이겁니다', "
        "'왜 중요하냐면', '포인트는' 같은 진입 문장을 자연스럽게 활용한다. 본문은 "
        "문단당 2-3문장 중심으로 짧게 끊고, 각 문단 첫 문장에 '먼저 볼 건', '문제는', "
        "'여기서 체크할 점', '다만', '결국'처럼 독자가 따라가기 쉬운 표지어를 넣을 수 "
        "있다. 기관명·법안명·수치는 그대로 쓰되 어려운 용어는 괄호나 짧은 설명으로 "
        "풀어준다. 독자에게 왜 내 일처럼 중요한지, 지금 무엇을 봐야 하는지까지 연결한다. "
        "어휘는 '핵심', '포인트', '이슈', '쟁점', '체감', '논란', '관전 포인트', "
        "'한 줄로 보면' 정도만 절제해서 쓰고, 오래된 신조어·밈·초성체·반말·이모지·"
        "낚시성 제목은 금지한다. 친근하지만 가벼워 보이지 않게, 모든 주장과 수치는 "
        "반드시 제공된 출처 안에서만 쓴다."
    ),
}


def _tone_instruction(tone: str | None) -> str:
    key = (tone or "default").lower()
    return ARTICLE_TONE_INSTRUCTIONS.get(key, ARTICLE_TONE_INSTRUCTIONS["default"])


def generate_article(
    extracted_json: dict,
    chunks: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
    ref_body_max_chars: int | None = None,
    style: str | None = None,
    tone: str | None = None,
) -> dict:
    """JSON + 참고 chunk로 속보기사 생성 (2차 LLM).

    ref_body_max_chars:
        참고기사 본문을 LLM 프롬프트에 넣을 때 자르는 길이 (기본 300자).
        참고가 메인을 정보량으로 압도하는 현상 완화 목적.
        None 또는 0 이하면 자르지 않음 (구버전 동작).
    style:
        "default" (기본) | "mediaus" (송창한·고성욱 기자 스타일).
        None이면 ARTICLE_STYLE 환경변수 또는 "default".
    """
    # style 결정: 인자 > config (=환경변수) > "default"
    effective_style = (style or llm_config.article_style or "default").lower()
    if effective_style == "mediaus":
        system_prompt = ARTICLE_SYSTEM_MEDIAUS
    else:
        system_prompt = ARTICLE_SYSTEM

    chunk_refs = "\n\n".join(
        f"[{i+1}] [{c.get('source', '')} | {c.get('date', '')}] {c.get('title', '')}\n"
        f"Body: {_truncate_ref_body(c.get('original_text', ''), _generate_limit_for(i, ref_body_max_chars))}"
        for i, c in enumerate(chunks)
    )

    user_prompt = f"""Write a Korean breaking news article based on the JSON below.

Writing requirements:
- Target body length: 1,400-2,200 Korean characters when the listed sources
  contain enough facts.
- Write 6-8 body paragraphs for normal policy/institution/labor articles.
- End every body paragraph with at least one citation marker like [1] or [2].
- Do not invent facts to satisfy length. If sources are thin, write shorter.
- Tone: {_tone_instruction(tone)}

Extracted JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

Reference sources:
{chunk_refs}"""

    result = _call_llm(
        system_prompt, user_prompt,
        provider=provider,
        model=model,
        temperature=GENERATE_TEMP,
        max_tokens=llm_config.generate_max_tokens,
    )

    # genre는 메타필드. 프론트엔 안 노출, 디버깅·분석용.
    return parse_article_text(result)


def stream_generate_article_text(
    extracted_json: dict,
    chunks: list[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
    ref_body_max_chars: int | None = None,
    style: str | None = None,
    tone: str | None = None,
) -> Iterator[str]:
    """기사 생성 원문을 token delta 단위로 stream."""
    effective_style = (style or llm_config.article_style or "default").lower()
    system_prompt = ARTICLE_SYSTEM_MEDIAUS if effective_style == "mediaus" else ARTICLE_SYSTEM
    chunk_refs = "\n\n".join(
        f"[{i+1}] [{c.get('source', '')} | {c.get('date', '')}] {c.get('title', '')}\n"
        f"Body: {_truncate_ref_body(c.get('original_text', ''), _generate_limit_for(i, ref_body_max_chars))}"
        for i, c in enumerate(chunks)
    )
    user_prompt = f"""Write a Korean breaking news article based on the JSON below.

Writing requirements:
- Target body length: 1,400-2,200 Korean characters when the listed sources
  contain enough facts.
- Write 6-8 body paragraphs for normal policy/institution/labor articles.
- End every body paragraph with at least one citation marker like [1] or [2].
- Do not invent facts to satisfy length. If sources are thin, write shorter.
- Tone: {_tone_instruction(tone)}

Extracted JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

Reference sources:
{chunk_refs}"""
    yield from _stream_llm(
        system_prompt,
        user_prompt,
        provider=provider,
        model=model,
        temperature=GENERATE_TEMP,
        max_tokens=llm_config.generate_max_tokens,
    )


def parse_article_text(result: str) -> dict:
    """LLM 원문 출력에서 제목/리드/본문 블록을 파싱."""
    article = {"genre": "", "title": "", "lead": "", "body": ""}
    lines = result.strip().split("\n")
    current = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("장르:"):
            current = "genre"
            article["genre"] = stripped.replace("장르:", "").strip()
        elif stripped.startswith("제목:"):
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

    result = _call_llm(
        VERIFY_SYSTEM, user_prompt,
        provider=provider, model=model, temperature=VERIFY_TEMP,
    )

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
