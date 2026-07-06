"""
Scrapit integrations — use Scrapit as a tool in AI agent frameworks.

Quick API (no YAML needed):

    from scraper.integrations import scrape_url, scrape_page, scrape_many, scrape_with_selectors

    text  = scrape_url("https://example.com")
    page  = scrape_page("https://example.com")          # structured: title, description, links...
    pages = scrape_many(["https://a.com", "https://b.com"])  # parallel
    data  = scrape_with_selectors("https://example.com", {"title": "h1", "price": ".price"})

LangChain / CrewAI / LangGraph:

    from scraper.integrations.langchain import ScrapitToolkit
    tools = ScrapitToolkit().get_tools()

Anthropic SDK (native tool use):

    from scraper.integrations.anthropic import as_anthropic_tools, handle_tool_call
    tools  = as_anthropic_tools()
    result = handle_tool_call(tool_name, tool_input)

OpenAI function calling:

    from scraper.integrations.openai import as_openai_functions, handle_function_call
    tools  = as_openai_functions()
    result = handle_function_call(name, arguments)

MCP server (Claude Desktop, Cursor, Claude Code):

    python -m scraper.integrations.mcp
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_STRIP_TAGS = ["script", "style", "nav", "footer", "aside", "header"]


def _clean_soup(soup: BeautifulSoup, strip_tags: list[str] | None = None) -> str:
    """Remove unwanted elements from soup and return clean text."""
    for tag in strip_tags or _STRIP_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ── scrape_url ────────────────────────────────────────────────────────────────

def scrape_url(
    url: str,
    *,
    remove_elements: list[str] | None = None,
    timeout: int = 15,
) -> str:
    """
    Fetch a URL and return clean readable text — no YAML needed.

    Strips scripts, styles, nav, footer automatically.
    Returns a plain string ready to feed to an LLM.
    """
    strip_tags = remove_elements or _STRIP_TAGS
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    return _clean_soup(soup, strip_tags)


# ── scrape_page ───────────────────────────────────────────────────────────────

def scrape_page(url: str, *, timeout: int = 15) -> dict[str, Any]:
    """
    Fetch a URL and return structured page metadata.

    Returns a dict with: url, title, description, main_content, links, word_count.
    More useful than scrape_url when the agent needs structured context.
    """
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"}) or \
                soup.find("meta", attrs={"property": "og:description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("http"):
            links.append(href)

    main_content = _clean_soup(soup)

    return {
        "url": url,
        "title": title,
        "description": description,
        "main_content": main_content,
        "links": list(dict.fromkeys(links)),  # deduplicated, order preserved
        "word_count": len(main_content.split()),
    }


# ── scrape_with_selectors ─────────────────────────────────────────────────────

def scrape_with_selectors(
    url: str,
    selectors: dict[str, str],
    *,
    all_matches: dict[str, bool] | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """
    Scrape specific fields from a page using CSS selectors — no YAML needed.

    Agents can dynamically define what to extract without pre-configuring a directive.

    Args:
        url: The URL to scrape.
        selectors: Mapping of field_name -> CSS selector.
            e.g. {"title": "h1", "price": ".price-color", "rating": "p.star-rating"}
        all_matches: Optional mapping of field_name -> bool.
            If True for a field, returns all matches as a list instead of just the first.
        timeout: Request timeout in seconds.

    Returns:
        Dict with scraped values plus "url" and "ok" keys.

    Example:
        scrape_with_selectors(
            "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000",
            selectors={"title": "h1", "price": "p.price_color"},
        )
        # → {"title": "A Light in the Attic", "price": "£51.77", "url": "...", "ok": True}
    """
    all_matches = all_matches or {}
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    result: dict[str, Any] = {"url": url, "ok": True}

    for field, selector in selectors.items():
        if all_matches.get(field):
            elements = soup.select(selector)
            result[field] = [el.get_text(strip=True) for el in elements]
        else:
            el = soup.select_one(selector)
            result[field] = el.get_text(strip=True) if el else None

    return result


# ── scrape_many ───────────────────────────────────────────────────────────────

def scrape_many(
    urls: list[str],
    *,
    mode: str = "text",
    selectors: dict[str, str] | None = None,
    max_workers: int = 8,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """
    Scrape multiple URLs in parallel.

    Args:
        urls: List of URLs to scrape.
        mode: 'text' (returns scrape_url), 'page' (returns scrape_page),
              or 'selectors' (requires selectors arg).
        selectors: Required when mode='selectors'.
        max_workers: Max parallel threads.
        timeout: Per-request timeout.

    Returns:
        List of results in the same order as urls.
    """
    results = [None] * len(urls)

    def _fetch(idx: int, url: str):
        try:
            if mode == "page":
                return idx, scrape_page(url, timeout=timeout)
            elif mode == "selectors" and selectors:
                return idx, scrape_with_selectors(url, selectors, timeout=timeout)
            else:
                return idx, {"url": url, "text": scrape_url(url, timeout=timeout), "ok": True}
        except Exception as e:
            return idx, {"url": url, "ok": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch, i, url) for i, url in enumerate(urls)]
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return results


# ── scrape_directive ──────────────────────────────────────────────────────────

def scrape_directive(directive: str) -> dict | list[dict]:
    """
    Run a Scrapit directive and return structured data.

    Args:
        directive: Directive name (e.g. 'wikipedia') or path to YAML file.
    """
    from scraper.main import _resolve
    path = _resolve(directive)
    return asyncio.run(_grab(str(path)))


async def _grab(path: str):
    from scraper.scrapers import grab_elements_by_directive
    return await grab_elements_by_directive(path)


# ── convenience factories ─────────────────────────────────────────────────────

def as_langchain_tool(directive: str | None = None):
    """Return a LangChain-compatible ScrapitTool (or ScrapitDirectiveTool if directive given)."""
    if directive:
        from scraper.integrations.langchain import ScrapitDirectiveTool
        return ScrapitDirectiveTool(directive=directive)
    from scraper.integrations.langchain import ScrapitTool
    return ScrapitTool()


def as_llamaindex_reader():
    """Return a ScrapitReader instance for LlamaIndex pipelines."""
    from scraper.integrations.llamaindex import ScrapitReader
    return ScrapitReader()


def as_anthropic_tools() -> list[dict]:
    """Return all Scrapit tools in Anthropic API format."""
    from scraper.integrations.anthropic import as_anthropic_tools as _f
    return _f()


def as_openai_functions() -> list[dict]:
    """Return all Scrapit tools in OpenAI function calling format."""
    from scraper.integrations.openai import as_openai_functions as _f
    return _f()
