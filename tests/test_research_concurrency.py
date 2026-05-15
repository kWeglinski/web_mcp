"""Tests for fetch concurrency limiting via semaphore in research pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_semaphore():
    """Reset the fetch semaphore before each test."""
    from web_mcp.research import pipeline

    # Replace the existing semaphore with a fresh one
    max_concurrent = 5
    pipeline._FETCH_SEMAPHORE = asyncio.Semaphore(max_concurrent)
    yield


@pytest.fixture
def mock_fetch_config():
    """Mock get_config to return a valid config."""
    config = MagicMock()
    config.timeout = 30
    with patch("web_mcp.research.pipeline.get_config", return_value=config):
        yield config


@pytest.fixture
def mock_fetch_url():
    """Mock fetch_url to return HTML."""
    with patch("web_mcp.research.pipeline.fetch_url") as mock:
        mock.return_value = "<html><body>test content</body></html>"
        yield mock


@pytest.fixture
def mock_extractor():
    """Mock the trafilatura extractor."""
    with patch("web_mcp.research.pipeline._extractor") as mock:
        mock.extract = AsyncMock(return_value=MagicMock(title="Test", text="extracted content"))
        yield mock


@pytest.fixture
def urls_to_fetch():
    """Generate a list of test URLs."""
    return [f"https://example.com/page/{i}" for i in range(10)]


class TestFetchSemaphoreLimitsConcurrent:
    """Tests that the semaphore limits concurrent fetches."""

    async def test_fetch_semaphore_limits_concurrent_requests(
        self, mock_fetch_config, mock_fetch_url, mock_extractor
    ):
        """10 URLs should never have more than 5 fetching at once."""
        from web_mcp.research.pipeline import FetchedContent, _fetch_and_extract

        max_concurrent = 0
        current_concurrent = 0
        concurrent_lock = asyncio.Lock()

        async def tracking_fetch(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with concurrent_lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.05)
            async with concurrent_lock:
                current_concurrent -= 1
            return "<html><body>test content</body></html>"

        mock_fetch_url.side_effect = tracking_fetch
        mock_extractor.extract = AsyncMock(
            return_value=MagicMock(title="Test", text="extracted content")
        )

        urls = [f"https://example.com/page/{i}" for i in range(10)]
        tasks = [_fetch_and_extract(url, f"Title {i}") for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)

        assert max_concurrent <= 5, f"Max concurrent was {max_concurrent}, expected <= 5"
        assert len(results) == 10
        for result in results:
            assert isinstance(result, FetchedContent)
            assert result.text == "extracted content"

    async def test_fetch_semaphore_allows_next_batch(
        self, mock_fetch_config, mock_fetch_url, mock_extractor
    ):
        """After one fetch completes, another should start (batching works)."""
        from web_mcp.research.pipeline import _fetch_and_extract

        max_concurrent = 0
        current_concurrent = 0
        concurrent_lock = asyncio.Lock()

        async def tracking_fetch(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with concurrent_lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.1)
            async with concurrent_lock:
                current_concurrent -= 1
            return "<html><body>test content</body></html>"

        mock_fetch_url.side_effect = tracking_fetch
        mock_extractor.extract = AsyncMock(
            return_value=MagicMock(title="Test", text="extracted content")
        )

        urls = [f"https://example.com/page/{i}" for i in range(10)]
        tasks = [_fetch_and_extract(url, f"Title {i}") for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for result in results:
            assert not result.error
