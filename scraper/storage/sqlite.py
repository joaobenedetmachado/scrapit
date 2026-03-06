"""
SQLite storage — zero-config local database alternative to MongoDB.

All scrapes are stored in output/scrapit.db with full JSON payload.
Automatically creates the table on first use.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from scraper.config import OUTPUT_DIR

_DB_PATH = OUTPUT_DIR / "scrapit.db"


def _get_db_path(output_dir: str | None = None) -> Path:
    base = Path(output_dir) if output_dir else OUTPUT_DIR
    return base / "scrapit.db"


def _connect(output_dir: str | None = None) -> sqlite3.Connection:
    db_path = _get_db_path(output_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
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


def save(
    data: dict,
    directive_name: str,
    *,
    output_dir: str | None = None,
    unique_on: list[str] | None = None,
) -> str:
    """Save a scrape result to SQLite.

    Args:
        data: Scraped data dict.
        directive_name: Name of the directive (used as table key).
        output_dir: Override output directory.
        unique_on: List of field names to use as a uniqueness key.
            If a row with the same values already exists, the save is skipped.
            Example: unique_on=["url"] skips duplicate URLs.
    """
    db_path = _get_db_path(output_dir)
    conn = _connect(output_dir)
    serializable = {k: str(v) for k, v in data.items() if k != "_id"}

    if unique_on:
        # Build a composite key from the specified fields
        key_parts = [str(data.get(f, "")) for f in unique_on]
        composite_key = "|".join(key_parts)
        # Check for existing row with the same key
        existing = conn.execute(
            "SELECT id FROM scrapes WHERE directive = ? AND data LIKE ?",
            (directive_name, f"%{composite_key}%"),
        ).fetchone()
        if existing:
            conn.close()
            return str(db_path)

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
    return str(db_path)


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
