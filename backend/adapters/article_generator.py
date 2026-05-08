"""기사 생성 실제 구현체. rag.llm 3단계 체인."""

from __future__ import annotations

from rag.llm import extract_json, generate_article, verify_article


class LLMArticleGenerator:
    """선택된 보도자료 + 참고기사 chunk로 LLM 3단계 호출하여 기사 생성."""

    def generate(
        self,
        press_releases: list[dict],
        related_chunks: list[dict],
    ) -> dict:
        """
        Args:
            press_releases: [{id, title, source, date, content_text, detail_url}, ...]
            related_chunks: [{chunk_id, source, date, title, original_text, full_text}, ...]
        Returns:
            {title, lead, body, citations, extracted_json}
        """
        # 1차 LLM 입력용 chunk 형태로 통합
        # 보도자료 본문 자체도 chunk처럼 처리
        merged: list[dict] = []
        for pr in press_releases:
            merged.append({
                "source": pr.get("source", ""),
                "date": pr.get("date", ""),
                "title": pr.get("title", ""),
                "original_text": pr.get("content_text") or pr.get("title", ""),
            })
        for c in related_chunks:
            merged.append({
                "source": c.get("source", ""),
                "date": c.get("date", ""),
                "title": c.get("title", ""),
                "original_text": c.get("original_text") or c.get("full_text", ""),
            })

        # citations: 보도자료 + 참고기사 → 번호 매핑
        citations: dict[str, dict] = {}
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

        # LLM 1차: JSON 추출
        try:
            extracted = extract_json(merged)
        except Exception as e:
            extracted = {
                "who": "-", "policy": "-", "decision": "-",
                "target": "-", "numbers": "-", "origin": "-",
                "_error": f"extract_json 실패: {e}",
            }

        # LLM 2차: 기사 생성
        try:
            article = generate_article(extracted, merged)
        except Exception as e:
            article = {
                "title": "(기사 생성 실패)",
                "lead": "",
                "body": f"LLM 호출 실패: {e}",
            }

        return {
            "title": article.get("title", ""),
            "lead": article.get("lead", ""),
            "body": article.get("body", ""),
            "citations": citations,
            "extracted_json": extracted,
        }

    def extract_only(self, press_release: dict) -> dict:
        """보도자료 1건에서 JSON만 추출 (관련기사 검색 시 동시 표시용)."""
        chunk = {
            "source": press_release.get("source", ""),
            "date": press_release.get("date", ""),
            "title": press_release.get("title", ""),
            "original_text": press_release.get("content_text")
                              or press_release.get("title", ""),
        }
        try:
            return extract_json([chunk])
        except Exception as e:
            return {
                "who": "-", "policy": "-", "decision": "-",
                "target": "-", "numbers": "-", "origin": "-",
                "_error": str(e),
            }
