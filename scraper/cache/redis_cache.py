"""
Redis-backed HTTP cache — shares cache across processes and containers.

Directive usage:
  cache:
    backend: redis   # default: file
    ttl: 3600
    key_prefix: scrapit:   # optional
"""

import hashlib

_REDIS_URL_ENV = "REDIS_URL"
_DEFAULT_PREFIX = "scrapit:cache:"


def _connect():
    """Return a redis.Redis client, raising ImportError if redis is not installed."""
    try:
        import redis as _redis
    except ImportError:
        raise ImportError(
            "redis is required for Redis cache backend.\n"
            "Install with: pip install redis"
        )
    import os
    url = os.environ.get(_REDIS_URL_ENV, "redis://localhost:6379/0")
    return _redis.from_url(url, decode_responses=True)


def _key(url: str, prefix: str) -> str:
    h = hashlib.sha256(url.encode()).hexdigest()
    return f"{prefix}{h}"


def get(url: str, ttl: int, key_prefix: str = _DEFAULT_PREFIX) -> str | None:
    """Return cached HTML if fresh, else None."""
    if ttl <= 0:
        return None
    try:
        r = _connect()
        return r.get(_key(url, key_prefix))
    except Exception:
        return None


def put(url: str, html: str, ttl: int, key_prefix: str = _DEFAULT_PREFIX):
    """Store HTML in Redis with TTL."""
    try:
        r = _connect()
        r.setex(_key(url, key_prefix), ttl, html)
    except Exception:
        pass  # Silently degrade to no caching if Redis is unavailable


def invalidate(url: str, key_prefix: str = _DEFAULT_PREFIX):
    try:
        r = _connect()
        r.delete(_key(url, key_prefix))
    except Exception:
        pass


def clear_all(key_prefix: str = _DEFAULT_PREFIX):
    try:
        r = _connect()
        keys = r.keys(f"{key_prefix}*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def stats(key_prefix: str = _DEFAULT_PREFIX) -> dict:
    """Return number of keys and memory usage for the given prefix."""
    try:
        r = _connect()
        keys = r.keys(f"{key_prefix}*")
        entries = len(keys)
        
        # Get memory usage if possible (requires Redis 4.0+)
        # We can sum memory usage of keys or just use used_memory from info
        info = r.info("memory")
        size_bytes = info.get("used_memory", 0)
        
        return {"entries": entries, "size_kb": round(size_bytes / 1024, 1)}
    except Exception:
        return {"entries": 0, "size_kb": 0}
