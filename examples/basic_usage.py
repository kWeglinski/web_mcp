#!/usr/bin/env python3
"""
Web MCP Basic Usage Example

This example demonstrates how to use the web_mcp package to:
1. Start the MCP server
2. Use the get_page tool to fetch and extract web content
3. Use the search_web tool to search the web
4. Use the create_chart_tool to create interactive charts
5. Handle errors gracefully

Prerequisites:
    - Install the package: uv pip install -e .
    - Install Playwright browsers: web-mcp-install
    - Set environment variables (optional):
        - SEARXNG_URL: URL of your SearXNG instance (default: http://localhost:8080)
        - WEB_MCP_PUBLIC_URL: Public URL for chart/rendered content URLs

Usage:
    # Run this script directly
    uv run python examples/basic_usage.py

    # Or start the server separately and use MCP client
    uv run python -m web_mcp.server --http
"""

import asyncio
import json
import os
import sys
from typing import Any

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# HTTP client for MCP over HTTP
try:
    import httpx
except ImportError:
    print("Install httpx: uv pip install httpx")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

MCP_SERVER_URL = os.environ.get("WEB_MCP_SERVER_URL", "http://localhost:8000")
MCP_ENDPOINT = f"{MCP_SERVER_URL}/mcp"


# =============================================================================
# MCP Client Helper Functions
# =============================================================================


class MCPClient:
    """Simple MCP client for making tool calls over HTTP."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict:
        """
        Call an MCP tool and return the result.

        Args:
            tool_name: Name of the tool to call (e.g., 'get_page', 'search_web')
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            Dictionary containing the tool result

        Example:
            result = await client.call_tool("get_page", {"url": "https://example.com"})
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                headers=self.headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
            )
            response.raise_for_status()
            return response.json()


# =============================================================================
# Example 1: Starting the MCP Server
# =============================================================================


def example_start_server_subprocess():
    """
    Example: Starting the MCP server as a subprocess.

    The server can run in three modes:
    1. stdio (default): Communicates via stdin/stdout - for MCP clients
    2. --http: HTTP transport on port 8000
    3. --sse: Server-Sent Events transport

    For this example, we'll start it with HTTP transport.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Starting the MCP Server")
    print("=" * 70)

    print("""
# Option 1: Start server in stdio mode (for MCP clients like Claude Desktop)
uv run python -m web_mcp.server

# Option 2: Start server with HTTP transport
uv run python -m web_mcp.server --http

# Option 3: Start server with SSE transport
uv run python -m web_mcp.server --sse

# Option 4: Start with custom host/port
WEB_MCP_SERVER_HOST=0.0.0.0 WEB_MCP_SERVER_PORT=9000 uv run python -m web_mcp.server --http

# Option 5: Enable authentication
WEB_MCP_AUTH_TOKEN=your-secret-token uv run python -m web_mcp.server --http
""")

    print("Server provides these tools:")
    print("  - get_page: Fetch and extract content from URLs")
    print("  - search_web: Search the web via SearXNG")
    print("  - create_chart_tool: Create interactive Plotly charts")
    print("  - render_html: Render HTML content to a viewable URL")
    print("  - current_datetime: Get current date/time")
    print("  - health: Get server health metrics")
    print("  - run_javascript: Execute JavaScript in a sandboxed V8")


def example_start_server_programmatic():
    """
    Example: Starting the MCP server programmatically from Python.
    """
    print("\n" + "-" * 70)
    print("Programmatic Server Start:")
    print("-" * 70)

    print("""
import asyncio
from web_mcp.server import mcp

async def run_server():
    # Run with stdio transport (default)
    await mcp.run()

    # Or run with HTTP transport
    # await mcp.run(transport="streamable-http", mount_path="/mcp")

if __name__ == "__main__":
    asyncio.run(run_server())
