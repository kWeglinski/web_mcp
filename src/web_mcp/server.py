"""Web Browsing MCP Server - Browse the web with context-aware content extraction."""

import os
import sys
import time
from typing import Optional

# Add src to path for absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from web_mcp.config import Config, get_config
from web_mcp.fetcher import FetchError, fetch_url_with_fallback, fetch_url as fetch_html_httpx
from web_mcp.playwright_fetcher import fetch_with_playwright_cached, PlaywrightFetchError
from web_mcp.extractors.trafilatura import TrafilaturaExtractor
from web_mcp.extractors.custom import CustomSelectorExtractor
from web_mcp.optimizer import optimize_content, estimate_tokens
from web_mcp.searxng import SearXNGError, search, get_searxng_url
from web_mcp.research.pipeline import research, research_stream, ResearchResult
from web_mcp.research.citations import Source
from web_mcp.llm.config import get_llm_config
from web_mcp.logging import setup_logging, get_logger

# Server configuration
SERVER_HOST = os.environ.get("WEB_MCP_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("WEB_MCP_SERVER_PORT", "8000"))
VERSION = "1.0.0"

# Setup logging
setup_logging()

logger = get_logger(__name__)

# Server start time for uptime calculation
SERVER_START_TIME: float = time.time()

# Global metrics
_request_count: int = 0
_cache_hits: int = 0


def increment_request_count() -> None:
    """Increment the request count."""
    global _request_count
    _request_count += 1


def increment_cache_hits() -> None:
    """Increment the cache hits counter."""
    global _cache_hits
    _cache_hits += 1


def get_health_metrics() -> dict:
    """Get health metrics for the /health endpoint.
    
    Returns:
        Dictionary with health metrics
    """
    global _request_count, _cache_hits
    uptime = time.time() - SERVER_START_TIME
    
    # Calculate cache hit rate
    total_requests = _request_count + _cache_hits
    cache_hit_rate = (_cache_hits / total_requests) if total_requests > 0 else 0.0
    
    return {
        "status": "healthy",
        "version": VERSION,
        "cache_hit_rate": round(cache_hit_rate, 4),
        "request_count": _request_count,
        "uptime_seconds": round(uptime, 2),
    }


# Create MCP server with SSE transport support
mcp = FastMCP(
    name="web-browsing",
    instructions="A web browsing MCP server that extracts content from URLs with context optimization. "
                 "Use `fetch_url` to browse websites and extract their main content, "
                 "`web_search` to search the web using SearXNG, "
                 "or `ask`/`ask_stream` to research questions with AI-powered answers and citations.",
    host=SERVER_HOST,
    port=SERVER_PORT,
)


@mcp.tool()
async def health() -> dict:
    """Get server health metrics.
    
    Returns:
        Dictionary with health metrics including cache hit rate, request count, and uptime
    """
    increment_request_count()
    logger.info("Health check requested")
    return get_health_metrics()


@mcp.tool()
async def current_datetime(
    timezone: str = Field(
        default="UTC",
        description="Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London')"
    ),
    format: str = Field(
        default="iso",
        description="Output format: 'iso' (ISO 8601), 'unix' (timestamp), or 'readable' (human-readable)"
    )
) -> str:
    """Get the current date and time.
    
    Returns the current date and time in the specified timezone and format.
    
    Args:
        timezone: Timezone name (default: UTC)
        format: Output format - 'iso', 'unix', or 'readable'
        
    Returns:
        Current date and time as a string
    """
    from datetime import datetime, timezone as tz
    from zoneinfo import ZoneInfo
    
    increment_request_count()
    
    try:
        if timezone.upper() == "UTC":
            now = datetime.now(tz.utc)
        else:
            tz_info = ZoneInfo(timezone)
            now = datetime.now(tz_info)
        
        if format == "unix":
            return str(int(now.timestamp()))
        elif format == "readable":
            return now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")
        else:
            return now.isoformat()
    except Exception as e:
        return f"Error: {e}"

# Default extractor
_default_extractor = TrafilaturaExtractor()
_custom_extractor = CustomSelectorExtractor()


class FetchResult(BaseModel):
    """Result of fetching and extracting web content."""
    url: str = Field(description="The URL that was fetched")
    title: Optional[str] = Field(description="Page title if available", default=None)
    author: Optional[str] = Field(description="Author name if available", default=None)
    date: Optional[str] = Field(description="Publication date if available", default=None)
    language: Optional[str] = Field(description="Detected language if available", default=None)
    text: str = Field(description="Extracted text content")
    estimated_tokens: int = Field(description="Estimated token count of the result")
    truncated: bool = Field(description="Whether content was truncated to fit context limit")


@mcp.tool()
async def fetch_url(
    url: str = Field(description="The URL to fetch"),
    max_tokens: int = Field(
        default=120000,
        description="Maximum number of tokens to return (default: 120000)"
    ),
    include_metadata: bool = Field(
        default=True,
        description="Whether to include metadata (title, author, date)"
    ),
    extractor: str = Field(
        default="trafilatura",
        description="Extractor to use: 'trafilatura', 'readability', or 'custom'"
    ),
    render: str = Field(
        default="auto",
        description="Render mode: 'auto' (httpx with playwright fallback), 'playwright' (force browser), or 'httpx' (static only)"
    )
) -> FetchResult:
    """Fetch and extract content from a URL with context optimization.
    
    This tool fetches a web page, extracts the main content using Trafilatura,
    and optimizes it to fit within the specified token limit.
    
    Args:
        url: The URL to fetch
        max_tokens: Maximum tokens in output (default: 120000)
        include_metadata: Include title, author, date in output
        extractor: Which extractor to use (trafilatura, readability, or custom)
        render: Render mode - 'auto' tries httpx first, falls back to playwright for JS-heavy pages
        
    Returns:
        Extracted content with metadata and optimization info
    """
    config = get_config()
    
    # Fetch the URL based on render mode
    try:
        if render == "playwright":
            html = await fetch_with_playwright_cached(url, config)
        elif render == "httpx":
            html = await fetch_html_httpx(url, config)
        else:  # auto
            html = await fetch_url_with_fallback(url, config)
    except (FetchError, PlaywrightFetchError) as e:
        return FetchResult(
            url=url,
            text=f"Error fetching URL: {e}",
            estimated_tokens=estimate_tokens(str(e)),
            truncated=False,
        )
    
    # Select extractor based on parameter
    if extractor == "readability":
        from web_mcp.extractors.readability import ReadabilityExtractor
        extractor_obj = ReadabilityExtractor()
    elif extractor == "custom":
        extractor_obj = _custom_extractor
    else:
        extractor_obj = _default_extractor
    
    # Extract content using Trafilatura
    try:
        extracted = await extractor_obj.extract(html, url)
    except Exception as e:
        return FetchResult(
            url=url,
            text=f"Error extracting content: {e}",
            estimated_tokens=estimate_tokens(str(e)),
            truncated=False,
        )
    
    # Build result text
    if include_metadata:
        parts = []
        if extracted.title:
            parts.append(f"Title: {extracted.title}")
        if extracted.author:
            parts.append(f"Author: {extracted.author}")
        if extracted.date:
            parts.append(f"Date: {extracted.date}")
        if extracted.language:
            parts.append(f"Language: {extracted.language}")
        parts.append("Content:")
        parts.append(extracted.text)
        text = "\n".join(parts)
    else:
        text = extracted.text
    
    # Optimize for context window
    result = optimize_content(text, max_tokens, config)
    
    return FetchResult(
        url=url,
        title=extracted.title if include_metadata else None,
        author=extracted.author if include_metadata else None,
        date=extracted.date if include_metadata else None,
        language=extracted.language if include_metadata else None,
        text=result["text"],
        estimated_tokens=result["optimization_info"]["original_tokens"],
        truncated=result["optimization_info"].get("truncated", False),
    )


@mcp.tool()
async def fetch_url_simple(
    url: str = Field(description="The URL to fetch"),
    max_tokens: int = Field(
        default=120000,
        description="Maximum number of tokens to return (default: 120000)"
    ),
    render: str = Field(
        default="auto",
        description="Render mode: 'auto' (httpx with playwright fallback), 'playwright' (force browser), or 'httpx' (static only)"
    )
) -> str:
    """Fetch and extract content from a URL (simplified version).
    
    Returns only the text content without metadata.
    
    Args:
        url: The URL to fetch
        max_tokens: Maximum tokens in output (default: 120000)
        render: Render mode - 'auto' tries httpx first, falls back to playwright for JS-heavy pages
        
    Returns:
        Extracted text content
    """
    config = get_config()
    
    try:
        if render == "playwright":
            html = await fetch_with_playwright_cached(url, config)
        elif render == "httpx":
            html = await fetch_html_httpx(url, config)
        else:
            html = await fetch_url_with_fallback(url, config)
    except (FetchError, PlaywrightFetchError) as e:
        return f"Error fetching URL: {e}"
    
    try:
        extracted = await _default_extractor.extract(html, url)
    except Exception as e:
        return f"Error extracting content: {e}"
    
    result = optimize_content(extracted.text, max_tokens, config)
    
    return result["text"]


@mcp.tool()
async def fetch_url_query(
    url: str = Field(description="The URL to fetch"),
    query: str = Field(description="What information to look for on the page"),
    max_chunks: int = Field(
        default=5,
        description="Maximum number of relevant chunks to return (default: 5)"
    ),
    render: str = Field(
        default="auto",
        description="Render mode: 'auto' (httpx with playwright fallback), 'playwright' (force browser), or 'httpx' (static only)"
    )
) -> str:
    """Fetch a URL and extract only content relevant to your query.
    
    Chunks the page content and returns only the chunks most relevant
    to your query using BM25 ranking. Use this when you need specific
    information from a page rather than the full content.
    
    Args:
        url: The URL to fetch
        query: What information you're looking for
        max_chunks: Maximum chunks to return (default: 5)
        render: Render mode - 'auto' tries httpx first, falls back to playwright
        
    Returns:
        Most relevant chunks from the page
    """
    from web_mcp.research.chunker import chunk_text
    from web_mcp.research.bm25 import BM25
    
    config = get_config()
    
    try:
        if render == "playwright":
            html = await fetch_with_playwright_cached(url, config)
        elif render == "httpx":
            html = await fetch_html_httpx(url, config)
        else:
            html = await fetch_url_with_fallback(url, config)
    except (FetchError, PlaywrightFetchError) as e:
        return f"Error fetching URL: {e}"
    
    try:
        extracted = await _default_extractor.extract(html, url)
    except Exception as e:
        return f"Error extracting content: {e}"
    
    if not extracted.text or not extracted.text.strip():
        return "No content extracted from page"
    
    chunks = chunk_text(
        extracted.text,
        url,
        extracted.title or url,
        chunk_size=500,
        overlap=50,
    )
    
    if not chunks:
        return extracted.text[:2000] if extracted.text else "No content"
    
    documents = [{"text": c.text, "chunk": c} for c in chunks]
    bm25 = BM25()
    bm25.fit(documents, text_field="text")
    ranked = bm25.rank(query)
    
    top_chunks = ranked[:max_chunks]
    
    if extracted.title:
        header = f"Title: {extracted.title}\n\n"
    else:
        header = ""
    
    parts = []
    for doc, score in top_chunks:
        chunk = doc["chunk"]
        parts.append(chunk.text)
    
    return header + "\n\n---\n\n".join(parts)


class SearchResult(BaseModel):
    """Result of a SearXNG search."""
    title: str = Field(description="Page title")
    url: str = Field(description="The URL of the result")
    snippet: str = Field(description="Snippet or content preview")
    published_date: Optional[str] = Field(
        description="Publication date if available", default=None
    )
    score: Optional[float] = Field(
        description="Relevance score if available", default=None
    )


@mcp.tool()
async def web_search(
    query: str = Field(description="The search query string"),
    max_results: int = Field(
        default=10,
        description="Maximum number of search results to return (default: 10)"
    ),
    rerank: bool = Field(
        default=True,
        description="Rerank results by relevance using BM25 (default: true)"
    )
) -> list[SearchResult]:
    """Search the web using SearXNG.
    
    This tool performs a search query against a configured SearXNG instance
    and returns search results with titles, URLs, and snippets.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)
        rerank: Rerank results by relevance using BM25 (default: true)
        
    Returns:
        List of search results with title, url, snippet, and optional content
        
    Raises:
        SearXNGError: If the search fails or SearXNG is not configured
    """
    try:
        fetch_count = max_results * 3 if rerank else max_results
        fetch_count = min(fetch_count, 50)
        
        results = await search(query, fetch_count)
        
        if rerank and results:
            from web_mcp.research.bm25 import rerank_search_results
            results = rerank_search_results(results, query)
            results = results[:max_results]
        
        return results
        
    except Exception as e:
        return [
            SearchResult(
                title="Error",
                url="",
                snippet=f"Search failed: {e}",
            )
        ]


@mcp.tool()
async def web_search_simple(
    query: str = Field(description="The search query string")
) -> list[SearchResult]:
    """Search the web using SearXNG and return top 3 results.
    
    Fetches 30 results, reranks by relevance using BM25, and returns the top 3.
    Use this for quick searches when you just need the most relevant results.
    
    Args:
        query: The search query string
        
    Returns:
        Top 3 search results sorted by relevance
    """
    try:
        results = await search(query, 30)
        
        if results:
            from web_mcp.research.bm25 import rerank_search_results
            results = rerank_search_results(results, query)
            results = results[:3]
        
        return results
        
    except Exception as e:
        return [
            SearchResult(
                title="Error",
                url="",
                snippet=f"Search failed: {e}",
            )
        ]


class AskResult(BaseModel):
    """Result of an ask query with web-grounded research."""
    answer: str = Field(description="The answer to the question with citation markers [1], [2], etc.")
    sources: list[Source] = Field(description="List of sources cited in the answer")
    elapsed_ms: int = Field(description="Time taken to generate the answer in milliseconds")


@mcp.tool()
async def ask(
    question: str = Field(description="The question to research and answer"),
    max_sources: int = Field(
        default=5,
        description="Maximum number of sources to use for the answer (default: 5)"
    ),
    search_results: int = Field(
        default=10,
        description="Number of search results to fetch (default: 10)"
    )
) -> AskResult:
    """Research a question using web search and AI to provide a grounded answer with citations.
    
    This tool performs a comprehensive research process:
    1. Searches the web for relevant results
    2. Fetches and extracts content from top sources
    3. Uses embeddings to find the most relevant passages
    4. Generates an answer with inline citations [1], [2], etc.
    
    Requires LLM configuration via environment variables:
    - WEB_MCP_LLM_API_KEY: API key for the LLM service
    - WEB_MCP_LLM_API_URL: API endpoint (default: OpenAI)
    - WEB_MCP_LLM_MODEL: Model for generation (default: gpt-4o)
    - WEB_MCP_LLM_EMBED_MODEL: Model for embeddings (default: text-embedding-3-small)
    
    Args:
        question: The question to research and answer
        max_sources: Maximum number of sources to use (default: 5)
        search_results: Number of search results to fetch (default: 10)
        
    Returns:
        AskResult with answer, sources, and timing info
    """
    llm_config = get_llm_config()
    
    if not llm_config.is_configured:
        return AskResult(
            answer="Error: LLM not configured. Set the following environment variables:\n"
                   "- WEB_MCP_LLM_API_KEY: Your API key\n"
                   "- WEB_MCP_LLM_API_URL: API endpoint (optional, defaults to OpenAI)\n"
                   "- WEB_MCP_LLM_MODEL: Model name (optional, defaults to gpt-4o)\n"
                   "- WEB_MCP_LLM_EMBED_MODEL: Embedding model (optional)",
            sources=[],
            elapsed_ms=0,
        )
    
    result = await research(
        query=question,
        max_sources=max_sources,
        search_results=search_results,
    )
    
    return AskResult(
        answer=result.answer,
        sources=result.sources,
        elapsed_ms=result.elapsed_ms,
    )


@mcp.tool()
async def ask_stream(
    question: str = Field(description="The question to research and answer"),
    max_sources: int = Field(
        default=5,
        description="Maximum number of sources to use for the answer (default: 5)"
    ),
    search_results: int = Field(
        default=10,
        description="Number of search results to fetch (default: 10)"
    )
) -> str:
    """Research a question and stream the answer with citations.
    
    This is the streaming version of the 'ask' tool. It performs the same research
    process but returns the answer incrementally as it's generated, followed by
    the sources list.
    
    Requires LLM configuration via environment variables:
    - WEB_MCP_LLM_API_KEY: API key for the LLM service
    - WEB_MCP_LLM_API_URL: API endpoint (default: OpenAI)
    - WEB_MCP_LLM_MODEL: Model for generation (default: gpt-4o)
    - WEB_MCP_LLM_EMBED_MODEL: Model for embeddings (default: text-embedding-3-small)
    
    Args:
        question: The question to research and answer
        max_sources: Maximum number of sources to use (default: 5)
        search_results: Number of search results to fetch (default: 10)
        
    Returns:
        The complete answer with sources (streamed during generation)
    """
    llm_config = get_llm_config()
    
    if not llm_config.is_configured:
        return ("Error: LLM not configured. Set the following environment variables:\n"
                "- WEB_MCP_LLM_API_KEY: Your API key\n"
                "- WEB_MCP_LLM_API_URL: API endpoint (optional, defaults to OpenAI)\n"
                "- WEB_MCP_LLM_MODEL: Model name (optional, defaults to gpt-4o)\n"
                "- WEB_MCP_LLM_EMBED_MODEL: Embedding model (optional)")
    
    parts = []
    async for chunk in research_stream(
        query=question,
        max_sources=max_sources,
        search_results=search_results,
    ):
        parts.append(chunk)
    
    return "".join(parts)


def main():
    """Run the MCP server."""
    import sys
    
    tools = "fetch_url, fetch_url_simple, fetch_url_query, web_search, web_search_simple, ask, ask_stream, current_datetime"
    
    if "--http" in sys.argv or "--streamable-http" in sys.argv:
        logger.info(f"Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"Tools available: {tools}")
        mcp.run(transport="streamable-http", mount_path="/mcp")
    elif "--sse" in sys.argv:
        logger.info(f"Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"Tools available: {tools}")
        mcp.run(transport="sse", mount_path="/sse")
    else:
        logger.info("Starting MCP server in stdio mode")
        mcp.run()


if __name__ == "__main__":
    main()
