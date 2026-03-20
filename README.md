# Scrapit

[![CI](https://github.com/joaobenedetmachado/scrapit/actions/workflows/ci.yml/badge.svg)](https://github.com/joaobenedetmachado/scrapit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Scraped with Scrapit](https://img.shields.io/badge/scraped_with-scrapit-58a6ff)](https://github.com/joaobenedetmachado/scrapit)

A modular, YAML-driven web scraper framework. Describe any scraping target in a config file — Scrapit handles fetching, parsing, transforming, validating, and storing the data.

No code required for new targets. Just write a YAML.

---

## Features

| Feature | Description |
|---------|-------------|
| **YAML directives** | Declarative scrape configs — selectors, transforms, validation, cache |
| **Five backends** | BeautifulSoup, Playwright (JS), httpx (async), GraphQL, Bright Data |
| **Fallback selectors** | Per-field list of CSS selectors tried in order |
| **XPath support** | Use `xpath:` prefix in any selector (requires `lxml`) |
| **`all: true`** | Extract all matches for a selector, not just the first |
| **Pagination** | Follow "next page" links automatically |
| **Spider mode** | Discover and scrape all linked pages from an index |
| **Parallel spider** | Set `follow.parallel: 10` for concurrent async fetching with httpx |
| **Incremental spider** | `follow.incremental: true` — skip previously visited URLs across runs |
| **Multi-site** | Scrape multiple URLs with the same spec in one directive |
| **Transform pipeline** | 28+ declarative field transforms: strip, regex, date, hash, boolean… |
| **Validation** | Per-field rules: required, type, min/max, pattern, enum |
| **Eight output backends** | JSON, CSV, SQLite, MongoDB, PostgreSQL, Excel, Google Sheets, Parquet |
| **HTTP cache** | File-based or Redis-backed cache with TTL |
| **Proxy rotation** | Round-robin/random pool with per-proxy failure tracking |
| **Stealth mode** | Playwright fingerprint randomisation — UA, viewport, locale, timezone |
| **Change detection** | Diff result against previous run, fire webhook on change |
| **Webhook notifications** | POST JSON payload to Slack/Discord when changes detected |
| **Built-in scheduler** | `schedule: "*/30 * * * *"` + `scrapit run` daemon |
| **Streaming output** | `--stream` emits NDJSON lines as each spider page completes |
| **Backend export** | `scrapit export --from sqlite --to csv` — migrate between backends |
| **Web dashboard** | `scrapit serve` — browse results, run directives, download output |
| **Stats reporter** | Field coverage %, timing, error count per run |
| **Hook system** | Register callbacks for scrape lifecycle events |
| **Plugin system** | Publish custom transforms/backends as pip packages via entry_points |
| **Async queue** | RabbitMQ producer/consumer for background processing |
| **Structured logging** | Console + `output/scraper.log` |

---

## Installation

```bash
git clone <repo-url>
cd scrapit

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# if you use the playwright backend:
playwright install chromium
```

Copy and fill in your credentials:

```bash
cp scraper/.env.example .env
```

```dotenv
# MongoDB (optional)
MONGO_URI=mongodb+srv://user:pass@cluster/
MONGO_DATABASE=mydb
MONGO_COLLECTION=scraped

# RabbitMQ (optional)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASS=guest

# Webhook notifications (optional)
SCRAPIT_WEBHOOK_URL=https://hooks.example.com/...
```

---

## Quick Start

```bash
# create a new directive interactively
scrapit init

# scrape Wikipedia, save to JSON
scrapit scrape wikipedia --json

# scrape Hacker News (paginated), save to SQLite
scrapit scrape hn --sqlite

# spider Books to Scrape, preview only
scrapit scrape books --preview

# stream results as they arrive (spider mode)
scrapit scrape blog --json --stream

# scrape all directives in the default folder
scrapit batch --json

# list available directives
scrapit list

# open the web dashboard
scrapit serve

# run a scheduled directive as a daemon
scrapit run hn --json

# export SQLite → CSV
scrapit export --from sqlite --to csv --directive hn

# check environment
scrapit doctor
```

---

## CLI Reference

### `init` — create a new directive interactively

```bash
python -m scraper.main init
```

Guides you through a series of prompts and generates a ready-to-edit YAML in `scraper/directives/`:

```
? Site URL: https://news.ycombinator.com
? Scraping backend (beautifulsoup/playwright) [beautifulsoup]:
? Output file name (without .yaml): hackernews
? Fields to scrape (comma-separated, e.g. titles, links, scores): titles, links, scores

→ Created scraper/directives/hackernews.yaml

Next steps:
  1. Open scraper/directives/hackernews.yaml and replace each 'FIXME' with a real CSS selector.
  2. Run: python -m scraper.main scrape hackernews --preview
  3. Save results: python -m scraper.main scrape hackernews --json
```

Each field is stubbed with a `FIXME` placeholder — open the file, fill in your CSS selectors, and you're ready to scrape.

---

### `scrape` — single directive

```bash
scrapit scrape <directive> [--json|--csv|--sqlite|--mongo|--postgres|--excel|--sheets|--parquet] [--preview] [--diff] [--stream]
```

`<directive>` can be a name (`wikipedia`), filename (`wikipedia.yaml`), or path.

| Flag | Description |
|------|-------------|
| `--json` | Save to `output/<name>.json` (default) |
| `--csv` | Append to `output/<name>.csv` |
| `--sqlite` | Save to `output/scrapit.db` |
| `--mongo` | Save to MongoDB |
| `--postgres` | Save to PostgreSQL |
| `--excel` | Append to `output/<name>.xlsx` |
| `--sheets` | Append to Google Sheets (requires `--sheets-id`) |
| `--parquet` | Save to `output/<name>.parquet` |
| `--format` | JSON format: `pretty` (indented, default) or `compact` (minified) |
| `--preview` | Print result, do not save |
| `--diff` | Compare with previous JSON output and show changes |
| `--stream` | Emit NDJSON lines to stdout as each spider page completes |
| `--resume` | Resume interrupted spider/paginated scrape from checkpoint |
| `--reset-state` | Clear incremental spider state for this directive |
| `--timeout N` | Per-request timeout in seconds (overrides directive setting) |

### `batch` — all directives in a folder

```bash
scrapit batch [folder] [--json|--csv|--sqlite|--mongo|--excel] [--preview] [--diff]
```

Default folder: `scraper/directives/`

### `list` — inspect directives

```bash
scrapit list [--dir path/to/folder]
```

Shows site, backend, fields, transforms, validation rules, cache, and schedule config.

### `run` — daemon / recurring schedule

```bash
scrapit run <directive> [--json|--sqlite|...]
```

Reads the `schedule:` key from the directive YAML and runs it repeatedly on that schedule. Supports cron expressions (requires `croniter`) or simple intervals like `5m`, `1h`.

```yaml
site: https://news.ycombinator.com
use: beautifulsoup
schedule: "*/30 * * * *"   # every 30 minutes
scrape:
  titles: ['.titleline > a', {attr: text, all: true}]
```

### `export` — migrate between backends

```bash
scrapit export --from sqlite --to csv --directive hn
scrapit export --from sqlite --to mongo --directive product --since 2026-01-01
scrapit export --from json   --to parquet --directive wikipedia
scrapit export --from sqlite --to csv --all   # all directives
```

### `suggest-selectors` — ask Claude for CSS selectors

```bash
scrapit suggest-selectors https://books.toscrape.com --fields "title,price,rating"
```

Fetches the page and asks Claude to suggest the best CSS selectors for each field. Outputs a ready-to-paste `scrape:` block. Requires `pip install anthropic`.

---

### `share` — share a directive with the community

```bash
scrapit share wikipedia
```

Creates a GitHub issue in the Scrapit repo with your directive YAML, making it available to everyone. Requires the `gh` CLI authenticated.

---

### `ai-init` — generate a directive with Claude

```bash
scrapit ai-init https://news.ycombinator.com --name hackernews
scrapit ai-init https://books.toscrape.com --fields "title,price,rating"
```

Fetches the page, sends the content to Claude, and generates a ready-to-use YAML directive. Requires `pip install anthropic` and `ANTHROPIC_API_KEY` in your environment.

---

### `query` — read stored data

```bash
scrapit query --backend sqlite --limit 10
scrapit query --directive wikipedia
scrapit query --url wikipedia.org
```

### `cache` — manage HTTP cache

```bash
scrapit cache stats                              # show cache size and entry count
scrapit cache clear                              # delete all cached responses
scrapit cache invalidate --url https://example.com
```

### `diff` — compare two output files

```bash
scrapit diff old.json new.json
scrapit diff old.json new.json --key url         # use URL as record key
scrapit diff old.json new.json --summary         # counts only, no detail
```

### `validate` — lint a directive

```bash
scrapit validate wikipedia        # check required keys, transforms, selectors
```

### `serve` — web dashboard

```bash
scrapit serve                     # opens http://127.0.0.1:7331
scrapit serve --host 0.0.0.0 --port 8080 --no-browser
```

### `doctor` — environment check

```bash
scrapit doctor                    # checks all optional/required dependencies
```

---

## Writing Directives

> **VS Code autocomplete:** add this line to the top of any directive YAML for inline docs and validation:
> ```yaml
> # yaml-language-server: $schema=https://raw.githubusercontent.com/joaobenedetmachado/scrapit/main/scrapit.schema.json
> ```

### Minimal directive

```yaml
site: https://example.com
use: beautifulsoup   # or playwright

scrape:
  field_name:
    - 'css-selector'
    - attr: text     # 'text' = inner text, or any HTML attribute (href, src, …)
```

### All directive options

```yaml
site: https://example.com
use: beautifulsoup       # beautifulsoup | playwright | httpx | graphql | brightdata

# ── Mode ─────────────────────────────────────────────────────────────────────
mode: single             # single (default) | spider

# ── Multiple sites (same scrape spec applied to each) ────────────────────────
sites:
  - https://example.com/page-1
  - https://example.com/page-2

# ── Request options ───────────────────────────────────────────────────────────
retries: 3               # HTTP retries with exponential backoff (bs4)
timeout: 15              # seconds (bs4) or milliseconds (playwright)
delay: 1.0               # seconds between requests (rate limiting)
headers:                 # extra HTTP headers
  Authorization: Bearer ${TOKEN}   # ${VAR} is interpolated from environment
cookies:                 # bs4: dict  |  playwright: list of {name,value,domain}
  session_id: abc123
proxy: http://proxy:8080 # or: brightdata (uses BRIGHTDATA_* env vars)
respect_robots: true     # check robots.txt before fetching (bs4 only)

# ── Proxy pool (rotation) ─────────────────────────────────────────────────────
proxies:
  - http://proxy1:8080
  - http://proxy2:8080
proxy_strategy: round_robin   # round_robin (default) | random

# ── Throttle ─────────────────────────────────────────────────────────────────
throttle:
  requests_per_second: 2
  jitter: 0.5            # adds random 0–0.5s extra delay

# ── Cache ─────────────────────────────────────────────────────────────────────
cache:
  ttl: 3600              # seconds (0 = disabled)
  backend: file          # file (default) | redis
  key_prefix: scrapit:   # Redis only

# ── Schedule (used by `scrapit run` daemon) ───────────────────────────────────
schedule: "*/30 * * * *" # cron expression, or simple: 5m, 1h

# ── Playwright-only ───────────────────────────────────────────────────────────
wait_for: '#content'     # wait for selector before parsing
screenshot: true         # save full-page screenshot to output/
stealth: true            # randomise UA, viewport, locale, navigator fingerprint

# ── Scrape spec ───────────────────────────────────────────────────────────────
scrape:
  title:
    - 'h1'               # single selector
    - attr: text

  image:
    - ['img.hero', 'img.main', 'img']   # fallback selectors
    - attr: src

  all_links:
    - 'a.result'
    - attr: href
      all: true          # return list of all matches

# ── Pagination (bs4 only) ─────────────────────────────────────────────────────
paginate:
  selector: 'a.next-page'
  attr: href
  max_pages: 5

# ── Spider mode ───────────────────────────────────────────────────────────────
follow:
  selector: 'a.article-link'
  attr: href
  max: 50                # max pages to scrape
  same_domain: true      # stay on same domain
  depth: 1               # link-following depth
  incremental: true      # skip URLs visited in previous runs (persistent state)
  parallel: 5            # async concurrent fetching (requires httpx)

# ── Transform pipeline ────────────────────────────────────────────────────────
transform:
  price:
    - strip
    - {replace: {"€": "", ",": "."}}
    - float
  title:
    - strip
    - upper
  description:
    - strip
    - {slice: {end: 200}}
  tags:
    - {split: ","}
    - first

# ── Validation ────────────────────────────────────────────────────────────────
validate:
  title:
    required: true
    min_length: 2
    max_length: 500
  price:
    type: float
    min: 0
  status:
    in: [active, inactive, pending]

# ── Notifications ─────────────────────────────────────────────────────────────
notify:
  webhook: https://hooks.slack.com/...   # called when --diff detects changes
```

### Available transforms

| Transform | Argument | Description |
|-----------|----------|-------------|
| `strip` | — | Strip leading/trailing whitespace |
| `lower` / `upper` / `title` | — | Change case |
| `capitalize` | — | First character upper, rest unchanged |
| `sentence_case` | — | First character upper, rest lower |
| `int` / `float` | — | Parse number (removes non-numeric chars, handles European notation) |
| `boolean` | — | `"true"`/`"yes"`/`"1"` → `True`, `"false"`/`"no"` → `False` |
| `count` | — | Length of a string or list |
| `regex` | `pattern` | Extract first regex match |
| `regex_group` | `{pattern, group}` | Extract specific capture group |
| `replace` | `{old: new}` | String substitution (multiple pairs) |
| `split` | `","` | Split string into list |
| `join` | `", "` | Join list into string |
| `first` / `last` | — | Pick first/last item from list |
| `default` | `value` | Fallback if value is None |
| `slice` | `{start, end}` or `N` | Substring / sublist |
| `prepend` / `append` | `"str"` | Add text before/after |
| `remove_tags` | — | Strip HTML tags |
| `template` | `"prefix {value}"` | String template with `{value}` or `{other_field}` |
| `slugify` | — | Convert text to a URL-friendly slug (`Hello World` → `hello-world`) |
| `truncate` | `N` | Truncate to N characters without breaking words, appends `...` |
| `normalize_whitespace` | — | Collapse multiple spaces/tabs into a single space and strip |
| `date` | — | Parse date string to ISO `YYYY-MM-DD` (auto-detects common formats) |
| `parse_date` | `{input_format, output_format}` | Parse date with custom strptime format |
| `pad` | `{width, char, side}` | Pad string to fixed width (`pad: {width: 5, char: "0", side: left}`) |
| `hash` | `algorithm` | Hash value: `md5`, `sha1`, `sha256`, `sha512` |

### Available validation rules

| Rule | Example | Description |
|------|---------|-------------|
| `required` | `true` | Must not be None |
| `type` | `float` | Type check: `str`, `int`, `float`, `list`, `bool` |
| `not_empty` | `true` | Must not be empty string/list |
| `min` / `max` | `0` / `1000` | Numeric range |
| `min_length` / `max_length` | `2` / `500` | String/list length |
| `pattern` | `^\d{4}$` | Regex must match |
| `in` | `[a, b, c]` | Value must be in enum |
| `not_in` | `[a, b, c]` | Value must NOT be in enum |

---

## Output

All outputs go to `output/` at the project root.

| File | Description |
|------|-------------|
| `output/<name>.json` | Last scrape as JSON |
| `output/<name>.csv` | All scrapes in append-mode CSV |
| `output/scrapit.db` | SQLite database with all scrapes |
| `output/scraper.log` | Full log (also printed to console) |
| `output/<name>_<ts>.png` | Screenshot (Playwright + `screenshot: true`) |
| PostgreSQL `scrapes` table | All scrapes saved to PostgreSQL database |

---

## Project Structure

```
scrapit/
  scraper/
    main.py                   CLI (scrape/batch/list/query/cache/export/run/serve/diff/validate/doctor…)
    config.py                 Environment variables and paths
    logger.py                 Logging → console + output/scraper.log
    hooks.py                  Lifecycle hook registry
    reporter.py               Timing and field coverage stats
    plugins.py                Plugin loader — discovers transforms/backends via entry_points
    proxy.py                  ProxyPool — round-robin / random rotation
    colors.py                 ANSI color helpers for CLI output
    dashboard.py              FastAPI web dashboard (scrapit serve)
    directives/               Built-in example directives
      wikipedia.yaml
      hn.yaml                 Hacker News (paginated)
      books.yaml              Books to Scrape (spider mode)
      github_trending.yaml    GitHub trending (all: true)
    scrapers/
      __init__.py             Pipeline dispatcher
      bs4_scraper.py          BeautifulSoup + retry + proxy + cache
      playwright_scraper.py   Playwright + stealth mode
      httpx_scraper.py        httpx async backend
      graphql_scraper.py      GraphQL API backend
      paginator.py            Pagination support
      spider.py               Spider (incremental, parallel asyncio)
    transforms/
      __init__.py             28+ transform functions + plugin registry
    validators/
      __init__.py             Validation engine
    storage/
      mongo.py                MongoDB (lazy connect)
      json_file.py            JSON output
      csv_file.py             CSV output (append)
      sqlite.py               SQLite (zero-config, with read() for export)
      excel.py                Excel XLSX (append mode)
      google_sheets.py        Google Sheets live sync
      postgres.py             PostgreSQL
      parquet_file.py         Apache Parquet (pyarrow)
      diff.py                 Change detection
    cache/
      __init__.py             HTTP cache with TTL (file or Redis)
      redis_cache.py          Redis cache backend
    integrations/
      anthropic.py            Anthropic SDK tools + agentic loop
      openai.py               OpenAI function calling + agent
      langchain.py            LangChain / CrewAI / LangGraph toolkit
      llamaindex.py           LlamaIndex reader
      mcp.py                  MCP server (Claude Desktop / Cursor / Claude Code)
      brightdata.py           Bright Data Scraping Browser integration
    notifications/
      __init__.py             Webhook notifications (Slack, Discord, custom)
    queue/
      producer.py             RabbitMQ producer
      consumer.py             RabbitMQ consumer
  output/                     Generated data (gitignored)
  .cache/                     HTTP cache (gitignored)
  pyproject.toml              Extras: ui, anthropic, mcp, httpx, parquet, redis…
  requirements.txt
  .env
```

## Scheduling

Scrapit includes a built-in scheduler to run your directives on a recurring basis without needing external tools like `cron`.

### YAML Configuration

Add the `schedule:` key to any directive YAML. It supports two formats:

1.  **Cron Expressions**: Standard 5-field cron syntax (requires `pip install croniter`).
2.  **Simple Intervals**: Human-readable strings like `5m`, `1h`, `12h`, `1d`.

```yaml
site: https://news.ycombinator.com
use: beautifulsoup

# Run every 30 minutes
schedule: "*/30 * * * *"

# Or use an interval:
# schedule: "1h"

scrape:
  titles: ['.titleline > a', {attr: text, all: true}]
```

### Running the Daemon

To start the scheduler for a specific directive, use the `run` command:

```bash
scrapit run hn --json
```

This will start a long-running process that waits for the next scheduled time, runs the scraper, saves the output, and repeats.

> [!NOTE]
> If you use cron expressions, ensure you have the optional dependency installed:
> `pip install croniter`

---

## Hook System

Register Python callbacks for scrape lifecycle events:

```python
from scraper import hooks

@hooks.on("after_scrape")
def log_result(result, dados):
    print(f"scraped {result['url']} — {len(result)} fields")

@hooks.on("on_change")
def alert(changes, result):
    print(f"change in {result['url']}: {list(changes.keys())}")

@hooks.on("on_error")
def handle_error(exc, dados):
    print(f"failed on {dados['site']}: {exc}")
```

Available events: `before_scrape`, `after_scrape`, `on_error`, `on_save`, `on_change`

---

## AI Agent Integrations

Scrapit integrates natively with every major AI agent framework. Give any agent the ability to scrape the web on demand — no boilerplate required.

### MCP Server (Claude Desktop, Cursor, Claude Code)

The fastest way to add Scrapit to Claude:

```bash
# Claude Code
claude mcp add scrapit -- python -m scraper.integrations.mcp
```

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scrapit": {
      "command": "python",
      "args": ["-m", "scraper.integrations.mcp"],
      "cwd": "/path/to/scrapit"
    }
  }
}
```

After adding, Claude will have 4 web scraping tools available automatically.

### Anthropic SDK (native tool use)

```python
import anthropic
from scraper.integrations.anthropic import as_anthropic_tools, handle_tool_call

