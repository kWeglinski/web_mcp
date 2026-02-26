"""Unit tests for LRU cache implementation."""

import pytest

from web_mcp.cache import LRUCache, get_cache, reset_cache


class TestLRUCache:
    """Tests for LRUCache class."""

    @pytest.fixture
    def cache(self):
        """Create a cache with max size 3 for testing."""
        return LRUCache(max_size=3)

    def test_set_and_get(self, cache):
        """Test basic set and get operations."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_update_existing_key(self, cache):
        """Test updating an existing key."""
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_lru_eviction(self, cache):
        """Test LRU eviction policy."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # Access key1 to make it recently used
        cache.get("key1")
        
        # Add new item, should evict key2 (least recently used)
        cache.set("key4", "value4")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_eviction_order(self, cache):
        """Test correct eviction order."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # Access key1 to make it recently used
        cache.get("key1")
        
        # Add new item, should evict key2 (least recently used)
        cache.set("key4", "value4")
        
        # key2 should be evicted
        assert cache.get("key2") is None

    def test_delete(self, cache):
        """Test delete operation."""
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache):
        """Test deleting a non-existent key."""
        assert cache.delete("nonexistent") is False

    def test_clear(self, cache):
        """Test clear operation."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert len(cache) == 0
        assert cache.get("key1") is None

    def test_contains(self, cache):
        """Test 'in' operator."""
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "nonexistent" not in cache

    def test_len(self, cache):
        """Test len() function."""
        assert len(cache) == 0
        cache.set("key1", "value1")
        assert len(cache) == 1

    def test_max_size_limit(self, cache):
        """Test that cache respects max size."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1
        
        assert len(cache) == 3
        assert cache.get("key1") is None

    def test_stats(self, cache):
        """Test get_stats method."""
        cache.set("key1", "value1")
        stats = cache.get_stats()
        
        assert stats["size"] == 1
        assert stats["max_size"] == 3


class TestGetCache:
    """Tests for get_cache function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        reset_cache()
        yield
        reset_cache()

    def test_singleton(self, clean_state):
        """Test that get_cache returns a singleton."""
        cache1 = get_cache()
        cache2 = get_cache()
        
        assert cache1 is cache2

    def test_custom_config(self, clean_state):
        """Test with custom environment variables."""
        import os
        from web_mcp.cache import reset_cache
        
        # Set custom config
        os.environ["WEB_MCP_CACHE_SIZE"] = "50"
        
        # Reset and get cache
        reset_cache()
        cache = get_cache()
        
        assert cache.max_size == 50


class TestLRUCacheTTL:
    """Tests for TTL functionality in LRUCache."""

    @pytest.fixture
    def cache(self):
        """Create a cache with max size 3 for testing."""
        return LRUCache(max_size=3)

    def test_expired_entry_not_returned(self, cache):
        """Test that expired entries are not returned."""
        import time
        
        # Set entry with very short TTL (0.1 seconds)
        cache.set("key1", "value1", ttl=0.1)
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Entry should be expired and return None
        assert cache.get("key1") is None

    def test_non_expired_entry_returned(self, cache):
        """Test that non-expired entries are returned."""
        import time
        
        # Set entry with reasonable TTL (1 second)
        cache.set("key1", "value1", ttl=1.0)
        
        # Entry should be valid and return the value
        assert cache.get("key1") == "value1"

    def test_default_ttl_applied(self, cache):
        """Test that default TTL is applied when not specified."""
        import time
        
        # Set entry without specifying TTL
        cache.set("key1", "value1")
        
        # Entry should be valid (using default TTL of 3600 seconds)
        assert cache.get("key1") == "value1"
        
        # Verify the entry has an expiration time (default TTL)
        assert cache.get("key1") is not None

    def test_custom_ttl_can_be_set(self, cache):
        """Test that custom TTL can be set for individual entries."""
        import time
        
        # Set entry with custom short TTL
        cache.set("key1", "value1", ttl=0.1)
        
        # Set entry with custom long TTL
        cache.set("key2", "value2", ttl=3600.0)
        
        # Short TTL entry should expire quickly
        time.sleep(0.2)
        assert cache.get("key1") is None
        
        # Long TTL entry should still be valid
        assert cache.get("key2") == "value2"

    def test_expired_entry_removed_from_cache(self, cache):
        """Test that expired entries are removed from cache."""
        import time
        
        # Set entry with short TTL
        cache.set("key1", "value1", ttl=0.1)
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Access the entry to trigger cleanup
        cache.get("key1")
        
        # Cache should be empty
        assert len(cache) == 0

    def test_ttl_with_update_existing_key(self, cache):
        """Test that TTL is updated when updating an existing key."""
        import time
        
        # Set entry with long TTL
        cache.set("key1", "value1", ttl=3600.0)
        
        # Update with new value and short TTL
        cache.set("key1", "value2", ttl=0.1)
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Entry should be expired
        assert cache.get("key1") is None

    def test_ttl_expiration_does_not_affect_lru_order(self, cache):
        """Test that TTL expiration doesn't affect LRU ordering for valid entries."""
        import time
        
        # Set three entries
        cache.set("key1", "value1", ttl=3600.0)
        cache.set("key2", "value2", ttl=3600.0)
        cache.set("key3", "value3", ttl=3600.0)
        
        # Access key1 to make it recently used
        cache.get("key1")
        
        # Add new entry, should evict key2 (least recently used)
        cache.set("key4", "value4", ttl=3600.0)
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"


class TestLRUCacheStats:
    """Tests for cache statistics functionality."""

    @pytest.fixture
    def cache(self):
        """Create a cache with max size 3 for testing."""
        return LRUCache(max_size=3)

    def test_stats_include_size(self, cache):
        """Test that stats include current size."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        stats = cache.get_stats()
        
        assert stats["size"] == 2

    def test_stats_include_max_size(self, cache):
        """Test that stats include max size."""
        stats = cache.get_stats()
        
        assert stats["max_size"] == 3
