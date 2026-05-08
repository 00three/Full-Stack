"""목업 구현체. USE_MOCK=1 일 때 사용."""

from backend.data.mock import (
    MOCK_PRESS_RELEASES,
    MOCK_RELATED,
    MOCK_RELATED_CONTENT,
    MOCK_JSON,
)


class MockPressReleaseProvider:
    def get_releases(self) -> list[dict]:
        return MOCK_PRESS_RELEASES

    def get_release_by_id(self, doc_id: str) -> dict | None:
        from backend.data.mock import MOCK_CONTENT
        for pr in MOCK_PRESS_RELEASES:
            if pr.get("id") == doc_id:
                out = dict(pr)
                out["content_text"] = MOCK_CONTENT.get(doc_id, "")
                return out
        return None


class MockRAGService:
    def search_related(self, query_text, source_release_id=None, source_release_title=None):
        # 간단한 fallback: source_release_id로 mock 데이터 매핑
        return MOCK_RELATED.get(source_release_id or "", [])

    def get_chunk_content(self, chunk_id):
        text = MOCK_RELATED_CONTENT.get(chunk_id)
        return {"id": chunk_id, "content_text": text} if text else None

    def get_chunks_by_ids(self, chunk_ids):
        out = []
        for cid in chunk_ids:
            text = MOCK_RELATED_CONTENT.get(cid, "")
            out.append({
                "chunk_id": cid,
                "source": "mock",
                "date": None,
                "title": cid,
                "original_text": text,
                "full_text": text,
            })
        return out


class MockArticleGenerator:
    def generate(self, press_releases, related_chunks):
        # 첫 보도자료 기준 mock json으로 동작 흉내
        pr_id = press_releases[0]["id"] if press_releases else None
        extracted = MOCK_JSON.get(pr_id, {
            "who": "-", "policy": "-", "decision": "-",
            "target": "-", "numbers": "-", "origin": "-",
        })
        citations = {}
        idx = 1
        for pr in press_releases:
            citations[str(idx)] = {
                "category": f"{pr.get('source', '')} 보도자료",
                "title": pr.get("title", ""),
                "date": pr.get("date", ""),
                "url": pr.get("detail_url", ""),
            }
            idx += 1
        for c in related_chunks:
            citations[str(idx)] = {
                "category": f"{c.get('source', '')} 참고기사",
                "title": c.get("title", ""),
                "date": c.get("date", ""),
                "url": f"#related/{c.get('chunk_id', '')}",
            }
            idx += 1
        return {
            "title": "(mock) 기사 제목",
            "lead": "(mock) 리드 문장",
            "body": "(mock) 본문 [1] [2]",
            "citations": citations,
            "extracted_json": extracted,
        }

    def extract_only(self, press_release):
        return MOCK_JSON.get(press_release.get("id"), {
            "who": "-", "policy": "-", "decision": "-",
            "target": "-", "numbers": "-", "origin": "-",
        })
