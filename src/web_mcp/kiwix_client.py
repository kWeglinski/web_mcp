"""Client for interacting with a Zimi (Kiwix-compatible) server."""

import httpx

from web_mcp.config import get_config
from web_mcp.logging import get_logger

logger = get_logger(__name__)


class KiwixClient:
    """A client to interact with the Zimi/Kiwix server."""

    def __init__(self) -> None:
        """Initialize the KiwixClient with configuration."""
        config = get_config()
        self.kiwix_url = config.kiwix_url
        self.kiwix_wikipedia_zim = config.kiwix_wikipedia_zim

        if not self.kiwix_url:
            logger.error("WEB_MCP_KIWIX_URL is not configured")
            raise ValueError("WEB_MCP_KIWIX_URL is not configured.")

        self.kiwix_url = self.kiwix_url.rstrip("/")
        logger.debug(
            f"KiwixClient initialized: url={self.kiwix_url}, zim={self.kiwix_wikipedia_zim}"
        )

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

        logger.debug(f"Kiwix search: url={url}, params={params}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                logger.debug(f"Kiwix search response: status={response.status_code}")
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            logger.info(f"Kiwix search returned {len(results)} results for query='{query}'")

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
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kiwix search HTTP error: status={e.response.status_code}, url={url}, body={e.response.text[:500]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Kiwix search request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Kiwix search unexpected error: {e}")
            raise

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

        logger.debug(f"Kiwix get_content: url={url}, path={path}, max_length={max_length}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                logger.debug(
                    f"Kiwix get_content response: status={response.status_code}, path={path}"
                )
                response.raise_for_status()
                data = response.json()

            content = data.get("content", "")
            logger.debug(f"Kiwix get_content: retrieved {len(content)} chars for path={path}")
            return content
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kiwix get_content HTTP error: status={e.response.status_code}, path={path}, body={e.response.text[:500]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Kiwix get_content request error: path={path}, error={e}")
            raise
        except Exception as e:
            logger.error(f"Kiwix get_content unexpected error: path={path}, error={e}")
            raise

    async def get_catalog(self) -> list[dict]:
        """
        Get the catalog of available ZIM files.

        Returns:
            A list of catalog entries (dictionaries).

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.kiwix_url}/list"

        logger.debug(f"Kiwix get_catalog: url={url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                logger.debug(f"Kiwix get_catalog response: status={response.status_code}")
                response.raise_for_status()
                data = response.json()

            if isinstance(data, list):
                logger.info(f"Kiwix catalog: {len(data)} ZIM files available")
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
            logger.warning(f"Kiwix catalog: unexpected response type {type(data).__name__}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kiwix get_catalog HTTP error: status={e.response.status_code}, body={e.response.text[:500]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Kiwix get_catalog request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Kiwix get_catalog unexpected error: {e}")
            raise

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

        logger.debug(f"Kiwix suggest: url={url}, params={params}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                logger.debug(f"Kiwix suggest response: status={response.status_code}")
                response.raise_for_status()
                data = response.json()

            suggestions = data.get(self.kiwix_wikipedia_zim, [])
            logger.info(f"Kiwix suggest: {len(suggestions)} suggestions for query='{query}'")
            return [{"title": s.get("title", ""), "url": s.get("path", "")} for s in suggestions]
        except httpx.HTTPStatusError as e:
            logger.error(f"Kiwix suggest HTTP error: status={e.response.status_code}, url={url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Kiwix suggest request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Kiwix suggest unexpected error: {e}")
            raise

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

        logger.debug(f"Kiwix random_article: url={url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                logger.debug(f"Kiwix random_article response: status={response.status_code}")
                response.raise_for_status()
                data = response.json()

            if data:
                logger.info(f"Kiwix random_article: retrieved '{data.get('title', '')}'")
                return {
                    "title": data.get("title", ""),
                    "url": data.get("path", ""),
                }
            logger.info("Kiwix random_article: no article found")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Kiwix random_article HTTP error: status={e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Kiwix random_article request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Kiwix random_article unexpected error: {e}")
            raise
