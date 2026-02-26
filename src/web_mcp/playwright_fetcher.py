"""Playwright-based URL fetching for JavaScript-heavy pages."""

import subprocess
import sys

from typing import Optional

from web_mcp.logging_utils import get_logger
from web_mcp.security import (
    validate_url,
    validate_url_ip,
    validate_url_no_credentials,
)

logger = get_logger(__name__)

_browser_context = None
_playwright_instance = None
_browsers_installed = False


def _ensure_browsers_installed() -> bool:
    """Ensure Playwright browsers are installed.
    
    Returns:
        True if browsers are available, False otherwise
    """
    global _browsers_installed
    
    if _browsers_installed:
        return True
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            chromium_path = p.chromium.executable_path
            import os
            if os.path.exists(chromium_path):
                _browsers_installed = True
                return True
    except Exception:
        pass
    
    logger.info("Chromium not found, installing automatically...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        logger.info("Chromium installed successfully")
        _browsers_installed = True
        return True
    
    logger.error(f"Failed to install Chromium: {result.stderr}")
    return False


def install_browsers() -> None:
    """Install Playwright browser binaries.
    
    This is called via the web-mcp-install script entry point.
    """
    print("Installing Playwright Chromium browser...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("✓ Chromium installed successfully")
    else:
        print(f"✗ Failed to install Chromium: {result.stderr}")
        sys.exit(1)


class PlaywrightFetchError(Exception):
    """Custom exception for Playwright fetch errors."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def get_browser_context():
    """Get or create the shared Playwright browser context.
    
    Returns:
        Playwright BrowserContext instance
    """
    global _browser_context, _playwright_instance
    
    if _browser_context is not None:
        return _browser_context
    
    try:
        from playwright.async_api import async_playwright
        
        if not _ensure_browsers_installed():
            raise PlaywrightFetchError(
                "Chromium browser not installed. Run: web-mcp-install "
                "or: uv run playwright install chromium"
            )
        
        _playwright_instance = await async_playwright().start()
        browser = await _playwright_instance.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        _browser_context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            java_script_enabled=True,
        )
        return _browser_context
    except ImportError:
        raise PlaywrightFetchError(
            "Playwright is not installed. Run: uv pip install playwright"
        )


async def close_playwright() -> None:
    """Close the Playwright browser instance."""
    global _browser_context, _playwright_instance
    
    if _browser_context is not None:
        await _browser_context.close()
        _browser_context = None
    
    if _playwright_instance is not None:
        await _playwright_instance.stop()
        _playwright_instance = None


async def fetch_with_playwright(
    url: str,
    timeout: int = 30000,
    wait_for_selector: Optional[str] = None,
    wait_time: int = 1000,
) -> str:
    """Fetch a URL using Playwright for JavaScript rendering.
    
    Args:
        url: The URL to fetch
        timeout: Page load timeout in milliseconds
        wait_for_selector: Optional CSS selector to wait for
        wait_time: Additional wait time after page load in milliseconds
        
    Returns:
        Rendered HTML content
        
    Raises:
        PlaywrightFetchError: If the page cannot be loaded
    """
    if not validate_url(url):
        raise PlaywrightFetchError(f"Invalid URL format: {url}")
    
    if not validate_url_no_credentials(url):
        raise PlaywrightFetchError("URL with credentials not allowed")
    
    if not validate_url_ip(url):
        raise PlaywrightFetchError("URL resolves to private IP address - SSRF attempt blocked")
    
    try:
        context = await get_browser_context()
        page = await context.new_page()
        
        try:
            await page.goto(
                url,
                timeout=timeout,
                wait_until='domcontentloaded',
            )
            
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout // 2)
            else:
                await page.wait_for_timeout(wait_time)
            
            html = await page.content()
            return html
            
        finally:
            await page.close()
            
    except Exception as e:
        error_msg = str(e)
        if "Timeout" in error_msg or "timeout" in error_msg.lower():
            raise PlaywrightFetchError(f"Page load timed out: {error_msg}")
        raise PlaywrightFetchError(f"Failed to load page: {error_msg}")


async def fetch_with_playwright_cached(
    url: str,
    config,
    timeout: Optional[int] = None,
) -> str:
    """Fetch URL with Playwright and caching.
    
    Args:
        url: The URL to fetch
        config: Configuration object
        timeout: Optional timeout override in milliseconds
        
    Returns:
        Rendered HTML content
    """
    from web_mcp.cache import get_cache
    
    cache = get_cache()
    cache_key = f"playwright:{url}"
    
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(f"Playwright cache hit for URL: {url}")
        return cached
    
    result = await fetch_with_playwright(
        url,
        timeout=timeout or config.playwright_timeout,
    )
    
    cache.set(cache_key, result, ttl=config.cache_ttl)
    
    return result
