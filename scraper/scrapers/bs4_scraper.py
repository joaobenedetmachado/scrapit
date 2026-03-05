"""
BeautifulSoup scraper backend.

Directive options consumed here:
  site: url                    — target URL
  scrape:                      — field → [selector(s), {attr, all}]
    field:
      - 'css-selector'         — single selector
      - ['sel1', 'sel2', ...]  — fallback selectors (first match wins)
      - attr: text             — 'text' for inner text, else HTML attribute
        all: true              — return list of all matches (not just first)
  headers: {}                  — extra HTTP headers merged with defaults
  cookies: {}                  — cookie dict
  proxy: "http://..."          — proxy URL
  retries: 3                   — retry count on HTTP error (default 3)
  timeout: 15                  — request timeout in seconds (default 15)
  cache:
    ttl: 3600                  — cache TTL in seconds (0 = disabled)
"""

import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from scraper import cache as _cache

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


# ── HTTP fetch ────────────────────────────────────────────────────────────────

def fetch_html(
    url: str,
    *,
    retries: int = 3,
    backoff: float = 2.0,
    timeout: int = 15,
    headers: dict | None = None,
    cookies: dict | None = None,
    proxy: str | None = None,
    cache_ttl: int = 0,
) -> str:
    """Fetch URL and return HTML string. Caches if cache_ttl > 0."""
    cached = _cache.get(url, cache_ttl)
    if cached is not None:
        return cached

    merged_headers = {**_HEADERS, **(headers or {})}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    last_exc = None

    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                headers=merged_headers,
                cookies=cookies,
                proxies=proxies,
                timeout=timeout,
            )
            resp.raise_for_status()
            html = resp.text
            if cache_ttl > 0:
                _cache.put(url, html)
            return html
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))

    raise last_exc


# ── Page parsing ──────────────────────────────────────────────────────────────

def parse_page(soup: BeautifulSoup, url: str, scrape_spec: dict) -> dict:
    """Extract fields from a BeautifulSoup object according to scrape_spec."""
    result = {}

    for key, value in scrape_spec.items():
        selectors_raw = value[0]
        options = value[1] if len(value) > 1 else {}
        attr = options.get("attr", "text")
        get_all = options.get("all", False)

        # Support fallback selectors: single string or list of strings
        selectors = (
            selectors_raw if isinstance(selectors_raw, list) else [selectors_raw]
        )

        element = None
        for sel in selectors:
            element = soup.select_one(sel)
            if element:
                break

        if element is None:
            result[key] = [] if get_all else None
            continue

        if get_all:
            # Grab all matching elements (use first selector that yields results)
            for sel in selectors:
                elements = soup.select(sel)
                if elements:
                    result[key] = _extract_many(elements, attr)
                    break
            else:
                result[key] = []
        else:
            result[key] = _extract_one(element, attr)

    result["url"] = url
    result["timestamp"] = datetime.now()
    return result


def _extract_one(element, attr: str):
    if attr == "text":
        return element.get_text(strip=True)
    elif attr == "html":
        return str(element)
    else:
        return element.get(attr)


def _extract_many(elements, attr: str) -> list:
    return [_extract_one(el, attr) for el in elements]


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape(dados: dict) -> dict:
    """Scrape a single URL using BeautifulSoup."""
    # Add delay between requests if specified
    delay = dados.get("delay", 0)
    if delay > 0:
        import time
        time.sleep(delay)
    
    cache_cfg = dados.get("cache", {})
    cache_ttl = cache_cfg.get("ttl", 0) if isinstance(cache_cfg, dict) else 0

    html = fetch_html(
        dados["site"],
        retries=dados.get("retries", 3),
        timeout=dados.get("timeout", 15),
        headers=dados.get("headers"),
        cookies=dados.get("cookies"),
        proxy=dados.get("proxy"),
        cache_ttl=cache_ttl,
    )
    soup = BeautifulSoup(html, "html.parser")
    return parse_page(soup, dados["site"], dados["scrape"])
