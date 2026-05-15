"""Knowledge gatherer pipeline — orchestrates search, fetch, extract, dedup, store."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from web_mcp.config import get_config
from web_mcp.knowledge.categories import Category, get_relevant_categories
from web_mcp.knowledge.dedup import DedupCache, semantic_dedup
from web_mcp.knowledge.extractor import Fact, FactExtractionResult, extract_facts
from web_mcp.knowledge.validation import validate_fact_quality, validate_topic_width

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeResult:
    """Result of a knowledge gathering session."""

    topic: str
    facts: list[Fact] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    total_searched: int = 0
    total_fetched: int = 0
    total_extracted: int = 0
    dedup_removed: int = 0
    semantic_dedup_removed: int = 0
    stored_count: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    validation: dict | None = None

    def summary(self) -> str:
        """Human-readable summary of the result."""
        lines = [
            f"Knowledge gathered for: {self.topic}",
            f"  Facts: {len(self.facts)} (searched: {self.total_searched}, fetched: {self.total_fetched}, extracted: {self.total_extracted})",
            f"  Dedup: {self.dedup_removed} exact + {self.semantic_dedup_removed} semantic removed",
            f"  Stored: {self.stored_count} to mem0",
            f"  Categories: {[c.name for c in self.categories]}",
            f"  Duration: {self.duration_seconds:.1f}s",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
        return "\n".join(lines)


class KnowledgeGatherer:
    """Orchestrates the full knowledge gathering pipeline."""

    def __init__(
        self,
        llm_client=None,
        mem0_memory=None,
        max_search_results: int = 5,
        max_facts_per_source: int = 20,
        min_confidence: float = 0.7,
        semantic_threshold: float = 0.85,
    ):
        """Initialize the knowledge gatherer.

        Args:
            llm_client: LLMClient instance (creates one if not provided)
            mem0_memory: mem0.Memory instance (for storing results)
            max_search_results: Max URLs to search for
            max_facts_per_source: Max facts to extract per source
            min_confidence: Minimum confidence for facts
            semantic_threshold: Semantic dedup threshold
        """
        self.llm_client = llm_client
        self.mem0_memory = mem0_memory
        self.max_search_results = max_search_results
        self.max_facts_per_source = max_facts_per_source
        self.min_confidence = min_confidence
        self.semantic_threshold = semantic_threshold
        self._dedup_cache = DedupCache()
        self._dedup_cache.semantic_threshold = semantic_threshold

    async def gather(
        self,
        topic: str,
        max_search_results: int | None = None,
        categories: list[str] | None = None,
    ) -> KnowledgeResult:
        """Run the full knowledge gathering pipeline.

        Pipeline: validate topic -> search -> fetch -> extract facts -> dedup -> store

        Args:
            topic: The topic to gather knowledge about
            max_search_results: Override max search results
            categories: Filter to specific categories

        Returns:
            KnowledgeResult with all gathered facts
        """
        start_time = time.time()
        max_results = max_search_results or self.max_search_results

        # Phase 1: Validate topic
        topic_validation = validate_topic_width(topic)
        if not topic_validation["valid"]:
            logger.warning(f"Topic validation issues: {topic_validation['issues']}")
            # Continue but note the issues

        # Phase 2: Search
        logger.info(f"Knowledge gathering: searching for '{topic}'")
        search_urls = await self._search(topic, max_results)
        if not search_urls:
            return KnowledgeResult(
                topic=topic,
                errors=["No search results found"],
                duration_seconds=time.time() - start_time,
            )

        # Phase 3: Fetch content
        logger.info(f"Knowledge gathering: fetching {len(search_urls)} URLs")
        fetched_contents = await self._fetch_contents(search_urls)
        if not fetched_contents:
            return KnowledgeResult(
                topic=topic,
                errors=["Failed to fetch any URLs"],
                duration_seconds=time.time() - start_time,
            )

        # Phase 4: Extract facts
        logger.info(f"Knowledge gathering: extracting facts from {len(fetched_contents)} sources")
        all_results = await self._extract_facts_from_contents(fetched_contents)

        # Phase 5: Collect all facts
        all_facts = []
        for result in all_results:
            all_facts.extend(result.facts)

        exact_before = len(all_facts)

        # Phase 6: Dedup (exact already handled in add_fact, semantic next)
        # Phase 7: Semantic dedup
        semantic_facts = await semantic_dedup(
            all_facts,
            existing_cache=self._dedup_cache,
            semantic_threshold=self.semantic_threshold,
            llm_client=self.llm_client,
        )

        semantic_removed = len(all_facts) - len(semantic_facts)

        # Phase 8: Classify categories
        classified_categories = get_relevant_categories(
            url=topic,  # Use topic as proxy for URL
            text=" ".join(f.text for f in semantic_facts),
        )
        if classified_categories:
            classified_categories = classified_categories[:5]

        # Phase 9: Store to mem0
        stored_count = 0
        if self.mem0_memory and semantic_facts:
            stored_count = await self._store_facts(semantic_facts)

        # Validation
        quality = validate_fact_quality(semantic_facts)

        duration = time.time() - start_time

        return KnowledgeResult(
            topic=topic,
            facts=semantic_facts,
            sources=[fc["source"] for fc in fetched_contents],
            categories=classified_categories,
            total_searched=len(search_urls),
            total_fetched=len(fetched_contents),
            total_extracted=exact_before,
            dedup_removed=exact_before - len(all_facts),  # From exact dedup in add_fact
            semantic_dedup_removed=semantic_removed,
            stored_count=stored_count,
            errors=[r.extraction_error for r in all_results if r.extraction_error],
            duration_seconds=duration,
            validation=quality,
        )

    async def _search(self, topic: str, max_results: int) -> list[str]:
        """Search for URLs related to the topic."""
        from web_mcp.searxng import search as searxng_search

        try:
            raw_results = await searxng_search(topic, max_results)
            return [r["url"] for r in raw_results if r.get("url")]
        except Exception as e:
            logger.error(f"Search failed for '{topic}': {e}")
            return []

    async def _fetch_contents(self, urls: list[str]) -> list[dict]:
        """Fetch content from URLs."""
        from web_mcp.tools.fetching import get_page

        fetched = []
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent fetches

        async def fetch_one(url: str) -> dict | None:
            async with semaphore:
                try:
                    content = await get_page(url)
                    if content and len(content.strip()) > 100:
                        return {"url": url, "content": content, "source": {"url": url}}
                    return None
                except Exception as e:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    return None

        tasks = [fetch_one(url) for url in urls]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r:
                fetched.append(r)

        return fetched

    async def _extract_facts_from_contents(
        self,
        fetched_contents: list[dict],
    ) -> list[FactExtractionResult]:
        """Extract facts from fetched content."""
        from web_mcp.research.chunker import chunk_text

        if self.llm_client is None:
            from web_mcp.llm.client import LLMClient

            self.llm_client = LLMClient()

        config = get_config()

        async def extract_from_one(fc: dict) -> FactExtractionResult:
            chunks = chunk_text(
                fc["content"],
                source_url=fc["url"],
                source_title="",
                chunk_size=1000,
                overlap=200,
            )
            all_facts_for_source = []

            for i, chunk in enumerate(chunks):
                result = await extract_facts(
                    text=chunk.text,
                    source_url=fc["url"],
                    source_title="",  # Would get from render_html in production
                    chunk_index=i,
                    max_facts=self.max_facts_per_source,
                    min_confidence=self.min_confidence,
                    llm_client=self.llm_client,
                    model=config.knowledge_extract_model,
                )
                all_facts_for_source.append(result)

            # Merge results
            merged = FactExtractionResult(
                source_url=fc["url"],
                source_title="",
                facts=[f for r in all_facts_for_source for f in r.facts],
                chunks_processed=sum(r.chunks_processed for r in all_facts_for_source),
                total_chunks=len(chunks),
            )
            return merged

        tasks = [extract_from_one(fc) for fc in fetched_contents]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _store_facts(self, facts: list[Fact]) -> int:
        """Store facts as mem0 memories."""
        if self.mem0_memory is None:
            return 0

        stored = 0
        for fact in facts:
            try:
                # Build memory text with source citation
                memory_text = f"{fact.text} [Source: {fact.source_url}]"
                metadata = {
                    "source_url": fact.source_url,
                    "source_title": fact.source_title,
                    "confidence": fact.confidence,
                    "category": fact.category,
                    "type": "knowledge_fact",
                    "created_at": time.time(),
                }

                self.mem0_memory.add(
                    message=memory_text,
                    metadata=metadata,
                )
                stored += 1
            except Exception as e:
                logger.error(f"Failed to store fact: {e}")

        return stored


async def gather_knowledge(
    topic: str,
    max_search_results: int = 5,
    categories: list[str] | None = None,
) -> KnowledgeResult:
    """Convenience function to gather knowledge about a topic.

    Args:
        topic: The topic to gather knowledge about
        max_search_results: Max URLs to search for
        categories: Filter to specific categories

    Returns:
        KnowledgeResult with all gathered facts
    """
    from web_mcp.mem0 import mem0_manager

    config = get_config()
    gatherer = KnowledgeGatherer(
        mem0_memory=mem0_manager.get_memory(),
        max_search_results=max_search_results,
        min_confidence=config.knowledge_min_confidence,
        semantic_threshold=config.knowledge_semantic_threshold,
    )

    return await gatherer.gather(
        topic, max_search_results=max_search_results, categories=categories
    )
