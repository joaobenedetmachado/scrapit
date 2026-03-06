"""
MCP (Model Context Protocol) server for Scrapit.

Exposes Scrapit as an MCP server, making it available as a native tool in:
- Claude Desktop
- Claude Code (claude.ai/code)
- Cursor
- Any MCP-compatible AI client

Installation:

    pip install mcp

Running the server:

    python -m scraper.integrations.mcp

Adding to Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):

    {
      "mcpServers": {
        "scrapit": {
          "command": "python",
          "args": ["-m", "scraper.integrations.mcp"],
          "cwd": "/path/to/your/scrapit"
        }
      }
    }

Adding to Claude Code:

    claude mcp add scrapit -- python -m scraper.integrations.mcp

After adding, restart Claude Desktop or reload Claude Code.
The tools will appear automatically in the tools panel.
"""

from __future__ import annotations

import json

from scraper.integrations import scrape_url, scrape_page, scrape_with_selectors, scrape_directive, scrape_many


def _get_mcp():
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
        return FastMCP
    except ImportError:
        raise ImportError(
            "mcp package is required to run the Scrapit MCP server.\n"
            "Install with: pip install mcp"
        )


def create_server():
    """Create and return the configured MCP server instance."""
    FastMCP = _get_mcp()
    mcp = FastMCP(
        "scrapit",
        instructions=(
            "Scrapit is a web scraping toolkit. Use these tools to fetch and extract "
            "content from web pages in real time. "
            "Start with scrape_page to get an overview of a page, "
            "then use scrape_url for the full text or scrape_with_selectors "
            "to extract specific fields."
        ),
    )

    @mcp.tool()
    def scrape_url_tool(url: str) -> str:
        """
        Fetch a web page and return its clean readable text.

        Strips scripts, styles, navigation, and footers automatically.
        Returns plain text ready to read or summarize.

        Args:
            url: The URL to fetch. Must start with http:// or https://
        """
        return scrape_url(url)

    @mcp.tool()
    def scrape_page_tool(url: str, link_limit: int = 100) -> str:
        """
        Fetch a web page and return structured metadata as JSON.

        Returns: title, meta description, main content text,
        list of outbound links, and word count.

        Use this when you need the page title, want to discover what links
        exist on a page, or need a structured overview before going deeper.

        Args:
            url: The URL to fetch.
            link_limit: Max number of links to return (default 100, set to 0 for all).
        """
        page = scrape_page(url)
        page["main_content"] = page["main_content"][:4000]
        if link_limit > 0:
            page["links"] = page["links"][:link_limit]
        return json.dumps(page, indent=2, default=str)

    @mcp.tool()
    def scrape_with_selectors_tool(
        url: str,
        selectors: dict[str, str],
        all_matches: dict[str, bool] | None = None,
    ) -> str:
        """
        Scrape specific fields from a web page using CSS selectors.

        Use this when you know which HTML elements contain the data you need.
        You define the field names and CSS selectors — no config file required.

        Args:
            url: The URL to scrape.
            selectors: A dict mapping field names to CSS selectors.
                Example: {"title": "h1", "price": ".price-color", "author": ".byline"}
            all_matches: Optional dict controlling which fields return all matches as a list.
                Example: {"items": true} — returns every element matching ".item" as a list.
                By default only the first match is returned for each field.

        Returns:
            JSON with the extracted values for each field.
        """
        result = scrape_with_selectors(url, selectors, all_matches=all_matches or {})
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def scrape_many_tool(
        urls: list[str],
        mode: str = "text",
        selectors: dict[str, str] | None = None,
    ) -> str:
        """
        Scrape multiple URLs in parallel and return all results.

        Use this when you need to fetch several pages at once — much faster than
        calling scrape_url_tool repeatedly.

        Args:
            urls: List of URLs to scrape (up to ~20 for best performance).
            mode: What to extract from each page:
                - "text"      — clean readable text (default)
                - "page"      — structured metadata (title, links, word_count, …)
                - "selectors" — specific fields via CSS selectors (requires selectors arg)
            selectors: Required when mode="selectors". Maps field names to CSS selectors.
                Example: {"title": "h1", "price": ".price"}

        Returns:
            JSON array with one result per URL, in the same order as the input list.
        """
        results = scrape_many(urls, mode=mode, selectors=selectors or {})
        return json.dumps(results, indent=2, default=str)

    @mcp.tool()
    def run_directive_tool(directive: str) -> str:
        """
        Run a pre-configured Scrapit directive by name.

        Scrapit directives are YAML files that define how to scrape a specific site,
        including CSS selectors, transforms, and validation rules.

        Use this when a directive already exists for the target site.
        Available directives: wikipedia, hn, books, github_trending

        Args:
            directive: Directive name (e.g. "wikipedia") or path to a YAML file.

        Returns:
            JSON with the structured scraped data.
        """
        result = scrape_directive(directive)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def scrape_paginated_tool(
        url: str,
        selectors: dict[str, str],
        next_selector: str,
        max_pages: int = 10,
    ) -> str:
        """
        Scrape a paginated website by following "next page" links automatically.

        Use this when a site splits content across multiple pages (search results,
        blog archives, product listings) and you want all pages at once.

        Args:
            url: Starting URL (first page).
            selectors: Dict mapping field names to CSS selectors.
                Example: {"title": "h2.post-title", "link": "a.read-more"}
            next_selector: CSS selector for the "next page" link.
                Example: "a.next", "li.next > a", "a[rel=next]"
            max_pages: Maximum number of pages to follow (default 10).

        Returns:
            JSON array of results, one object per page, each with a "_page" field.
        """
        from scraper.scrapers.paginator import paginate

        dados = {
            "site": url,
            "use": "beautifulsoup",
            "scrape": {field: [sel, {"attr": "text"}] for field, sel in selectors.items()},
            "paginate": {
                "selector": next_selector,
                "attr": "href",
                "max_pages": max_pages,
            },
        }
        results = paginate(dados)
        return json.dumps(results, indent=2, default=str)

    @mcp.tool()
    def run_batch_tool(folder: str | None = None) -> str:
        """
        Run all Scrapit directives in a folder and return combined results.

        Use this to scrape several pre-configured sites at once.
        Each directive is a YAML file that describes how to scrape a specific site.

        Args:
            folder: Path to a folder containing YAML directives.
                    Defaults to the built-in directives folder (wikipedia, hn, books, github_trending, etc.)

        Returns:
            JSON object mapping directive name to its scraped result (or error message).
        """
        import pathlib
        from scraper.integrations import scrape_directive

        if folder:
            directives_dir = pathlib.Path(folder)
        else:
            directives_dir = pathlib.Path(__file__).resolve().parent.parent / "directives"

        yamls = sorted(directives_dir.glob("*.yaml")) + sorted(directives_dir.glob("*.yml"))
        if not yamls:
            return json.dumps({"error": f"No YAML directives found in {directives_dir}"})

        results = {}
        for y in yamls:
            try:
                results[y.stem] = scrape_directive(str(y))
            except Exception as e:
                results[y.stem] = {"error": str(e)}

        return json.dumps(results, indent=2, default=str)

    return mcp


if __name__ == "__main__":
    server = create_server()
    server.run()
