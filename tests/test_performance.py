"""Unit tests for LRU cache and connection pooling."""

import pytest

from web_mcp.cache import LRUCache, get_cache, reset_cache
from web_mcp.fetcher import (
    FetchError,
    get_connection_pool,
)


class TestConnectionPool:
    """Tests for connection pool functionality.

    Note: get_connection_pool is deprecated since we now use tls-client
    as the primary fetcher. It returns None for backward compatibility.
    """

    def test_get_connection_pool_returns_none(self):
        """Test that get_connection_pool returns None (deprecated)."""
        pool = get_connection_pool()
        assert pool is None


class TestFetchUrlCached:
    """Tests for fetch_url_cached function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        reset_cache()
        yield
        reset_cache()

    def test_cache_hit(self, clean_state):
        """Test that cached content is returned on second fetch."""

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
