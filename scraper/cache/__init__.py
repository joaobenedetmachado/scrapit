"""
HTTP cache — store fetched HTML on disk (default) or Redis.

Avoids re-fetching pages during development / repeated runs.
File cache lives in <project_root>/.cache/

Usage in directive:
  cache:
    ttl: 3600          # seconds (0 = disabled)
    backend: file      # 'file' (default) or 'redis'
    key_prefix: scrapit:  # Redis only, optional

Redis backend requires:
  pip install redis
  REDIS_URL=redis://localhost:6379/0  (env var)
"""

import hashlib
import json
import time
from pathlib import Path

from scraper.config import PROJECT_ROOT

_CACHE_DIR = PROJECT_ROOT / ".cache"


def _key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


# ── Public API (backend-aware) ────────────────────────────────────────────────

def get(url: str, ttl: int, cache_cfg: dict | None = None) -> str | None:
    """Return cached HTML if fresh, else None."""
    if ttl <= 0:
        return None
    backend = (cache_cfg or {}).get("backend", "file")
    if backend == "redis":
        from scraper.cache.redis_cache import get as redis_get
        prefix = (cache_cfg or {}).get("key_prefix", "scrapit:cache:")
        return redis_get(url, ttl, key_prefix=prefix)
    return _file_get(url, ttl)


def put(url: str, html: str, ttl: int = 0, cache_cfg: dict | None = None):
    """Store HTML in cache."""
    backend = (cache_cfg or {}).get("backend", "file")
    if backend == "redis":
        from scraper.cache.redis_cache import put as redis_put
        prefix = (cache_cfg or {}).get("key_prefix", "scrapit:cache:")
        redis_put(url, html, ttl, key_prefix=prefix)
        return
    _file_put(url, html)


def invalidate(url: str, cache_cfg: dict | None = None):
    backend = (cache_cfg or {}).get("backend", "file")
    if backend == "redis":
        from scraper.cache.redis_cache import invalidate as redis_invalidate
        prefix = (cache_cfg or {}).get("key_prefix", "scrapit:cache:")
        redis_invalidate(url, key_prefix=prefix)
        return
    _file_invalidate(url)


def clear_all(cache_cfg: dict | None = None):
    backend = (cache_cfg or {}).get("backend", "file")
    if backend == "redis":
        from scraper.cache.redis_cache import clear_all as redis_clear
        prefix = (cache_cfg or {}).get("key_prefix", "scrapit:cache:")
        redis_clear(key_prefix=prefix)
        return
    _file_clear_all()


# ── File backend ──────────────────────────────────────────────────────────────

def _file_get(url: str, ttl: int) -> str | None:
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


def _file_put(url: str, html: str):
    _CACHE_DIR.mkdir(exist_ok=True)
    k = _key(url)
    (_CACHE_DIR / k).write_text(html, encoding="utf-8")
    (_CACHE_DIR / f"{k}.meta").write_text(
        json.dumps({"url": url, "cached_at": time.time()}), encoding="utf-8"
    )


def _file_invalidate(url: str):
    k = _key(url)
    (_CACHE_DIR / k).unlink(missing_ok=True)
    (_CACHE_DIR / f"{k}.meta").unlink(missing_ok=True)


def _file_clear_all():
    import shutil
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)


def stats() -> dict:
    if not _CACHE_DIR.exists():
        return {"entries": 0, "size_kb": 0}
    html_files = [f for f in _CACHE_DIR.iterdir() if not f.suffix]
    size = sum(f.stat().st_size for f in html_files)
    return {"entries": len(html_files), "size_kb": round(size / 1024, 1)}
