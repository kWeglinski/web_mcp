# Usage Guide

## Overview

This guide covers how to use the Web Browsing MCP Server, including all available tools and their parameters.

## Available Tools

### 1. `health`

Get server health metrics including cache hit rate, request count, and uptime.

**Parameters:** None

**Returns:**
```json
{
  "status": "healthy",
  "cache_hit_rate": 0.25,
  "request_count": 100,
  "uptime_seconds": 3600.5
}
```

### 2. `fetch_url`

Fetch and extract content from a URL with full metadata.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | - | The URL to fetch (required) |
| `max_tokens` | integer | 120000 | Maximum tokens in output |
| `include_metadata` | boolean | true | Include title, author, date |
| `extractor` | string | "trafilatura" | Extractor: "trafilatura", "readability", or "custom" |

**Returns:** `FetchResult` with:
- `url`: The fetched URL
- `title`: Page title (if available)
- `author`: Author name (if available)
- `date`: Publication date (if available)
- `language`: Detected language (if available)
- `text`: Extracted content
- `estimated_tokens`: Token count
- `truncated`: Whether content was truncated

**Example:**
```json
{
  "tool": "fetch_url",
  "arguments": {
    "url": "https://example.com/article",
    "max_tokens": 4096,
    "include_metadata": true,
    "extractor": "trafilatura"
  }
}
```

### 3. `fetch_url_simple`

Simplified version that returns only text content.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | - | The URL to fetch (required) |
| `max_tokens` | integer | 120000 | Maximum tokens in output |

**Returns:** Extracted text string

### 4. `web_search`

Search the web using SearXNG.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | - | The search query (required) |
| `max_results` | integer | 10 | Maximum number of results |
| `fetch_content` | boolean | false | Fetch full content for each result |

**Returns:** List of search results with:
- `title`: Page title
- `url`: The URL of the result
- `snippet`: Content preview
- `published_date`: Publication date (if available)
- `score`: Relevance score (if available)

### 5. `ask`

Research a question using web search and AI to provide a grounded answer with citations.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | string | - | The question to research (required) |
| `max_sources` | integer | 5 | Maximum number of sources to use |
| `search_results` | integer | 10 | Number of search results to fetch |

**Returns:** `AskResult` with:
- `answer`: The answer with citation markers [1], [2], etc.
- `sources`: List of cited sources
- `elapsed_ms`: Time taken in milliseconds

### 6. `ask_stream`

Stream research results as they're generated.

**Parameters:** Same as `ask`

**Returns:** String with streamed answer, followed by sources at the end

## Usage Examples

### Python API

```python
import asyncio
from web_mcp.server import fetch_url, web_search, ask

async def main():
    # Fetch a URL
    result = await fetch_url(
        url="https://en.wikipedia.org/wiki/Artificial_intelligence",
        max_tokens=8192,
        include_metadata=True
    )
    print(f"Title: {result.title}")
    print(f"Content: {result.text[:500]}...")
    
    # Search the web
    results = await web_search(
        query="machine learning trends 2024",
        max_results=5,
        fetch_content=False
    )
    for r in results:
        print(f"{r.title}: {r.url}")
    
    # Research a question
    research_result = await ask(
        question="What are the latest developments in quantum computing?",
        max_sources=5,
        search_results=10
    )
    print(f"Answer: {research_result.answer}")
    for source in research_result.sources:
        print(f"[{source.index}] {source.title}")

asyncio.run(main())
```

### MCP Client

```python
from mcp import ClientSession, StdioServerParameters, create_client
import asyncio

async def main():
    # Create MCP client
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "web_mcp.server"]
    )
    
    async with await create_client(server_params) as session:
        # Initialize session
        await session.initialize()
        
        # Call fetch_url tool
        result = await session.call_tool("fetch_url", {
            "url": "https://example.com",
            "max_tokens": 4096
        })
        print(result.content)
        
        # Call web_search tool
        search_result = await session.call_tool("web_search", {
            "query": "AI trends 2024",
            "max_results": 5
        })
        print(search_result.content)

asyncio.run(main())
```

### Command Line

```bash
# Start server in stdio mode
uv run python -m web_mcp.server

# Start server with SSE transport
uv run python -m web_mcp.server --sse

# Start server with HTTP transport
uv run python -m web_mcp.server --http
```

## Response Formats

### Fetch Result

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "author": "John Doe",
  "date": "2024-01-15",
  "language": "en",
  "text": "Extracted content...",
  "estimated_tokens": 1500,
  "truncated": false
}
```

### Search Result

```json
{
  "title": "Search Result Title",
  "url": "https://example.com/article",
  "snippet": "Content preview...",
  "published_date": "2024-01-15",
  "score": 0.95
}
```

### Ask Result

```json
{
  "answer": "Quantum computing is a type of computation...",
  "sources": [
    {
      "index": 1,
      "url": "https://example.com/quantum",
      "title": "Quantum Computing Basics",
      "snippet": "Quantum computing uses quantum mechanics..."
    }
  ],
  "elapsed_ms": 15234
}
```

## Error Handling

### Fetch Errors

```python
from web_mcp.fetcher import FetchError

try:
    result = await fetch_url("https://invalid-url")
except FetchError as e:
    print(f"Fetch error: {e}")
```

### Search Errors

```python
from web_mcp.searxng import SearXNGError

try:
    results = await web_search("query")
except SearXNGError as e:
    print(f"Search error: {e}")
```

### LLM Errors

```python
from web_mcp.llm.client import LLMError

try:
    result = await ask("question")
except LLMError as e:
    print(f"LLM error: {e}")
```

## Best Practices

1. **Set appropriate token limits** based on your use case
2. **Use `fetch_url_simple`** when you don't need metadata
3. **Enable caching** for repeated fetches
4. **Use `ask_stream`** for long research tasks to see progress
5. **Handle errors gracefully** with try/except blocks

## Performance Tips

1. **Connection pooling**: The server uses connection pooling for efficient HTTP requests
2. **Caching**: Enable caching to avoid repeated fetches of the same URL
3. **Token estimation**: Use token estimation to avoid over-fetching content
4. **Streaming**: Use streaming for large research tasks to see results faster
