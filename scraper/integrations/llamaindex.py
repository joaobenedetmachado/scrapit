"""
LlamaIndex integration for Scrapit.

Provides a BaseReader-compatible reader for use in LlamaIndex
ingestion pipelines and RAG applications.

Usage:

    from scraper.integrations.llamaindex import ScrapitReader

    reader = ScrapitReader()

    # From a URL
    docs = reader.load_data(url="https://example.com")

    # From a directive
    docs = reader.load_data(directive="wikipedia")

    # Multiple URLs in parallel
    docs = reader.load_data(urls=["https://site1.com", "https://site2.com"])

    # Build a RAG index
    from llama_index.core import VectorStoreIndex
    index = VectorStoreIndex.from_documents(docs)
    engine = index.as_query_engine()
    response = engine.query("Summarize the main points.")
"""

from __future__ import annotations

from scraper.integrations import scrape_page, scrape_many, scrape_directive


def _dict_to_text(data: dict) -> str:
    skip = {"url", "timestamp", "_id", "_page", "_source", "_valid", "_errors", "ok"}
    lines = []
    for key, value in data.items():
        if key in skip or value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class ScrapitReader:
    """
    LlamaIndex-compatible reader for Scrapit.

    Implements the BaseReader interface — works with LlamaIndex's
    ingestion pipeline and VectorStoreIndex.from_documents().
    """

    def load_data(
        self,
        url: str | None = None,
        directive: str | None = None,
        urls: list[str] | None = None,
        directives: list[str] | None = None,
    ) -> list:
        """
        Load scraped content as LlamaIndex Document objects.

        Args:
            url: Single URL to scrape.
            directive: Directive name or path (structured data).
            urls: List of URLs to scrape in parallel.
            directives: List of directive names/paths.
        """
        Document = _import_document()
        docs = []

        if url:
            docs.extend(self._from_url(url, Document))

        if urls:
            results = scrape_many(urls, mode="page")
            for item in results:
                if not item.get("ok"):
                    continue
                content = item.get("main_content", "")[:4000]
                metadata = {
                    "source": item.get("url", ""),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "word_count": item.get("word_count", 0),
                }
                docs.append(Document(text=content, metadata=metadata))

        if directive:
            docs.extend(self._from_directive(directive, Document))

        for d in directives or []:
            docs.extend(self._from_directive(d, Document))

        return docs

    def _from_url(self, url: str, Document) -> list:
        try:
            page = scrape_page(url)
            content = page["main_content"][:4000]
            metadata = {
                "source": url,
                "title": page.get("title", ""),
                "description": page.get("description", ""),
                "word_count": page.get("word_count", 0),
            }
            return [Document(text=content, metadata=metadata)]
        except Exception as e:
            from scraper.logger import log
            log(f"ScrapitReader: error scraping {url}: {e}", "warning")
            return []

    def _from_directive(self, directive: str, Document) -> list:
        result = scrape_directive(directive)
        results = result if isinstance(result, list) else [result]
        docs = []
        for item in results:
            text = _dict_to_text(item)
            metadata = {
                "source": item.get("url", directive),
                "timestamp": str(item.get("timestamp", "")),
                "directive": directive,
            }
            docs.append(Document(text=text, metadata=metadata))
        return docs


def _import_document():
    try:
        from llama_index.core import Document  # type: ignore
        return Document
    except ImportError:
        try:
            from llama_index import Document  # type: ignore
            return Document
        except ImportError:
            raise ImportError(
                "llama-index is required. Install with: pip install llama-index-core"
            )
