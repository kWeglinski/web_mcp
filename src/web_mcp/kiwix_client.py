"""Client for interacting with a Zimi (Kiwix-compatible) server."""

import httpx

from web_mcp.config import get_config


class KiwixClient:
    """A client to interact with the Zimi/Kiwix server."""

    def __init__(self) -> None:
        """Initialize the KiwixClient with configuration."""
        config = get_config()
        self.kiwix_url = config.kiwix_url
        self.kiwix_wikipedia_zim = config.kiwix_wikipedia_zim

        if not self.kiwix_url:
            raise ValueError("WEB_MCP_KIWIX_URL is not configured.")

        self.kiwix_url = self.kiwix_url.rstrip("/")

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search for content using Zimi's full-text search API.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            A list of search results (dictionaries).

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.kiwix_url}/search"
        params: dict[str, str | int | None] = {
            "q": query,
            "limit": limit,
            "zim": self.kiwix_wikipedia_zim,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("path", ""),
                "content": r.get("snippet", ""),
                "score": r.get("score", 0),
                "zim": r.get("zim", ""),
            }
            for r in results
        ]

    async def get_content(self, path: str, max_length: int = 8000) -> str:
        """
        Fetch article content from the Zimi server.

        Args:
            path: The path to the article within the ZIM file.
            max_length: Maximum length of content to return.

        Returns:
            The content as a plain text string.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.kiwix_url}/read"
        params: dict[str, str | int | None] = {
            "zim": self.kiwix_wikipedia_zim,
            "path": path,
            "max_length": max_length,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        return data.get("content", "")

    async def get_catalog(self) -> list[dict]:
        """
        Get the catalog of available ZIM files.

        Returns:
            A list of catalog entries (dictionaries).

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.kiwix_url}/list"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, list):
            return [
                {
                    "name": z.get("name", ""),
                    "title": z.get("title", ""),
                    "description": z.get("description", ""),
                    "language": z.get("language", ""),
                    "file": z.get("file", ""),
                    "entries": z.get("entries", 0),
                }
                for z in data
            ]
        return []

    async def suggest(self, query: str, limit: int = 10) -> list[dict]:
        """
        Get title autocomplete suggestions.

        Args:
            query: The search query string.
            limit: Maximum number of suggestions.

        Returns:
            A list of suggestion dictionaries.
        """
        url = f"{self.kiwix_url}/suggest"
        params: dict[str, str | int | None] = {
            "q": query,
            "limit": limit,
            "zim": self.kiwix_wikipedia_zim,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        suggestions = data.get(self.kiwix_wikipedia_zim, [])
        return [{"title": s.get("title", ""), "url": s.get("path", "")} for s in suggestions]

    async def random_article(self) -> dict | None:
        """
        Get a random article from the ZIM file.

        Returns:
            A dictionary with title, path, or None if no article found.
        """
        url = f"{self.kiwix_url}/random"
        params: dict[str, str | None] = {
            "zim": self.kiwix_wikipedia_zim,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data:
            return {
                "title": data.get("title", ""),
                "url": data.get("path", ""),
            }
        return None
