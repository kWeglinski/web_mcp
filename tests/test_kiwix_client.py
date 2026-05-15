"""Unit tests for Kiwix client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.kiwix_client import KiwixClient


class TestKiwixClient:
    @patch("web_mcp.kiwix_client.get_config")
    def test_init_sets_url(self, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en_all_maxi.zim"
        client = KiwixClient()
        assert client.kiwix_url == "http://localhost:8000"
        assert client.kiwix_wikipedia_zim == "en_all_maxi.zim"

    @patch("web_mcp.kiwix_client.get_config")
    def test_init_strips_trailing_slash(self, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000/"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"
        client = KiwixClient()
        assert client.kiwix_url == "http://localhost:8000"

    @patch("web_mcp.kiwix_client.get_config")
    def test_init_raises_without_url(self, mock_config):
        mock_config.return_value.kiwix_url = None
        with pytest.raises(ValueError, match="WEB_MCP_KIWIX_URL is not configured"):
            KiwixClient()

    @patch("web_mcp.kiwix_client.get_config")
    def test_init_default_zim(self, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = None
        client = KiwixClient()
        assert client.kiwix_wikipedia_zim is None


class TestKiwixClientSearch:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_returns_list(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"title": "Result 1", "url": "/page1"},
            {"title": "Result 2", "url": "/page2"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("test query")
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_returns_results_from_dict(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"title": "Found"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("test")
        assert len(results) == 1

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_returns_empty_for_unexpected_format(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "format"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("test")
        assert results == []

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_handles_non_json(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("test")
        assert results == []

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_uses_correct_url(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        await client.search("hello world")
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args.kwargs.get("params") == {"q": "hello world"}

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_parses_kiwix_xml(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<results>
  <result>
    <title>Python (programming language)</title>
    <url>./Python_(programming_language)</url>
    <content>Python is a high-level programming language...</content>
  </result>
  <result>
    <title>Python (genus)</title>
    <url>./Python_(genus)</url>
    <content>Python is a genus of venomous snakes...</content>
  </result>
</results>"""
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("python")
        assert len(results) == 2
        assert results[0]["title"] == "Python (programming language)"
        assert results[0]["content"] == "Python is a high-level programming language..."
        assert results[1]["title"] == "Python (genus)"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_xml_empty_results(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = '<?xml version="1.0" encoding="utf-8"?><results></results>'
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("zzzznotfound")
        assert results == []


class TestKiwixClientGetContent:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_content(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.text = "<html><body>Page content</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        content = await client.get_content("wikipedia/Main_Page.html")
        assert content == "<html><body>Page content</body></html>"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_content_strips_leading_slash(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.text = "content"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        await client.get_content("/path/to/page")
        call_args = mock_client.get.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert "//path" not in url


class TestKiwixClientGetCatalog:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_catalog_returns_list(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"name": "en.zim", "id": "en"},
            {"name": "fr.zim", "id": "fr"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        catalog = await client.get_catalog()
        assert len(catalog) == 2
        assert catalog[0]["name"] == "en.zim"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_catalog_returns_empty_for_dict(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = {"other": "data"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        catalog = await client.get_catalog()
        assert catalog == []

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_catalog_handles_non_json(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        catalog = await client.get_catalog()
        assert catalog == []

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_catalog_uses_correct_url(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "en.zim"

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        await client.get_catalog()
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args.args[0] == "http://localhost:8000/catalog/v2"
