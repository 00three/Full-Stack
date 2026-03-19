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

EXTRACT_SYSTEM = """너는 보도자료에서 핵심 팩트를 추출하는 전문가다.
주어진 텍스트에서 정보를 추출하여 반드시 JSON 형식으로만 출력하라.
추측하지 말고, 텍스트에 없는 정보는 null로 표시하라."""

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

    user_prompt = f"""다음 텍스트에서 정보를 추출하여 JSON으로 출력하라.

스키마:
{EXTRACT_SCHEMA}

텍스트:
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
                    user_prompt + "\n\n이전 응답이 JSON 파싱에 실패했다. 반드시 유효한 JSON만 출력하라.",
                )

    raise RuntimeError("JSON 파싱 3회 실패")


# ──────────────────────────────────────────────
# 2차: 기사 생성
# ──────────────────────────────────────────────

ARTICLE_SYSTEM = """너는 속보기사를 작성하는 전문 기자다.
규칙:
- 첫 문장에 핵심 요약을 넣어라
- 배경 설명은 마지막 단락에 배치하라
- 추측성 표현(~것으로 보인다, ~할 수 있다)은 금지
- JSON에 없는 내용은 절대 추가하지 마라
- 출처 마커 [1], [2]를 문장 끝에 포함하라

출력 형식:
제목: ...
리드: ...
본문: ..."""


def generate_article(extracted_json: dict, chunks: list[dict]) -> dict:
    """JSON + 참고 chunk로 속보기사 생성 (2차 LLM)"""
    chunk_refs = "\n".join(
        f"[{i+1}] [{c.get('source', '')} | {c.get('date', '')}] {c.get('title', '')}"
        for i, c in enumerate(chunks)
    )

    user_prompt = f"""다음 JSON 정보를 기반으로 속보기사를 작성하라.

추출된 정보:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

참고 출처:
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

VERIFY_SYSTEM = """너는 팩트체크 전문가다.
1차에서 추출한 JSON과 2차에서 생성한 기사를 비교하여 불일치를 찾아라.

검증 항목:
- 기관명이 정확한가
- 수치(금액, 인원, 날짜)가 일치하는가
- JSON에 없는 내용이 기사에 추가되었는가

출력 형식 (JSON):
{
  "passed": true/false,
  "issues": ["불일치 내용 1", "불일치 내용 2"]
}"""


def verify_article(extracted_json: dict, article: dict) -> dict:
    """생성된 기사를 1차 JSON과 비교하여 사실검증 (3차 LLM)"""
    user_prompt = f"""1차 추출 JSON:
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

생성된 기사:
제목: {article['title']}
리드: {article['lead']}
본문: {article['body']}"""

    result = _call_llm(VERIFY_SYSTEM, user_prompt)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"passed": False, "issues": ["검증 결과 파싱 실패"]}
