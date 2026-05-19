"""기사 생성 API"""

import json
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.deps import (
    get_press_release_provider,
    get_rag_service,
    get_article_generator,
    get_article_repository,
)
from backend.llm_catalog import resolve_model
from rag.config import llm_config


router = APIRouter(prefix="/articles", tags=["articles"])


class GenerateRequest(BaseModel):
    press_release_ids: list[str]
    related_article_ids: list[str]
    created_by: str | None = None
    model_key: str | None = None
    article_style: Literal["default", "mediaus"] | None = None


@router.post("/generate")
def generate_article(
    body: GenerateRequest,
    provider=Depends(get_press_release_provider),
    rag=Depends(get_rag_service),
    gen=Depends(get_article_generator),
    repo=Depends(get_article_repository),
):
    """선택된 보도자료 + 참고기사를 컨텍스트로 LLM 기사 생성."""
    try:
        selected_model = resolve_model(body.model_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    article_style = body.article_style or llm_config.article_style

    press_releases = []
    for rid in body.press_release_ids:
        pr = provider.get_release_by_id(rid)
        if pr:
            press_releases.append(pr)

    related_chunks = rag.get_chunks_by_ids(body.related_article_ids)

    article = gen.generate(
        press_releases=press_releases,
        related_chunks=related_chunks,
        provider=selected_model.provider,
        model=selected_model.model_id,
        style=article_style,
        created_by=body.created_by,
    )
    article["article_id"] = repo.save(
        article=article,
        press_release_ids=body.press_release_ids,
        selected_chunk_ids=body.related_article_ids,
        created_by=body.created_by,
        llm_provider=selected_model.provider,
        llm_model_id=selected_model.model_id,
        article_style=article_style,
    )
    return article


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _stage(stage: str, message: str, **extra) -> str:
    return _sse({"type": "stage", "stage": stage, "message": message, **extra})


@router.post("/generate/stream")
def stream_generate_article(
    body: GenerateRequest,
    provider=Depends(get_press_release_provider),
    rag=Depends(get_rag_service),
    gen=Depends(get_article_generator),
    repo=Depends(get_article_repository),
):
    """기사 생성 진행 상황과 초안 토큰을 SSE로 반환."""
    try:
        selected_model = resolve_model(body.model_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    article_style = body.article_style or llm_config.article_style

    def event_stream() -> Iterator[str]:
        try:
            press_releases = []
            for rid in body.press_release_ids:
                pr = provider.get_release_by_id(rid)
                if pr:
                    press_releases.append(pr)
            if not press_releases:
                raise RuntimeError("선택한 보도자료를 찾지 못했습니다.")

            related_chunks = rag.get_chunks_by_ids(body.related_article_ids)

            final_article = None
            for event in gen.stream_generate(
                press_releases=press_releases,
                related_chunks=related_chunks,
                provider=selected_model.provider,
                model=selected_model.model_id,
                style=article_style,
                created_by=body.created_by,
            ):
                if event["type"] == "article":
                    final_article = event["article"]
                    continue
                yield _sse(event)

            if final_article is None:
                raise RuntimeError("기사 생성 결과가 비어 있습니다.")

            yield _stage("saving", "생성 결과를 DB에 저장하는 중입니다.")
            final_article["article_id"] = repo.save(
                article=final_article,
                press_release_ids=body.press_release_ids,
                selected_chunk_ids=body.related_article_ids,
                created_by=body.created_by,
                llm_provider=selected_model.provider,
                llm_model_id=selected_model.model_id,
                article_style=article_style,
            )
            yield _sse({"type": "complete", "article": final_article})
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