""")


# =============================================================================
# Example 2: Using get_page Tool
# =============================================================================


async def example_get_page_basic(client: MCPClient):
    """
    Example: Basic usage of get_page tool.

    The get_page tool fetches a URL and extracts its main content using
    content extraction algorithms (trafilatura, readability, or custom selectors).

    Expected output:
        - Extracted text content from the page
        - Title and main article content
        - Cleaned and formatted text
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Using get_page Tool - Basic")
    print("=" * 70)

    url = "https://example.com"
    print(f"\nFetching: {url}")

    try:
        result = await client.call_tool("get_page", {"url": url})

        if "result" in result:
            content = result["result"].get("content", [])
            if content and len(content) > 0:
                text = content[0].get("text", "")
                print("\nExtracted content (first 500 chars):")
                print("-" * 40)
                print(text[:500] + "..." if len(text) > 500 else text)
            else:
                print("No content returned")
        elif "error" in result:
            print(f"Error: {result['error']}")

    except httpx.HTTPError as e:
        print(f"HTTP Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


async def example_get_page_with_query(client: MCPClient):
    """
    Example: Using get_page with a query for BM25-ranked chunk retrieval.

    When you provide a query, the tool:
    1. Extracts the full page content
    2. Chunks the content into smaller pieces
    3. Ranks chunks by BM25 relevance to your query
    4. Returns only the most relevant chunks

    This is useful for:
    - Finding specific information in long articles
    - Extracting relevant sections for RAG pipelines
    - Reducing context size for LLM processing
    """
    print("\n" + "-" * 70)
    print("Using get_page with BM25 Query Filtering")
    print("-" * 70)

    url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    query = "type hints and static typing"

    print(f"\nURL: {url}")
    print(f"Query: '{query}'")
    print("\nThis will return only the chunks most relevant to 'type hints'")

    try:
        result = await client.call_tool("get_page", {"url": url, "query": query})

        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                print("\nRelevant chunks (first 800 chars):")
                print("-" * 40)
                print(text[:800] + "..." if len(text) > 800 else text)

    except Exception as e:
        print(f"Error: {e}")


async def example_get_page_extractors(client: MCPClient):
    """
    Example: Using different content extractors.

    Available extractors:
    - trafilatura (default): Good for news articles and blogs
    - readability: Mozilla's readability algorithm
    - custom: Use CSS selectors for specific content
    """
    print("\n" + "-" * 70)
    print("Using Different Extractors")
    print("-" * 70)

    url = "https://example.com"

    print(f"\nURL: {url}")
    print("\nExtractor comparison:")

    for extractor in ["trafilatura", "readability"]:
        print(f"\n  {extractor.upper()} extractor:")
        try:
            result = await client.call_tool("get_page", {"url": url, "extractor": extractor})
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")[:200]
                    print(f"    {text}...")
        except Exception as e:
            print(f"    Error: {e}")


# =============================================================================
# Example 3: Using search_web Tool
# =============================================================================


async def example_search_web_basic(client: MCPClient):
    """
    Example: Basic usage of search_web tool.

    The search_web tool:
    1. Sends your query to SearXNG (a privacy-respecting metasearch engine)
    2. Fetches up to 30 results
    3. Re-ranks results using BM25 relevance to your query
    4. Returns the top 5 most relevant results

    Prerequisites:
    - A running SearXNG instance
    - Set SEARXNG_URL environment variable (default: http://localhost:8080)

    Expected output:
        - List of search results with titles, URLs, and snippets
        - Results ranked by relevance to your query
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Using search_web Tool")
    print("=" * 70)

    query = "Python asyncio tutorial"
    print(f"\nSearching for: '{query}'")
    print("\nNote: Requires SearXNG running at SEARXNG_URL (default: localhost:8080)")

    try:
        result = await client.call_tool("search_web", {"query": query})

        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                print("\nSearch results:")
                print("-" * 40)
                print(text[:1000] + "..." if len(text) > 1000 else text)
        elif "error" in result:
            print(f"Error: {result['error']}")

    except httpx.ConnectError:
        print("\nError: Could not connect to MCP server.")
        print("Make sure the server is running: uv run python -m web_mcp.server --http")
    except Exception as e:
        print(f"Error: {e}")


async def example_search_web_research(client: MCPClient):
    """
    Example: Using search_web for research queries.

    The BM25 re-ranking helps surface the most relevant results
    even if the search engine returns them in a different order.
    """
    print("\n" + "-" * 70)
    print("Search for Research Topics")
    print("-" * 70)

    queries = [
        "MCP protocol model context protocol",
        "FastMCP Python framework",
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        try:
            result = await client.call_tool("search_web", {"query": query})
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    lines = text.split("\n")[:10]
                    print("\n".join(lines))
        except Exception as e:
            print(f"  Error: {e}")


# =============================================================================
# Example 4: Using create_chart_tool
# =============================================================================


async def example_create_chart_basic(client: MCPClient):
    """
    Example: Basic usage of create_chart_tool.

    The create_chart_tool generates interactive Plotly charts.
    Output formats:
    - html: Returns full HTML (default)
    - url: Returns a URL to view the chart (requires WEB_MCP_PUBLIC_URL)
    - image: Returns a PNG image URL (requires WEB_MCP_PUBLIC_URL)

    Supported chart types:
    - line, bar, scatter, pie, area, histogram
    - box, heatmap, treemap, sunburst, funnel
    - gauge, indicator, bubble
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Using create_chart_tool")
    print("=" * 70)

    chart_config = {
        "type": "bar",
        "title": "Monthly Sales Data",
        "x_label": "Month",
        "y_label": "Revenue ($)",
        "data": {
            "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "y": [1200, 1900, 1500, 2200, 2800, 2400],
        },
        "output": "html",
    }

    print("\nCreating a bar chart...")
    print(f"Chart type: {chart_config['type']}")
    print(f"Title: {chart_config['title']}")

    try:
        result = await client.call_tool("create_chart_tool", chart_config)

        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                html = content[0].get("text", "")
                print("\nGenerated HTML (first 500 chars):")
                print("-" * 40)
                print(html[:500] + "..." if len(html) > 500 else html)

                # Save to file
                output_path = "/tmp/example_chart.html"
                with open(output_path, "w") as f:
                    f.write(html)
                print(f"\nFull chart saved to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")


async def example_create_chart_various_types(client: MCPClient):
    """
    Example: Creating different chart types.
    """
    print("\n" + "-" * 70)
    print("Various Chart Types")
    print("-" * 70)

    chart_examples = [
        {
            "name": "Line Chart",
            "config": {
                "type": "line",
                "title": "Temperature Trend",
                "x_label": "Day",
                "y_label": "Temperature (°C)",
                "data": {
                    "x": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                    "y": [20, 22, 19, 24, 26],
                },
                "output": "html",
            },
        },
        {
            "name": "Pie Chart",
            "config": {
                "type": "pie",
                "title": "Market Share",
                "data": {
                    "labels": ["Chrome", "Firefox", "Safari", "Edge"],
                    "values": [65, 15, 12, 8],
                },
                "output": "html",
            },
        },
        {
            "name": "Scatter Plot",
            "config": {
                "type": "scatter",
                "title": "Correlation Analysis",
                "x_label": "X Values",
                "y_label": "Y Values",
                "data": {
                    "x": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                    "y": [2, 4, 5, 4, 5, 7, 8, 9, 10, 12],
                },
                "output": "html",
            },
        },
    ]

    for example in chart_examples:
        print(f"\n{example['name']}:")
        try:
            result = await client.call_tool("create_chart_tool", example["config"])
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    html = content[0].get("text", "")
                    print(f"  Generated {len(html)} bytes of HTML")

                    # Save chart
                    filename = example["name"].lower().replace(" ", "_")
                    with open(f"/tmp/{filename}.html", "w") as f:
                        f.write(html)
                    print(f"  Saved to: /tmp/{filename}.html")
        except Exception as e:
            print(f"  Error: {e}")


async def example_create_chart_with_options(client: MCPClient):
    """
    Example: Creating charts with custom styling options.
    """
    print("\n" + "-" * 70)
    print("Chart with Custom Styling")
    print("-" * 70)

    config = {
        "type": "bar",
        "title": "Styled Bar Chart",
        "x_label": "Category",
        "y_label": "Value",
        "data": {
            "x": ["A", "B", "C", "D"],
            "y": [10, 20, 15, 25],
        },
        "options": {
            "width": 800,
            "height": 500,
            "template": "plotly_dark",
            "colors": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"],
        },
        "output": "html",
    }

    print("\nCreating chart with dark theme and custom colors...")

    try:
        result = await client.call_tool("create_chart_tool", config)
        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                html = content[0].get("text", "")
                with open("/tmp/styled_chart.html", "w") as f:
                    f.write(html)
                print("Saved styled chart to: /tmp/styled_chart.html")
    except Exception as e:
        print(f"Error: {e}")


# =============================================================================
# Example 5: Error Handling
# =============================================================================


async def example_error_handling(client: MCPClient):
    """
    Example: Proper error handling for all tools.

    Common errors:
    - Connection errors (server not running)
    - Invalid URLs (malformed, private IPs blocked)
    - Fetch errors (timeouts, 404s, etc.)
    - Chart errors (invalid data, missing fields)
    - Search errors (SearXNG not available)
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Error Handling")
    print("=" * 70)

    # Test 1: Invalid URL
    print("\n1. Testing with invalid URL:")
    try:
        result = await client.call_tool("get_page", {"url": "not-a-valid-url"})
        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                print(f"  Result: {content[0].get('text', 'No message')[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # Test 2: Non-existent URL
    print("\n2. Testing with non-existent URL:")
    try:
        result = await client.call_tool(
            "get_page", {"url": "https://this-domain-does-not-exist-12345.com"}
        )
        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                print(f"  Result: {content[0].get('text', 'No message')[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # Test 3: Invalid chart type
    print("\n3. Testing with invalid chart type:")
    try:
        result = await client.call_tool(
            "create_chart_tool",
            {"type": "invalid_type", "data": {"x": [1, 2], "y": [3, 4]}, "output": "html"},
        )
        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                print(f"  Result: {content[0].get('text', 'No message')[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # Test 4: URL output without WEB_MCP_PUBLIC_URL
    print("\n4. Testing URL output without WEB_MCP_PUBLIC_URL:")
    try:
        result = await client.call_tool(
            "create_chart_tool",
            {
                "type": "bar",
                "data": {"x": [1, 2], "y": [3, 4]},
                "output": "url",
            },
        )
        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                print(f"  Result: {content[0].get('text', 'No message')[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # Test 5: Search without SearXNG
    print("\n5. Testing search (may fail if SearXNG not running):")
    try:
        result = await client.call_tool("search_web", {"query": "test"})
        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                if "failed" in text.lower() or "error" in text.lower():
                    print("  Search failed (expected if SearXNG not running)")
                else:
                    print("  Search succeeded!")
    except Exception as e:
        print(f"  Exception: {e}")


async def example_error_handling_patterns():
    """
    Example: Recommended error handling patterns.
    """
    print("\n" + "-" * 70)
    print("Recommended Error Handling Patterns")
    print("-" * 70)

    print("""
# Pattern 1: Check for error messages in response
result = await client.call_tool("get_page", {"url": url})
if "result" in result:
    content = result["result"].get("content", [])
    if content:
        text = content[0].get("text", "")
        if text.startswith("Error:"):
            print(f"Tool returned error: {text}")
        else:
            print(f"Success: {text[:100]}")

# Pattern 2: Handle connection errors
try:
    result = await client.call_tool("get_page", {"url": url})
except httpx.ConnectError:
    print("Server not running. Start with: uv run python -m web_mcp.server --http")
except httpx.TimeoutException:
    print("Request timed out")
except httpx.HTTPStatusError as e:
    print(f"HTTP error: {e.response.status_code}")

# Pattern 3: Validate inputs before calling tools
def validate_url(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

if not validate_url(user_url):
    print("Invalid URL format")
else:
    result = await client.call_tool("get_page", {"url": user_url})

# Pattern 4: Retry with exponential backoff
async def call_with_retry(client, tool_name, args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await client.call_tool(tool_name, args)
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise
""")


# =============================================================================
# Example 6: Health Check and Monitoring
# =============================================================================


async def example_health_check(client: MCPClient):
    """
    Example: Using the health tool to monitor server status.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Health Check and Monitoring")
    print("=" * 70)

    try:
        result = await client.call_tool("health", {})

        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                print("\nServer Health Metrics:")
                print("-" * 40)
                try:
                    data = json.loads(text)
                    for key, value in data.items():
                        print(f"  {key}: {value}")
                except json.JSONDecodeError:
                    print(text)

    except Exception as e:
        print(f"Error: {e}")


# =============================================================================
# Example 7: Direct Tool Usage (without HTTP)
# =============================================================================


async def example_direct_tool_usage():
    """
    Example: Using tools directly without the MCP server.

    This is useful for:
    - Testing during development
    - Embedding in other applications
    - Batch processing scripts
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Direct Tool Usage (without MCP server)")
    print("=" * 70)

    print("""
# Import and use tools directly in your Python code:

import asyncio
from web_mcp.fetcher import fetch_url_with_fallback
from web_mcp.extractors.trafilatura import TrafilaturaExtractor
from web_mcp.config import get_config

async def fetch_and_extract(url: str) -> str:
    config = get_config()
    extractor = TrafilaturaExtractor()

    # Fetch the HTML
    html = await fetch_url_with_fallback(url, config)

    # Extract main content
    result = await extractor.extract(html, url)

    return result.text

# Run it
content = asyncio.run(fetch_and_extract("https://example.com"))
print(content)

# For search functionality:
from web_mcp.searxng import search

async def search_web(query: str):
    results = await search(query, max_results=10)
    return results

results = asyncio.run(search_web("Python asyncio"))
for r in results:
    print(f"{r['title']}: {r['url']}")

# For chart generation:
from web_mcp.charts import ChartConfig, create_chart

config = ChartConfig(
    type="bar",
    title="My Chart",
    data={"x": [1, 2, 3], "y": [4, 5, 6]},
)
html = create_chart(config)
with open("chart.html", "w") as f:
    f.write(html)
""")


# =============================================================================
# Main Entry Point
# =============================================================================


async def run_examples():
    """Run all examples."""
    print("=" * 70)
    print("Web MCP - Basic Usage Examples")
    print("=" * 70)

    # Example 1: Server startup info
    example_start_server_subprocess()
    example_start_server_programmatic()

    # Create client
    client = MCPClient(MCP_SERVER_URL)

    # Check if server is running
    print("\n" + "=" * 70)
    print("Checking server connection...")
    print("=" * 70)

    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            response = await http_client.get(f"{MCP_SERVER_URL}/health")
            if response.status_code == 200:
                print(f"Server is running at {MCP_SERVER_URL}")
            else:
                print(f"Server responded with status {response.status_code}")
    except httpx.ConnectError:
        print(f"\nCannot connect to server at {MCP_SERVER_URL}")
        print("\nTo start the server, run:")
        print("  uv run python -m web_mcp.server --http")
        print("\nSome examples will show errors until the server is started.")
        print("Continuing with examples...\n")

    # Run examples
    await example_get_page_basic(client)
    await example_get_page_with_query(client)
    await example_get_page_extractors(client)
    await example_search_web_basic(client)
    await example_search_web_research(client)
    await example_create_chart_basic(client)
    await example_create_chart_various_types(client)
    await example_create_chart_with_options(client)
    await example_error_handling(client)
    await example_error_handling_patterns()
    await example_health_check(client)
    await example_direct_tool_usage()

    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)
    print("\nGenerated files saved to /tmp/:")
    print("  - example_chart.html")
    print("  - line_chart.html")
    print("  - pie_chart.html")
    print("  - scatter_plot.html")
    print("  - styled_chart.html")


if __name__ == "__main__":
    asyncio.run(run_examples())
