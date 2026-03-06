# Scrapit — TODO

## 🔴 Bugs / Quick Wins

- [x] **`openpyxl` missing from dependencies** — added to `requirements.txt` ✓
- [x] **`run_directive` crashes if `openpyxl` not installed** — `excel.py` now uses lazy import with a clear error message ✓
- [x] **MCP `scrape_with_selectors` returns only first match** — added `all_matches` param to MCP tool ✓
- [x] **`scrape_page` MCP tool returns only 30 links** — now accepts `link_limit` param (default 100) ✓

---

## 🟠 MCP Server — Make It Actually Powerful

- [x] **Add `all` param to `scrape_with_selectors`** — `all_matches: dict[str, bool]` param added ✓
- [x] **Expose `scrape_many` as MCP tool** — `scrape_many_tool` added ✓
- [ ] **Add `scrape_paginated` tool** — accepts a URL + next-page selector + max_pages, returns all results
- [x] **Add `run_batch` tool** — runs all directives in a folder, returns combined results ✓
- [ ] **Better tool descriptions** — current descriptions are dev-facing, not LLM-facing. Rewrite to guide the model on when to use each tool and what to expect back

---

## 🟡 Core Features

- [ ] **XPath selector support** — CSS selectors don't work for XML/RSS feeds or complex HTML. Add `xpath:` prefix or a `use_xpath: true` option per field
- [x] **User-agent rotation** — pool of 7 real browser UAs rotating per request ✓
- [ ] **Robots.txt compliance** — add `respect_robots: true` option (default false). Parse and cache robots.txt before scraping
- [ ] **Async concurrent scraping** — `scrape_many` currently runs sequentially. Use `asyncio` + `httpx` or `aiohttp` for parallel fetches
- [ ] **Resume interrupted scrapes** — spider/paginated scrapes die mid-run with no recovery. Save progress to SQLite, add `--resume` flag
- [x] **Data deduplication** — `unique_on: [field1, field2]` param added to SQLite `save()` ✓

---

## 🟢 Developer Experience

- [x] **Publish to PyPI** — v0.2.0 published ✓
- [x] **`scrapit` CLI command** — works via `pyproject.toml` entry point ✓
- [x] **`scrapit doctor` command** — checks all optional/required deps ✓
- [ ] **Type hints throughout** — `scraper/scrapers/bs4_scraper.py`, `transforms/`, `validators/` have minimal or no type annotations
- [ ] **Better YAML validation errors** — when a directive has a bad selector or missing field, error message is cryptic. Should show line number + field name
- [ ] **VS Code YAML schema** — publish a JSON Schema for directive YAML so VS Code gives autocomplete and inline docs

---

## 🔵 AI / LLM Features

- [ ] **`scrapit ai-init`** — natural language → YAML directive. "Scrape product names and prices from amazon.com/bestsellers" → generates the YAML using Claude/OpenAI
- [ ] **Auto-selector detection** — given a URL and field names, use an LLM to suggest the best CSS selectors. Add as `scrapit suggest-selectors <url> --fields title,price,rating`
- [ ] **Smart pagination detection** — automatically detect "next page" patterns (common CSS selectors, URL patterns) instead of requiring manual config
- [ ] **MCP tool: `generate_directive`** — Claude can call this to auto-generate a YAML directive for any URL, which it then runs immediately

---

## 📦 Community / Growth

- [ ] **Directive registry** — a public repo or website where users submit `.yaml` directives for popular sites (Reddit, Product Hunt, LinkedIn Jobs, etc.)
- [ ] **More built-in directives** — currently only 4 (wikipedia, hn, books, github_trending). Add: Reddit, Product Hunt, Indeed, Glassdoor, Amazon, RSS feeds
- [ ] **`scrapit share`** — CLI command to submit a directive to the registry with one command
- [ ] **GitHub Action** — `scrapit/action` that runs a directive on a schedule and commits the output to the repo (perfect for data repos)
- [ ] **Badge** — "Scraped with Scrapit" badge for READMEs of data repos

---

## 🧪 Tests

- [x] **Test coverage for transforms** — tests for all transforms including capitalize, sentence_case, count, truncate, slugify, normalize_whitespace, date ✓
- [x] **Test coverage for validators** — comprehensive tests for all validation rules ✓
- [ ] **Integration test for MCP server** — spin up the MCP server and call each tool, assert output shape
- [ ] **Test the Playwright backend** — zero tests for the playwright scraper
- [x] **CI: add coverage report** — `pytest-cov` added, coverage shown in CI output ✓

---

## Priority order if you want max impact fast:

1. `scrapit ai-init` (viral feature, 1 day)
2. Directive registry (community, ongoing)
3. XPath selector support (power users)
4. User-agent rotation (reliability)
5. Resume interrupted scrapes (spider/paginate robustness)
