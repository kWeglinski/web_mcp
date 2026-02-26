"""Research module for web-grounded Q&A."""

from web_mcp.research.chunker import chunk_text, merge_small_chunks, Chunk
from web_mcp.research.citations import Source, format_sources, build_context_with_citations, validate_citations
from web_mcp.research.pipeline import research, research_stream, ResearchResult

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
