"""LLM configuration for the research tools."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """Configuration for LLM operations."""
    
    api_url: str = field(
        default_factory=lambda: os.environ.get(
            "WEB_MCP_LLM_API_URL", "https://api.openai.com/v1"
        )
    )
    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("WEB_MCP_LLM_API_KEY")
    )
    model: str = field(
        default_factory=lambda: os.environ.get("WEB_MCP_LLM_MODEL", "gpt-4o")
    )
    embedding_model: str = field(
        default_factory=lambda: os.environ.get(
            "WEB_MCP_LLM_EMBED_MODEL", "text-embedding-3-small"
        )
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_LLM_MAX_TOKENS", "4096"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.environ.get("WEB_MCP_LLM_TEMPERATURE", "0.1"))
    )
    request_timeout: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_LLM_TIMEOUT", "60"))
    )

    @property
    def is_configured(self) -> bool:
        """Check if LLM is properly configured."""
        return self.api_key is not None and len(self.api_key) > 0


@dataclass
class ResearchConfig:
    """Configuration for the research pipeline."""
    
    max_sources: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_RESEARCH_MAX_SOURCES", "5"))
    )
    search_results: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_RESEARCH_SEARCH_RESULTS", "10"))
    )
    chunk_size: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_RESEARCH_CHUNK_SIZE", "1000"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_RESEARCH_CHUNK_OVERLAP", "200"))
    )
    top_chunks: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_RESEARCH_TOP_CHUNKS", "10"))
    )
    rerank_enabled: bool = field(
        default_factory=lambda: os.environ.get("WEB_MCP_RERANK_ENABLED", "true").lower() == "true"
    )
    embedding_cache_size: int = field(
        default_factory=lambda: int(os.environ.get("WEB_MCP_EMBEDDING_CACHE_SIZE", "1000"))
    )


_llm_config: Optional[LLMConfig] = None
_research_config: Optional[ResearchConfig] = None


def get_llm_config() -> LLMConfig:
    """Get the LLM configuration (singleton)."""
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig()
    return _llm_config


def get_research_config() -> ResearchConfig:
    """Get the research configuration (singleton)."""
    global _research_config
    if _research_config is None:
        _research_config = ResearchConfig()
    return _research_config
