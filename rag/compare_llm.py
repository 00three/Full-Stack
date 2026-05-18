"""
LLM 비교 스크립트: 동일 입력을 OpenAI vs Anthropic 양쪽에 흘려 결과를 나란히 출력.

사용 예시:
    # 1) Query 문자열로 검색부터 실행해 비교
    python -m rag.compare_llm --query "이동통신 단말기 유통구조 개선법"

    # 2) 검색 + 비교 후 결과를 마크다운 파일로 저장
    python -m rag.compare_llm --query "..." --out compare_result.md

    # 3) 모델/개수 옵션
    python -m rag.compare_llm --query "..." \
        --openai-model gpt-4o-mini \
        --anthropic-model claude-sonnet-4-6 \
        --top-k 5

사장님 미팅 데모용. 동일한 검색 결과(같은 참고기사)를 양쪽에 주기 때문에
"검색은 동일, 생성 LLM만 다름"이라는 공정 비교가 됨.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from io import StringIO

from .embedder import encode_query
from .llm import extract_json, generate_article, verify_article
from .search import hybrid_search


def _run_one(
    chunks: list[dict],
    *,
    provider: str,
    model: str,
    ref_body_max_chars: int | None = 300,
    style: str = "default",
) -> dict:
    """선택된 chunk로 1→2→3차 LLM 순차 실행. 각 단계 소요시간 포함."""
    t0 = time.time()
    extracted = extract_json(chunks, provider=provider, model=model)
    t_extract = time.time() - t0

    t1 = time.time()
    article = generate_article(
        extracted,
        chunks,
        provider=provider,
        model=model,
        ref_body_max_chars=ref_body_max_chars,
        style=style,
    )
    t_generate = time.time() - t1

    t2 = time.time()
    verification = verify_article(
        extracted, article, chunks, provider=provider, model=model
    )
    t_verify = time.time() - t2

    return {
        "provider": provider,
        "model": model,
        "style": style,
        "extracted_json": extracted,
        "article": article,
        "verification": verification,
        "timing": {
            "extract": round(t_extract, 2),
            "generate": round(t_generate, 2),
            "verify": round(t_verify, 2),
            "total": round(t_extract + t_generate + t_verify, 2),
        },
    }


def _format_md(query: str, chunks: list[dict], left: dict, right: dict) -> str:
    """양측 결과를 마크다운 비교 포맷으로."""
    buf = StringIO()
    w = buf.write

    w(f"# LLM 비교 — `{query}`\n\n")
    w(f"- 참고기사 (검색 결과): {len(chunks)}건 (양측 동일 입력)\n")
    w(f"- 좌: **{left['provider']} / {left['model']} / style={left.get('style','default')}** — {left['timing']['total']}s\n")
    w(f"- 우: **{right['provider']} / {right['model']} / style={right.get('style','default')}** — {right['timing']['total']}s\n\n")

    # 검색결과 요약
    w("## 검색된 참고기사\n\n")
    for i, c in enumerate(chunks, 1):
        title = c.get("title", "")
        src = c.get("source", "")
        date = c.get("date", "")
        w(f"{i}. [{src} | {date}] {title}\n")
    w("\n")

    # 1차 JSON
    w("## 1차 JSON 추출\n\n")
    w("| 항목 | 좌 | 우 |\n|---|---|---|\n")
    keys = sorted(set(left["extracted_json"].keys()) | set(right["extracted_json"].keys()))
    for k in keys:
        lv = json.dumps(left["extracted_json"].get(k), ensure_ascii=False)
        rv = json.dumps(right["extracted_json"].get(k), ensure_ascii=False)
        w(f"| `{k}` | {lv} | {rv} |\n")
    w("\n")

    # 2차 기사
    w("## 2차 기사 생성\n\n")
    w(f"### {left['provider']} / {left['model']} / style={left.get('style','default')}\n\n")
    w(f"**장르 (모델 자체 판단)**: {left['article'].get('genre') or '—'}\n\n")
    w(f"**제목**: {left['article']['title']}\n\n")
    w(f"**리드**: {left['article']['lead']}\n\n")
    w(f"**본문**:\n\n{left['article']['body']}\n\n")
    w("---\n\n")
    w(f"### {right['provider']} / {right['model']} / style={right.get('style','default')}\n\n")
    w(f"**장르 (모델 자체 판단)**: {right['article'].get('genre') or '—'}\n\n")
    w(f"**제목**: {right['article']['title']}\n\n")
    w(f"**리드**: {right['article']['lead']}\n\n")
    w(f"**본문**:\n\n{right['article']['body']}\n\n")

    # 3차 검증
    w("## 3차 사실검증\n\n")

    def _issues_text(v: dict) -> str:
        # 새 포맷(dict 리스트) → issues_summary 또는 직접 변환
        summ = v.get("issues_summary")
        if summ:
            return "<br>".join(f"- {s}" for s in summ) or "—"
        issues = v.get("issues") or []
        if issues and isinstance(issues[0], dict):
            return "<br>".join(
                f"- {it.get('unsupported_item', '?')} — {it.get('reason', '')}"
                for it in issues
            ) or "—"
        return "; ".join(issues) or "—"

    w("| | 좌 | 우 |\n|---|---|---|\n")
    w(f"| passed | {left['verification'].get('passed')} | {right['verification'].get('passed')} |\n")
    w(f"| unsupported_count | {left['verification'].get('unsupported_count', '—')} | "
      f"{right['verification'].get('unsupported_count', '—')} |\n")
    w(f"| issues | {_issues_text(left['verification'])} | "
      f"{_issues_text(right['verification'])} |\n\n")

    # 타이밍
    w("## 단계별 소요시간 (초)\n\n")
    w("| 단계 | 좌 | 우 |\n|---|---|---|\n")
    for step in ("extract", "generate", "verify", "total"):
        w(f"| {step} | {left['timing'][step]} | {right['timing'][step]} |\n")

    return buf.getvalue()


def _format_terminal(query: str, left: dict, right: dict) -> str:
    """터미널 출력용 간략 포맷."""
    buf = StringIO()
    w = buf.write
    w(f"\n{'=' * 80}\n")
    w(f"Query: {query}\n")
    w(f"{'=' * 80}\n\n")

    for side in (left, right):
        w(f"━━ {side['provider']} / {side['model']} / style={side.get('style','default')}  ({side['timing']['total']}s)\n")
        w(f"장르(모델 판단): {side['article'].get('genre') or '—'}\n")
        w(f"제목: {side['article']['title']}\n")
        w(f"리드: {side['article']['lead']}\n")
        w(f"본문:\n{side['article']['body']}\n")
        v = side["verification"]
        issues_repr = v.get("issues_summary") or v.get("issues") or []
        w(f"검증: passed={v.get('passed')} unsupported_count={v.get('unsupported_count')} "
          f"issues={issues_repr}\n\n")

    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI vs Anthropic 기사 생성 비교")
    parser.add_argument("--query", required=True, help="보도자료/검색 쿼리 텍스트")
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--anthropic-model", default="claude-sonnet-4-6")
    parser.add_argument("--top-k", type=int, default=5, help="검색결과 중 사용할 상위 N개")
    parser.add_argument(
        "--ref-body-max-chars",
        type=int,
        default=300,
        help="참고기사 본문을 프롬프트에 넣을 때 자르는 길이 (0 또는 음수면 자르지 않음)",
    )
    parser.add_argument(
        "--style",
        choices=["default", "mediaus"],
        default="default",
        help="기사 스타일. default=일반 뉴스, mediaus=송창한·고성욱 톤",
    )
    parser.add_argument(
        "--style-compare",
        action="store_true",
        help="좌(default) vs 우(mediaus) 비교 모드. Anthropic 모델 양쪽 사용. "
             "OpenAI vs Anthropic 비교 대신 같은 모델로 두 스타일 비교.",
    )
    parser.add_argument("--out", default=None, help="마크다운 결과 저장 경로 (선택)")
    args = parser.parse_args()

    ref_cap: int | None = args.ref_body_max_chars if args.ref_body_max_chars > 0 else None

    print(f"[1/4] 검색 중: {args.query}", file=sys.stderr)
    qvec = encode_query(args.query)
    results = hybrid_search(args.query, qvec)
    chunks = results[: args.top_k]
    print(f"      → {len(chunks)}건 사용", file=sys.stderr)

    if args.style_compare:
        # 스타일 비교 모드: Anthropic 양쪽, 좌=default 우=mediaus
        print(f"[2/4] Anthropic default style 실행 중 (ref_cap={ref_cap})...", file=sys.stderr)
        left = _run_one(
            chunks, provider="anthropic", model=args.anthropic_model,
            ref_body_max_chars=ref_cap, style="default",
        )
        print(f"      → {left['timing']['total']}s", file=sys.stderr)

        print(f"[3/4] Anthropic mediaus style 실행 중 (ref_cap={ref_cap})...", file=sys.stderr)
        right = _run_one(
            chunks, provider="anthropic", model=args.anthropic_model,
            ref_body_max_chars=ref_cap, style="mediaus",
        )
        print(f"      → {right['timing']['total']}s", file=sys.stderr)
    else:
        # 일반 모드: OpenAI vs Anthropic, 같은 style 적용
        print(f"[2/4] OpenAI ({args.openai_model}) 실행 중 (ref_cap={ref_cap}, style={args.style})...", file=sys.stderr)
        left = _run_one(
            chunks, provider="openai", model=args.openai_model,
            ref_body_max_chars=ref_cap, style=args.style,
        )
        print(f"      → {left['timing']['total']}s", file=sys.stderr)

        print(f"[3/4] Anthropic ({args.anthropic_model}) 실행 중 (ref_cap={ref_cap}, style={args.style})...", file=sys.stderr)
        right = _run_one(
            chunks, provider="anthropic", model=args.anthropic_model,
            ref_body_max_chars=ref_cap, style=args.style,
        )
        print(f"      → {right['timing']['total']}s", file=sys.stderr)

    print("[4/4] 결과 출력\n", file=sys.stderr)
    print(_format_terminal(args.query, left, right))

    if args.out:
        md = _format_md(args.query, chunks, left, right)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"마크다운 저장: {args.out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
