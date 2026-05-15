"""Client for interacting with a Kiwix server."""

import httpx

from web_mcp.config import get_config


class KiwixClient:
    """A client to interact with the Kiwix server."""

    def __init__(self) -> None:
        """Initialize the KiwixClient with configuration."""
        config = get_config()
        self.kiwix_url = config.kiwix_url
        self.kiwix_wikipedia_zim = config.kiwix_wikipedia_zim

        if not self.kiwix_url:
            raise ValueError("WEB_MCP_KIWIX_URL is not configured.")

        # Ensure URL doesn't have a trailing slash for consistent endpoint joining
        self.kiwix_url = self.kiwix_url.rstrip("/")

    async def search(self, query: str) -> list[dict]:
        """
        Search for content in the Kiwix server.

        Args:
            query: The search query string.

        Returns:
            A list of search results (dictionaries).

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.kiwix_url}/search"
        params = {"q": query}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            # Assuming the response is a JSON list or contains a list of results
            try:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "results" in data:
                    return data["results"]
                else:
                    return []
            except ValueError:
                # If not JSON, return empty list or handle as error
                return []

    async def get_content(self, path: str) -> str:
        """
        Fetch raw content from the Kiwix server.

        Args:
            path: The path to the content within the ZIM file.

        Returns:
            The content as a string.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        # Ensure path doesn't start with a slash to avoid double slashes if needed,
        # but the requirement says /raw/{zim_name}/{path}
        clean_path = path.lstrip("/")
        url = f"{self.kiwix_url}/raw/{self.kiwix_wikipedia_zim}/{clean_path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def get_catalog(self) -> list[dict]:
        """
        Get the catalog of available ZIM files.

        Returns:
            A list of catalog entries (dictionaries).

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.kiwix_url}/catalog/v2"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            try:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "catalog" in data:
                    return data["catalog"]
                else:
                    return []
            except ValueError:
                return []
