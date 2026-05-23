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
_SUMMARY_PREVIEW_LIMIT = 220


def _preview_summary(summary: str | None, content_text: str | None) -> str:
    """Return a readable list preview without cutting fallback text mid-flow."""
    source = summary or content_text or ""
    normalized = " ".join(source.split())
    if len(normalized) <= _SUMMARY_PREVIEW_LIMIT:
        return normalized

    cut = normalized[:_SUMMARY_PREVIEW_LIMIT].rstrip()
    sentence_end = max(cut.rfind(mark) for mark in (".", "!", "?", "다.", "요.", "함.", "임."))
    if sentence_end >= 80:
        return cut[: sentence_end + 1].rstrip()

    split_at = max(cut.rfind(mark) for mark in (" ", ",", "·", "…", "-"))
    if split_at >= 120:
        cut = cut[:split_at].rstrip()
    return f"{cut}..."


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
            WHERE document_kind = 'press_release'
              AND (
                  title ILIKE %s OR source ILIKE %s
                  OR COALESCE(summary, '') ILIKE %s
                  OR content_text ILIKE %s
              )
            """
            like = f"%{q.strip()}%"
            params = [like, like, like, like]
        else:
            where = "WHERE document_kind = 'press_release'"

        # DISTINCT ON으로 (title, source, date) 동일한 중복 행 제거.
        # 같은 보도자료가 공백/언더스코어 doc_id로 중복 수집된 경우에는
        # reference_article이 연결된 행을 우선 노출해야 관련기사 매핑이 살아난다.
        sql = f"""
            SELECT * FROM (
                SELECT DISTINCT ON (rd.title, rd.source, rd.date)
                    rd.doc_id,
                    rd.source,
                    rd.title,
                    rd.date,
                    rd.summary,
                    rd.content_text,
                    rd.detail_url,
                    rd.image_urls,
                    rd.crawled_at,
                    refs.ref_count
                FROM raw_documents rd
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS ref_count
                    FROM raw_documents ref
                    WHERE ref.document_kind = 'reference_article'
                      AND ref.parent_doc_id = rd.doc_id
                ) refs ON TRUE
                {where}
                ORDER BY rd.title, rd.source, rd.date, refs.ref_count DESC, rd.crawled_at DESC
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
            summary = _preview_summary(r["summary"], r["content_text"])
            # image_urls는 JSONB. psycopg2가 list로 디코딩.
            imgs = r.get("image_urls") or []
            thumbnail = imgs[0] if isinstance(imgs, list) and imgs else None
            out.append({
                "id": r["doc_id"],
                "title": r["title"],
                "source": r["source"],
                "date": d.isoformat() if d else None,
                "summary": summary,
                "detail_url": r["detail_url"],
                "thumbnail_url": thumbnail,
                "image_urls": imgs if isinstance(imgs, list) else [],
                "is_new": is_new,
            })
        return out

    def get_release_by_id(self, doc_id: str) -> dict | None:
        """단건 조회 (상세보기·기사생성 시 content_text 필요)."""
        sql = """
            SELECT doc_id, source, title, date, summary, content_text, detail_url, image_urls
            FROM raw_documents
            WHERE doc_id = %s
              AND document_kind = 'press_release'
        """
        with psycopg2.connect(db_config.dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (doc_id,))
                row = cur.fetchone()
        if not row:
            return None
        imgs = row.get("image_urls") or []
        if not isinstance(imgs, list):
            imgs = []
        return {
            "id": row["doc_id"],
            "title": row["title"],
            "source": row["source"],
            "date": row["date"].isoformat() if row["date"] else None,
            "summary": _preview_summary(row["summary"], row["content_text"]),
            "content_text": row["content_text"] or "",
            "detail_url": row["detail_url"],
            "thumbnail_url": imgs[0] if imgs else None,
            "image_urls": imgs,
        }
