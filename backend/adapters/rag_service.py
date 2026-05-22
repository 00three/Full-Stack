"""실제 RAG 검색 구현체. rag.search.hybrid_search 래퍼."""

from __future__ import annotations

import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

from rag.config import db_config
from rag.embedder import encode_query
from rag.search import hybrid_search


_RELATED_QUERY_MAX_CHARS = 1200
_RELATED_MAX_TERMS = 6
# 기본값 벡터 하이브리드 검색 ON. 키워드 매칭만 쓰려면 RELATED_SEARCH_USE_VECTOR=0
_RELATED_USE_VECTOR = os.getenv("RELATED_SEARCH_USE_VECTOR", "1") == "1"
_TERM_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_STOP_TERMS = {
    "방송",
    "보도자료",
    "관련",
    "오늘",
    "지난",
    "이번",
    "대한",
    "통해",
    "위해",
    "에서",
}


def _connection():
    conn = psycopg2.connect(db_config.dsn)
    register_vector(conn)
    return conn


def _compact_related_query(text: str) -> str:
    """Keep related-article search responsive by avoiding full-article rerank queries."""
    return " ".join((text or "").split())[:_RELATED_QUERY_MAX_CHARS]


def _related_terms(*texts: str | None) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for text in texts:
        for term in _TERM_RE.findall(text or ""):
            normalized = term.lower()
            if normalized in seen or normalized in _STOP_TERMS:
                continue
            seen.add(normalized)
            terms.append(term)
            if len(terms) >= _RELATED_MAX_TERMS:
                return terms
    return terms


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
        선택된 보도자료(source_release_id)에 크롤러가 parent_doc_id로
        연결해 둔 참고기사(reference_article)를 반환한다.
        같은 (source, title, date) 기사당 chunk 1개만 남겨 frontend 포맷으로 반환.
        source_release_id가 없을 때만 글로벌 유사도 검색으로 폴백한다.
        """
        # 크롤러가 parent_doc_id로 연결해 둔 참고기사를 우선 사용한다.
        # 글로벌 유사도 검색은 보도자료 종류·소속을 구분하지 못해
        # 다른 보도자료를 "참고기사"로 끌어오므로, source_release_id가
        # 있으면 해당 보도자료에 매핑된 reference_article만 반환한다.
        if source_release_id:
            results = self._linked_references(source_release_id)
        elif not query_text or not query_text.strip():
            return []
        elif not _RELATED_USE_VECTOR:
            results = self._fast_keyword_related(
                query_text=query_text,
                source_release_id=source_release_id,
                source_release_title=source_release_title,
                max_results=max_results * 4,
            )
        else:
            results = self._vector_related(query_text)

        return self._format_related_results(
            results=results,
            source_release_id=source_release_id,
            source_release_title=source_release_title,
            source_release_source=source_release_source,
            source_release_date=source_release_date,
            max_results=max_results,
        )

    def _linked_references(self, source_release_id: str) -> list[dict]:
        """크롤러가 parent_doc_id로 연결해 둔 참고기사 chunk를 조회한다.

        글로벌 유사도 검색과 달리, 선택된 보도자료에 실제로 매핑된
        reference_article만 반환하므로 다른 보도자료가 섞이지 않는다.
        """
        sql = """
            SELECT d.id, d.chunk_id, d.source, d.date, d.title,
                   d.original_text, d.full_text, d.raw_document_id,
                   rd.doc_id AS raw_doc_id, rd.document_kind, rd.detail_url
            FROM documents d
            JOIN raw_documents rd ON rd.id = d.raw_document_id
            WHERE rd.document_kind = 'reference_article'
              AND rd.parent_doc_id = %s
            ORDER BY d.date DESC NULLS LAST, d.chunk_id
        """
        with _connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (source_release_id,))
                return list(cur.fetchall())

    def _vector_related(self, query_text: str) -> list[dict]:
        compact_query = _compact_related_query(query_text)
        emb = encode_query(compact_query)
        return hybrid_search(compact_query, emb, use_rerank=False)

    def _fast_keyword_related(
        self,
        *,
        query_text: str,
        source_release_id: str | None,
        source_release_title: str | None,
        max_results: int,
    ) -> list[dict]:
        terms = _related_terms(source_release_title, _compact_related_query(query_text))
        if not terms:
            return []

        score_parts = []
        where_parts = []
        score_params: list[str] = []
        where_params: list[str] = []
        for term in terms:
            like = f"%{term}%"
            score_parts.append(
                "(CASE WHEN d.title ILIKE %s THEN 4 ELSE 0 END + "
                "CASE WHEN d.original_text ILIKE %s THEN 1 ELSE 0 END)"
            )
            score_params.extend([like, like])
            where_parts.append("(d.title ILIKE %s OR d.original_text ILIKE %s)")
            where_params.extend([like, like])

        sql = f"""
            SELECT d.id, d.chunk_id, d.source, d.date, d.title, d.original_text, d.full_text,
                   d.raw_document_id, rd.doc_id AS raw_doc_id, rd.document_kind, rd.detail_url,
                   ({' + '.join(score_parts)}) AS rerank_score
            FROM documents d
            JOIN raw_documents rd ON rd.id = d.raw_document_id
            WHERE rd.document_kind IN ('press_release', 'reference_article')
              AND (%s IS NULL OR rd.doc_id <> %s)
              AND ({' OR '.join(where_parts)})
            ORDER BY rerank_score DESC, d.date DESC NULLS LAST
            LIMIT %s
        """
        params = score_params + [source_release_id, source_release_id] + where_params + [max_results]
        with _connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    @staticmethod
    def _format_related_results(
        *,
        results: list[dict],
        source_release_id: str | None,
        source_release_title: str | None,
        source_release_source: str | None,
        source_release_date: str | None,
        max_results: int,
    ) -> list[dict]:

        # 메인 보도자료 식별용 키 (source_release_*가 들어왔을 때만 필터링)
        main_title = (source_release_title or "").strip()
        main_source = (source_release_source or "").strip()
        main_date = (source_release_date or "").strip()
        has_main_filter = bool(main_title)  # title만 있어도 필터 동작

        # 같은 원본 article(=source+title+date)당 가장 점수 높은 chunk 1개만
        seen: set[tuple] = set()
        out: list[dict] = []
        for r in results:
            if source_release_id and r.get("raw_doc_id") == source_release_id:
                continue
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
            out.append({
                "id": r["chunk_id"],
                "title": r.get("title") or "",
                "source": r.get("source") or "",
                "date": date_str,
                "source_release_id": source_release_id or "",
                "source_release_title": source_release_title or "",
                "detail_url": r.get("detail_url") or "",
                "document_kind": r.get("document_kind") or "",
            })
            if len(out) >= max_results:
                break

        return out

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
            SELECT d.chunk_id, d.source, d.date, d.title, d.original_text, d.full_text,
                   rd.detail_url, rd.document_kind
            FROM documents d
            JOIN raw_documents rd ON rd.id = d.raw_document_id
            WHERE d.chunk_id = ANY(%s)
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
                "detail_url": r["detail_url"],
                "document_kind": r["document_kind"],
            }
            for r in rows
        ]
