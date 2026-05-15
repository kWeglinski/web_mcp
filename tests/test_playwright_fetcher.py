"""Unit tests for Playwright-based URL fetching."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.playwright_fetcher import (
    PlaywrightFetchError,
    close_playwright,
    fetch_with_playwright,
    fetch_with_playwright_cached,
    get_browser_context,
    install_browsers,
)


class TestInstallBrowsers:
    @patch("web_mcp.playwright_fetcher.subprocess.run")
    def test_install_browsers_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with patch("web_mcp.playwright_fetcher.logger") as mock_logger:
            install_browsers()
            mock_logger.info.assert_called()

    @patch("web_mcp.playwright_fetcher.subprocess.run")
    def test_install_browsers_failure_exits(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="Install failed")
        with patch("web_mcp.playwright_fetcher.logger") as mock_logger:
            with pytest.raises(SystemExit):
                install_browsers()
            mock_logger.error.assert_called()

    @patch("web_mcp.playwright_fetcher.subprocess.run")
    def test_install_browsers_linux_warning(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with patch("web_mcp.playwright_fetcher.logger") as mock_logger:
            with patch("platform.system", return_value="Linux"):
                install_browsers()
                calls = [c[0][0] for c in mock_logger.info.call_args_list]
                assert any("Linux" in str(c) for c in calls)


class TestEnsureBrowsersInstalled:
    @patch("web_mcp.playwright_fetcher._ensure_browsers_installed")
    def test_returns_true_when_already_installed(self, mock_ensure):
        mock_ensure.return_value = True
        from web_mcp.playwright_fetcher import _ensure_browsers_installed

        result = _ensure_browsers_installed()
        assert result is True


class TestPlaywrightFetchError:
    def test_error_has_message(self):
        err = PlaywrightFetchError("Test error message")
        assert str(err) == "Test error message"
        assert err.message == "Test error message"

    def test_error_inherits_from_exception(self):
        err = PlaywrightFetchError("Test")
        assert isinstance(err, Exception)


class TestGetBrowserContext:
    @patch("web_mcp.playwright_fetcher._ensure_browsers_installed")
    @patch("playwright.async_api.async_playwright")
    async def test_get_browser_context_creates_new(self, mock_async_pw, mock_ensure):
        mock_ensure.return_value = True
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_pw.start = AsyncMock(return_value=mock_pw)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_async_pw.return_value = mock_pw

        context = await get_browser_context()
        assert context is not None

    @patch("web_mcp.playwright_fetcher._ensure_browsers_installed")
    async def test_get_browser_context_returns_cached(self, mock_ensure):
        mock_ensure.return_value = True
        with patch("web_mcp.playwright_fetcher.get_browser_context") as mock_ctx:
            mock_ctx.return_value = MagicMock()
            ctx1 = await mock_ctx()
            ctx2 = await mock_ctx()
            assert ctx1 is ctx2

    async def test_get_browser_context_raises_on_missing_browsers(self):
        import web_mcp.playwright_fetcher as pf

        pf._browser_context = None
        pf._playwright_instance = None
        with patch("web_mcp.playwright_fetcher._ensure_browsers_installed", return_value=False):
            with pytest.raises(PlaywrightFetchError, match="Chromium browser not installed"):
                await get_browser_context()

    async def test_get_browser_context_raises_on_import_error(self):
        import web_mcp.playwright_fetcher as pf

        pf._browser_context = None
        pf._playwright_instance = None
        with patch("web_mcp.playwright_fetcher._ensure_browsers_installed", return_value=True):
            with patch("playwright.async_api.async_playwright") as mock_async_pw:
                mock_async_pw.side_effect = ImportError("No module named playwright")
                with pytest.raises(PlaywrightFetchError, match="Playwright is not installed"):
                    await get_browser_context()


class TestClosePlaywright:
    async def test_close_playwright_no_context(self):
        import web_mcp.playwright_fetcher as pf

        pf._browser_context = None
        pf._playwright_instance = None
        await close_playwright()

    async def test_close_playwright_closes_context(self):
        import web_mcp.playwright_fetcher as pf

        mock_context = AsyncMock()
        mock_instance = AsyncMock()
        pf._browser_context = mock_context
        pf._playwright_instance = mock_instance
        await close_playwright()
        mock_context.close.assert_called_once()
        mock_instance.stop.assert_called_once()


class TestFetchWithPlaywright:
    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    async def test_fetch_with_playwright_invalid_url(self, mock_ip, mock_creds, mock_url):
        mock_url.return_value = False
        with pytest.raises(PlaywrightFetchError, match="Invalid URL format"):
            await fetch_with_playwright("not a url")

    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    async def test_fetch_with_playwright_credentials_blocked(self, mock_ip, mock_creds, mock_url):
        mock_url.return_value = True
        mock_creds.return_value = False
        with pytest.raises(PlaywrightFetchError, match="URL with credentials not allowed"):
            await fetch_with_playwright("https://user:pass@example.com")

    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    async def test_fetch_with_playwright_private_ip_blocked(self, mock_ip, mock_creds, mock_url):
        mock_url.return_value = True
        mock_creds.return_value = True
        mock_ip.return_value = False
        with pytest.raises(PlaywrightFetchError, match="SSRF attempt blocked"):
            await fetch_with_playwright("https://192.168.1.1/page")

    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.get_browser_context")
    async def test_fetch_with_playwright_success(self, mock_ctx, mock_url, mock_creds, mock_ip):
        mock_url.return_value = True
        mock_creds.return_value = True
        mock_ip.return_value = True

        mock_context = MagicMock()
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_ctx.return_value = mock_context

        result = await fetch_with_playwright("https://example.com")
        assert result == "<html><body>Test</body></html>"
        mock_page.close.assert_called_once()

    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.get_browser_context")
    async def test_fetch_with_playwright_timeout_error(
        self, mock_ctx, mock_url, mock_creds, mock_ip
    ):
        mock_url.return_value = True
        mock_creds.return_value = True
        mock_ip.return_value = True

        mock_context = MagicMock()
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("TimeoutError: Page timeout"))
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_ctx.return_value = mock_context

        with pytest.raises(PlaywrightFetchError, match="timed out"):
            await fetch_with_playwright("https://example.com")

    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.get_browser_context")
    async def test_fetch_with_playwright_system_deps_error(
        self, mock_ctx, mock_url, mock_creds, mock_ip
    ):
        mock_url.return_value = True
        mock_creds.return_value = True
        mock_ip.return_value = True

        mock_context = MagicMock()
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("libglib shared libraries error"))
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_ctx.return_value = mock_context

        with pytest.raises(PlaywrightFetchError, match="system dependencies missing"):
            await fetch_with_playwright("https://example.com")

    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.get_browser_context")
    async def test_fetch_with_playwright_wait_for_selector(
        self, mock_ctx, mock_url, mock_creds, mock_ip
    ):
        mock_url.return_value = True
        mock_creds.return_value = True
        mock_ip.return_value = True

        mock_context = MagicMock()
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_ctx.return_value = mock_context

        await fetch_with_playwright("https://example.com", wait_for_selector="#content")
        mock_page.wait_for_selector.assert_called_once()

    @patch("web_mcp.playwright_fetcher.validate_url_ip")
    @patch("web_mcp.playwright_fetcher.validate_url_no_credentials")
    @patch("web_mcp.playwright_fetcher.validate_url")
    @patch("web_mcp.playwright_fetcher.get_browser_context")
    async def test_fetch_with_playwright_with_proxy(self, mock_ctx, mock_url, mock_creds, mock_ip):
        mock_url.return_value = True
        mock_creds.return_value = True
        mock_ip.return_value = True

        mock_context = MagicMock()
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_ctx.return_value = mock_context

        await fetch_with_playwright("https://example.com", proxy="http://proxy:8080")
        mock_ctx.assert_called_once_with(proxy="http://proxy:8080")


class TestFetchWithPlaywrightCached:
    @patch("web_mcp.cache.get_cache")
    async def test_fetch_cached_returns_cache_hit(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached html"
        mock_get_cache.return_value = mock_cache

        mock_config = MagicMock()
        result = await fetch_with_playwright_cached("https://example.com", mock_config)
        assert result == "cached html"

    @patch("web_mcp.cache.get_cache")
    @patch("web_mcp.playwright_fetcher.fetch_with_playwright")
    async def test_fetch_cached_miss(self, mock_pw_fetch, mock_get_cache):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.set = MagicMock()
        mock_get_cache.return_value = mock_cache

        mock_pw_fetch.return_value = "<html>fresh</html>"
        mock_config = MagicMock()
        mock_config.playwright_timeout = 30000
        mock_config.proxy_url = None
        mock_config.cache_ttl = 3600

        result = await fetch_with_playwright_cached("https://example.com", mock_config)
        assert result == "<html>fresh</html>"
        mock_cache.set.assert_called_once()

    @patch("web_mcp.cache.get_cache")
    @patch("web_mcp.playwright_fetcher.fetch_with_playwright")
    async def test_fetch_cached_uses_custom_timeout(self, mock_pw_fetch, mock_get_cache):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.set = MagicMock()
        mock_get_cache.return_value = mock_cache

        mock_pw_fetch.return_value = "content"
        mock_config = MagicMock()
        mock_config.playwright_timeout = 30000
        mock_config.proxy_url = None
        mock_config.cache_ttl = 3600

        await fetch_with_playwright_cached("https://example.com", mock_config, timeout=60000)
        mock_pw_fetch.assert_called_once()
        call_kwargs = mock_pw_fetch.call_args
        assert call_kwargs.kwargs.get("timeout") == 60000
