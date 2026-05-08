"""
ingest 진입점 (가이드 8·9단계 + 전체 파이프라인 연결)

JSONL 1줄 → raw_documents UPSERT → 청킹 → 임베딩 → documents INSERT.
4단계 Contextual Retriever는 step 5에서 추가 (현재는 빈 prefix).
8단계 중복 체크 + 메타 병합은 step 6에서 추가 (현재는 chunk_id 단위 UPSERT).

CLI 사용:
    python -m rag.ingest --jsonl rag/data/results_2026-04-21.jsonl
    python -m rag.ingest --limit 5      # 5건만 처리 (디버그)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Iterable

import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector

from .config import db_config
from .preprocess import split_inputs, clean_text, normalize_source
from .chunker import split
from .embedder import BGEEmbedder, make_meta_prefix, make_full_text
from . import contextualizer


# ──────────────────────────────────────────────
# Chunk 데이터클래스
# ──────────────────────────────────────────────

@dataclass
class Chunk:
    raw_document_id: str
    chunk_id: str
    source: str
    date: str | None
    title: str | None
    data_type: str
    context_prefix: str
    original_text: str
    full_text: str
    embedding: list[float] = field(default_factory=list)


# ──────────────────────────────────────────────
# DB 연결 + pgvector 어댑터 등록
# ──────────────────────────────────────────────

def get_connection():
    conn = psycopg2.connect(db_config.dsn)
    register_vector(conn)
    return conn


# ──────────────────────────────────────────────
# raw_documents UPSERT
# ──────────────────────────────────────────────

UPSERT_RAW_SQL = """
INSERT INTO raw_documents (
    doc_id, source, department, author, title, date, summary,
    content_text, attachment_text, detail_url,
    image_urls, attachments, hashtags, "references", crawled_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s
)
ON CONFLICT (doc_id) DO UPDATE SET
    source          = EXCLUDED.source,
    department      = EXCLUDED.department,
    author          = EXCLUDED.author,
    title           = EXCLUDED.title,
    date            = EXCLUDED.date,
    summary         = EXCLUDED.summary,
    content_text    = EXCLUDED.content_text,
    attachment_text = EXCLUDED.attachment_text,
    detail_url      = EXCLUDED.detail_url,
    image_urls      = EXCLUDED.image_urls,
    attachments     = EXCLUDED.attachments,
    hashtags        = EXCLUDED.hashtags,
    "references"    = EXCLUDED."references",
    crawled_at      = EXCLUDED.crawled_at
