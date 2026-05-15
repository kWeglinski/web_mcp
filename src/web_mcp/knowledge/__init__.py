"""Knowledge gatherer — search, fetch, extract, dedup, and store grounded facts."""

from __future__ import annotations

from .categories import CATEGORY_TAXONOMY, Category, classify_topic, get_relevant_categories
from .cleanup import KnowledgeCleanupTask, start_cleanup_task, stop_cleanup_task
from .dedup import DedupCache, semantic_dedup
from .extractor import Fact, FactExtractionResult, extract_facts
from .pipeline import KnowledgeGatherer, KnowledgeResult, gather_knowledge
from .validation import validate_fact_quality, validate_topic_width

__all__ = [
    "Fact",
    "FactExtractionResult",
    "extract_facts",
    "DedupCache",
    "semantic_dedup",
    "Category",
    "CATEGORY_TAXONOMY",
    "classify_topic",
    "get_relevant_categories",
    "validate_topic_width",
    "validate_fact_quality",
    "KnowledgeCleanupTask",
    "start_cleanup_task",
    "stop_cleanup_task",
    "KnowledgeResult",
    "KnowledgeGatherer",
    "gather_knowledge",
]
