"""raw_documents 테이블에서 보도자료 목록을 제공하는 실제 구현체.
Mock 대체용. brew PG (rag_db)를 직접 조회.
"""

from __future__ import annotations

from datetime import date, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor

from rag.config import db_config


# 7일 이내면 is_new 표시
_NEW_DAYS = 7


class DBPressReleaseProvider:
    """raw_documents 테이블 기반 PressReleaseProvider."""

    def get_releases(self, q: str | None = None) -> list[dict]:
        """
        보도자료 목록. q 지정 시 title/summary/content_text/source ILIKE 검색.
        """
        params: list = []
        where = ""
        if q and q.strip():
            where = """
            WHERE title ILIKE %s OR source ILIKE %s
               OR COALESCE(summary, '') ILIKE %s
               OR content_text ILIKE %s
            """
            like = f"%{q.strip()}%"
            params = [like, like, like, like]

        # DISTINCT ON으로 (title, source, date) 동일한 중복 행 제거.
        # 크롤러가 같은 보도자료를 여러 URL로 수집해 doc_id만 다른 케이스가 있어서.
        sql = f"""
            SELECT * FROM (
                SELECT DISTINCT ON (title, source, date)
                    doc_id,
                    source,
                    title,
                    date,
                    summary,
                    content_text,
                    detail_url,
                    crawled_at
                FROM raw_documents
                {where}
                ORDER BY title, source, date, crawled_at DESC
            ) t
            ORDER BY t.date DESC NULLS LAST, t.crawled_at DESC
            LIMIT 200
        """
        with psycopg2.connect(db_config.dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        threshold = date.today() - timedelta(days=_NEW_DAYS)
        out = []
        for r in rows:
            d = r["date"]
            is_new = bool(d and d >= threshold)
            # summary 없으면 본문 앞 80자로 대체
            summary = r["summary"] or (r["content_text"] or "")[:80]
            out.append({
                "id": r["doc_id"],
                "title": r["title"],
                "source": r["source"],
                "date": d.isoformat() if d else None,
                "summary": summary,
                "detail_url": r["detail_url"],
                "is_new": is_new,
            })
        return out

    def get_release_by_id(self, doc_id: str) -> dict | None:
        """단건 조회 (상세보기·기사생성 시 content_text 필요)."""
        sql = """
            SELECT doc_id, source, title, date, summary, content_text, detail_url
            FROM raw_documents
            WHERE doc_id = %s
        """
        with psycopg2.connect(db_config.dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (doc_id,))
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["doc_id"],
            "title": row["title"],
            "source": row["source"],
            "date": row["date"].isoformat() if row["date"] else None,
            "summary": row["summary"],
            "content_text": row["content_text"] or "",
            "detail_url": row["detail_url"],
        }
