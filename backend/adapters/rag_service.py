"""실제 RAG 검색 구현체. rag.search.hybrid_search 래퍼."""

from __future__ import annotations

import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

from rag.config import db_config
from rag.embedder import encode_query
from rag.search import hybrid_search


def _connection():
    conn = psycopg2.connect(db_config.dsn)
    register_vector(conn)
    return conn


class DBRAGService:
    """rag/ 모듈을 백엔드용 응답 포맷으로 래핑."""

    def search_related(
        self,
        query_text: str,
        source_release_id: str | None = None,
        source_release_title: str | None = None,
        source_release_source: str | None = None,
        source_release_date: str | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        """
        query_text로 관련 chunk 검색 → 같은 (source, title, date) 보도자료당
        가장 높은 점수의 chunk 1개만 남겨서 frontend 포맷으로 반환.
        메인 보도자료 자기 자신은 결과에서 제외 (self-retrieval 방지).
        detail_url(원문 링크)도 함께 반환.
        """
        if not query_text or not query_text.strip():
            return []

        emb = encode_query(query_text)
        results = hybrid_search(query_text, emb)

        # 메인 보도자료 식별용 키 (source_release_*가 들어왔을 때만 필터링)
        main_title = (source_release_title or "").strip()
        main_source = (source_release_source or "").strip()
        main_date = (source_release_date or "").strip()
        has_main_filter = bool(main_title)  # title만 있어도 필터 동작

        # 같은 원본 article(=source+title+date)당 가장 점수 높은 chunk 1개만
        seen: set[tuple] = set()
        out: list[dict] = []
        chunk_ids: list[str] = []
        for r in results:
            d = r.get("date")
            date_str = d.isoformat() if hasattr(d, "isoformat") else (d or "")
            r_title = (r.get("title") or "").strip()
            r_source = (r.get("source") or "").strip()

            # ── self-retrieval 제외: 메인 보도자료와 일치하면 스킵
            if has_main_filter and r_title == main_title:
                # title이 같으면 일단 후보, source/date까지 들어왔으면 정확히 매칭
                if not main_source or r_source == main_source:
                    if not main_date or date_str == main_date:
                        continue

            key = (r_source, r_title, date_str)
            if key in seen:
                continue
            seen.add(key)
            chunk_ids.append(r["chunk_id"])
            out.append({
                "id": r["chunk_id"],
                "title": r.get("title") or "",
                "source": r.get("source") or "",
                "date": date_str,
                "source_release_id": source_release_id or "",
                "source_release_title": source_release_title or "",
                "detail_url": "",  # 아래에서 채움
            })
            if len(out) >= max_results:
                break

        # 한 번에 detail_url 일괄 조회 (raw_documents JOIN)
        if chunk_ids:
            url_map = self._fetch_detail_urls(chunk_ids)
            for item in out:
                item["detail_url"] = url_map.get(item["id"], "")

        return out

    def _fetch_detail_urls(self, chunk_ids: list[str]) -> dict[str, str]:
        sql = """
            SELECT d.chunk_id, rd.detail_url
            FROM documents d
            JOIN raw_documents rd ON d.raw_document_id = rd.id
            WHERE d.chunk_id = ANY(%s)
        """
        with _connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (chunk_ids,))
                return {row[0]: (row[1] or "") for row in cur.fetchall()}

    def get_chunk_content(self, chunk_id: str) -> dict | None:
        """단일 chunk 원문 조회 (참고기사 상세보기용)."""
        sql = """
            SELECT chunk_id, source, date, title, original_text, full_text
            FROM documents
            WHERE chunk_id = %s
        """
        with _connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (chunk_id,))
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["chunk_id"],
            "title": row["title"],
            "source": row["source"],
            "date": row["date"].isoformat() if row["date"] else None,
            "content_text": row["original_text"],
        }

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[dict]:
        """여러 chunk를 chunk_id로 일괄 조회 (기사 생성 시 컨텍스트)."""
        if not chunk_ids:
            return []
        sql = """
            SELECT chunk_id, source, date, title, original_text, full_text
            FROM documents
            WHERE chunk_id = ANY(%s)
        """
        with _connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (chunk_ids,))
                rows = cur.fetchall()
        return [
            {
                "chunk_id": r["chunk_id"],
                "source": r["source"],
                "date": r["date"].isoformat() if r["date"] else None,
                "title": r["title"],
                "original_text": r["original_text"],
                "full_text": r["full_text"],
            }
            for r in rows
        ]
