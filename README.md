# Scrapit

[![CI](https://github.com/joaobenedetmachado/scrapit/actions/workflows/ci.yml/badge.svg)](https://github.com/joaobenedetmachado/scrapit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

A modular, YAML-driven web scraper framework. Describe any scraping target in a config file — Scrapit handles fetching, parsing, transforming, validating, and storing the data.

No code required for new targets. Just write a YAML.

---

## Features

| Feature | Description |
|---------|-------------|
| **YAML directives** | Declarative scrape configs — selectors, transforms, validation, cache |
| **Two backends** | BeautifulSoup (fast, static) or Playwright (JS-rendered) |
| **Fallback selectors** | Per-field list of CSS selectors tried in order |
| **`all: true`** | Extract all matches for a selector, not just the first |
| **Pagination** | Follow "next page" links automatically |
| **Spider mode** | Discover and scrape all linked pages from an index |
| **Multi-site** | Scrape multiple URLs with the same spec in one directive |
| **Transform pipeline** | Declarative field transforms: strip, regex, float, replace, split… |
| **Validation** | Per-field rules: required, type, min/max, pattern, enum |
| **Five output backends** | JSON, CSV (append), SQLite (zero-config), MongoDB, PostgreSQL |
| **HTTP cache** | File-based cache with TTL — avoid re-fetching during dev |
| **Change detection** | Diff result against previous run, fire webhook on change |
| **Webhook notifications** | POST JSON payload to any URL when changes detected |
| **Stats reporter** | Field coverage %, timing, error count per run |
| **Hook system** | Register callbacks for scrape lifecycle events |
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
python -m scraper.main init

# scrape Wikipedia, save to JSON
python -m scraper.main scrape wikipedia --json

# scrape Hacker News (paginated), save to SQLite
python -m scraper.main scrape hn --sqlite

# spider Books to Scrape, preview only
python -m scraper.main scrape books --preview

# scrape all directives in the default folder
python -m scraper.main batch --json

# list available directives
python -m scraper.main list
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
python -m scraper.main scrape <directive> [--json|--csv|--sqlite|--mongo] [--preview] [--diff]
```

`<directive>` can be a name (`wikipedia`), filename (`wikipedia.yaml`), or path.

| Flag | Description |
|------|-------------|
| `--json` | Save to `output/<name>.json` (default) |
| `--csv` | Append to `output/<name>.csv` |
| `--sqlite` | Save to `output/scrapit.db` |
| `--mongo` | Save to MongoDB |
| `--excel` | Append to `output/<name>.xlsx` |
| `--format` | JSON format: `pretty` (indented, default) or `compact` (minified) |
| `--preview` | Print result, do not save |
| `--diff` | Compare with previous JSON output and show changes |

### `batch` — all directives in a folder

```bash
python -m scraper.main batch [folder] [--json|--csv|--sqlite|--mongo|--excel] [--preview] [--diff]
```

Default folder: `scraper/directives/`

### `list` — inspect directives

```bash
python -m scraper.main list [--dir path/to/folder]
```

Shows site, backend, fields, transforms, validation rules, and cache config.

### `query` — read stored data

```bash
# recent scrapes from SQLite
python -m scraper.main query --backend sqlite --limit 10

# filter by directive name
python -m scraper.main query --directive wikipedia

# filter by URL fragment
python -m scraper.main query --url wikipedia.org
```

### `cache` — manage HTTP cache

```bash
python -m scraper.main cache stats        # show cache size and entry count
python -m scraper.main cache clear        # delete all cached responses
python -m scraper.main cache invalidate --url https://example.com
```

---

## Writing Directives

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
use: beautifulsoup       # or playwright

# ── Mode ─────────────────────────────────────────────────────────────────────
mode: single             # single (default) | spider

# ── Multiple sites (same scrape spec applied to each) ────────────────────────
sites:
  - https://example.com/page-1
  - https://example.com/page-2

# ── Request options ───────────────────────────────────────────────────────────
retries: 3               # HTTP retries with exponential backoff (bs4)
timeout: 15              # seconds (bs4) or milliseconds (playwright)
headers:                 # extra HTTP headers
  Authorization: Bearer xxx
cookies:                 # bs4: dict  |  playwright: list of {name,value,domain}
  session_id: abc123
proxy: http://proxy:8080

# Proxy with authentication:
# proxy: http://user:password@proxy:8080
# proxy: https://user:password@proxy:8080
# proxy: socks5://user:password@proxy:1080

# Using environment variable (set in .env):
# proxy: ${PROXY_URL}

# ── Cache ─────────────────────────────────────────────────────────────────────
cache:
  ttl: 3600              # seconds (0 = disabled)

# ── Playwright-only ───────────────────────────────────────────────────────────
wait_for: '#content'     # wait for selector before parsing
screenshot: true         # save full-page screenshot to output/

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

# ── Spider mode (bs4 only) ────────────────────────────────────────────────────
follow:
  selector: 'a.article-link'
  attr: href
  max: 50                # max pages to scrape
  same_domain: true      # stay on same domain

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
| `strip` | — | Strip whitespace |
| `lower` / `upper` / `title` | — | Change case |
| `capitalize` | — | First character upper, rest unchanged |
| `sentence_case` | — | First character upper, rest lower |
| `int` / `float` | — | Parse number (removes non-numeric chars) |
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
    main.py                   CLI entry point (init/scrape/batch/list/query/cache)
    config.py                 Environment variables and paths
    logger.py                 Logging → console + output/scraper.log
    hooks.py                  Lifecycle hook registry
    reporter.py               Timing and field coverage stats
    directives/               Built-in example directives
      wikipedia.yaml
      hn.yaml                 Hacker News (paginated)
      books.yaml              Books to Scrape (spider mode)
      github_trending.yaml    GitHub trending (all: true)
    scrapers/
      __init__.py             Pipeline dispatcher
      bs4_scraper.py          BeautifulSoup backend
      playwright_scraper.py   Playwright backend
      paginator.py            Pagination support
      spider.py               Spider / link-following
    transforms/
      __init__.py             Transform pipeline engine
    validators/
      __init__.py             Validation engine
    storage/
      mongo.py                MongoDB (lazy connect)
      json_file.py            JSON output
      csv_file.py             CSV output (append)
      sqlite.py               SQLite (zero-config)
      diff.py                 Change detection
    cache/
      __init__.py             HTTP cache with TTL
    notifications/
      __init__.py             Webhook notifications
    queue/
      producer.py             RabbitMQ producer
      consumer.py             RabbitMQ consumer
  output/                     Generated data (gitignored)
  .cache/                     HTTP cache (gitignored)
  requirements.txt
  .env
```

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

You can use proxies in your directives to route requests through proxy servers.

### Basic Usage

```yaml
site: example.com
use: bs4

scrape:
  url: https://example.com/products
  items:
    selector: ".product"
    fields:
      name:
        selector: "h3"
        method: text

# Proxy configuration
proxy:
  enabled: true
  url: "http://proxy.example.com:8080"
  # Or use environment variables
  # url: "${HTTP_PROXY}"
```

### Using with Environment Variables

```yaml
proxy:
  enabled: true
  url: "${HTTP_PROXY}"  # Reads from HTTP_PROXY or HTTPS_PROXY env var
```

### Proxies for Different Protocols

```yaml
proxy:
  http: "http://http-proxy.example.com:8080"
  https: "https://https-proxy.example.com:8080"
```

### Rotating Proxies

```yaml
proxy:
  enabled: true
  rotate: true
  proxies:
    - "http://proxy1.example.com:8080"
    - "http://proxy2.example.com:8080"
```

### Common Proxy Providers

- **SmartProxy** - Residential proxies
- **Oxylabs** - Enterprise proxies  
- **ScraperAPI** - API with proxy rotation
- **ScrapingBee** - Headless browser with proxies

---

### Best Practices

1. Use residential proxies for sensitive sites
2. Rotate proxies to avoid blocks
3. Set appropriate delay between requests
4. Monitor proxy health and replace dead proxies
