"""Pytest fixtures and configuration for web-mcp tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_mem0():
    """Mock the mem0 module so tests don't need the mem0 package installed."""
    import sys
    from types import ModuleType

    # Save original modules to restore later
    original_mem0 = sys.modules.get("web_mcp.mem0")
    original_mem0_tools = sys.modules.get("web_mcp.mem0.tools")
    original_mem0_root = sys.modules.get("mem0")

    # Create a mock module for web_mcp.mem0 with a tools submodule
    mock_mem0_pkg = ModuleType("web_mcp.mem0")
    mock_tools = ModuleType("web_mcp.mem0.tools")

    mock_memory = MagicMock()
    mock_memory.add = MagicMock(return_value=None)
    mock_memory.search = MagicMock(return_value=[])
    mock_memory.get_all = MagicMock(return_value=[])

    mock_manager = MagicMock()
    mock_manager.get_memory = MagicMock(return_value=mock_memory)

    # Set up the tools module with mock tool functions
    mock_add_memory_tool = MagicMock()
    mock_search_memory_tool = MagicMock()
    mock_get_user_memories_tool = MagicMock()
    mock_tools.add_memory_tool = mock_add_memory_tool
    mock_tools.search_memory_tool = mock_search_memory_tool
    mock_tools.get_user_memories_tool = mock_get_user_memories_tool

    mock_mem0_pkg.mem0_manager = mock_manager
    mock_mem0_pkg.tools = mock_tools

    # Install in sys.modules
    sys.modules["web_mcp.mem0"] = mock_mem0_pkg
    sys.modules["web_mcp.mem0.tools"] = mock_tools

    yield mock_manager

    # Clean up - restore original modules
    if original_mem0 is not None:
        sys.modules["web_mcp.mem0"] = original_mem0
    elif "web_mcp.mem0" in sys.modules:
        del sys.modules["web_mcp.mem0"]

    if original_mem0_tools is not None:
        sys.modules["web_mcp.mem0.tools"] = original_mem0_tools
    elif "web_mcp.mem0.tools" in sys.modules:
        del sys.modules["web_mcp.mem0.tools"]

    # Restore original mem0 root module if it was replaced
    if original_mem0_root is not None:
        sys.modules["mem0"] = original_mem0_root


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _reset_search_cache():
    """Reset search cache before each test to avoid cross-test pollution."""
    from web_mcp.searxng import reset_search_cache

    reset_search_cache()


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
