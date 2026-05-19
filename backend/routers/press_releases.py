"""보도자료 API"""

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import (
    get_press_release_provider,
    get_rag_service,
    get_article_generator,
)


router = APIRouter(prefix="/press-releases", tags=["press-releases"])


@router.get("")
def get_press_releases(q: str | None = None, provider=Depends(get_press_release_provider)):
    """보도자료 목록 반환. q=검색어 시 title/source/summary/content_text ILIKE 검색."""
    # provider가 q를 직접 받으면 SQL 레벨에서 본문까지 검색 (DB 구현체)
    try:
        return provider.get_releases(q=q)
    except TypeError:
        # Mock 등 q 파라미터 미지원 → Python 필터로 fallback
        items = provider.get_releases()
        if q:
            ql = q.lower()
            items = [
                i for i in items
                if ql in (i.get("title") or "").lower()
                or ql in (i.get("source") or "").lower()
                or ql in (i.get("summary") or "").lower()
            ]
        return items


@router.get("/related")
def get_related_articles_batch(
    ids: str = "",
    provider=Depends(get_press_release_provider),
    rag=Depends(get_rag_service),
    gen=Depends(get_article_generator),
):
    """복수 보도자료 ID에 대한 참고 기사 + 핵심 정보 JSON. ids=1,2,3 형태."""
    release_ids = [x.strip() for x in ids.split(",") if x.strip()]
    if not release_ids:
        return {"related": [], "json": _empty_json()}

    seen: set[str] = set()
    merged_related: list[dict] = []
    last_release: dict | None = None

    for rid in release_ids:
        pr = provider.get_release_by_id(rid)
        if not pr:
            continue
        last_release = pr
        # query는 보도자료 본문(또는 제목 fallback)
        query = pr.get("content_text") or pr.get("title", "")
        chunks = rag.search_related(
            query_text=query,
            source_release_id=pr["id"],
            source_release_title=pr.get("title", ""),
            source_release_source=pr.get("source", ""),
            source_release_date=pr.get("date", ""),
        )
        # 같은 chunk_id 중복 제거 + 본인 보도자료 chunk 제외
        for c in chunks:
            cid = c.get("id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            merged_related.append(c)

    return {"related": merged_related, "json": _empty_json()}


@router.get("/related-articles/{article_id}")
def get_related_article_detail(article_id: str, rag=Depends(get_rag_service)):
    """참고 기사(chunk) 원문 조회."""
    content = rag.get_chunk_content(article_id)
    if not content:
        return {"id": article_id, "content_text": "(원문 없음)"}
    return {"id": article_id, "content_text": content.get("content_text", "")}


@router.get("/{release_id}/related")
def get_related_articles(
    release_id: str,
    provider=Depends(get_press_release_provider),
    rag=Depends(get_rag_service),
    gen=Depends(get_article_generator),
):
    """단일 보도자료의 참고 기사 + 기사 핵심 정보."""
    pr = provider.get_release_by_id(release_id)
    if not pr:
        return {"related": [], "json": _empty_json()}

    query = pr.get("content_text") or pr.get("title", "")
    related = rag.search_related(
        query_text=query,
        source_release_id=pr["id"],
        source_release_title=pr.get("title", ""),
        source_release_source=pr.get("source", ""),
        source_release_date=pr.get("date", ""),
    )
    return {"related": related, "json": _empty_json()}


@router.get("/{release_id}")
def get_press_release_detail(release_id: str, provider=Depends(get_press_release_provider)):
    """보도자료 상세 (원문 content_text 포함)."""
    pr = provider.get_release_by_id(release_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Not found")
    return pr


def _empty_json() -> dict:
    return {
        "who": "-",
        "policy": "-",
        "decision": "-",
        "target": "-",
        "numbers": "-",
        "origin": "-",
    }
