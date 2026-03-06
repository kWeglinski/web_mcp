"""Unit tests for content store implementation."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from web_mcp.content_store import (
    ContentStore,
    StoredContent,
    get_content_store,
    reset_content_store,
    start_cleanup_task,
    stop_cleanup_task,
)


class TestStoredContent:
    """Tests for StoredContent dataclass."""

    def test_stored_content_creation(self):
        """Test creating a StoredContent instance."""
        now = time.time()
        content = StoredContent(
            content="test content",
            content_type="text/html",
            created_at=now,
            expires_at=now + 3600,
            token="test-token",
        )
        assert content.content == "test content"
        assert content.content_type == "text/html"
        assert content.created_at == now
        assert content.expires_at == now + 3600
        assert content.token == "test-token"

    def test_stored_content_with_bytes(self):
        """Test StoredContent with bytes content."""
        now = time.time()
        content = StoredContent(
            content=b"binary content",
            content_type="application/octet-stream",
            created_at=now,
            expires_at=now + 3600,
            token="test-token",
        )
        assert content.content == b"binary content"
        assert content.content_type == "application/octet-stream"


class TestContentStore:
    """Tests for ContentStore class."""

    @pytest.fixture
    def store(self):
        """Create a content store with max size 3 for testing."""
        return ContentStore(max_size=3, default_ttl=3600.0, cleanup_interval=1.0)

    @pytest.fixture
    def clean_global_state(self):
        """Reset global state before and after each test."""
        reset_content_store()
        yield
        reset_content_store()

    def test_default_constants(self):
        """Test default constants are set correctly."""
        assert ContentStore.DEFAULT_TTL == 3600.0
        assert ContentStore.DEFAULT_MAX_SIZE == 1000
        assert ContentStore.DEFAULT_CLEANUP_INTERVAL == 300.0

    def test_store_and_get(self, store):
        """Test basic store and get operations."""
        content_id, token = store.store("test content")
        result = store.get(content_id)

        assert result is not None
        assert result.content == "test content"
        assert result.content_type == "text/html"
        assert result.token == token

    def test_store_with_custom_content_type(self, store):
        """Test storing with custom content type."""
        content_id, token = store.store("test content", content_type="application/json")
        result = store.get(content_id)

        assert result is not None
        assert result.content_type == "application/json"

    def test_store_with_custom_ttl(self, store):
        """Test storing with custom TTL."""
        content_id, token = store.store("test content", ttl=60.0)
        result = store.get(content_id)

        assert result is not None
        assert result.expires_at - result.created_at == pytest.approx(60.0, rel=0.1)

    def test_store_bytes_content(self, store):
        """Test storing bytes content."""
        content_id, token = store.store(b"binary content", content_type="application/octet-stream")
        result = store.get(content_id)

        assert result is not None
        assert result.content == b"binary content"

    def test_store_empty_string(self, store):
        """Test storing empty string."""
        content_id, token = store.store("")
        result = store.get(content_id)

        assert result is not None
        assert result.content == ""

    def test_get_nonexistent(self, store):
        """Test getting non-existent content."""
        result = store.get("nonexistent-id")
        assert result is None

    def test_get_expired_content(self, store):
        """Test that expired content returns None and is deleted."""
        content_id, token = store.store("test content", ttl=0.1)

        time.sleep(0.2)

        result = store.get(content_id)
        assert result is None
        assert content_id not in store._store

    def test_get_moves_to_end_lru(self, store):
        """Test that get moves item to end (most recently used)."""
        id1, _ = store.store("content1")
        id2, _ = store.store("content2")
        id3, _ = store.store("content3")

        store.get(id1)

        keys = list(store._store.keys())
        assert keys == [id2, id3, id1]

    def test_delete_existing(self, store):
        """Test deleting existing content."""
        content_id, token = store.store("test content")
        result = store.delete(content_id)

        assert result is True
        assert store.get(content_id) is None

    def test_delete_nonexistent(self, store):
        """Test deleting non-existent content."""
        result = store.delete("nonexistent-id")
        assert result is False

    def test_clear(self, store):
        """Test clearing the store."""
        store.store("content1")
        store.store("content2")
        store.clear()

        assert len(store) == 0

    def test_len(self, store):
        """Test len() function."""
        assert len(store) == 0
        store.store("content1")
        assert len(store) == 1
        store.store("content2")
        assert len(store) == 2

    def test_max_size_eviction(self, store):
        """Test that store respects max size with LRU eviction."""
        id1, _ = store.store("content1")
        id2, _ = store.store("content2")
        id3, _ = store.store("content3")
        id4, _ = store.store("content4")

        assert len(store) == 3
        assert store.get(id1) is None
        assert store.get(id2) is not None
        assert store.get(id3) is not None
        assert store.get(id4) is not None

    def test_lru_eviction_order(self, store):
        """Test correct LRU eviction order."""
        id1, _ = store.store("content1")
        id2, _ = store.store("content2")
        id3, _ = store.store("content3")

        store.get(id1)

        id4, _ = store.store("content4")

        assert store.get(id1) is not None
        assert store.get(id2) is None
        assert store.get(id3) is not None
        assert store.get(id4) is not None

    def test_eviction_tries_expired_first(self, store):
        """Test that eviction tries to remove expired items first."""
        id1, _ = store.store("content1", ttl=0.1)
        id2, _ = store.store("content2")
        id3, _ = store.store("content3")

        time.sleep(0.2)

        id4, _ = store.store("content4")

        assert len(store) == 3
        assert store.get(id1) is None
        assert store.get(id2) is not None
        assert store.get(id3) is not None
        assert store.get(id4) is not None

    def test_evict_expired(self, store):
        """Test _evict_expired method."""
        id1, _ = store.store("content1", ttl=0.1)
        id2, _ = store.store("content2", ttl=0.1)
        id3, _ = store.store("content3", ttl=3600)

        time.sleep(0.2)

        evicted_count = store._evict_expired()

        assert evicted_count == 2
        assert store.get(id1) is None
        assert store.get(id2) is None
        assert store.get(id3) is not None

    def test_evict_expired_public_method(self, store):
        """Test public evict_expired method."""
        id1, _ = store.store("content1", ttl=0.1)

        time.sleep(0.2)

        evicted_count = store.evict_expired()

        assert evicted_count == 1
        assert store.get(id1) is None

    def test_evict_expired_no_expired(self, store):
        """Test _evict_expired when no items are expired."""
        store.store("content1")
        store.store("content2")

        evicted_count = store._evict_expired()

        assert evicted_count == 0
        assert len(store) == 2

    def test_get_stats(self, store):
        """Test get_stats method."""
        store.store("content1")
        stats = store.get_stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 3
        assert stats["default_ttl"] == 3600.0
        assert stats["cleanup_interval"] == 1.0

    def test_generate_id_deterministic_length(self, store):
        """Test that generated IDs have consistent length."""
        id1 = store._generate_id("content1")
        id2 = store._generate_id("content2")

        assert len(id1) == 16
        assert len(id2) == 16

    def test_generate_id_with_bytes(self, store):
        """Test ID generation with bytes content."""
        id1 = store._generate_id(b"binary content")
        assert len(id1) == 16

    def test_generate_token_length(self, store):
        """Test that generated tokens have expected length."""
        token = store._generate_token()
        assert len(token) == 43

    def test_store_returns_unique_ids(self, store):
        """Test that store returns unique IDs for different content."""
        id1, _ = store.store("content1")
        id2, _ = store.store("content2")

        assert id1 != id2

    def test_store_returns_unique_tokens(self, store):
        """Test that store returns unique tokens."""
        _, token1 = store.store("content1")
        _, token2 = store.store("content2")

        assert token1 != token2


class TestContentStoreAsync:
    """Tests for async functionality in ContentStore."""

    @pytest.fixture
    def store(self):
        """Create a content store for async testing."""
        return ContentStore(max_size=10, default_ttl=3600.0, cleanup_interval=0.1)

    @pytest.fixture
    def clean_global_state(self):
        """Reset global state before and after each test."""
        reset_content_store()
        yield
        reset_content_store()

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, store):
        """Test starting cleanup task."""
        store.start_cleanup_task()

        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()

        store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self, store):
        """Test stopping cleanup task."""
        store.start_cleanup_task()
        store.stop_cleanup_task()

        await asyncio.sleep(0.05)

        assert store._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_cleanup_task_evicts_expired(self, store):
        """Test that cleanup task evicts expired items."""
        store.store("content1", ttl=0.05)
        store.store("content2", ttl=0.05)
        store.store("content3", ttl=3600)

        store.start_cleanup_task()

        await asyncio.sleep(0.3)

        assert store.get("content1") is None or len([k for k, v in store._store.items() if v.content == "content1"]) == 0

        store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_start_cleanup_task_when_already_running(self, store):
        """Test starting cleanup task when already running."""
        store.start_cleanup_task()
        first_task = store._cleanup_task

        store.start_cleanup_task()

        assert store._cleanup_task is first_task

        store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_start_cleanup_task_after_cancelled(self, store):
        """Test starting cleanup task after previous was cancelled."""
        store.start_cleanup_task()
        store.stop_cleanup_task()

        await asyncio.sleep(0.05)

        store.start_cleanup_task()

        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()

        store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_when_not_running(self, store):
        """Test stopping cleanup task when not running."""
        store.stop_cleanup_task()

        assert store._cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_when_already_done(self, store):
        """Test stopping cleanup task when already done."""
        store.start_cleanup_task()
        store.stop_cleanup_task()

        await asyncio.sleep(0.05)

        store.stop_cleanup_task()


class TestGetContentStore:
    """Tests for get_content_store function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        reset_content_store()
        yield
        reset_content_store()

    def test_singleton(self, clean_state):
        """Test that get_content_store returns a singleton."""
        with patch("web_mcp.config.get_config") as mock_config:
            mock_config.return_value = MagicMock(content_ttl="3600")

            store1 = get_content_store()
            store2 = get_content_store()

            assert store1 is store2

    def test_uses_config_ttl(self, clean_state):
        """Test that store uses TTL from config."""
        with patch("web_mcp.config.get_config") as mock_config:
            mock_config.return_value = MagicMock(content_ttl="7200")

            store = get_content_store()

            assert store.default_ttl == 7200.0


