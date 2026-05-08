"""
Contextual Retriever (가이드 4단계)

각 chunk가 전체 문서 안에서 어떤 위치·맥락인지 LLM이 1-2 문장 요약을 생성.
이 prefix를 chunk 앞에 붙여 임베딩하면 검색 정확도가 크게 오른다 (Anthropic).

- LLM: gpt-4o-mini (config.LLMConfig 재사용)
- API 키 비어있으면 자동 skip → 빈 문자열 반환
- 호출 실패 시에도 빈 문자열 반환 (전체 ingest는 통과)
- 토큰 사용량/비용 모듈 통계로 누적
"""

from __future__ import annotations

import logging
from threading import Lock

from openai import OpenAI

from .config import llm_config


log = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "너는 문서의 chunk가 전체 문서 안에서 어떤 위치·맥락에 해당하는지 "
    "한국어 1-2 문장으로 요약하는 보조자다. "
    "출력은 맥락 요약만. 부연·인사말·따옴표 금지."
)


_USER_TEMPLATE = """<document>
{document}
</document>

<chunk>
{chunk}
</chunk>

위 chunk가 문서 어느 부분에 해당하는지 1-2문장 한국어로만 답하라."""


# 모듈 통계 (전체 ingest 종료 시 출력용)
_lock = Lock()
_stats = {
    "calls": 0,
    "skipped_no_key": 0,
    "errors": 0,
    "input_tokens": 0,
    "output_tokens": 0,
}


def get_stats() -> dict:
    with _lock:
        return dict(_stats)


def estimate_cost_usd() -> float:
    """gpt-4o-mini 단가: $0.15 / 1M input, $0.60 / 1M output"""
    s = get_stats()
    return round(
        s["input_tokens"] * 0.15 / 1_000_000
        + s["output_tokens"] * 0.60 / 1_000_000,
        4,
    )


def make_context_prefix(
    document: str,
    chunk: str,
    max_doc_chars: int = 8000,
) -> str:
    """
    chunk가 문서에서 차지하는 맥락을 1-2문장으로 생성.
    실패·키없음 시 빈 문자열 반환 (full_text는 prefix 없이 진행).
    """
    if not llm_config.api_key:
        with _lock:
            _stats["skipped_no_key"] += 1
        return ""

    # 입력 문서가 너무 길면 절단 (비용·토큰 제한)
    doc = document[:max_doc_chars]

    try:
        client = OpenAI(api_key=llm_config.api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _USER_TEMPLATE.format(document=doc, chunk=chunk),
                },
            ],
        )
        with _lock:
            _stats["calls"] += 1
            if resp.usage:
                _stats["input_tokens"] += resp.usage.prompt_tokens
                _stats["output_tokens"] += resp.usage.completion_tokens
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log.warning("contextualizer 실패: %s: %s", type(e).__name__, e)
        with _lock:
            _stats["errors"] += 1
        return ""