client = anthropic.Anthropic()
tools  = as_anthropic_tools()

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What are the top posts on Hacker News?"}],
)

for block in response.content:
    if block.type == "tool_use":
        result = handle_tool_call(block.name, block.input)

# Or use the built-in agent loop:
from scraper.integrations.anthropic import ScrapitAnthropicAgent

agent = ScrapitAnthropicAgent(model="claude-opus-4-6")
answer = agent.run("Summarize the top 3 Hacker News posts today.")
```

### LangChain / CrewAI / LangGraph

```python
from scraper.integrations.langchain import ScrapitToolkit
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI

tools = ScrapitToolkit().get_tools()
# → [ScrapitTool, ScrapitPageTool, ScrapitSelectorTool]

agent = initialize_agent(
    tools=tools,
    llm=ChatOpenAI(model="gpt-4o"),
    agent=AgentType.OPENAI_FUNCTIONS,
)
agent.run("What does the Wikipedia article on Python say?")
```

Works with **CrewAI** — pass `ScrapitToolkit().get_tools()` to any `Agent(tools=[...])`.

### OpenAI SDK (function calling)

```python
from openai import OpenAI
from scraper.integrations.openai import as_openai_functions, handle_function_call

client = OpenAI()
tools  = as_openai_functions()

response = client.chat.completions.create(
    model="gpt-4o", tools=tools,
    messages=[{"role": "user", "content": "Scrape the top GitHub trending repos."}],
)

