"""Pytest fixtures and configuration for web-mcp tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    with patch("httpx.AsyncClient") as mock_client:
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_trafilatura():
    """Mock trafilatura module."""
    with patch("web_mcp.extractors.trafilatura.trafilatura") as mock:
        yield mock


@pytest.fixture
def mock_searxng_response():
    """Mock SearXNG search response."""
    return {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com/test",
                "snippet": "This is a test snippet",
                "publishedDate": "2024-01-01",
                "score": 0.95,
            }
        ]
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    with patch("web_mcp.llm.client.get_llm_client") as mock:
        client = MagicMock()
        client.embed = AsyncMock(return_value=[[0.1] * 384])
        client.chat = AsyncMock(return_value="Test answer")
        client.chat_stream = AsyncMock(
            return_value=asyncio.AsyncIteratorMock(["Test", " ", "answer"])
        )
        mock.return_value = client
        yield client


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <article>
                <h1>Test Title</h1>
                <p>This is test content.</p>
                <p>More test content here.</p>
            </article>
        </body>
    </html>
    """


@pytest.fixture
def sample_html_with_metadata():
    """Sample HTML with author and date metadata."""
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Test Page</title>
            <meta name="author" content="John Doe">
        </head>
        <body>
            <article>
                <h1>Test Title</h1>
                <time datetime="2024-01-01">January 1, 2024</time>
                <p>This is test content.</p>
            </article>
        </body>
    </html>
    """
