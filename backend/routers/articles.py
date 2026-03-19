"""기사 생성 API (스켈레톤)"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.data.mock import MOCK_PRESS_RELEASES, MOCK_RELATED

router = APIRouter(prefix="/articles", tags=["articles"])


class GenerateRequest(BaseModel):
    press_release_ids: list[str]
    related_article_ids: list[str]


def _get_citation_sources(press_release_ids: list[str], related_article_ids: list[str]) -> dict:
    """보도자료·참고기사 ID로 출처 메타데이터 구성."""
    citations = {}
    idx = 1

    for rid in press_release_ids:
        pr = next((p for p in MOCK_PRESS_RELEASES if p.get("id") == rid), None)
        if pr:
            citations[str(idx)] = {
                "category": f"{pr.get('source', '')} 보도자료",
                "title": pr.get("title", ""),
                "date": pr.get("date", ""),
                "url": pr.get("detail_url", ""),
            }
            idx += 1

    for aid in related_article_ids:
        for rid, articles in MOCK_RELATED.items():
            art = next((a for a in articles if a.get("id") == aid), None)
            if art:
                citations[str(idx)] = {
                    "category": f"{art.get('source', '')} 참고기사",
                    "title": art.get("title", ""),
                    "date": art.get("date", ""),
                    "url": f"#related/{aid}",
                }
                idx += 1
                break

    return citations


@router.post("/generate")
def generate_article(body: GenerateRequest):
    """기사 생성 - 추후 RAG/LLM 연동 시 구현. 현재는 목업 반환. 본문에 [1],[2] 등 출처 마커 포함."""
    citations = _get_citation_sources(body.press_release_ids, body.related_article_ids)
    # 목업: 첫 문단·둘째 문단 끝에 [1] 출처 마커
    body_text = (
        "이번 조치는 연 매출 10억 원 이하 소상공인의 경제 회복을 지원하기 위한 것이다.[1]\n\n"
        "해당 정책은 코로나19 확산 당시인 2022년 처음 도입됐으며 현재 약 2만 명의 이용자가 사용하고 있다.[1]"
    )
    if len(citations) >= 2:
        body_text = (
            "이번 조치는 연 매출 10억 원 이하 소상공인의 경제 회복을 지원하기 위한 것이다.[1]\n\n"
            "해당 정책은 코로나19 확산 당시인 2022년 처음 도입됐으며 현재 약 2만 명의 이용자가 사용하고 있다.[1][2]"
        )
    return {
        "title": "방통위, 소상공인 점포 정보 전송 서비스 2년 연장",
        "lead": "방송통신위원회가 소상공인 점포 정보 전송 서비스의 사전동의 예외 허용을 2년 더 연장하기로 했다.",
        "body": body_text,
        "citations": citations,
    }
