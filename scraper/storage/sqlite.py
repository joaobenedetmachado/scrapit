"""
SQLite storage — zero-config local database alternative to MongoDB.

All scrapes are stored in output/scrapit.db with full JSON payload.
Automatically creates the table on first use.
"""

import json
import sqlite3
from datetime import datetime
from scraper.config import OUTPUT_DIR

_DB_PATH = OUTPUT_DIR / "scrapit.db"


def _connect() -> sqlite3.Connection:
    OUTPUT_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrapes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            directive TEXT    NOT NULL,
            url       TEXT,
            timestamp TEXT,
            data      TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_directive ON scrapes(directive)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON scrapes(url)")
    conn.commit()
    return conn


def save(data: dict, directive_name: str) -> str:
    conn = _connect()
    serializable = {k: str(v) for k, v in data.items() if k != "_id"}
    conn.execute(
        "INSERT INTO scrapes (directive, url, timestamp, data) VALUES (?, ?, ?, ?)",
        (
            directive_name,
            data.get("url"),
            str(data.get("timestamp", datetime.now())),
            json.dumps(serializable, default=str),
        ),
    )
    conn.commit()
    conn.close()
    return str(_DB_PATH)


def find_by_directive(directive_name: str, limit: int = 100) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM scrapes WHERE directive = ? ORDER BY id DESC LIMIT ?",
        (directive_name, limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def find_by_url(url_fragment: str, limit: int = 100) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM scrapes WHERE url LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{url_fragment}%", limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def recent(limit: int = 20) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM scrapes ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["data"] = json.loads(d["data"])
    except (json.JSONDecodeError, KeyError):
        pass
    return d
