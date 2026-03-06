"""LRU cache implementation for web content."""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from typing import Any, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache[K, V]:
    """Simple LRU cache implementation with TTL support.

    Uses OrderedDict for O(1) operations and maintains access order
    to implement LRU eviction policy.

    Each cached value is stored as a tuple of (value, expiration_time).
    """

    DEFAULT_TTL: float = 3600.0  # Default TTL of 1 hour in seconds

    def __init__(self, max_size: int = 100):
        """Initialize the LRU cache.

        Args:
            max_size: Maximum number of items in cache
        """
        self.max_size: int = max_size
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def is_expired(self, key: str) -> bool:
        """Check if a cache entry has expired.

        Args:
            key: The cache key

        Returns:
            True if the entry has expired or doesn't exist, False otherwise
        """
        if key not in self._cache:
            return True

        _, expiration_time = self._cache[key]
        return time.time() > expiration_time

    def get(self, key: str) -> Any | None:
        """Get an item from the cache.

        Args:
            key: The cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self._cache:
            return None

        # Check if entry has expired
        if self.is_expired(key):
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)

        value, _ = self._cache[key]
        return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Add an item to the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds. If None, uses default TTL (3600s)
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL

        expiration_time = time.time() + ttl

        if key in self._cache:
            # Update and move to end
            self._cache[key] = (value, expiration_time)
            self._cache.move_to_end(key)
        else:
            # Add new item
            if len(self._cache) >= self.max_size:
                # Remove oldest (first) item
                self._cache.popitem(last=False)

            self._cache[key] = (value, expiration_time)

    def delete(self, key: str) -> bool:
        """Remove an item from the cache.

        Args:
            key: The cache key

        Returns:
            True if item was removed, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all items from the cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of items in cache."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return key in self._cache

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
        }


# Global cache instance
_cache: LRUCache | None = None


def get_cache() -> LRUCache:
    """Get the global LRU cache instance.

    Returns:
        The global LRUCache instance
    """
    global _cache

    if _cache is None:
        max_size = int(os.environ.get("WEB_MCP_CACHE_SIZE", "100"))
        _cache = LRUCache(max_size=max_size)

    return _cache


def reset_cache() -> None:
    """Reset the global cache. For testing purposes."""
    global _cache
    _cache = None
