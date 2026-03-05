"""
PostgreSQL storage backend for Scrapit.

Stores all scrapes in a PostgreSQL database, following the same
pattern as sqlite.py and mongo.py.

Requires: psycopg2-binary
  pip install psycopg2-binary
"""

import json
from datetime import datetime
from scraper.logger import log


def _get_conn():
    try:
        import psycopg2
    except ImportError:
        raise ImportError(
            "psycopg2 is required for PostgreSQL storage.\n"
            "Install it with: pip install psycopg2-binary"
        )
    import os
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "scrapit"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    return conn


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scrapes (
                id            SERIAL PRIMARY KEY,
                directive     TEXT NOT NULL,
                url           TEXT,
                timestamp     TEXT,
                data          JSONB NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_directive ON scrapes(directive)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_url ON scrapes(url)"
        )
    conn.commit()


def save(data: dict, directive_name: str, **__) -> str:
    if not isinstance(data, dict):
        raise TypeError(f"save expected dict, got {type(data)}")
    try:
        conn = _get_conn()
        _ensure_table(conn)
        serializable = {k: str(v) for k, v in data.items() if k != "_id"}
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scrapes (directive, url, timestamp, data)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    directive_name,
                    data.get("url"),
                    str(data.get("timestamp", datetime.now())),
                    json.dumps(serializable, default=str),
                ),
            )
        conn.commit()
        conn.close()
        return "saved to PostgreSQL"
    except Exception as e:
        log(f"error saving to PostgreSQL: {e}", "error")
        return "error in PostgreSQL storage"