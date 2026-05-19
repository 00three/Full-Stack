"""DB schema bootstrap utilities."""

from __future__ import annotations

from pathlib import Path

import psycopg2

from .config import db_config


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def apply_schema() -> None:
    """Create or migrate the local schema to the current version."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg2.connect(db_config.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
