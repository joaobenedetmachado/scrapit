"""Tests for hooks lifecycle system."""
import pytest
from unittest.mock import MagicMock, call
import scraper.hooks as hooks


@pytest.fixture(autouse=True)
def clear_hooks():
    """Clear all hooks before and after each test."""
    hooks.clear()
    yield
    hooks.clear()


class TestRegisterAndFire:
    def test_register_and_fire_basic(self):
        mock_fn = MagicMock()
        hooks.register("after_scrape", mock_fn)
        hooks.fire("after_scrape", {"url": "https://example.com"})
        mock_fn.assert_called_once_with({"url": "https://example.com"})

    def test_unknown_event_raises(self):
        with pytest.raises(ValueError):
            hooks.register("unknown_event", MagicMock())

    def test_fire_empty_event_is_noop(self):
        # no hooks registered, should not raise
        hooks.fire("after_scrape")


class TestMultipleHooks:
    def test_multiple_hooks_fire_in_order(self):
        call_order = []
        hooks.register("after_scrape", lambda *a, **kw: call_order.append("first"))
        hooks.register("after_scrape", lambda *a, **kw: call_order.append("second"))
        hooks.fire("after_scrape", {})
        assert call_order == ["first", "second"]

    def test_exception_does_not_prevent_subsequent_hooks(self):
        def bad_hook(*args, **kwargs):
            raise RuntimeError("something went wrong")

        second_fn = MagicMock()
        hooks.register("after_scrape", bad_hook)
        hooks.register("after_scrape", second_fn)
        hooks.fire("after_scrape", {})
        assert second_fn.called


class TestDecorator:
    def test_on_decorator_registers_hook(self):
        @hooks.on("before_scrape")
        def my_hook(dados):
            pass

        assert my_hook in hooks._HOOKS["before_scrape"]


class TestClear:
    def test_clear_specific_event(self):
        hooks.register("after_scrape", MagicMock())
        hooks.clear("after_scrape")
        assert hooks._HOOKS["after_scrape"] == []

    def test_clear_all_events(self):
        hooks.register("after_scrape", MagicMock())
        hooks.register("on_error", MagicMock())
        hooks.clear()
        assert all(len(v) == 0 for v in hooks._HOOKS.values())