# Development Guide

## Overview

This guide covers setting up the development environment, running tests, and contributing to the Web Browsing MCP Server.

## Prerequisites

- Python 3.12+
- `uv` (recommended) or `pip`
- `httpx`, `trafilatura`, `beautifulsoup4` dependencies

## Installation

### Using uv (Recommended)

```bash
# Initialize project
uv init --name web-mcp

# Add dependencies
uv add mcp trafilatura httpx beautifulsoup4

# Add dev dependencies
uv add --dev pytest
```

### Using pip

```bash
pip install mcp trafilatura httpx beautifulsoup4
pip install pytest --dev
```

## Project Structure

```
web_mcp/
├── src/web_mcp/          # Main source code
│   ├── __init__.py       # Package initialization
│   ├── __main__.py       # CLI entry point
│   ├── server.py         # MCP server and tools
│   ├── config.py         # Configuration management
│   ├── fetcher.py        # URL fetching
│   ├── optimizer.py      # Token estimation & truncation
│   ├── security.py       # Security utilities
│   ├── searxng.py      # SearXNG integration
│   ├── cache.py          # LRU caching
│   ├── logging.py        # Logging setup
│   ├── logging_utils.py  # Logging utilities
│   ├── extractors/       # Content extraction modules
│   │   ├── __init__.py
│   │   ├── base.py       # Base extractor interface
│   │   ├── trafilatura.py
│   │   ├── readability.py
│   │   └── custom.py
│   ├── llm/            # LLM integration
│   │   ├── __init__.py
│   │   ├── client.py     # OpenAI-compatible API client
│   │   ├── config.py     # LLM configuration
│   │   └── embeddings.py # Embedding operations
│   └── research/       # Research pipeline
│       ├── __init__.py
│       ├── pipeline.py   # Main research orchestration
│       ├── citations.py  # Citation formatting
│       ├── chunker.py    # Text chunking
│       └── reranking.py  # Result reranking
├── docs/               # Documentation
│   ├── index.md
│   ├── architecture.md
│   ├── configuration.md
│   ├── usage.md
│   ├── extractors.md
│   └── development.md
├── plans/              # Project planning
├── .env.example        # Environment template
├── pyproject.toml      # Project configuration
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
└── test_fetch.py       # Test script
```

## Running the Server

### Development Mode

```bash
# Using uv
uv run python -m web_mcp.server

# Or directly
python src/web_mcp/server.py

# With custom host/port
WEB_MCP_SERVER_HOST=0.0.0.0 WEB_MCP_SERVER_PORT=8000 uv run python -m web_mcp.server
```

### Transport Modes

```bash
# stdio mode (default)
uv run python -m web_mcp.server

# SSE transport
uv run python -m web_mcp.server --sse

# HTTP transport
uv run python -m web_mcp.server --http
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest test_fetch.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src/web_mcp
```

### Test Structure

```python
# test_fetch.py - Example test structure
import pytest
from web_mcp.fetcher import fetch_url, FetchError

@pytest.mark.asyncio
async def test_fetch_success():
    """Test successful URL fetching."""
    pass

@pytest.mark.asyncio
async def test_fetch_error():
    """Test error handling for invalid URLs."""
    pass

@pytest.mark.asyncio
async def test_timeout():
    """Test request timeout handling."""
    pass
```

## Adding New Features

### 1. Add New Extractor

1. Create `src/web_mcp/extractors/new_extractor.py`:
```python
from .base import ContentExtractor, ExtractedContent

class NewExtractor(ContentExtractor):
    name = "new_extractor"
    
    async def extract(self, html: str, url: str) -> ExtractedContent:
        # Implementation
```

2. Register in `src/web_mcp/extractors/__init__.py`:
```python
from .new_extractor import NewExtractor

__all__ = [..., "NewExtractor"]
```

### 2. Add New Tool

1. Add tool function in `src/web_mcp/server.py`:
```python
@mcp.tool()
async def new_tool(param: str = Field(description="Parameter")) -> str:
    """Tool description."""
    # Implementation
```

2. Update server instructions in `FastMCP` initialization

### 3. Add New Module

1. Create module directory: `src/web_mcp/new_module/`
2. Add `__init__.py`:
```python
from .module import SomeClass, some_function

__all__ = ["SomeClass", "some_function"]
```

## Code Style

### Python Conventions

- Use type hints
- Follow PEP 8 style guide
- Add docstrings to functions and classes
- Use f-strings for string formatting

### Example Code

```python
"""Module description."""

from typing import Optional

from web_mcp.logging_utils import get_logger

logger = get_logger(__name__)


class MyClass:
    """Class description."""
    
    def __init__(self, param: str) -> None:
        """Initialize the class.
        
        Args:
            param: Parameter description
        """
        self.param = param
    
    def method(self, value: int) -> str:
        """Method description.
        
        Args:
            value: Value to process
            
        Returns:
            Processed result
        """
        return f"Result: {value}"
```

## Docker Development

### Build Image

```bash
docker build -t web-mcp-dev .
```

### Run Container

```bash
# With environment variables
docker run --env-file .env -p 8000:8000 web-mcp-dev

# With interactive shell
docker run -it --env-file .env -p 8000:8000 web-mcp-dev /bin/bash
```

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Environment Variables for Development

```bash
# Enable debug logging
WEB_MCP_LOG_LEVEL=DEBUG

# Enable token estimation
WEB_MCP_ENABLE_TOKEN_ESTIMATION=true

# Set context limit
WEB_MCP_CONTEXT_LIMIT=120000
```

## Debugging

### Logging

```python
from web_mcp.logging_utils import get_logger

logger = get_logger(__name__)
logger.info("Debug message")
logger.error("Error message")
```

### Common Issues

1. **Connection Pool Errors**
   - Ensure connection pool is initialized
   - Check for proper async/await usage

2. **Extraction Errors**
   - Verify HTML content is valid
   - Check extractor configuration

3. **LLM Errors**
   - Verify API key is set
   - Check API endpoint configuration

## Performance Optimization

### Connection Pooling

```python
from web_mcp.fetcher import get_connection_pool, close_connection_pool

# Use shared connection pool
pool = get_connection_pool()

# Close on shutdown
await close_connection_pool()
```

### Caching

```python
from web_mcp.cache import get_cache, LRUCache

cache = get_cache()
# Cache is automatically used in fetch_url_cached
```

### Token Estimation

```python
from web_mcp.optimizer import estimate_tokens, optimize_content

# Estimate tokens
tokens = estimate_tokens("text")

# Optimize content
result = optimize_content(text, max_tokens, config)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT - See LICENSE file for details.
