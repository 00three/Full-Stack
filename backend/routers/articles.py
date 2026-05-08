"""기사 생성 API"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.deps import get_press_release_provider, get_rag_service, get_article_generator


router = APIRouter(prefix="/articles", tags=["articles"])


class GenerateRequest(BaseModel):
    press_release_ids: list[str]
    related_article_ids: list[str]


@router.post("/generate")
def generate_article(
    body: GenerateRequest,
    provider=Depends(get_press_release_provider),
    rag=Depends(get_rag_service),
    gen=Depends(get_article_generator),
):
    """선택된 보도자료 + 참고기사를 컨텍스트로 LLM 기사 생성."""

    press_releases = []
    for rid in body.press_release_ids:
        pr = provider.get_release_by_id(rid)
        if pr:
            press_releases.append(pr)

    related_chunks = rag.get_chunks_by_ids(body.related_article_ids)

    return gen.generate(press_releases=press_releases, related_chunks=related_chunks)
