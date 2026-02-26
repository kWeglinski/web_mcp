"""LLM module for research tools."""

from web_mcp.llm.config import LLMConfig, ResearchConfig, get_llm_config, get_research_config
from web_mcp.llm.client import LLMClient, LLMError, get_llm_client
from web_mcp.llm.embeddings import EmbeddedChunk, embed_chunks, embed_query, find_most_relevant
from web_mcp.llm.embedding_cache import EmbeddingCache, get_embedding_cache

__all__ = [
    "LLMConfig",
    "ResearchConfig",
    "get_llm_config",
    "get_research_config",
    "LLMClient",
    "LLMError",
    "get_llm_client",
    "EmbeddedChunk",
    "embed_chunks",
    "embed_query",
    "find_most_relevant",
    "EmbeddingCache",
    "get_embedding_cache",
]
