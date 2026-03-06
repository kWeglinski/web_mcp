"""Unit tests for embedding cache implementation."""

import os

import pytest

from web_mcp.llm.embedding_cache import (
    EmbeddingCache,
    clear_embedding_cache,
    get_embedding_cache,
    set_embedding_cache_size,
)


class TestEmbeddingCacheCreate:
    """Tests for EmbeddingCache.create factory method."""

    def test_create_with_default_size(self):
        """Test creating cache with default size."""
        cache = EmbeddingCache.create()
        assert cache._max_size == 1000
        assert len(cache.cache) == 0

    def test_create_with_custom_size(self):
        """Test creating cache with custom size."""
        cache = EmbeddingCache.create(max_size=500)
        assert cache._max_size == 500
        assert len(cache.cache) == 0

    def test_create_with_size_one(self):
        """Test creating cache with minimum size."""
        cache = EmbeddingCache.create(max_size=1)
        assert cache._max_size == 1

    def test_create_returns_embedding_cache_instance(self):
        """Test that create returns an EmbeddingCache instance."""
        cache = EmbeddingCache.create()
        assert isinstance(cache, EmbeddingCache)

    def test_create_multiple_independent_caches(self):
        """Test that multiple creates return independent caches."""
        cache1 = EmbeddingCache.create(max_size=10)
        cache2 = EmbeddingCache.create(max_size=20)

        cache1.set("test", [0.1, 0.2, 0.3])

        assert cache1._max_size == 10
        assert cache2._max_size == 20
        assert cache1.get("test") is not None
        assert cache2.get("test") is None


class TestEmbeddingCacheHashContent:
    """Tests for _hash_content method."""

    @pytest.fixture
    def cache(self):
        """Create a cache for testing."""
        return EmbeddingCache.create()

    def test_hash_content_returns_string(self, cache):
        """Test that hash returns a string."""
        result = cache._hash_content("test content")
        assert isinstance(result, str)

    def test_hash_content_returns_16_chars(self, cache):
        """Test that hash is truncated to 16 characters."""
        result = cache._hash_content("test content")
        assert len(result) == 16

    def test_hash_content_is_hex(self, cache):
        """Test that hash contains only hex characters."""
        result = cache._hash_content("test content")
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_content_consistent(self, cache):
        """Test that same input produces same hash."""
        text = "test content for hashing"
        hash1 = cache._hash_content(text)
        hash2 = cache._hash_content(text)
        assert hash1 == hash2

    def test_hash_content_different_for_different_input(self, cache):
        """Test that different inputs produce different hashes."""
        hash1 = cache._hash_content("content one")
        hash2 = cache._hash_content("content two")
        assert hash1 != hash2

    def test_hash_content_empty_string(self, cache):
        """Test hashing empty string."""
        result = cache._hash_content("")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_content_unicode(self, cache):
        """Test hashing unicode content."""
        result = cache._hash_content("Hello 世界 🌍")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_content_whitespace_differences(self, cache):
        """Test that whitespace differences produce different hashes."""
        hash1 = cache._hash_content("test content")
        hash2 = cache._hash_content("test  content")
        hash3 = cache._hash_content(" test content")
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_hash_content_long_text(self, cache):
        """Test hashing long text."""
        long_text = "a" * 10000
        result = cache._hash_content(long_text)
        assert isinstance(result, str)
        assert len(result) == 16


