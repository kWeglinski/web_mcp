"""SearXNG search module for web browsing MCP server."""

import os
from typing import Optional

import httpx


class SearXNGError(Exception):
    """Custom exception for SearXNG search errors."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def get_searxng_url() -> Optional[str]:
    """Get the SearXNG URL from environment variable.
    
    Returns:
        The SearXNG URL if configured, None otherwise.
    """
    return os.environ.get("WEB_MCP_SEARXNG_URL", None)


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search using SearXNG.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)
        
    Returns:
        List of search result dictionaries with title, url, and snippet
        
    Raises:
        SearXNGError: If the search fails or SearXNG is not configured
    """
    searxng_url = get_searxng_url()
    
    if not searxng_url:
        raise SearXNGError(
            "SearXNG is not configured. Set WEB_MCP_SEARXNG_URL environment variable."
        )
    
    # Clean up the URL - ensure it doesn't have a trailing slash
    searxng_url = searxng_url.rstrip("/")
    
    # Build the search URL
    # SearXNG API endpoint is typically /search
    search_url = f"{searxng_url}/search"
    
    timeout = 30
    
    try:
        async with httpx.AsyncClient() as client:
            params = {
                "q": query,
                "format": "json",
                "pageno": 1,
                "num_results": max_results,
            }
            response = await client.get(search_url, params=params, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # SearXNG returns results in the 'results' key
            results = data.get("results", [])
            
            # Parse and format results
            formatted_results = []
            for result in results:
                formatted_result = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", result.get("snippet", "")),
                }
                
                # Add optional fields if available
                if "publishedDate" in result:
                    formatted_result["published_date"] = result["publishedDate"]
                if "score" in result:
                    formatted_result["score"] = result["score"]
                
                formatted_results.append(formatted_result)
            
            return formatted_results
            
    except httpx.TimeoutException as e:
        raise SearXNGError(f"Request timed out: {e}")
    except httpx.HTTPStatusError as e:
        raise SearXNGError(f"HTTP error {e.response.status_code}: {e}")
    except httpx.RequestError as e:
        raise SearXNGError(f"Request failed: {e}")
    except Exception as e:
        raise SearXNGError(f"Search failed: {e}")


async def search_and_fetch(
    query: str, 
    max_results: int = 5,
    fetch_content: bool = False
) -> list[dict]:
    """Search using SearXNG and optionally fetch content.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
        fetch_content: Whether to fetch full content for each result
        
    Returns:
        List of search results with optional fetched content
    """
    from web_mcp.fetcher import FetchError, fetch_url_with_fallback as fetch_html
    from web_mcp.config import get_config
    
    results = await search(query, max_results)
    
    if not fetch_content:
        return results
    
    # Fetch content for each result
    config = get_config()
    for result in results:
        url = result.get("url", "")
        if url:
            try:
                html = await fetch_html(url, config)
                result["fetched_content"] = html
            except FetchError as e:
                result["fetch_error"] = str(e)
    
    return results
