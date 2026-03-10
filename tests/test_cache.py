from unittest.mock import patch,MagicMock
import pytest
import scraper.cache as cache

@pytest.fixture(autouse=True)
def temp_cache(tmp_path, monkeypatch):
    # redirect _CACHE_DIR to tmp_path so tests don't pollute real cache
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)

class TestFileBackend:
    def test_put_and_get(self):
        # put some html, then get it back
        cache.put("https://example.com", "<html>hello</html>", ttl=3600)
        result = cache.get("https://example.com",ttl=3360)
        assert result == "<html>hello</html>"

    def test_ttl_zero_returns_none(self):
        # ttl=0 means disabled
        cache.put("https://example.com", "<html>hello</html>")
        result = cache.get("https://example.com",ttl=0)
        assert result is None
        pass

    def test_expired_returns_none(self):
        with patch("scraper.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.put("https://example.com", "<html>hello</html>")
            
            # simulate 2 hours later
            mock_time.time.return_value = 1000.0 + 7201
            result = cache.get("https://example.com", ttl=3600)
            assert result is None

    def test_invalidate_removes_entry(self):
        # put, then invalidate, then get should return None
        cache.put("https://example.com", "<html>hello</html>")
        cache.invalidate("https://example.com")
        result = cache.get("https://example.com", ttl=3600) 
        assert result is None
        

    def test_clear_all_removes_everything(self):
        # put two urls, clear_all, then both gets return None
        cache.put("https://example.com", "<html>hello</html>")
        cache.put("https://example1.com", "<html>world</html>")
        cache.clear_all()
        assert cache.get("https://example.com", ttl=3600) is None
        assert cache.get("https://example1.com", ttl=3600) is None

    
class TestRedisBackend:
    def test_redis_get_called(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = "<html>cached</html>"
        with patch.dict("sys.modules", {"scraper.cache.redis_cache": mock_redis}):
            result = cache.get(
                "https://example.com",
                ttl=3600,
                cache_cfg={"backend": "redis"}
            )
            assert mock_redis.get.called

    def test_redis_put_called(self):
        mock_redis = MagicMock()
        with patch.dict("sys.modules", {"scraper.cache.redis_cache": mock_redis}):
            cache.put(
                "https://example.com",
                "<html>hello</html>",
                cache_cfg={"backend": "redis"}
            )
            assert mock_redis.put.called