RETURNING id;
"""


def upsert_raw(conn, raw: dict) -> str:
    src = normalize_source(raw["source"])
    with conn.cursor() as cur:
        cur.execute(UPSERT_RAW_SQL, (
            raw["doc_id"],
            src,
            raw.get("department"),
            raw.get("author"),
            raw.get("title") or "",
            raw.get("date"),
            raw.get("summary"),
            raw.get("content_text") or "",
            raw.get("attachment_text"),
            raw.get("detail_url"),
            json.dumps(raw.get("image_urls") or []),
            json.dumps(raw.get("attachments") or []),
            json.dumps(raw.get("hashtags") or []),
            json.dumps(raw.get("references") or []),
            raw.get("crawled_at"),
        ))
        return cur.fetchone()[0]


# ──────────────────────────────────────────────
# 청킹 + 메타 prefix + full_text
# ──────────────────────────────────────────────

def build_chunks(
    raw: dict,
    raw_id: str,
    use_context: bool = True,
) -> list[Chunk]:
    """
    1·2·3·5·6단계: 청킹 + 메타prefix + (선택) 4단계 contextualizer + full_text 조립.

    use_context=False: 4단계 LLM 호출 skip (디버그/--no-context용).
    """
    src = normalize_source(raw["source"])
    date_str = raw.get("date") or ""
    date_compact = date_str.replace("-", "") or "00000000"
    title = raw.get("title") or ""
    meta_prefix = make_meta_prefix(src, date_str, title)

    # 같은 source+date의 다른 문서끼리 chunk_id 충돌 방지용 doc 해시
    doc_hash = hashlib.md5(raw["doc_id"].encode()).hexdigest()[:8]

    chunks: list[Chunk] = []
    counter = 1

    for data_type, text in split_inputs(raw).items():
        cleaned = clean_text(text)
        chunk_texts = split(cleaned)
        for original in chunk_texts:
            chunk_id = f"{src}_{date_compact}_{doc_hash}_{counter:03d}"
            counter += 1
            ctx_prefix = (
                contextualizer.make_context_prefix(document=cleaned, chunk=original)
                if use_context
                else ""
            )
            full_text = make_full_text(ctx_prefix, meta_prefix, original)
            chunks.append(Chunk(
                raw_document_id=raw_id,
                chunk_id=chunk_id,
                source=src,
                date=raw.get("date"),
                title=title,
                data_type=data_type,
                context_prefix=ctx_prefix,
                original_text=original,
                full_text=full_text,
            ))
    return chunks


# ──────────────────────────────────────────────
# 배치 임베딩
# ──────────────────────────────────────────────

def embed_chunks(chunks: list[Chunk], batch_size: int = 32) -> None:
    if not chunks:
        return
    texts = [c.full_text for c in chunks]
    embeddings = BGEEmbedder().encode(texts, batch_size=batch_size)
    for c, emb in zip(chunks, embeddings):
        c.embedding = emb.tolist()


# ──────────────────────────────────────────────
# documents INSERT (chunk_id 충돌 시 UPSERT)
# ──────────────────────────────────────────────

INSERT_DOC_SQL = """
INSERT INTO documents (
    raw_document_id, chunk_id, source, date, title, data_type,
    context_prefix, original_text, full_text, embedding_dense, source_doc_ids
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
ON CONFLICT (chunk_id) DO UPDATE SET
    raw_document_id = EXCLUDED.raw_document_id,
    source          = EXCLUDED.source,
    date            = EXCLUDED.date,
    title           = EXCLUDED.title,
    data_type       = EXCLUDED.data_type,
    context_prefix  = EXCLUDED.context_prefix,
    original_text   = EXCLUDED.original_text,
    full_text       = EXCLUDED.full_text,
    embedding_dense = EXCLUDED.embedding_dense,
    source_doc_ids  = EXCLUDED.source_doc_ids
"""


# 8단계: 코사인 ≥ DUP_THRESHOLD면 중복으로 판단
DUP_THRESHOLD = 0.95


FIND_DUP_SQL = """
SELECT id, source_doc_ids
FROM documents
WHERE 1 - (embedding_dense <=> %s::vector) >= %s
ORDER BY embedding_dense <=> %s::vector
LIMIT 1
"""


def _doc_meta(c: Chunk) -> dict:
    """source_doc_ids에 append할 doc 메타데이터."""
    return {
        "doc_id": str(c.raw_document_id),
        "source": c.source,
        "title": c.title,
        "date": str(c.date) if c.date else None,
    }


def find_duplicate(conn, chunk: Chunk) -> str | None:
    """기존 chunk와 코사인 ≥ DUP_THRESHOLD 매치 시 그 chunk id 반환."""
    with conn.cursor() as cur:
        cur.execute(FIND_DUP_SQL, (chunk.embedding, DUP_THRESHOLD, chunk.embedding))
        row = cur.fetchone()
        return row[0] if row else None


def merge_into_existing(conn, existing_id: str, new_chunk: Chunk) -> None:
    """기존 chunk의 source_doc_ids에 새 doc 메타를 append (중복 doc_id는 skip)."""
    new_meta = _doc_meta(new_chunk)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
            SET source_doc_ids = source_doc_ids ||
                CASE
                    WHEN NOT source_doc_ids @> jsonb_build_array(%s::jsonb)
                    THEN jsonb_build_array(%s::jsonb)
                    ELSE '[]'::jsonb
                END
            WHERE id = %s
            """,
            (json.dumps(new_meta), json.dumps(new_meta), existing_id),
        )


def insert_documents(
    conn,
    chunks: list[Chunk],
    dedup: bool = True,
) -> tuple[int, int]:
    """
    chunks를 documents에 적재. dedup=True면 코사인 ≥ 0.95 매치 시 병합.
    반환: (inserted, merged) 카운트.
    """
    if not chunks:
        return 0, 0

    inserted = 0
    merged = 0

    for c in chunks:
        existing_id = find_duplicate(conn, c) if dedup else None
        if existing_id:
            merge_into_existing(conn, existing_id, c)
            merged += 1
        else:
            # 첫 등장: source_doc_ids에 본인 메타 1건 넣고 시작
            initial_sources = [_doc_meta(c)]
            with conn.cursor() as cur:
                cur.execute(
                    INSERT_DOC_SQL,
                    (
                        c.raw_document_id, c.chunk_id, c.source, c.date, c.title,
                        c.data_type, c.context_prefix, c.original_text, c.full_text,
                        c.embedding, json.dumps(initial_sources),
                    ),
                )
            inserted += 1

    return inserted, merged


