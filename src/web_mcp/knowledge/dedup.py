"""Deduplication for knowledge facts using exact and semantic matching."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field

from web_mcp.knowledge.extractor import Fact

logger = logging.getLogger(__name__)


@dataclass
class DedupCache:
    """Cache for deduplicating facts across sources."""

    # Exact match: fact text -> count of sources containing it
    exact_hashes: dict[str, int] = field(default_factory=dict)
    # Semantic match: embeddings stored separately
    _embeddings: dict[str, list[float]] = field(default_factory=dict)
    # Timestamp of last cleanup
    last_cleanup: float = field(default_factory=time.time)
    # Semantic threshold (configurable)
    semantic_threshold: float = 0.85

    def _fact_hash(self, fact: Fact) -> str:
        """Create a hash for exact dedup of a fact's text."""
        return hashlib.md5(fact.text.strip().lower().encode()).hexdigest()

    def _text_hash(self, text: str) -> str:
        """Create a hash for a raw text string."""
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    def is_duplicate_exact(self, fact: Fact) -> bool:
        """Check if a fact already exists via exact text matching."""
        h = self._fact_hash(fact)
        return h in self.exact_hashes

    def add_fact(self, fact: Fact) -> bool:
        """Add a fact to the dedup cache. Returns True if new (not duplicate)."""
        h = self._fact_hash(fact)
        if h in self.exact_hashes:
            self.exact_hashes[h] += 1
            return False  # duplicate
        self.exact_hashes[h] = 1
        return True  # new

    def add_semantic_embedding(self, fact: Fact, embedding: list[float]) -> bool:
        """Add a semantic embedding for a fact. Returns True if no semantic duplicate found."""
        from web_mcp.llm.embeddings import cosine_similarity

        for _existing_hash, existing_emb in self._embeddings.items():
            sim = cosine_similarity(embedding, existing_emb)
            if sim >= self.semantic_threshold:
                logger.debug(f"Semantic duplicate found: {sim:.3f} >= {self.semantic_threshold}")
                return False  # semantic duplicate
        self._embeddings[fact.text] = embedding
        return True  # not a semantic duplicate

    def is_semantic_duplicate(self, embedding: list[float]) -> bool:
        """Check if an embedding is semantically similar to any stored fact."""
        from web_mcp.llm.embeddings import cosine_similarity

        for emb in self._embeddings.values():
            sim = cosine_similarity(embedding, emb)
            if sim >= self.semantic_threshold:
                return True
        return False

    def cleanup_old_entries(self, max_age_seconds: int = 3600) -> int:
        """Remove entries older than max_age_seconds. Returns count removed."""
        # Note: exact_hashes don't have timestamps, so this only cleans semantic entries
        # In production, you'd add timestamps to track this
        now = time.time()
        # Placeholder - in practice you'd track insertion time per entry
        self.last_cleanup = now
        return 0

    def get_stats(self) -> dict:
        """Return dedup cache statistics."""
        return {
            "exact_matches": len(self.exact_hashes),
            "semantic_entries": len(self._embeddings),
            "last_cleanup": self.last_cleanup,
        }


async def semantic_dedup(
    facts: list[Fact],
    existing_cache: DedupCache | None = None,
    semantic_threshold: float = 0.85,
    llm_client=None,
) -> list[Fact]:
    """Deduplicate facts using semantic similarity.

    Args:
        facts: List of facts to deduplicate
        existing_cache: Pre-existing dedup cache (creates new one if None)
        semantic_threshold: Minimum similarity to consider duplicate
        llm_client: LLMClient for embedding

    Returns:
        Deduplicated list of facts
    """
    if existing_cache is None:
        cache = DedupCache()
    else:
        cache = existing_cache

    cache.semantic_threshold = semantic_threshold

    if llm_client is None:
        from web_mcp.llm.client import LLMClient

        llm_client = LLMClient()

    # Extract unique facts by exact match first
    seen_exact: set[str] = set()
    unique_facts = []
    for fact in facts:
        h = cache._fact_hash(fact)
        if h not in seen_exact:
            seen_exact.add(h)
            unique_facts.append(fact)

    # Now do semantic dedup on unique facts
    semantic_facts = []
    for fact in unique_facts:
        embedding = await llm_client.embed(fact.text)
        if not cache.is_semantic_duplicate(embedding):
            cache.add_semantic_embedding(fact, embedding)
            semantic_facts.append(fact)

    return semantic_facts
