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
_RELATED_MAX_TERMS = 8
_RELATED_MIN_MATCH = 1  # 최소 이 개수의 키워드가 매칭되어야 결과에 포함
_RELATED_USE_VECTOR = os.getenv("RELATED_SEARCH_USE_VECTOR", "1") == "1"

_TERM_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_PHRASE_RE = re.compile(r"[가-힣]{2,}[\s·][가-힣]{2,}")  # 2어절 구문 추출

_STOP_TERMS = {
    "방송", "보도자료", "관련", "오늘", "지난", "이번", "대한", "통해",
    "위해", "에서", "있다", "한다", "된다", "것이", "하는", "대해",
    "따른", "위한", "등을", "발표", "결과", "현재", "진행", "강화",
    "제고", "방안", "추진", "검토", "실시", "확대", "개선", "운영",
}


def _connection():
    conn = psycopg2.connect(db_config.dsn)
    register_vector(conn)
    return conn


def _compact_related_query(text: str) -> str:
    """Keep related-article search responsive by avoiding full-article rerank queries."""
    return " ".join((text or "").split())[:_RELATED_QUERY_MAX_CHARS]


def _related_terms(*texts: str | None) -> list[str]:
    """핵심 키워드 추출. 구문 우선, 단일어 보충."""
    seen: set[str] = set()
    terms: list[str] = []

    # 1차: 2어절 구문 추출 (더 정확한 매칭)
    for text in texts:
        if not text:
            continue
        for phrase in _PHRASE_RE.findall(text):
            normalized = phrase.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            terms.append(phrase)
            if len(terms) >= _RELATED_MAX_TERMS:
                return terms

    # 2차: 단일 단어 보충 (3글자 이상, 불용어 제외)
    for text in texts:
        for term in _TERM_RE.findall(text or ""):
            if len(term) < 3:
                continue
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
        max_results: int = 30,
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

        # linked 참고기사가 없으면 키워드 검색으로 fallback
        if not results and query_text and query_text.strip():
            results = self._fast_keyword_related(
                query_text=query_text,
                source_release_id=source_release_id,
                source_release_title=source_release_title,
                max_results=max_results * 4,
            )

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
                   rd.doc_id AS raw_doc_id, rd.document_kind, rd.detail_url,
                   rd.image_urls
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
        match_count_parts = []
        score_params: list[str] = []
        match_params: list[str] = []
        for term in terms:
            like = f"%{term}%"
            score_parts.append(
                "(CASE WHEN d.title ILIKE %s THEN 6 ELSE 0 END + "
                "CASE WHEN d.original_text ILIKE %s THEN 2 ELSE 0 END)"
            )
            score_params.extend([like, like])
            match_count_parts.append(
                "(CASE WHEN d.title ILIKE %s OR d.original_text ILIKE %s THEN 1 ELSE 0 END)"
            )
            match_params.extend([like, like])

        min_match = min(_RELATED_MIN_MATCH, len(terms))

        sql = f"""
            SELECT * FROM (
                SELECT d.id, d.chunk_id, d.source, d.date, d.title, d.original_text, d.full_text,
                       d.raw_document_id, rd.doc_id AS raw_doc_id, rd.document_kind, rd.detail_url,
                       rd.image_urls,
                       ({' + '.join(score_parts)}) AS rerank_score,
                       ({' + '.join(match_count_parts)}) AS match_count
                FROM documents d
                JOIN raw_documents rd ON rd.id = d.raw_document_id
                WHERE rd.document_kind IN ('press_release', 'reference_article')
                  AND (%s IS NULL OR rd.doc_id <> %s)
            ) sub
            WHERE match_count >= %s
            ORDER BY rerank_score DESC, date DESC NULLS LAST
            LIMIT %s
        """
        params = score_params + match_params + [source_release_id, source_release_id] + [min_match, max_results]
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
            image_urls = r.get("image_urls") if isinstance(r.get("image_urls"), list) else []
            out.append({
                "id": r["chunk_id"],
                "title": r.get("title") or "",
                "source": r.get("source") or "",
                "date": date_str,
                "source_release_id": source_release_id or "",
                "source_release_title": source_release_title or "",
                "detail_url": r.get("detail_url") or "",
                "document_kind": r.get("document_kind") or "",
                "thumbnail_url": image_urls[0] if image_urls else None,
                "image_urls": image_urls,
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
                   rd.detail_url, rd.document_kind, rd.image_urls
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
                "image_urls": r["image_urls"] or [],
            }
            for r in rows
        ]
