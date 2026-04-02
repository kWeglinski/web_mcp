"""Brave Search API module for web browsing MCP server."""

import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 20


class BraveSearchError(Exception):
    """Custom exception for Brave Search errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def get_brave_api_key() -> str | None:
    """Get the Brave API key from environment variable.

    Returns:
        The Brave API key if configured, None otherwise.
    """
    return os.environ.get("BRAVE_API_KEY", None)


def remove_html_tags(text: str | None) -> str:
    """Strip HTML tags and normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^<]+?>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_brave_to_markdown(
    json_data: dict,
    query: str = "",
    max_results: int = 10,
    max_content_length: int = 1500,
) -> str:
    """Convert Brave Search JSON to LLM-optimized markdown format.

    Args:
        json_data: Brave Search JSON response containing web results
        query: The original search query for the header
        max_results: Maximum number of results to include (default: 10)
        max_content_length: Maximum content length per result (default: 1500)

    Returns:
        Formatted markdown string optimized for LLM context windows
    """
    web_results = json_data.get("web", {})
    raw_results = web_results.get("results", [])

    if not raw_results:
        return "*No search results found*"

    normalized_results = []

    for result in raw_results:
        description = result.get("description", "")
        clean_content = remove_html_tags(description)
        if len(clean_content) > max_content_length:
            clean_content = clean_content[:max_content_length] + "..."

        page_age = result.get("page_age", "")
        profile = result.get("profile", {})

        normalized_results.append(
            {
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "content": clean_content,
                "date": page_age,
                "source": profile.get("name", ""),
            }
        )

    output = (
        f'# Search Results for: "{query}"\n**Total Results:** {len(normalized_results)}\n\n---\n\n'
    )

    for i, result in enumerate(normalized_results[:max_results], 1):
        output += f"### Result #{i}\n"
        output += f"**Source:** [{result['title']}]({result['url']})  \n"
        if result["date"]:
            output += f"**Published:** {result['date']}  \n"
        if result["source"]:
            output += f"**Site:** {result['source']}  \n"
        output += "\n#### Key Findings\n"
        output += f"{result['content']}\n\n"
        output += f"[End of Result #{i}]\n\n---\n\n"

    return output


async def search(query: str, max_results: int = 10, count: int = 20) -> list[dict]:
    """Search using Brave Search API.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)
        count: Number of results to request from API (default: 20, max: 20)

    Returns:
        List of search result dictionaries with title, url, and snippet

    Raises:
        BraveSearchError: If the search fails
    """
    api_key = get_brave_api_key()

    if not api_key:
        raise BraveSearchError("BRAVE_API_KEY environment variable not set")

    count = min(count, MAX_RESULTS)

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    params: dict[str, str | int] = {
        "q": query,
        "count": count,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                BRAVE_API_URL,
                params=params,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 401:
                raise BraveSearchError("Invalid Brave API key")
            if response.status_code == 429:
                raise BraveSearchError("Brave API rate limit exceeded")
            if response.status_code == 422:
                raise BraveSearchError(f"Invalid request: {response.text}")

            response.raise_for_status()

            data = response.json()
            web_results = data.get("web", {}).get("results", [])

            formatted_results = []
            for result in web_results[:max_results]:
                formatted_result = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": remove_html_tags(result.get("description", "")),
                }

                if result.get("page_age"):
                    formatted_result["published_date"] = result["page_age"]

                formatted_results.append(formatted_result)

            logger.info(f"[Brave] Search successful - got {len(formatted_results)} results")
            return formatted_results

    except httpx.TimeoutException:
        raise BraveSearchError("Brave API request timed out")
    except httpx.HTTPStatusError as e:
        raise BraveSearchError(f"Brave API HTTP error: {e.response.status_code}")
    except httpx.RequestError as e:
        raise BraveSearchError(f"Brave API request failed: {e}")
    except Exception as e:
        raise BraveSearchError(f"Search failed: {e}")
