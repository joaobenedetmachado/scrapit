"""
HTTP cache — store fetched HTML on disk with TTL.

Avoids re-fetching pages during development / repeated runs.
Cache lives in <project_root>/.cache/

Usage in directive:
  cache:
    ttl: 3600   # seconds (0 = disabled)
"""

import hashlib
import json
import time
from pathlib import Path

from scraper.config import PROJECT_ROOT

_CACHE_DIR = PROJECT_ROOT / ".cache"


def _key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def get(url: str, ttl: int) -> str | None:
    """Return cached HTML if fresh, else None."""
    if ttl <= 0:
        return None
    html_path = _CACHE_DIR / _key(url)
    meta_path = html_path.with_suffix(".meta")
    if not html_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        if time.time() - meta["cached_at"] > ttl:
            html_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            return None
        return html_path.read_text(encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        return None


def put(url: str, html: str):
    """Store HTML in cache."""
    _CACHE_DIR.mkdir(exist_ok=True)
    k = _key(url)
    (_CACHE_DIR / k).write_text(html, encoding="utf-8")
    (_CACHE_DIR / f"{k}.meta").write_text(
        json.dumps({"url": url, "cached_at": time.time()}), encoding="utf-8"
    )


def invalidate(url: str):
    k = _key(url)
    (_CACHE_DIR / k).unlink(missing_ok=True)
    (_CACHE_DIR / f"{k}.meta").unlink(missing_ok=True)


def clear_all():
    import shutil
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)


def stats() -> dict:
    if not _CACHE_DIR.exists():
        return {"entries": 0, "size_kb": 0}
    html_files = [f for f in _CACHE_DIR.iterdir() if not f.suffix]
    size = sum(f.stat().st_size for f in html_files)
    return {"entries": len(html_files), "size_kb": round(size / 1024, 1)}
