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
    parallel: 5            — concurrent requests (default: 1, sequential)

The spider starts at `site`, discovers links matching `selector`,
then scrapes each discovered URL with the same `scrape` spec.
"""

import asyncio
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
        self._parallel = int(self.follow.get("parallel", 1))
        self._exclude_patterns = self.follow.get("exclude", [])

        cache_cfg = dados.get("cache", {})
        throttle_cfg = dados.get("throttle", {})
        if isinstance(throttle_cfg, (int, float)):
            self._delay = float(throttle_cfg)
            self._per_domain = False
        else:
            self._delay = float(throttle_cfg.get("delay", dados.get("delay", 0)))
            self._per_domain = throttle_cfg.get("per_domain", False)

        self._last_request = {}  # domain -> timestamp
        self._locks = {}        # domain -> asyncio.Lock

        self._fetch_kw = dict(
            retries=dados.get("retries", 3),
            timeout=dados.get("timeout", 15),
            headers=dados.get("headers"),
            cookies=dados.get("cookies"),
            proxy=dados.get("proxy"),
            cache_ttl=cache_cfg.get("ttl", 0) if isinstance(cache_cfg, dict) else 0,
            delay=0,  # Handled directly by Spider
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

    def run(self, directive_name: str = "spider", on_result=None) -> list[dict]:
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

        queue = [
            url for url in discovered[: self.max]
            if url not in completed and not (self._incremental and url in visited)
        ]

        if self._parallel > 1:
            results = asyncio.run(
                self._run_parallel(queue, directive_name, completed, visited)
            )
        else:
            results = self._run_sequential(queue, directive_name, completed, visited, on_result=on_result)

        # Persist incremental state (survives across runs)
        if self._incremental:
            self._save_state(directive_name, visited)

        # Clear crash-recovery checkpoint on successful completion
        cp = self._checkpoint_path(directive_name)
        if cp.exists():
            cp.unlink()

        return results

    def _run_sequential(
        self,
        queue: list[str],
        directive_name: str,
        completed: set[str],
        visited: set[str],
        on_result=None,
    ) -> list[dict]:
        results = []
        discovered = queue  # already filtered
        total = len(queue)
        import time
        for i, url in enumerate(queue, 1):
            try:
                if self._delay > 0:
                    domain = urlparse(url).netloc if self._per_domain else "global"
                    last = self._last_request.get(domain, 0)
                    elapsed = time.time() - last
                    needed = self._delay - elapsed
                    if needed > 0:
                        time.sleep(needed)

                html = fetch_html(url, **self._fetch_kw)
                if self._delay > 0:
                    self._last_request[domain] = time.time()
                soup = BeautifulSoup(html, "html.parser")
                result = parse_page(soup, url, self.dados["scrape"], raw_html=html)
                result["_source"] = self.dados["site"]
                results.append(result)
                completed.add(url)
                visited.add(url)
                self._save_checkpoint(directive_name, discovered, completed)
                log(f"spider: [{i}/{total}] scraped {url}")
                if on_result:
                    on_result(result, i, total)
            except Exception as e:
                log(f"spider: error scraping {url}: {e}", "warning")
        return results

    async def _run_parallel(
        self,
        queue: list[str],
        directive_name: str,
        completed: set[str],
        visited: set[str],
    ) -> list[dict]:
        try:
            import httpx
        except ImportError:
            log("spider: httpx not installed, falling back to sequential", "warning")
            return self._run_sequential(queue, directive_name, completed, visited)

        semaphore = asyncio.Semaphore(self._parallel)
        results_map: dict[int, dict] = {}

        async def fetch_one(idx: int, url: str):
            async with semaphore:
                try:
                    import time
                    if self._delay > 0:
                        domain = urlparse(url).netloc if self._per_domain else "global"
                        lock = self._locks.setdefault(domain, asyncio.Lock())
                        async with lock:
                            last = self._last_request.get(domain, 0)
                            elapsed = time.time() - last
                            if elapsed < 0:
                                elapsed = 0  # sanity
                            needed = self._delay - elapsed
                            if needed > 0:
                                await asyncio.sleep(needed)
                            self._last_request[domain] = time.time()

                    timeout = self._fetch_kw.get("timeout", 15)
                    headers = self._fetch_kw.get("headers") or {}
                    proxy = self._fetch_kw.get("proxy")
                    proxies = {"http://": proxy, "https://": proxy} if proxy else None
                    async with httpx.AsyncClient(
                        headers=headers,
                        proxies=proxies,
                        timeout=timeout,
                        follow_redirects=True,
                    ) as client:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        html = resp.text
                    soup = BeautifulSoup(html, "html.parser")
                    result = parse_page(soup, url, self.dados["scrape"], raw_html=html)
                    result["_source"] = self.dados["site"]
                    results_map[idx] = result
                    completed.add(url)
                    visited.add(url)
                    log(f"spider: scraped {url}")
                except Exception as e:
                    log(f"spider: error scraping {url}: {e}", "warning")

        tasks = [fetch_one(i, url) for i, url in enumerate(queue)]
        await asyncio.gather(*tasks)

        # Preserve order
        return [results_map[i] for i in sorted(results_map)]

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
                # Check exclusion patterns
                import re as _re
                should_exclude = False
                for pattern in self._exclude_patterns:
                    if _re.search(str(pattern), url):
                        should_exclude = True
                        break
                
                if should_exclude:
                    continue

                seen.add(url)
                urls.append(url)

        return urls
