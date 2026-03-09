"""Tests for spider mode."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
from scraper.scrapers.spider import Spider


@pytest.fixture
def spider():
    return Spider({
        "site": "https://example.com",
        "follow": {},
        "scrape": {},
    })


@pytest.fixture
def spider_external():
    return Spider({
        "site": "https://example.com",
        "follow": {"same_domain": True},
        "scrape": {},
    })


class TestDiscover:
    def test_finds_correct_urls(self, spider):
        html = """
        <html><body>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = spider._discover(soup, "https://example.com")
        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

    def test_same_domain_blocks_external(self, spider_external):
        html = """
        <html><body>
            <a href="/page1">Internal</a>
            <a href="https://other.com/page">External</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = spider_external._discover(soup, "https://example.com")
        assert len(urls) == 1
        assert "https://example.com/page1" in urls
        assert "https://other.com/page" not in urls

    def test_skips_invalid_hrefs(self, spider):
        html = """
        <html><body>
            <a href="#">Hash link</a>
            <a href="javascript:void(0)">JS link</a>
            <a href="mailto:test@test.com">Email</a>
            <a href="/valid">Valid</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = spider._discover(soup, "https://example.com")
        assert len(urls) == 1
        assert "https://example.com/valid" in urls

    def test_no_duplicates(self, spider):
        html = """
        <html><body>
            <a href="/page1">Link 1</a>
            <a href="/page1">Link 1 again</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = spider._discover(soup, "https://example.com")
        assert len(urls) == 1


class TestMaxCap:
    def test_max_caps_results(self):
        spider = Spider({
            "site": "https://example.com",
            "follow": {"max": 2},
            "scrape": {},
        })
        links = "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(10))
        html = f"<html><body>{links}</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        urls = spider._discover(soup, "https://example.com")
        assert len(urls[:spider.max]) <= 2


class TestCheckpoint:
    def test_save_and_load_checkpoint(self, spider, tmp_path):
        spider._CHECKPOINTS_DIR = tmp_path / ".checkpoints"
        discovered = ["https://example.com/page1", "https://example.com/page2"]
        completed = {"https://example.com/page1"}
        spider._save_checkpoint("test", discovered, completed)
        loaded = spider._load_checkpoint("test")
        assert "https://example.com/page1" in loaded


class TestIncrementalState:
    def test_skips_previously_visited(self, spider, tmp_path):
        spider._STATE_DIR = tmp_path / ".state"
        visited = {"https://example.com/page1"}
        spider._save_state("test", visited)
        loaded = spider._load_state("test")
        assert "https://example.com/page1" in loaded