"""Unit tests for Zimi (Kiwix-compatible) client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.kiwix_client import KiwixClient


class TestKiwixClient:
    @patch("web_mcp.kiwix_client.get_config")
    def test_init_sets_url(self, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"
        client = KiwixClient()
        assert client.kiwix_url == "http://localhost:8000"
        assert client.kiwix_wikipedia_zim == "wikipedia"

    @patch("web_mcp.kiwix_client.get_config")
    def test_init_strips_trailing_slash(self, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000/"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"
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
    async def test_search_returns_zimi_results(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Python (programming language)",
                    "path": "A/Python_(programming_language)",
                    "snippet": "Python is a language",
                    "score": 113.6,
                },
                {
                    "title": "Python (genus)",
                    "path": "A/Python_(genus)",
                    "snippet": "Python is a snake",
                    "score": 100.0,
                },
            ]
        }
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
        assert results[0]["url"] == "A/Python_(programming_language)"
        assert results[0]["content"] == "Python is a language"
        assert results[0]["score"] == 113.6

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_empty_results(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("zzzznotfound")
        assert results == []

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_uses_correct_url_and_params(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        await client.search("test query", limit=10)
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args.args[0] == "http://localhost:8000/search"
        assert call_args.kwargs.get("params") == {
            "q": "test query",
            "limit": 10,
            "zim": "wikipedia",
        }

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_search_no_results_key(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {"other": "data"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        results = await client.search("test")
        assert results == []


class TestKiwixClientGetContent:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_content_returns_text(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "zim": "wikipedia",
            "path": "A/Python_(programming_language)",
            "title": "Python (programming language)",
            "content": "Python is a high-level programming language",
            "truncated": False,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        content = await client.get_content("A/Python_(programming_language)")
        assert content == "Python is a high-level programming language"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_content_uses_correct_params(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": "test"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        await client.get_content("A/Test", max_length=4000)
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args.args[0] == "http://localhost:8000/read"
        assert call_args.kwargs.get("params") == {
            "zim": "wikipedia",
            "path": "A/Test",
            "max_length": 4000,
        }

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_content_empty_on_missing_key(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {"other": "data"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        content = await client.get_content("A/SomePage")
        assert content == ""


class TestKiwixClientGetCatalog:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_catalog_returns_zimi_format(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "name": "wikipedia",
                "file": "wikipedia_en_all_nopic_2024-02.zim",
                "size_gb": 52.0,
                "entries": 6879428,
                "title": "Wikipedia",
                "description": "Offline version of Wikipedia in English",
                "date": "2024-02-21",
                "language": "en",
                "has_icon": True,
                "category": "Wikimedia",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        catalog = await client.get_catalog()
        assert len(catalog) == 1
        assert catalog[0]["name"] == "wikipedia"
        assert catalog[0]["title"] == "Wikipedia"
        assert catalog[0]["language"] == "en"
        assert catalog[0]["entries"] == 6879428

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_get_catalog_returns_empty_for_non_list(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

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
    async def test_get_catalog_uses_correct_url(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

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
        assert call_args.args[0] == "http://localhost:8000/list"


class TestKiwixClientSuggest:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_suggest_returns_suggestions(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "wikipedia": [
                {"path": "A/Python", "title": "Python"},
                {"path": "A/Python_(automobile_maker)", "title": "Python (automobile maker)"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        suggestions = await client.suggest("python")
        assert len(suggestions) == 2
        assert suggestions[0]["title"] == "Python"
        assert suggestions[0]["url"] == "A/Python"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_suggest_empty_on_missing_zim_key(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {"other_zim": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        suggestions = await client.suggest("test")
        assert suggestions == []


class TestKiwixClientRandomArticle:
    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_random_article_returns_dict(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "zim": "wikipedia",
            "path": "A/Random_Page",
            "title": "Random Page",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        article = await client.random_article()
        assert article is not None
        assert article["title"] == "Random Page"
        assert article["url"] == "A/Random_Page"

    @patch("web_mcp.kiwix_client.get_config")
    @patch("web_mcp.kiwix_client.httpx.AsyncClient")
    async def test_random_article_returns_none_on_empty(self, mock_client_class, mock_config):
        mock_config.return_value.kiwix_url = "http://localhost:8000"
        mock_config.return_value.kiwix_wikipedia_zim = "wikipedia"

        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = KiwixClient()
        article = await client.random_article()
        assert article is None
