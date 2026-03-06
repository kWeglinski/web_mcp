"""Embedding cache with LRU eviction for efficient similarity search."""

import hashlib
from dataclasses import dataclass

from web_mcp.cache import LRUCache


@dataclass
class EmbeddingCache:
    """A cache for embeddings with LRU eviction.

    Uses content hashing to avoid re-embedding identical or similar content.
    """

    cache: LRUCache[str, list[float]]
    _max_size: int = 1000

    @staticmethod
    def create(max_size: int = 1000) -> "EmbeddingCache":
        """Create a new embedding cache with specified size."""
        return EmbeddingCache(
            cache=LRUCache(max_size),
            _max_size=max_size,
        )

    def _hash_content(self, text: str) -> str:
        """Generate a hash key for content.

        Args:
            text: The text to hash

        Returns:
            Short hex hash string
        """
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def get(self, text: str) -> list[float] | None:
        """Get cached embedding for text.

        Args:
            text: The text to look up

        Returns:
            Embedding if cached, None otherwise
        """
        key = self._hash_content(text)
        return self.cache.get(key)

    def set(self, text: str, embedding: list[float]) -> None:
        """Cache an embedding.

        Args:
            text: The original text
            embedding: The embedding vector to cache
        """
        key = self._hash_content(text)
        self.cache.set(key, embedding)

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self.cache.clear()

    def stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "max_size": self._max_size,
            "current_size": len(self.cache),
        }


# Global cache instance
_cache: EmbeddingCache | None = None


def get_embedding_cache() -> EmbeddingCache:
    """Get the global embedding cache instance.

    Creates a new cache if one doesn't exist.

    Returns:
        The embedding cache instance
    """
    global _cache
    if _cache is None:
        # Get max size from environment or use default
        import os

        max_size = int(os.environ.get("WEB_MCP_EMBEDDING_CACHE_SIZE", "1000"))
        _cache = EmbeddingCache.create(max_size)
    return _cache


def clear_embedding_cache() -> None:
    """Clear the global embedding cache."""
    global _cache
    if _cache is not None:
        _cache.clear()


def set_embedding_cache_size(size: int) -> None:
    """Set the embedding cache size.

    Args:
        size: Maximum number of embeddings to cache
    """
    global _cache
    if _cache is not None:
        # Create new cache with updated size and copy existing entries
        new_cache = EmbeddingCache.create(size)
        # Note: This is a simplified approach; in production you might want
        # to preserve existing cache entries during resize
        _cache = new_cache