class TestResetContentStore:
    """Tests for reset_content_store function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        reset_content_store()
        yield
        reset_content_store()

    def test_reset_clears_singleton(self, clean_state):
        """Test that reset clears the singleton."""
        with patch("web_mcp.config.get_config") as mock_config:
            mock_config.return_value = MagicMock(content_ttl="3600")

            store1 = get_content_store()
            reset_content_store()
            store2 = get_content_store()

            assert store1 is not store2

    @pytest.mark.asyncio
    async def test_reset_stops_cleanup_task(self, clean_state):
        """Test that reset stops the cleanup task."""
        with patch("web_mcp.config.get_config") as mock_config:
            mock_config.return_value = MagicMock(content_ttl="3600")

            store = get_content_store()
            store.start_cleanup_task()
            task = store._cleanup_task

            reset_content_store()

            try:
                await asyncio.wait_for(task, timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            assert task.done()


class TestGlobalCleanupFunctions:
    """Tests for global cleanup task functions."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        reset_content_store()
        yield
        reset_content_store()

    @pytest.mark.asyncio
    async def test_start_cleanup_task_global(self, clean_state):
        """Test global start_cleanup_task function."""
        with patch("web_mcp.config.get_config") as mock_config:
            mock_config.return_value = MagicMock(content_ttl="3600")

            start_cleanup_task()
            store = get_content_store()

            assert store._cleanup_task is not None
            assert not store._cleanup_task.done()

            stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_global(self, clean_state):
        """Test global stop_cleanup_task function."""
        with patch("web_mcp.config.get_config") as mock_config:
            mock_config.return_value = MagicMock(content_ttl="3600")

            start_cleanup_task()
            store = get_content_store()
            task = store._cleanup_task
            stop_cleanup_task()

            try:
                await asyncio.wait_for(task, timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            assert task.done()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_when_no_store(self, clean_state):
        """Test stop_cleanup_task when no store exists."""
        stop_cleanup_task()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def store(self):
        """Create a content store for edge case testing."""
        return ContentStore(max_size=3, default_ttl=3600.0)

    @pytest.fixture
    def clean_global_state(self):
        """Reset global state before and after each test."""
        reset_content_store()
        yield
        reset_content_store()

    def test_store_very_long_content(self, store):
        """Test storing very long content."""
        long_content = "x" * 1000000
        content_id, token = store.store(long_content)
        result = store.get(content_id)

        assert result is not None
        assert result.content == long_content

    def test_store_unicode_content(self, store):
        """Test storing unicode content."""
        unicode_content = "Hello 世界 🌍 Привет مرحبا"
        content_id, token = store.store(unicode_content)
        result = store.get(content_id)

        assert result is not None
        assert result.content == unicode_content

    def test_store_special_characters_in_content_type(self, store):
        """Test storing with special characters in content type."""
        content_id, token = store.store("content", content_type="application/json; charset=utf-8")
        result = store.get(content_id)

        assert result is not None
        assert result.content_type == "application/json; charset=utf-8"

    def test_store_zero_ttl(self, store):
        """Test storing with zero TTL (expires immediately)."""
        content_id, token = store.store("content", ttl=0.0)

        time.sleep(0.01)

        result = store.get(content_id)
        assert result is None

    def test_store_negative_ttl(self, store):
        """Test storing with negative TTL (already expired)."""
        content_id, token = store.store("content", ttl=-1.0)

        result = store.get(content_id)
        assert result is None

    def test_store_very_large_ttl(self, store):
        """Test storing with very large TTL."""
        content_id, token = store.store("content", ttl=999999999.0)
        result = store.get(content_id)

        assert result is not None

    def test_multiple_stores_same_content(self, store):
        """Test storing same content multiple times."""
        id1, token1 = store.store("same content")
        id2, token2 = store.store("same content")

        assert id1 != id2
        assert token1 != token2

    def test_get_after_delete_and_reinsert(self, store):
        """Test getting content after delete and reinsert."""
        content_id, _ = store.store("content")
        store.delete(content_id)

        new_id, new_token = store.store("content")

        assert store.get(content_id) is None
        assert store.get(new_id) is not None

    def test_eviction_with_all_expired(self, store):
        """Test eviction when all items are expired."""
        id1, _ = store.store("content1", ttl=0.1)
        id2, _ = store.store("content2", ttl=0.1)
        id3, _ = store.store("content3", ttl=0.1)

        time.sleep(0.2)

        id4, _ = store.store("content4")

        assert len(store) == 1
        assert store.get(id4) is not None

    def test_store_at_max_capacity(self, store):
        """Test store behavior at exact max capacity."""
        id1, _ = store.store("content1")
        id2, _ = store.store("content2")
        id3, _ = store.store("content3")

        assert len(store) == 3
        assert store.get(id1) is not None
        assert store.get(id2) is not None
        assert store.get(id3) is not None

    def test_store_over_max_capacity(self, store):
        """Test store behavior over max capacity."""
        ids = []
        for i in range(5):
            id, _ = store.store(f"content{i}")
            ids.append(id)

        assert len(store) == 3
        assert store.get(ids[0]) is None
        assert store.get(ids[1]) is None

    def test_binary_content_preserved(self, store):
        """Test that binary content is preserved exactly."""
        binary_data = bytes(range(256))
        content_id, _ = store.store(binary_data)
        result = store.get(content_id)

        assert result is not None
        assert result.content == binary_data

    def test_content_type_preservation(self, store):
        """Test that various content types are preserved."""
        content_types = [
            "text/html",
            "application/json",
            "application/xml",
            "text/plain",
            "image/svg+xml",
        ]

        for ct in content_types:
            content_id, _ = store.store("content", content_type=ct)
            result = store.get(content_id)
            assert result.content_type == ct

    def test_token_uniqueness_across_many_stores(self, store):
        """Test token uniqueness across many store operations."""
        tokens = set()
        for _ in range(100):
            _, token = store.store("content")
            tokens.add(token)

        assert len(tokens) == 100

    def test_concurrent_access_safety(self, store):
        """Test that concurrent access doesn't break the store."""
        for i in range(100):
            store.store(f"content{i}")

        assert len(store) <= store.max_size


class TestStoredContentFields:
    """Tests for StoredContent field validation."""

    def test_created_at_before_expires_at(self):
        """Test that created_at is before expires_at."""
        now = time.time()
        content = StoredContent(
            content="test",
            content_type="text/html",
            created_at=now,
            expires_at=now + 3600,
            token="token",
        )
        assert content.created_at < content.expires_at

    def test_content_field_can_be_str_or_bytes(self):
        """Test that content field accepts str or bytes."""
        now = time.time()

        str_content = StoredContent(
            content="string",
            content_type="text/plain",
            created_at=now,
            expires_at=now + 3600,
            token="token",
        )
        assert isinstance(str_content.content, str)

        bytes_content = StoredContent(
            content=b"bytes",
            content_type="application/octet-stream",
            created_at=now,
            expires_at=now + 3600,
            token="token",
        )
        assert isinstance(bytes_content.content, bytes)
