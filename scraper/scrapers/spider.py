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
    incremental: true      — skip URLs visited in previous runs (persistent state)

The spider starts at `site`, discovers links matching `selector`,
then scrapes each discovered URL with the same `scrape` spec.
"""

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from scraper.scrapers.bs4_scraper import fetch_html, parse_page
from scraper.logger import log

_CHECKPOINTS_DIR = Path("output") / ".checkpoints"
_STATE_DIR        = Path("output") / ".scrapit_state"


class Spider:
    def __init__(self, dados: dict, resume: bool = False):
        self.dados = dados
        self.follow = dados.get("follow", {})
        self.max = self.follow.get("max", 50)
        self.same_domain = self.follow.get("same_domain", True)
        self.depth = self.follow.get("depth", 1)
        self.selector = self.follow.get("selector", "a")
        self.attr = self.follow.get("attr", "href")
        self.base_domain = urlparse(dados["site"]).netloc
        self._resume = resume
        self._incremental = self.follow.get("incremental", False)

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

    def _checkpoint_path(self, directive_name: str) -> Path:
        _CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        return _CHECKPOINTS_DIR / f"{directive_name}.json"

    def _load_checkpoint(self, directive_name: str) -> set[str]:
        cp_file = self._checkpoint_path(directive_name)
        if cp_file.exists():
            try:
                data = json.loads(cp_file.read_text())
                return set(data.get("completed", []))
            except Exception:
                pass
        return set()

    def _state_path(self, directive_name: str) -> Path:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        return _STATE_DIR / f"{directive_name}.json"

    def _load_state(self, directive_name: str) -> set[str]:
        path = self._state_path(directive_name)
        if path.exists():
            try:
                return set(json.loads(path.read_text()).get("visited", []))
            except Exception:
                pass
        return set()

    def _save_state(self, directive_name: str, visited: set[str]):
        path = self._state_path(directive_name)
        path.write_text(json.dumps({"visited": sorted(visited)}, indent=2))

    def reset_state(self, directive_name: str):
        path = self._state_path(directive_name)
        if path.exists():
            path.unlink()

    def _save_checkpoint(self, directive_name: str, discovered: list[str], completed: set[str]):
        cp_file = self._checkpoint_path(directive_name)
        cp_file.write_text(json.dumps(
            {"directive": directive_name, "discovered": discovered, "completed": list(completed)},
            indent=2,
        ))

    def run(self, directive_name: str = "spider") -> list[dict]:
        """Discover and scrape all linked pages. Returns list of result dicts."""
        completed: set[str] = set()
        visited: set[str] = set()

        if self._resume:
            completed = self._load_checkpoint(directive_name)
            if completed:
                log(f"spider: resuming — skipping {len(completed)} already-scraped URLs")

        if self._incremental:
            visited = self._load_state(directive_name)
            if visited:
                log(f"spider: incremental — skipping {len(visited)} previously visited URLs")

        index_html = fetch_html(self.dados["site"], **self._fetch_kw)
        index_soup = BeautifulSoup(index_html, "html.parser")

        discovered = self._discover(index_soup, self.dados["site"])
        log(f"spider: found {len(discovered)} URLs from {self.dados['site']}")
        self._save_checkpoint(directive_name, discovered, completed)

        results = []
        for url in discovered[: self.max]:
            if url in completed:
                continue
            if self._incremental and url in visited:
                continue
            try:
                html = fetch_html(url, **self._fetch_kw)
                soup = BeautifulSoup(html, "html.parser")
                result = parse_page(soup, url, self.dados["scrape"], raw_html=html)
                result["_source"] = self.dados["site"]
                results.append(result)
                completed.add(url)
                visited.add(url)
                self._save_checkpoint(directive_name, discovered, completed)
                log(f"spider: scraped {url}")
            except Exception as e:
                log(f"spider: error scraping {url}: {e}", "warning")

        # Persist incremental state (survives across runs)
        if self._incremental:
            self._save_state(directive_name, visited)

        # Clear crash-recovery checkpoint on successful completion
        cp = self._checkpoint_path(directive_name)
        if cp.exists():
            cp.unlink()

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
