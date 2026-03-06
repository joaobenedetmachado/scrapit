"""
Spider mode — discover and scrape linked pages automatically.

Directive format:
  mode: spider           — activates spider mode (or presence of `follow:` key)
  follow:
    selector: 'a.article'  — CSS selector for links to follow
    attr: href             — attribute with the URL (default: href)
    max: 50                — maximum pages to scrape (default: 50)
    same_domain: true      — restrict to same domain as `site` (default: true)
    depth: 1               — link-following depth from index (default: 1)

The spider starts at `site`, discovers links matching `selector`,
then scrapes each discovered URL with the same `scrape` spec.
"""

from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from scraper.scrapers.bs4_scraper import fetch_html, parse_page
from scraper.logger import log


class Spider:
    def __init__(self, dados: dict):
        self.dados = dados
        self.follow = dados.get("follow", {})
        self.max = self.follow.get("max", 50)
        self.same_domain = self.follow.get("same_domain", True)
        self.depth = self.follow.get("depth", 1)
        self.selector = self.follow.get("selector", "a")
        self.attr = self.follow.get("attr", "href")
        self.base_domain = urlparse(dados["site"]).netloc

        cache_cfg = dados.get("cache", {})
        self._fetch_kw = dict(
            retries=dados.get("retries", 3),
            timeout=dados.get("timeout", 15),
            headers=dados.get("headers"),
            cookies=dados.get("cookies"),
            proxy=dados.get("proxy"),
            cache_ttl=cache_cfg.get("ttl", 0) if isinstance(cache_cfg, dict) else 0,
            delay=dados.get("delay", 0),
        )

    def run(self) -> list[dict]:
        """Discover and scrape all linked pages. Returns list of result dicts."""
        index_html = fetch_html(self.dados["site"], **self._fetch_kw)
        index_soup = BeautifulSoup(index_html, "html.parser")

        discovered = self._discover(index_soup, self.dados["site"])
        log(f"spider: found {len(discovered)} URLs from {self.dados['site']}")

        results = []
        for url in discovered[: self.max]:
            try:
                html = fetch_html(url, **self._fetch_kw)
                soup = BeautifulSoup(html, "html.parser")
                result = parse_page(soup, url, self.dados["scrape"], raw_html=html)
                result["_source"] = self.dados["site"]
                results.append(result)
                log(f"spider: scraped {url}")
            except Exception as e:
                log(f"spider: error scraping {url}: {e}", "warning")

        return results

    def _discover(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []

        for el in soup.select(self.selector):
            href = el.get(self.attr)
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            url = urljoin(base_url, href).split("#")[0]
            if self.same_domain and urlparse(url).netloc != self.base_domain:
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)

        return urls
