"""
Pagination support for BeautifulSoup backend.

Directive format:
  paginate:
    selector: 'a.next'     — CSS selector for the "next page" link
    attr: href             — attribute containing the next URL (default: href)
    max_pages: 10          — maximum pages to follow (default: 10)

The paginator fetches the first page via bs4_scraper, extracts the next-page
link, and repeats until there is no next link or max_pages is reached.
Each page is parsed with the same scrape_spec and returned as a list of dicts.
"""

from urllib.parse import urljoin
from bs4 import BeautifulSoup

from scraper.scrapers.bs4_scraper import fetch_html, parse_page


def paginate(dados: dict) -> list[dict]:
    """Scrape a paginated site. Returns list of per-page dicts."""
    pag = dados.get("paginate") or {}
    selector = pag.get("selector")
    attr = pag.get("attr", "href")
    max_pages = pag.get("max_pages", 10)

    cache_cfg = dados.get("cache", {})
    cache_ttl = cache_cfg.get("ttl", 0) if isinstance(cache_cfg, dict) else 0
    fetch_kw = dict(
        retries=dados.get("retries", 3),
        timeout=dados.get("timeout", 15),
        headers=dados.get("headers"),
        cookies=dados.get("cookies"),
        proxy=dados.get("proxy"),
        cache_ttl=cache_ttl,
        delay=dados.get("delay", 0),
    )

    current_url = dados["site"]
    results = []

    for page_num in range(max_pages):
        html = fetch_html(current_url, **fetch_kw)
        soup = BeautifulSoup(html, "html.parser")
        result = parse_page(soup, current_url, dados["scrape"], raw_html=html)
        result["_page"] = page_num + 1
        results.append(result)

        if not selector:
            break  # no pagination spec, single page

        next_el = soup.select_one(selector)
        if not next_el:
            break
        next_href = next_el.get(attr)
        if not next_href:
            break
        next_url = urljoin(current_url, next_href)
        if next_url == current_url:
            break
        current_url = next_url

    return results
