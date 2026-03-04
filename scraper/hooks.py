"""
Hook registry — register callbacks for scrape lifecycle events.

Events:
  before_scrape(dados: dict)            — called before fetching, receives the directive
  after_scrape(result: dict, dados)     — called after scraping + transforms
  on_error(exc: Exception, dados)       — called when scraping raises
  on_save(result: dict, dest: str)      — called after saving
  on_change(changes: dict, result)      — called when diff detects changes

Usage:
    from scraper import hooks

    @hooks.on("after_scrape")
    def my_hook(result, dados):
        print("scraped:", result.get("url"))
"""

from typing import Callable

_HOOKS: dict[str, list[Callable]] = {
    "before_scrape": [],
    "after_scrape": [],
    "on_error": [],
    "on_save": [],
    "on_change": [],
}


def on(event: str):
    """Decorator to register a hook for an event."""
    def decorator(fn: Callable) -> Callable:
        register(event, fn)
        return fn
    return decorator


def register(event: str, fn: Callable):
    if event not in _HOOKS:
        raise ValueError(f"Unknown event: {event!r}. Available: {list(_HOOKS)}")
    _HOOKS[event].append(fn)


def fire(event: str, *args, **kwargs):
    from scraper.logger import log
    for fn in _HOOKS.get(event, []):
        try:
            fn(*args, **kwargs)
        except Exception as e:
            log(f"hook error [{event}] in {fn.__name__}: {e}", "warning")


def clear(event: str | None = None):
    """Clear hooks, for testing."""
    if event:
        _HOOKS[event].clear()
    else:
        for v in _HOOKS.values():
            v.clear()