# Or use the built-in agent loop:
from scraper.integrations.openai import ScrapitOpenAIAgent

agent = ScrapitOpenAIAgent(model="gpt-4o")
answer = agent.run("What are the trending Python repos on GitHub today?")
```

### LlamaIndex (RAG pipelines)

```python
from scraper.integrations.llamaindex import ScrapitReader
from llama_index.core import VectorStoreIndex

reader = ScrapitReader()
docs   = reader.load_data(urls=["https://site1.com", "https://site2.com"])  # parallel

index  = VectorStoreIndex.from_documents(docs)
engine = index.as_query_engine()
response = engine.query("Summarize the main points.")
```

### Quick programmatic API (no YAML needed)

```python
from scraper.integrations import scrape_url, scrape_page, scrape_with_selectors, scrape_many

# Clean text — ready to feed to an LLM
text = scrape_url("https://news.ycombinator.com")

# Structured metadata: title, description, links, word_count
page = scrape_page("https://example.com")

# Agent-defined extraction with CSS selectors — no YAML needed
data = scrape_with_selectors(
    "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000",
    selectors={"title": "h1", "price": "p.price_color"},
)

# Parallel scraping
pages = scrape_many(["https://a.com", "https://b.com"], mode="page")

# Run a directive and get structured data
data = scrape_directive("wikipedia")
```

### Optional dependencies

All integration dependencies are lazy — Scrapit works without any of them installed.
Install only what you need:

```bash
pip install anthropic          # Anthropic SDK integration
pip install openai             # OpenAI integration
pip install langchain-core     # LangChain / CrewAI / LangGraph
pip install llama-index-core   # LlamaIndex
pip install mcp                # MCP server (Claude Desktop / Cursor / Claude Code)
```

---

## Async Queue (RabbitMQ)

Send a directive to the background queue:

```python
from scraper.queue.producer import call_producer
call_producer("directives/wikipedia.yaml")
```

Start a consumer worker:

```bash
python -m scraper.queue.consumer
```

Workers scrape each received directive and save to MongoDB automatically.

---

## Programmatic Usage

```python
import asyncio
from scraper.scrapers import grab_elements_by_directive
from scraper.storage import json_file

