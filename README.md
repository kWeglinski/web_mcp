# Web Browsing MCP Server

A Model Context Protocol (MCP) server that enables models to browse the web with intelligent content extraction and context optimization.

## Features

- **Trafilatura-based Extraction**: Uses Trafilatura for high-quality content extraction
- **Extensible Architecture**: Easy to add new extractors (Readability, custom selectors)
- **Context Optimization**: Token estimation and smart truncation
- **Configurable Limits**: Environment variable for context limit (default: 120k tokens)

## Installation

```bash
# Initialize project with uv
uv init --name web-mcp
uv add mcp trafilatura httpx beautifulsoup4

# Or install dependencies
pip install mcp trafilatura httpx beautifulsoup4
```

## Configuration

Set environment variables in `.env` or your system:

```bash
# Context limit (default: 120000 tokens)
WEB_MCP_CONTEXT_LIMIT=120000

# Request timeout in seconds (default: 30)
WEB_MCP_REQUEST_TIMEOUT=30

# Default extractor (trafilatura or readability)
WEB_MCP_DEFAULT_EXTRACTOR=trafilatura

# Include metadata in output (default: true)
WEB_MCP_INCLUDE_METADATA=true

# Include links in extraction (default: false)
WEB_MCP_INCLUDE_LINKS=false

# Enable token estimation (default: true)
WEB_MCP_ENABLE_TOKEN_ESTIMATION=true

# Truncation strategy: smart or simple (default: smart)
WEB_MCP_TRUNCATION_STRATEGY=smart
```

## Usage

### Running the Server

```bash
# Using uv
uv run python -m web_mcp.server

# Or directly
python src/web_mcp/server.py
```

### MCP Tools

#### `fetch_url`
Fetch and extract content from a URL with full metadata.

**Parameters:**
- `url` (required): The URL to fetch
- `max_tokens` (optional, default: 120000): Maximum tokens in output
- `include_metadata` (optional, default: true): Include title, author, date
- `extractor` (optional, default: "trafilatura"): Extractor to use ("trafilatura", "readability", or "custom")

**Returns:** `FetchResult` with:
- `url`: The fetched URL
- `title`: Page title (if available)
- `author`: Author name (if available)
- `date`: Publication date (if available)
- `language`: Detected language (if available)
- `text`: Extracted content
- `estimated_tokens`: Token count
- `truncated`: Whether content was truncated

#### `fetch_url_simple`
Simplified version that returns only text content.

**Parameters:**
- `url` (required): The URL to fetch
- `max_tokens` (optional, default: 120000): Maximum tokens in output

**Returns:** Extracted text string

### Example Tool Call

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

### Extending with New Extractors

Create a new extractor class:

```python
from .base import ContentExtractor, ExtractedContent

class CustomExtractor(ContentExtractor):
    name = "custom"
    
    async def extract(self, html: str, url: str) -> ExtractedContent:
        # Your extraction logic
        return ExtractedContent(
            title="...",
            author=None,
            date=None,
            language=None,
            text="...",
            url=url,
            metadata={}
        )
```

Add to the registry in `extractors/__init__.py`:

```python
from .custom import CustomExtractor

__all__ = [
    # ... existing extractors
    "CustomExtractor",
]
```

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [Overview](docs/index.md) | Quick start and overview |
| [Architecture](docs/architecture.md) | System architecture and modules |
| [Configuration](docs/configuration.md) | Environment variables and settings |
| [Usage](docs/usage.md) | Tool usage examples |
| [Extractors](docs/extractors.md) | Content extraction strategies |
| [Research Pipeline](docs/research.md) | AI-powered research with citations |
| [LLM Integration](docs/llm-integration.md) | LLM configuration and usage |
| [Development](docs/development.md) | Development setup and contributing |

## Project Structure

```
web_mcp/
├── src/web_mcp/          # Main source code
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── fetcher.py        # URL fetching with httpx
│   ├── optimizer.py      # Token estimation & truncation
│   ├── security.py       # Security utilities
│   ├── searxng.py      # SearXNG integration
│   ├── cache.py          # LRU caching
│   ├── logging.py        # Logging setup
│   ├── logging_utils.py  # Logging utilities
│   ├── extractors/       # Content extraction modules
│   │   ├── base.py      # Base extractor interface
│   │   ├── trafilatura.py
│   │   ├── readability.py
│   │   └── custom.py
│   ├── llm/            # LLM integration
│   │   ├── client.py    # OpenAI-compatible API client
│   │   ├── config.py    # LLM configuration
│   │   └── embeddings.py
│   ├── research/         # Research pipeline
│   │   ├── pipeline.py  # Main orchestration
│   │   ├── citations.py # Citation formatting
│   │   ├── chunker.py   # Text chunking
│   │   └── reranking.py # Result reranking
│   └── server.py         # MCP server with tools
├── docs/                 # Documentation
│   ├── README.md
│   ├── index.md
│   ├── architecture.md
│   ├── configuration.md
│   ├── usage.md
│   ├── extractors.md
│   ├── research.md
│   ├── llm-integration.md
│   └── development.md
├── plans/                # Project planning
├── .env.example          # Environment template
├── README.md
└── pyproject.toml
```

## Development

```bash
# Install dependencies
uv add mcp trafilatura httpx beautifulsoup4

# Run tests
pytest

# Build for production
uv build
```

## License

MIT