class TestEmbeddingCacheGetSet:
    """Tests for get and set methods."""

    @pytest.fixture
    def cache(self):
        """Create a cache for testing."""
        return EmbeddingCache.create(max_size=10)

    def test_set_and_get_basic(self, cache):
        """Test basic set and get operations."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        cache.set("test text", embedding)
        result = cache.get("test text")
        assert result == embedding

    def test_get_nonexistent_returns_none(self, cache):
        """Test that get returns None for missing keys."""
        result = cache.get("nonexistent text")
        assert result is None

    def test_set_updates_existing(self, cache):
        """Test updating an existing entry."""
        cache.set("test", [0.1, 0.2])
        cache.set("test", [0.3, 0.4])
        result = cache.get("test")
        assert result == [0.3, 0.4]

    def test_get_uses_hashing(self, cache):
        """Test that get uses content hashing."""
        text = "some content"
        embedding = [0.5, 0.6, 0.7]
        cache.set(text, embedding)

        hash_key = cache._hash_content(text)
        assert cache.cache.get(hash_key) == embedding

    def test_set_uses_hashing(self, cache):
        """Test that set uses content hashing."""
        text = "some content"
        embedding = [0.5, 0.6, 0.7]
        cache.set(text, embedding)

        hash_key = cache._hash_content(text)
        assert cache.cache.get(hash_key) == embedding

    def test_set_empty_embedding(self, cache):
        """Test setting an empty embedding list."""
        cache.set("test", [])
        result = cache.get("test")
        assert result == []

    def test_set_large_embedding(self, cache):
        """Test setting a large embedding vector."""
        large_embedding = [0.1] * 1536
        cache.set("test", large_embedding)
        result = cache.get("test")
        assert result == large_embedding

    def test_identical_content_same_cache_key(self, cache):
        """Test that identical content uses same cache key."""
        embedding1 = [0.1, 0.2]
        embedding2 = [0.3, 0.4]

        cache.set("duplicate", embedding1)
        cache.set("duplicate", embedding2)

        assert cache.get("duplicate") == embedding2
        assert len(cache.cache) == 1

    def test_different_content_different_keys(self, cache):
        """Test that different content uses different keys."""
        cache.set("content one", [0.1])
        cache.set("content two", [0.2])

        assert len(cache.cache) == 2


class TestEmbeddingCacheClear:
    """Tests for clear method."""

    @pytest.fixture
    def cache(self):
        """Create a cache with some entries."""
        cache = EmbeddingCache.create(max_size=10)
        cache.set("text1", [0.1])
        cache.set("text2", [0.2])
        cache.set("text3", [0.3])
        return cache

    def test_clear_removes_all_entries(self, cache):
        """Test that clear removes all entries."""
        assert len(cache.cache) == 3
        cache.clear()
        assert len(cache.cache) == 0

    def test_clear_get_returns_none(self, cache):
        """Test that get returns None after clear."""
        cache.clear()
        assert cache.get("text1") is None
        assert cache.get("text2") is None
        assert cache.get("text3") is None

    def test_clear_preserves_max_size(self, cache):
        """Test that clear preserves max_size setting."""
        original_max_size = cache._max_size
        cache.clear()
        assert cache._max_size == original_max_size

    def test_clear_empty_cache(self):
        """Test clearing an already empty cache."""
        cache = EmbeddingCache.create()
        cache.clear()
        assert len(cache.cache) == 0

    def test_can_add_after_clear(self, cache):
        """Test that entries can be added after clear."""
        cache.clear()
        cache.set("new text", [0.5])
        assert cache.get("new text") == [0.5]


class TestEmbeddingCacheStats:
    """Tests for stats method."""

    @pytest.fixture
    def cache(self):
        """Create a cache for testing."""
        return EmbeddingCache.create(max_size=100)

    def test_stats_empty_cache(self, cache):
        """Test stats on empty cache."""
        stats = cache.stats()
        assert stats["max_size"] == 100
        assert stats["current_size"] == 0

    def test_stats_with_entries(self, cache):
        """Test stats with some entries."""
        cache.set("text1", [0.1])
        cache.set("text2", [0.2])
        stats = cache.stats()
        assert stats["max_size"] == 100
        assert stats["current_size"] == 2

    def test_stats_returns_dict(self, cache):
        """Test that stats returns a dictionary."""
        stats = cache.stats()
        assert isinstance(stats, dict)

    def test_stats_has_required_keys(self, cache):
        """Test that stats has required keys."""
        stats = cache.stats()
        assert "max_size" in stats
        assert "current_size" in stats

    def test_stats_after_clear(self, cache):
        """Test stats after clearing cache."""
        cache.set("text", [0.1])
        cache.clear()
        stats = cache.stats()
        assert stats["current_size"] == 0


class TestEmbeddingCacheEviction:
    """Tests for LRU eviction behavior."""

    def test_eviction_occurs_at_max_size(self):
        """Test that eviction occurs when max size is reached."""
        cache = EmbeddingCache.create(max_size=2)

        cache.set("text1", [0.1])
        cache.set("text2", [0.2])
        cache.set("text3", [0.3])

        assert len(cache.cache) == 2

    def test_lru_eviction_order(self):
        """Test that least recently used item is evicted."""
        cache = EmbeddingCache.create(max_size=3)

        cache.set("text1", [0.1])
        cache.set("text2", [0.2])
        cache.set("text3", [0.3])

        cache.get("text1")

        cache.set("text4", [0.4])

        assert cache.get("text1") == [0.1]
        assert cache.get("text2") is None
        assert cache.get("text3") == [0.3]
        assert cache.get("text4") == [0.4]

    def test_eviction_with_size_one(self):
        """Test eviction with cache size of 1."""
        cache = EmbeddingCache.create(max_size=1)

        cache.set("text1", [0.1])
        assert cache.get("text1") == [0.1]

        cache.set("text2", [0.2])
        assert cache.get("text1") is None
        assert cache.get("text2") == [0.2]


class TestGetEmbeddingCache:
    """Tests for get_embedding_cache global function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before and after test."""
        import web_mcp.llm.embedding_cache as cache_module

        cache_module._cache = None
        yield
        cache_module._cache = None

    def test_returns_embedding_cache(self, clean_state):
        """Test that get_embedding_cache returns an EmbeddingCache."""
        cache = get_embedding_cache()
        assert isinstance(cache, EmbeddingCache)

    def test_singleton_behavior(self, clean_state):
        """Test that get_embedding_cache returns same instance."""
        cache1 = get_embedding_cache()
        cache2 = get_embedding_cache()
        assert cache1 is cache2

    def test_default_size_from_env(self, clean_state):
        """Test default size when no env var is set."""
        cache = get_embedding_cache()
        assert cache._max_size == 1000

    def test_custom_size_from_env(self, clean_state):
        """Test custom size from environment variable."""
        os.environ["WEB_MCP_EMBEDDING_CACHE_SIZE"] = "500"
        try:
            import web_mcp.llm.embedding_cache as cache_module

            cache_module._cache = None
            cache = get_embedding_cache()
            assert cache._max_size == 500
        finally:
            del os.environ["WEB_MCP_EMBEDDING_CACHE_SIZE"]

    def test_creates_cache_on_first_call(self, clean_state):
        """Test that cache is created on first call."""
        import web_mcp.llm.embedding_cache as cache_module

        assert cache_module._cache is None
        cache = get_embedding_cache()
        assert cache_module._cache is cache


class TestClearEmbeddingCache:
    """Tests for clear_embedding_cache global function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before and after test."""
        import web_mcp.llm.embedding_cache as cache_module

        cache_module._cache = None
        yield
        cache_module._cache = None

    def test_clear_removes_entries(self, clean_state):
        """Test that clear removes all entries."""
        cache = get_embedding_cache()
        cache.set("test", [0.1])
        clear_embedding_cache()
        assert cache.get("test") is None

    def test_clear_when_no_cache(self, clean_state):
        """Test clear when no cache exists (should not raise)."""
        import web_mcp.llm.embedding_cache as cache_module

        cache_module._cache = None
        clear_embedding_cache()

    def test_clear_preserves_cache_instance(self, clean_state):
        """Test that clear preserves the cache instance."""
        cache = get_embedding_cache()
        cache.set("test", [0.1])
        clear_embedding_cache()
        assert get_embedding_cache() is cache


class TestSetEmbeddingCacheSize:
    """Tests for set_embedding_cache_size global function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before and after test."""
        import web_mcp.llm.embedding_cache as cache_module

        cache_module._cache = None
        yield
        cache_module._cache = None

    def test_creates_new_cache_with_size(self, clean_state):
        """Test that set_embedding_cache_size creates new cache when one exists."""
        get_embedding_cache()
        set_embedding_cache_size(200)
        cache = get_embedding_cache()
        assert cache._max_size == 200

    def test_resizes_existing_cache(self, clean_state):
        """Test resizing an existing cache."""
        cache = get_embedding_cache()
        cache.set("test", [0.1])

        set_embedding_cache_size(500)

        new_cache = get_embedding_cache()
        assert new_cache._max_size == 500

    def test_creates_new_cache_instance(self, clean_state):
        """Test that resize creates a new cache instance."""
        old_cache = get_embedding_cache()
        set_embedding_cache_size(100)
        new_cache = get_embedding_cache()
        assert new_cache is not old_cache

    def test_resize_when_no_cache(self, clean_state):
        """Test resize when no cache exists yet - should do nothing."""
        import web_mcp.llm.embedding_cache as cache_module

        cache_module._cache = None
        set_embedding_cache_size(300)
        assert cache_module._cache is None
        cache = get_embedding_cache()
        assert cache._max_size == 1000


class TestEmbeddingCacheEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_special_characters_in_content(self):
        """Test content with special characters."""
        cache = EmbeddingCache.create()
        special_text = "Hello\nWorld\t\r\nSpecial chars: !@#$%^&*()"
        embedding = [0.1, 0.2]
        cache.set(special_text, embedding)
        assert cache.get(special_text) == embedding

    def test_very_long_content(self):
        """Test with very long content."""
        cache = EmbeddingCache.create()
        long_text = "x" * 100000
        embedding = [0.5]
        cache.set(long_text, embedding)
        assert cache.get(long_text) == embedding

    def test_negative_embedding_values(self):
        """Test with negative embedding values."""
        cache = EmbeddingCache.create()
        embedding = [-0.5, -0.3, 0.0, 0.2, 0.8]
        cache.set("test", embedding)
        assert cache.get("test") == embedding

    def test_floating_point_embedding_values(self):
        """Test with various floating point values."""
        cache = EmbeddingCache.create()
        embedding = [0.000001, 0.999999, -0.5, 1e-10, 1e10]
        cache.set("test", embedding)
        assert cache.get("test") == embedding

    def test_multiple_operations_sequence(self):
        """Test a sequence of operations."""
        cache = EmbeddingCache.create(max_size=5)

        for i in range(10):
            cache.set(f"text{i}", [float(i)])

        assert len(cache.cache) == 5
        assert cache.get("text0") is None
        assert cache.get("text9") == [9.0]

    def test_same_text_different_embedding(self):
        """Test that setting same text with different embedding updates."""
        cache = EmbeddingCache.create()
        cache.set("test", [0.1, 0.2])
        cache.set("test", [0.3, 0.4, 0.5])
        assert cache.get("test") == [0.3, 0.4, 0.5]

    def test_content_with_newlines(self):
        """Test content containing newlines."""
        cache = EmbeddingCache.create()
        text = "line1\nline2\nline3"
        embedding = [0.1, 0.2]
        cache.set(text, embedding)
        assert cache.get(text) == embedding

    def test_content_with_tabs(self):
        """Test content containing tabs."""
        cache = EmbeddingCache.create()
        text = "col1\tcol2\tcol3"
        embedding = [0.1, 0.2]
        cache.set(text, embedding)
        assert cache.get(text) == embedding
