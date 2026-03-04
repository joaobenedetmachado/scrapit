"""
Playwright scraper backend — for JavaScript-rendered pages.

Directive options consumed here:
  site: url
  scrape:                      — same format as bs4_scraper
  headers: {}                  — extra HTTP headers
  cookies: []                  — list of cookie dicts: {name, value, domain}
  proxy: "http://..."          — proxy URL
  timeout: 30000               — page load timeout in ms (default 30000)
  wait_for: 'selector'         — wait for this selector before scraping
  screenshot: true             — save screenshot to output/<directive>_<ts>.png
"""

from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from scraper.config import OUTPUT_DIR


async def scrape(dados: dict, directive_name: str = "") -> dict:
    """Scrape a single URL using Playwright (headless Chromium)."""
    proxy_cfg = None
    if proxy := dados.get("proxy"):
        proxy_cfg = {"server": proxy}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=proxy_cfg)
        context_opts = {}
        if headers := dados.get("headers"):
            context_opts["extra_http_headers"] = headers

        context = await browser.new_context(**context_opts)

        if cookies := dados.get("cookies"):
            # Cookies must be a list of dicts with name/value/domain
            await context.add_cookies(cookies)

        page = await context.new_page()
        timeout_ms = dados.get("timeout", 30_000)
        await page.goto(dados["site"], timeout=timeout_ms)

        # Optional: wait for a specific selector before parsing
        if wait_for := dados.get("wait_for"):
            await page.wait_for_selector(wait_for, timeout=timeout_ms)

        result = {}
        for key, value in dados["scrape"].items():
            selectors_raw = value[0]
            options = value[1] if len(value) > 1 else {}
            attr = options.get("attr", "text")
            get_all = options.get("all", False)

            selectors = (
                selectors_raw if isinstance(selectors_raw, list) else [selectors_raw]
            )

            # Find first selector that matches
            locator = None
            for sel in selectors:
                try:
                    await page.wait_for_selector(sel, timeout=3_000)
                    locator = page.locator(sel)
                    if await locator.count() > 0:
                        break
                except Exception:
                    pass

            if locator is None or await locator.count() == 0:
                result[key] = [] if get_all else None
                continue

            if get_all:
                all_locators = locator.all() if hasattr(locator, "all") else [locator.first]
                items = []
                for loc in await _safe_all(locator):
                    items.append(await _get_attr(loc, attr))
                result[key] = items
            else:
                result[key] = await _get_attr(locator.first, attr)

        # Optional screenshot
        if dados.get("screenshot"):
            OUTPUT_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = directive_name or "screenshot"
            shot_path = OUTPUT_DIR / f"{name}_{ts}.png"
            await page.screenshot(path=str(shot_path), full_page=True)
            result["_screenshot"] = str(shot_path)

        await browser.close()

    result["url"] = dados["site"]
    result["timestamp"] = datetime.now()
    return result


async def _safe_all(locator):
    """Return list of element handles."""
    count = await locator.count()
    return [locator.nth(i) for i in range(count)]


async def _get_attr(locator, attr: str):
    if attr == "text":
        return await locator.inner_text()
    elif attr == "html":
        return await locator.inner_html()
    else:
        return await locator.get_attribute(attr)
