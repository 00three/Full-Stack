"""보도자료 API"""

from fastapi import APIRouter, Depends, HTTPException

from backend.data.mock import MOCK_CONTENT, MOCK_JSON, MOCK_RELATED, MOCK_RELATED_CONTENT
from backend.deps import get_press_release_provider

router = APIRouter(prefix="/press-releases", tags=["press-releases"])


@router.get("")
def get_press_releases(q: str | None = None, provider=Depends(get_press_release_provider)):
    """보도자료 목록 반환. q=검색어 시 필터링. 추상화: 담당 확정 시 실제 크롤러 데이터."""
    items = provider.get_releases()
    if q:
        q_lower = q.lower()
        items = [
            i
            for i in items
            if q_lower in i.get("title", "").lower()
            or q_lower in i.get("source", "").lower()
            or q_lower in i.get("summary", "").lower()
        ]
    return items


@router.get("/related")
def get_related_articles_batch(ids: str = "", provider=Depends(get_press_release_provider)):
    """복수 보도자료 ID에 대한 참고 기사 + JSON 통합. ids=1,2,3 형태."""
    release_ids = [x.strip() for x in ids.split(",") if x.strip()]
    if not release_ids:
        return {"related": [], "json": {"who": "-", "policy": "-", "decision": "-", "target": "-", "numbers": "-", "origin": "-"}}

    seen = set()
    merged_related = []
    for rid in release_ids:
        for r in MOCK_RELATED.get(rid, []):
            if r["id"] not in seen:
                seen.add(r["id"])
                merged_related.append(r)

    json_data = MOCK_JSON.get(
        release_ids[-1],
        {"who": "-", "policy": "-", "decision": "-", "target": "-", "numbers": "-", "origin": "-"},
    )
    return {"related": merged_related, "json": json_data}


@router.get("/related-articles/{article_id}")
def get_related_article_detail(article_id: str):
    """참고 기사 원문(content_text) 조회."""
    content = MOCK_RELATED_CONTENT.get(article_id, "(원문 없음)")
    return {"id": article_id, "content_text": content}


@router.get("/{release_id}/related")
def get_related_articles(release_id: str, provider=Depends(get_press_release_provider)):
    """선택된 보도자료 기반 참고 기사 + 기사 핵심 정보. 추상화: 담당 확정 시 실제 RAG."""
    related = MOCK_RELATED.get(release_id, [])
    json_data = MOCK_JSON.get(
        release_id,
        {"who": "-", "policy": "-", "decision": "-", "target": "-", "numbers": "-", "origin": "-"},
    )
    return {"related": related, "json": json_data}


@router.get("/{release_id}")
def get_press_release_detail(release_id: str, provider=Depends(get_press_release_provider)):
    """보도자료 상세 (원문 content_text 포함)."""
    items = provider.get_releases()
    found = next((i for i in items if i.get("id") == release_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    result = dict(found)
    result["content_text"] = MOCK_CONTENT.get(release_id, "")
    return result