result = asyncio.run(grab_elements_by_directive("scraper/directives/wikipedia.yaml"))
json_file.save(result, "wikipedia")
```

---

## Contributing

Contributions are welcome! Whether it's a bug fix, a new transform, a new storage backend, or just sharing a directive YAML that works for a site you scraped.

See [CONTRIBUTING.md](CONTRIBUTING.md) here, for a full guide on how to get started.

Quick ways to contribute:
- **Share a directive** — open an issue with the "Share a Directive" template
- **New transform** — add a function to `scraper/transforms/__init__.py` and open a PR
- **Bug report** — use the bug report issue template

### Contributors

<a href="https://github.com/joaobenedetmachado/scrapit/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=joaobenedetmachado/scrapit" />
</a>

### Star History

[![Star History Chart](https://api.star-history.com/svg?repos=joaobenedetmachado/scrapit&type=Date)](https://star-history.com/#joaobenedetmachado/scrapit&Date)

---

## Requirements

- Python 3.10+
- `requests`, `bs4`, `pyyaml` — always required
- `playwright` — only for playwright backend
- `pymongo`, `python-dotenv` — only for MongoDB
- `pika` — only for RabbitMQ queue
- SQLite is included in Python's stdlib (no install needed)

---

## License

[MIT](LICENSE) © João Benedet Machado

---

## Proxy Configuration

### Single proxy

```yaml
site: https://example.com
use: beautifulsoup
proxy: http://proxy.example.com:8080   # or ${PROXY_URL} from env
scrape:
  title: ['h1']
```

### Proxy pool (rotation)

```yaml
proxies:
  - http://proxy1.example.com:8080
  - http://proxy2.example.com:8080
  - http://proxy3.example.com:8080
proxy_strategy: round_robin   # or: random

# Scrapit automatically retries with the next proxy on failure
```

### Bright Data Scraping Browser

```yaml
use: brightdata   # full CDP via Scraping Browser
# requires BRIGHTDATA_CUSTOMER, BRIGHTDATA_ZONE, BRIGHTDATA_PASSWORD in .env
```

```bash
pip install scrapit-scraper[brightdata]
```

---
