"""Poll crawler batch files and ingest them into PostgreSQL."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .db import apply_schema
from .ingest import ingest_jsonl


OUTBOX_DIR = Path(os.getenv("CRAWLER_OUTBOX_DIR", "/shared/outbox"))
PROCESSED_DIR = Path(os.getenv("CRAWLER_PROCESSED_DIR", "/shared/processed"))
POLL_SECONDS = int(os.getenv("INGEST_POLL_SECONDS", "15"))
USE_CONTEXT = os.getenv("INGEST_USE_CONTEXT", "0") == "1"
DEDUP = os.getenv("INGEST_DEDUP", "1") != "0"


def process_batch(path: Path) -> bool:
    print(f"[ingest-worker] starting {path.name}", flush=True)
    stats = ingest_jsonl(
        str(path),
        use_context=USE_CONTEXT,
        dedup=DEDUP,
    )
    print(f"[ingest-worker] {path.name}: {stats}", flush=True)
    return stats["errors"] == 0


def main() -> int:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    apply_schema()

    while True:
        batch_files = sorted(OUTBOX_DIR.glob("*.jsonl"))
        for batch_path in batch_files:
            try:
                if process_batch(batch_path):
                    shutil.move(str(batch_path), PROCESSED_DIR / batch_path.name)
            except Exception as exc:
                print(f"[ingest-worker] failed {batch_path.name}: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
