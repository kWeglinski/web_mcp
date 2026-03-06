"""Research module for web-grounded Q&A."""

from web_mcp.research.chunker import Chunk, chunk_text, merge_small_chunks
from web_mcp.research.citations import (
    Source,
    build_context_with_citations,
    format_sources,
    validate_citations,
)
from web_mcp.research.pipeline import ResearchResult, research, research_stream

__all__ = [
    "chunk_text",
    "merge_small_chunks",
    "Chunk",
    "Source",
    "format_sources",
    "build_context_with_citations",
    "validate_citations",
    "research",
    "research_stream",
    "ResearchResult",
]