def delete_existing_chunks(conn, raw_id: str) -> int:
    """re-ingest 시 같은 raw_document에 속한 기존 chunk 삭제."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE raw_document_id = %s", (raw_id,))
        return cur.rowcount


# ──────────────────────────────────────────────
# 1건 처리
# ──────────────────────────────────────────────

def ingest_one(
    conn,
    raw: dict,
    use_context: bool = True,
    dedup: bool = True,
) -> dict:
    raw_id = upsert_raw(conn, raw)
    deleted = delete_existing_chunks(conn, raw_id)
    chunks = build_chunks(raw, raw_id, use_context=use_context)
    embed_chunks(chunks)
    inserted, merged = insert_documents(conn, chunks, dedup=dedup)
    return {
        "doc_id": raw["doc_id"],
        "raw_id": str(raw_id),
        "chunks": len(chunks),
        "inserted": inserted,
        "merged": merged,
        "deleted": deleted,
    }


# ──────────────────────────────────────────────
# JSONL 전체 처리
# ──────────────────────────────────────────────

def ingest_jsonl(
    path: str,
    limit: int | None = None,
    use_context: bool = True,
    dedup: bool = True,
) -> dict:
    stats = {
        "docs": 0,
        "chunks": 0,
        "inserted": 0,
        "merged": 0,
        "deleted": 0,
        "errors": 0,
    }
    started = time.time()
    conn = get_connection()
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit is not None and i >= limit:
                    break
                try:
                    raw = json.loads(line)
                    r = ingest_one(conn, raw, use_context=use_context, dedup=dedup)
                    conn.commit()
                    stats["docs"] += 1
                    stats["chunks"] += r["chunks"]
                    stats["inserted"] += r["inserted"]
                    stats["merged"] += r["merged"]
                    stats["deleted"] += r["deleted"]
                    if (i + 1) % 10 == 0:
                        elapsed = time.time() - started
                        print(f"  [{i+1}] {r['doc_id']}: "
                              f"+{r['inserted']} merged={r['merged']} "
                              f"(누적 ins={stats['inserted']}, mrg={stats['merged']}, "
                              f"{elapsed:.1f}s)")
                except Exception as e:
                    conn.rollback()
                    stats["errors"] += 1
                    print(f"  [ERROR] line {i+1}: {type(e).__name__}: {e}")
    finally:
        conn.close()
    stats["elapsed_sec"] = round(time.time() - started, 1)
    stats["context"] = contextualizer.get_stats()
    stats["context_cost_usd"] = contextualizer.estimate_cost_usd()
    return stats


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="RAG ingest pipeline")
    parser.add_argument(
        "--jsonl",
        default="rag/data/results_2026-04-21.jsonl",
        help="크롤러 JSONL 입력 경로",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="최대 처리 건수 (디버그용)",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="4단계 Contextual Retriever skip (LLM 호출 안 함, 빠른 디버그용)",
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="8단계 중복 체크 skip (모든 chunk를 그대로 INSERT)",
    )
    args = parser.parse_args()

    print(f"ingest 시작: {args.jsonl}")
    if args.limit:
        print(f"  (limit={args.limit})")
    if args.no_context:
        print(f"  (4단계 contextualizer skip)")
    if args.no_dedup:
        print(f"  (8단계 중복 체크 skip)")

    stats = ingest_jsonl(
        args.jsonl,
        limit=args.limit,
        use_context=not args.no_context,
        dedup=not args.no_dedup,
    )

    print(f"\n=== ingest 완료 ===")
    print(f"  처리 docs       : {stats['docs']}")
    print(f"  생성 chunks     : {stats['chunks']}")
    print(f"  신규 INSERT     : {stats['inserted']}")
    print(f"  중복 병합       : {stats['merged']}")
    print(f"  재처리 시 삭제  : {stats['deleted']}")
    print(f"  에러            : {stats['errors']}")
    print(f"  소요 시간       : {stats['elapsed_sec']}s")
    if stats["context"]["calls"] or stats["context"]["skipped_no_key"]:
        c = stats["context"]
        print(f"  contextualizer  : calls={c['calls']}, "
              f"skip(no_key)={c['skipped_no_key']}, errors={c['errors']}, "
              f"tokens={c['input_tokens']}+{c['output_tokens']}, "
              f"~${stats['context_cost_usd']}")
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
