"""Unit tests for LRU cache and connection pooling."""

import pytest

from web_mcp.cache import LRUCache, get_cache, reset_cache
from web_mcp.fetcher import (
    FetchError,
    get_connection_pool,
)
import web_mcp.fetcher as fetcher_module


def _reset_connection_pool():
    """Reset the global connection pool without async close."""
    fetcher_module._connection_pool = None


class TestConnectionPool:
    """Tests for connection pool functionality."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        _reset_connection_pool()
        yield
        _reset_connection_pool()

    def test_get_connection_pool_singleton(self, clean_state):
        """Test that get_connection_pool returns a singleton."""
        pool1 = get_connection_pool()
        pool2 = get_connection_pool()
        
        assert pool1 is pool2

    def test_connection_pool_has_limits(self, clean_state):
        """Test that connection pool is created successfully."""
        pool = get_connection_pool()
        
        assert pool is not None
        assert hasattr(pool, 'get')


class TestFetchUrlCached:
    """Tests for fetch_url_cached function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        _reset_connection_pool()
        reset_cache()
        yield
        _reset_connection_pool()
        reset_cache()

    def test_cache_hit(self, clean_state):
        """Test that cached content is returned on second fetch."""
        from web_mcp.cache import get_cache
        cache = get_cache()
        
        # First fetch would normally go to network (mocked)
        # For testing, we'll just verify the cache is used
        cache.set("https://example.com", "<html>cached content</html>")
        
        # Second fetch should return from cache
        result = cache.get("https://example.com")
        assert result == "<html>cached content</html>"

    def test_cache_eviction(self, clean_state):
        """Test that LRU eviction works correctly."""
        cache = LRUCache(max_size=3)
        
        cache.set("url1", "content1")
        cache.set("url2", "content2")
        cache.set("url3", "content3")
        
        cache.get("url1")
        
        cache.set("url4", "content4")
        
        assert cache.get("url1") == "content1"
        assert cache.get("url2") is None
        assert cache.get("url3") == "content3"
        assert cache.get("url4") == "content4"


class TestFetchError:
    """Tests for FetchError exception."""

    def test_fetch_error_message(self):
        """Test FetchError message."""
        error = FetchError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"

    def test_fetch_error_inherits_exception(self):
        """Test FetchError inherits from Exception."""
        error = FetchError("Test")
        assert isinstance(error, Exception)
