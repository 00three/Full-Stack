"""
검색 모듈: Hybrid 검색 (dense + tsvector) + RRF + 시간 가중치 + Re-ranking
"""

import math
from datetime import date, datetime

import psycopg2
from sentence_transformers import CrossEncoder

from .config import db_config, search_config


# ──────────────────────────────────────────────
# DB 연결
# ──────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(db_config.dsn)


# ──────────────────────────────────────────────
# 1. Dense 검색 (pgvector 코사인 유사도)
# ──────────────────────────────────────────────

def dense_search(query_embedding: list[float], top_k: int = 50) -> list[dict]:
    """query 임베딩으로 pgvector에서 코사인 유사도 검색"""
    sql = """
        SELECT id, chunk_id, source, date, title, original_text, full_text,
               1 - (embedding_dense <=> %s::vector) AS score
        FROM documents
        ORDER BY embedding_dense <=> %s::vector
        LIMIT %s
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (query_embedding, query_embedding, top_k))
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 2. 키워드 검색 (PostgreSQL tsvector)
# ──────────────────────────────────────────────

def keyword_search(query_text: str, top_k: int = 50) -> list[dict]:
    """PostgreSQL tsvector 기반 키워드 검색"""
    sql = """
        SELECT id, chunk_id, source, date, title, original_text, full_text,
               ts_rank(to_tsvector('simple', full_text), plainto_tsquery('simple', %s)) AS score
        FROM documents
        WHERE to_tsvector('simple', full_text) @@ plainto_tsquery('simple', %s)
        ORDER BY score DESC
        LIMIT %s
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (query_text, query_text, top_k))
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 3. RRF 합산 (Reciprocal Rank Fusion)
# ──────────────────────────────────────────────

def rrf_fusion(
    dense_results: list[dict],
    keyword_results: list[dict],
) -> list[dict]:
    """두 검색 결과를 RRF로 합산하여 상위 N개 반환"""
    k = search_config.rrf_k
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for rank, doc in enumerate(dense_results):
        cid = doc["chunk_id"]
        scores[cid] = scores.get(cid, 0) + search_config.dense_weight / (k + rank + 1)
        doc_map[cid] = doc

    for rank, doc in enumerate(keyword_results):
        cid = doc["chunk_id"]
        scores[cid] = scores.get(cid, 0) + search_config.keyword_weight / (k + rank + 1)
        doc_map[cid] = doc

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    results = []
    for cid in sorted_ids[: search_config.initial_candidates]:
        doc = doc_map[cid]
        doc["rrf_score"] = scores[cid]
        results.append(doc)

    return results


# ──────────────────────────────────────────────
# 4. 시간 가중치 (Time Decay)
# ──────────────────────────────────────────────

def apply_time_decay(results: list[dict], reference_date: date | None = None) -> list[dict]:
    """RRF 점수에 시간 감쇠 가중치를 곱하여 최신 문서 우선"""
    if reference_date is None:
        reference_date = date.today()

    half_life = search_config.half_life_days
    decay_lambda = math.log(2) / half_life

    for doc in results:
        doc_date = doc["date"]
        if isinstance(doc_date, str):
            doc_date = datetime.strptime(doc_date, "%Y-%m-%d").date()

        days_old = (reference_date - doc_date).days
        time_weight = math.exp(-decay_lambda * max(days_old, 0))
        doc["time_weight"] = time_weight
        doc["final_score"] = doc["rrf_score"] * time_weight

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[: search_config.after_time_decay]


# ──────────────────────────────────────────────
# 5. Re-ranking (Cross-Encoder)
# ──────────────────────────────────────────────

_reranker = None


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("bongsoo/klue-cross-encoder-v1")
    return _reranker


def rerank(query_text: str, results: list[dict]) -> list[dict]:
    """cross-encoder로 정밀 Re-ranking → 최종 N개 반환"""
    model = get_reranker()

    pairs = [(query_text, doc["full_text"]) for doc in results]
    ce_scores = model.predict(pairs)

    for doc, score in zip(results, ce_scores):
        doc["rerank_score"] = float(score)

    results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return results[: search_config.final_results]


# ──────────────────────────────────────────────
# 6. 통합 검색 (전체 파이프라인)
# ──────────────────────────────────────────────

def hybrid_search(query_text: str, query_embedding: list[float]) -> list[dict]:
    """
    전체 검색 파이프라인:
    dense + keyword → RRF(30개) → 시간 가중치(15개) → Re-ranking(10개)
    """
    dense_results = dense_search(query_embedding)
    kw_results = keyword_search(query_text)

    fused = rrf_fusion(dense_results, kw_results)
    decayed = apply_time_decay(fused)
    final = rerank(query_text, decayed)

    return final
