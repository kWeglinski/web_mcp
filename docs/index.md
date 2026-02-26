# Web Browsing MCP Server

A Model Context Protocol (MCP) server that enables AI models to browse the web with intelligent content extraction, context optimization, and research capabilities.

## Overview

The Web Browsing MCP Server provides a comprehensive set of tools for web content extraction, search, and AI-powered research. Built with the Model Context Protocol (MCP), it enables language models to:

- **Fetch and Extract Content**: Extract main content from web pages using multiple extraction strategies
- **Search the Web**: Query SearXNG instances for search results
- **Research Questions**: Perform comprehensive research with AI-generated answers and citations
- **Optimize Context**: Automatically truncate content to fit token limits

## Features

### Core Capabilities
- **Trafilatura-based Extraction**: High-quality content extraction using Trafilatura
- **Multiple Extractors**: Support for Trafilatura, Readability, and custom selectors
- **Context Optimization**: Token estimation and smart truncation strategies
- **Caching**: LRU cache for efficient repeated fetches
- **Rate Limiting**: Built-in rate limiting and security features

### Research Features
- **Web Search Integration**: Query SearXNG instances for search results
- **Embedding-based Relevance**: Find most relevant content using embeddings
- **Citation Management**: Automatic citation generation and validation
- **Streaming Answers**: Stream research results as they're generated

### Security Features
- URL validation and sanitization
- Domain whitelisting/blacklisting
- Input sanitization to prevent injection attacks
- Rate limiting for API protection

## Architecture

The server follows a modular architecture:

```
src/web_mcp/
├── server.py          # MCP server and tool definitions
├── config.py          # Configuration management
├── fetcher.py         # URL fetching with httpx
├── optimizer.py       # Token estimation & truncation
├── security.py        # Security utilities
├── searxng.py       # SearXNG search integration
├── cache.py           # LRU caching
├── extractors/        # Content extraction modules
│   ├── base.py       # Base extractor interface
│   ├── trafilatura.py
│   ├── readability.py
│   └── custom.py
├── llm/             # LLM integration
│   ├── client.py     # OpenAI-compatible API client
│   ├── config.py     # LLM configuration
│   └── embeddings.py # Embedding operations
└── research/        # Research pipeline
    ├── pipeline.py   # Main research orchestration
    ├── citations.py  # Citation formatting
    ├── chunker.py    # Text chunking
    └── reranking.py  # Result reranking
```

## Quick Start

### Installation

```bash
# Initialize project with uv
uv init --name web-mcp
uv add mcp trafilatura httpx beautifulsoup4

# Or with pip
pip install mcp trafilatura httpx beautifulsoup4
```

### Running the Server

```bash
# Using uv
uv run python -m web_mcp.server

# Or directly
python src/web_mcp/server.py

# With custom host/port
WEB_MCP_SERVER_HOST=0.0.0.0 WEB_MCP_SERVER_PORT=8000 uv run python -m web_mcp.server
```

### Available Tools

| Tool | Description |
|------|-------------|
| `health` | Get server health metrics |
| `fetch_url` | Fetch and extract content from a URL with full metadata |
| `fetch_url_simple` | Simplified version returning only text content |
| `web_search` | Search the web using SearXNG |
| `ask` | Research a question with AI-generated answer and citations |
| `ask_stream` | Stream research results as they're generated |

## Configuration

See the [Configuration Guide](configuration.md) for detailed configuration options.

### Environment Variables

```bash
# Server settings
WEB_MCP_SERVER_HOST=0.0.0.0
WEB_MCP_SERVER_PORT=8000

# Context settings
WEB_MCP_CONTEXT_LIMIT=120000
WEB_MCP_REQUEST_TIMEOUT=30

# Extractor settings
WEB_MCP_DEFAULT_EXTRACTOR=trafilatura
WEB_MCP_INCLUDE_METADATA=true

# Search settings
WEB_MCP_SEARXNG_URL=https://searx.example.com

# LLM settings (for research features)
WEB_MCP_LLM_API_KEY=your_api_key
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
WEB_MCP_LLM_MODEL=gpt-4o
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small
```

## Examples

### Fetching a URL

```python
import asyncio
from web_mcp.server import fetch_url

async def main():
    result = await fetch_url(
        url="https://example.com/article",
        max_tokens=4096,
        include_metadata=True
    )
    print(f"Title: {result.title}")
    print(f"Content: {result.text}")

asyncio.run(main())
```

### Web Search

```python
from web_mcp.server import web_search

async def main():
    results = await web_search(
        query="machine learning trends 2024",
        max_results=10,
        fetch_content=False
    )
    for result in results:
        print(f"{result.title}: {result.url}")
```

### Research with AI

```python
from web_mcp.server import ask

async def main():
    result = await ask(
        question="What are the latest developments in quantum computing?",
        max_sources=5,
        search_results=10
    )
    print(f"Answer: {result.answer}")
    for source in result.sources:
        print(f"Source: {source.title} [{source.index}]")
```

## Project Structure

- [`docs/`](../docs/) - Documentation
- [`src/web_mcp/`](../src/web_mcp/) - Main source code
- [`plans/`](../plans/) - Project planning documents

## License

MIT
