"""Generated article persistence implementations."""

from __future__ import annotations

import json

import psycopg2

from rag.config import db_config


class DBArticleRepository:
    """Persist generated article drafts in PostgreSQL."""

    def save(
        self,
        article: dict,
        press_release_ids: list[str],
        selected_chunk_ids: list[str],
        created_by: str | None = None,
        llm_provider: str | None = None,
        llm_model_id: str | None = None,
        article_style: str | None = None,
    ) -> str:
        raw_document_id = self._find_primary_raw_document_id(press_release_ids)
        sql = """
            INSERT INTO generated_articles (
                raw_document_id,
                title,
                lead,
                body,
                source_mapping,
                source_release_ids,
                selected_chunk_ids,
                citations,
                extracted_json,
                created_by,
                llm_provider,
                llm_model_id,
                article_style
            ) VALUES (
                %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                %s, %s, %s, %s
            )
            RETURNING id
        """
        with psycopg2.connect(db_config.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        raw_document_id,
                        article.get("title") or "",
                        article.get("lead"),
                        article.get("body") or "",
                        json.dumps(article.get("source_mapping") or {}),
                        json.dumps(press_release_ids),
                        json.dumps(selected_chunk_ids),
                        json.dumps(article.get("citations") or {}),
                        json.dumps(article.get("extracted_json") or {}),
                        created_by or None,
                        llm_provider,
                        llm_model_id,
                        article_style,
                    ),
                )
                return str(cur.fetchone()[0])

    @staticmethod
    def _find_primary_raw_document_id(press_release_ids: list[str]) -> str | None:
        if not press_release_ids:
            return None
        sql = """
            SELECT id
            FROM raw_documents
            WHERE doc_id = ANY(%s)
            ORDER BY array_position(%s::text[], doc_id)
            LIMIT 1
        """
        with psycopg2.connect(db_config.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (press_release_ids, press_release_ids))
                row = cur.fetchone()
                return str(row[0]) if row else None


class MockArticleRepository:
    """Mock repository used when USE_MOCK=1."""

    def save(
        self,
        article: dict,
        press_release_ids: list[str],
        selected_chunk_ids: list[str],
        created_by: str | None = None,
        llm_provider: str | None = None,
        llm_model_id: str | None = None,
        article_style: str | None = None,
    ) -> str:
        return "mock-article"
