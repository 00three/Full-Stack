"""
LLM 모듈: 1차 JSON 추출 + 2차 기사 생성 + 3차 사실검증
"""

import json

from openai import OpenAI

from .config import llm_config


def _get_client() -> OpenAI:
    return OpenAI(api_key=llm_config.api_key)


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """OpenAI API 호출 (재시도 3회)"""
    client = _get_client()
    last_error = None

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=llm_config.model,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e

    raise RuntimeError(f"LLM 호출 3회 실패: {last_error}")


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


def extract_json(chunks: list[dict]) -> dict:
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

    result = _call_llm(EXTRACT_SYSTEM, user_prompt)

    # JSON 파싱 (재시도 포함)
    for attempt in range(3):
        try:
            # ```json ... ``` 감싸진 경우 처리
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

SOURCE ROLES (critical):
- Main press release = source of CORE FACTS (decisions, policies, figures, dates)
- Reference articles = source of BACKGROUND, CONTEXT, and connections to related events
- When citing facts from reference articles, append [n] markers at the END of the sentence
- The main press release's conclusion must remain the central axis of the article
- Do NOT let reference articles overwhelm or replace the main message

KOREAN NEWS STYLE (strict):
- Short sentences (around 80 Korean characters each)
- Use ONLY declarative endings. NO speculation, prediction, expectation, or hope expressions.
  Forbidden patterns include but are not limited to:
    ~것으로 보인다, ~할 수 있다, ~될 전망이다, ~예상된다,
    ~기여할 것이다, ~기대된다, ~예측된다, ~할 것으로 분석된다
- Prioritize numbers, proper nouns, and dates in placement
- Minimize adjectives and adverbs; stick to objective facts
- Use a single-line noun-phrase headline with a key action verb (no parentheses, no subtitle)

ABSOLUTE RULES:
- NEVER add content not present in the JSON or reference sources
- All factual claims must be traceable to the provided inputs

OUTPUT FORMAT (write the content in Korean, keep these Korean labels exactly):
제목: ...
리드: ...
본문: ..."""


def generate_article(extracted_json: dict, chunks: list[dict]) -> dict:
    """JSON + 참고 chunk로 속보기사 생성 (2차 LLM)"""
    chunk_refs = "\n\n".join(
        f"[{i+1}] [{c.get('source', '')} | {c.get('date', '')}] {c.get('title', '')}\n"
        f"Body: {c.get('original_text', '')}"
        for i, c in enumerate(chunks)
    )

    user_prompt = f"""Write a Korean breaking news article based on the JSON below.

Extracted JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

Reference sources:
{chunk_refs}"""

    result = _call_llm(ARTICLE_SYSTEM, user_prompt)

    # 파싱: 제목/리드/본문 분리
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

VERIFY_SYSTEM = """You are a fact-checking expert.
Compare the JSON extracted in step 1 against the article generated in step 2, and identify mismatches.

CHECK ITEMS:
- Are institution names accurate?
- Do numerical values (amounts, counts, dates) match?
- Has any content been added to the article that is NOT in the JSON?

OUTPUT FORMAT (JSON):
{
  "passed": true/false,
  "issues": ["mismatch description 1", "mismatch description 2"]
}"""


def verify_article(extracted_json: dict, article: dict) -> dict:
    """생성된 기사를 1차 JSON과 비교하여 사실검증 (3차 LLM)"""
    user_prompt = f"""Step 1 extracted JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

Generated article:
Title: {article['title']}
Lead: {article['lead']}
Body: {article['body']}"""

    result = _call_llm(VERIFY_SYSTEM, user_prompt)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"passed": False, "issues": ["검증 결과 파싱 실패"]}
