# Web MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/YOUR_USERNAME/web_mcp/workflows/CI/badge.svg)](https://github.com/YOUR_USERNAME/web_mcp/actions)
[![Coverage](https://img.shields.io/badge/coverage-60%25-green.svg)](https://github.com/YOUR_USERNAME/web_mcp)
[![Docker](https://img.shields.io/docker/v/kweg/mcp-basics/latest?label=docker)](https://hub.docker.com/r/kweg/mcp-basics)
[![Docker Pulls](https://img.shields.io/docker/pulls/kweg/mcp-basics.svg)](https://hub.docker.com/r/kweg/mcp-basics)
[![Docker Image Size](https://img.shields.io/docker/image-size/kweg/mcp-basics/latest)](https://hub.docker.com/r/kweg/mcp-basics)

A Model Context Protocol (MCP) server providing web browsing, search, chart generation, JavaScript execution, and AI-powered knowledge gathering capabilities.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/web_mcp.git
cd web_mcp

# Install dependencies
uv sync

# Run the server (stdio mode - default)
uv run python -m web_mcp.server

# Or with SSE transport
uv run python -m web_mcp.server --sse

# Or with HTTP transport
uv run python -m web_mcp.server --http
```

## Features

- **Content Extraction**: Trafilatura, Readability, and custom extractors
- **Playwright Fallback**: Automatic fallback for JavaScript-heavy pages
- **Web Search**: SearXNG and Brave integration with BM25 reranking
- **Interactive Charts**: 14 Plotly chart types with HTML/URL/image output
- **JavaScript Execution**: Sandboxed V8 runtime with fetch support
- **Smart Truncation**: Token estimation and intelligent content truncation
- **LRU Caching**: Configurable cache with TTL support
- **Bearer Authentication**: Optional token-based security
- **AI Knowledge Gatherer**: Search, extract, dedup, and store grounded facts with Mem0
- **Persistent Memory**: Semantic search and retrieval via Mem0 + ChromaDB
- **Admin Panel**: Web UI for configuration and tool management

## Installation

```bash
# Using uv (recommended)
uv sync

# Install Playwright browsers
uv run web-mcp-install

# Or manually
uv run python -m web_mcp.playwright_fetcher
```

### Knowledge Gatherer Setup

The Knowledge Gatherer uses Mem0 for persistent memory storage with semantic search. Before using knowledge features, configure the following:

```bash
# LLM model for fact extraction (default: gpt-4o)
export WEB_MCP_KNOWLEDGE_EXTRACT_MODEL=gpt-4o

# Mem0 configuration
export WEB_MCP_MEM0_LLM_MODEL=llama3:8b
export WEB_MCP_MEM0_BASE_URL=http://host.docker.internal:1234/v1
export WEB_MCP_MEM0_EMBED_MODEL=BAAI/bge-small-en-v1.5
export WEB_MCP_MEM0_API_KEY=local-secret
export WEB_MCP_MEM0_CHROMA_PATH=/app/chroma_db

# Knowledge gathering thresholds
export WEB_MCP_KNOWLEDGE_MAX_FACTS=20
export WEB_MCP_KNOWLEDGE_MIN_CONFIDENCE=0.7
export WEB_MCP_KNOWLEDGE_TTL_DAYS=90
export WEB_MCP_KNOWLEDGE_MAX_COLLECTION_SIZE=500
export WEB_MCP_KNOWLEDGE_CLEANUP_INTERVAL=3600
export WEB_MCP_KNOWLEDGE_SEMANTIC_THRESHOLD=0.85
```

**Requirements:**

- An OpenAI-compatible LLM endpoint (e.g., llamafile, vLLM, or OpenAI API)
- HuggingFace embeddings model (downloaded automatically via `langchain_huggingface`)
- ChromaDB for vector storage (configured via `WEB_MCP_MEM0_CHROMA_PATH`)

The knowledge gatherer pipeline: validate topic -> search -> fetch -> extract facts -> semantic dedup -> store in Mem0.

## Entry Points

| Command | Description |
|---------|-------------|
| `web-mcp` | Run the MCP server |
| `web-mcp-install` | Install Playwright browsers |

## MCP Tools

### 1. get_page

Fetch and extract content from URLs with optional BM25-ranked filtering.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `url` | string | Yes | - | URL to fetch |
| `query` | string | No | - | Query for BM25-ranked chunk retrieval |
| `extractor` | string | No | trafilatura | Extractor: trafilatura, readability, custom |

**Features:**
- Supports Trafilatura, Readability, and custom extractors
- Automatic Playwright fallback for JS-heavy pages
- BM25-ranked chunk retrieval when query provided

### 2. search_web

Search the web via SearXNG with BM25 reranking.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query |

**Returns:** Top 5 results ranked by BM25 relevance.

### 3. brave_search

Search the web via Brave Search API.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query |

### 4. create_chart_tool

Generate interactive Plotly charts with multiple output formats.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `type` | string | Yes | - | Chart type |
| `data` | object | Yes | - | Chart data |
| `title` | string | No | - | Chart title |
| `x_label` | string | No | - | X-axis label |
| `y_label` | string | No | - | Y-axis label |
| `options` | object | No | - | Additional chart options |
| `output` | string | No | html | Output format: html, url, image |

**Supported Chart Types (14):**
- `line`, `bar`, `scatter`, `pie`, `area`
- `histogram`, `box`, `heatmap`
- `treemap`, `sunburst`, `funnel`
- `gauge`, `indicator`, `bubble`

**Output Formats:**
- `html` - Full HTML document
- `url` - Viewable URL (requires `WEB_MCP_PUBLIC_URL`)
- `image` - PNG image (uses Kaleido)

### 5. render_html

Store HTML content and return a viewable URL.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `html` | string | Yes | - | HTML content to render |
| `content_type` | string | No | text/html | MIME content type |

**Notes:**
- Requires `WEB_MCP_PUBLIC_URL` environment variable
- Content expires after 1 hour (`WEB_MCP_CONTENT_TTL`)

### 6. run_javascript

Execute JavaScript in a sandboxed V8 runtime.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `code` | string | Yes | - | JavaScript code to execute |
| `timeout_ms` | number | No | 5000 | Execution timeout in milliseconds |
| `context` | object | No | {} | Variables to inject into sandbox |

**Features:**
- Sandboxed execution via mini-racer
- Supports async/await
- Built-in `fetch()` with SSRF protection
- URL validation and private IP blocking
- Configurable limits (max requests, response size, total bytes)

### 7. current_datetime

Get the current date and time.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `timezone` | string | No | UTC | Timezone (e.g., UTC, America/New_York) |
| `format` | string | No | iso | Output format: iso, unix, readable |

### 8. health

Check server health and statistics.

**Returns:**
- `status` - Server status
- `version` - Server version
- `cache_hit_rate` - Cache hit rate percentage
- `request_count` - Total requests served
- `uptime_seconds` - Server uptime in seconds

### 9. add_memory

Add a memory with content for a specific user. Powered by Mem0 with semantic storage.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | - | Unique identifier for the user |
| `content` | string | Yes | - | The text content to extract memories from |

### 10. search_memory

Perform semantic search across stored memories for a user.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | - | Unique identifier for the user |
| `query` | string | Yes | - | The semantic query to search for |

**Returns:** List of relevant memory snippets with similarity scores.

### 11. get_user_memories

Retrieve the full history of stored memories for a user.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | - | Unique identifier for the user |

**Returns:** Complete list of memories with metadata.

### 12. gather_knowledge

Run the full knowledge gathering pipeline for a topic.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `topic` | string | Yes | - | The topic to gather knowledge about |
| `max_search_results` | int | No | 5 | Max URLs to search for |
| `categories` | string[] | No | - | Filter to specific categories |

**Returns:** KnowledgeResult with gathered facts, sources, categories, and dedup stats.

## Configuration

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_CONTEXT_LIMIT` | 120000 | Token limit for content |
| `WEB_MCP_REQUEST_TIMEOUT` | 30 | Request timeout in seconds |
| `WEB_MCP_DEFAULT_EXTRACTOR` | trafilatura | Default extractor (trafilatura/readability/custom) |
| `WEB_MCP_INCLUDE_METADATA` | true | Include metadata in output |
| `WEB_MCP_INCLUDE_LINKS` | false | Include links in extraction |
| `WEB_MCP_INCLUDE_COMMENTS` | false | Include comments in extraction |
| `WEB_MCP_ENABLE_TOKEN_ESTIMATION` | true | Enable token estimation |
| `WEB_MCP_TRUNCATION_STRATEGY` | smart | Truncation strategy (smart/simple) |
| `WEB_MCP_USER_AGENT` | WebMCP/1.0... | Custom user agent string |
| `WEB_MCP_MAX_CONTENT_LENGTH` | 10485760 | Max content length (10MB) |
| `WEB_MCP_CACHE_TTL` | 3600 | Cache TTL in seconds |

### Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_SERVER_HOST` | 0.0.0.0 | Server bind host |
| `WEB_MCP_SERVER_PORT` | 8000 | Server bind port |
| `WEB_MCP_PUBLIC_URL` | - | Public URL for render_html and chart URLs |
| `WEB_MCP_AUTH_TOKEN` | - | Bearer token for authentication |
| `WEB_MCP_CONTENT_TTL` | 3600 | Content store TTL in seconds |
| `WEB_MCP_OUTPUT_SCHEMAS` | false | Enable structured output schemas |

### SearXNG

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_SEARXNG_URL` | - | SearXNG instance URL |

### Brave Search

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_BRAVE_API_KEY` | - | Brave Search API key |

### Playwright

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_PLAYWRIGHT_ENABLED` | true | Enable Playwright fallback |
| `WEB_MCP_PLAYWRIGHT_TIMEOUT` | 30000 | Playwright timeout in ms |
| `WEB_MCP_PLAYWRIGHT_FALLBACK_THRESHOLD` | 500 | Content length threshold for fallback |

### JavaScript Execution

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_JS_FETCH_MAX_RESPONSE_SIZE` | 5242880 | Max fetch response size (5MB) |
| `WEB_MCP_JS_FETCH_MAX_REQUESTS` | 10 | Max fetch requests per execution |
| `WEB_MCP_JS_FETCH_MAX_TOTAL_BYTES` | 10485760 | Max total bytes fetched (10MB) |
| `WEB_MCP_JS_FETCH_TIMEOUT` | 10000 | Fetch timeout in ms |
| `WEB_MCP_JS_FETCH_VERIFY_SSL` | true | Verify SSL certificates |
| `WEB_MCP_JS_EXECUTION_TIMEOUT` | 30000 | JS execution timeout in ms |

### Anti-Bot Evasion

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_REQUEST_DELAY_MIN` | 0.3 | Minimum request delay (seconds) |
| `WEB_MCP_REQUEST_DELAY_MAX` | 1.5 | Maximum request delay (seconds) |
| `WEB_MCP_TLS_CLIENT_IDENTIFIER` | chrome120 | TLS client fingerprint |
| `WEB_MCP_REFERER` | - | Referer header |
| `WEB_MCP_PROXY_URL` | - | Proxy URL |

### Admin Panel

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_ADMIN_ENABLED` | false | Enable admin panel |
| `WEB_MCP_ADMIN_API_KEY` | - | Admin API key |
| `WEB_MCP_ADMIN_PATH` | /admin | Admin panel path |
| `WEB_MCP_ADMIN_CONFIG_FILE` | /data/mcp-admin-config.json | Config file path |

### Mem0 (Knowledge Storage)

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_MEM0_LLM_MODEL` | llama3:8b | LLM model for memory processing |
| `WEB_MCP_MEM0_BASE_URL` | http://host.docker.internal:1234/v1 | OpenAI-compatible API endpoint |
| `WEB_MCP_MEM0_EMBED_MODEL` | BAAI/bge-small-en-v1.5 | HuggingFace embedding model |
| `WEB_MCP_MEM0_API_KEY` | local-secret | API key for LLM endpoint |
| `WEB_MCP_MEM0_CHROMA_PATH` | /app/chroma_db | ChromaDB storage path |

### Knowledge Gatherer

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_KNOWLEDGE_EXTRACT_MODEL` | gpt-4o | LLM model for fact extraction |
| `WEB_MCP_KNOWLEDGE_MAX_FACTS` | 20 | Max facts to extract per source |
| `WEB_MCP_KNOWLEDGE_MIN_CONFIDENCE` | 0.7 | Minimum confidence threshold |
| `WEB_MCP_KNOWLEDGE_TTL_DAYS` | 90 | Fact TTL in days |
| `WEB_MCP_KNOWLEDGE_MAX_COLLECTION_SIZE` | 500 | Max collection size |
| `WEB_MCP_KNOWLEDGE_CLEANUP_INTERVAL` | 3600 | Cleanup task interval (seconds) |
| `WEB_MCP_KNOWLEDGE_SEMANTIC_THRESHOLD` | 0.85 | Semantic dedup similarity threshold |

## Transport Modes

| Mode | Command | Description |
|------|---------|-------------|
| stdio | `uv run python -m web_mcp.server` | Default, for local MCP clients |
| SSE | `uv run python -m web_mcp.server --sse` | Server-Sent Events |
| HTTP | `uv run python -m web_mcp.server --http` | Streamable HTTP |

## Docker

### Quick Start with Docker

```bash
docker pull kweg/mcp-basics:latest
docker run -p 8000:8000 kweg/mcp-basics:latest
```

### Available Tags

- `latest` - Latest stable release
- `1.0.0`, `1.0` - Version-specific tags
- `main` - Latest development build

### Multi-Platform Support

- `linux/amd64`
- `linux/arm64` (Apple Silicon, Raspberry Pi, etc.)

### Docker Hub

For more information, visit [Docker Hub - kweg/mcp-basics](https://hub.docker.com/r/kweg/mcp-basics).

## Project Structure

```
web_mcp/
├── src/web_mcp/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py              # Configuration management
│   ├── server.py              # MCP server with tools
│   ├── fetcher.py             # URL fetching with httpx
│   ├── playwright_fetcher.py  # Playwright-based fetching
│   ├── content_store.py       # Content storage for render_html
│   ├── optimizer.py           # Token estimation & truncation
│   ├── security.py            # Security utilities
│   ├── searxng.py             # SearXNG integration
│   ├── brave.py               # Brave Search integration
│   ├── cache.py               # LRU caching
│   ├── logging.py             # Logging setup
│   ├── logging_utils.py       # Logging utilities
│   ├── path_routing.py        # Path-based tool routing
│   ├── mem0/                  # Mem0 persistent memory
│   │   ├── __init__.py        # Mem0Manager (add/list/delete/search)
│   │   └── tools.py           # MCP tools (add_memory, search_memory, get_user_memories)
│   ├── knowledge/             # Knowledge gatherer pipeline
│   │   ├── __init__.py        # Public exports
│   │   ├── pipeline.py        # KnowledgeGatherer orchestration
│   │   ├── extractor.py       # LLM-based fact extraction
│   │   ├── dedup.py           # Exact & semantic deduplication
│   │   ├── categories.py      # Topic classification taxonomy
│   │   ├── validation.py      # Fact quality & topic validation
│   │   └── cleanup.py         # TTL-based cleanup task
│   ├── admin/                 # Admin panel (UI + REST API)
│   │   ├── __init__.py        # Route creation entry point
│   │   ├── router.py          # Admin configuration router
│   │   ├── ui.py              # Admin web UI
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── session_auth.py    # Session-based authentication
│   │   └── storage.py         # Persistent config storage
│   ├── tools/                 # MCP tool implementations
│   │   ├── __init__.py        # Tool registry
│   │   ├── _core.py           # Core tool utilities
│   │   ├── fetching.py        # get_page, render_html
│   │   ├── search.py          # search_web, brave_search, search_metrics
│   │   ├── advanced.py        # create_chart_tool, run_javascript
│   │   └── utils.py           # current_datetime, health
│   ├── extractors/            # Content extraction modules
│   │   ├── __init__.py
│   │   ├── base.py            # Base extractor interface
│   │   ├── trafilatura.py     # Trafilatura extractor
│   │   ├── readability.py     # Readability extractor
│   │   └── custom.py          # Custom selector extractor
│   ├── charts/                # Chart generation
│   │   ├── __init__.py
│   │   └── generator.py       # Plotly chart generator
│   ├── research/              # Research pipeline
│   │   ├── __init__.py
│   │   ├── pipeline.py        # Main orchestration
│   │   ├── bm25.py            # BM25 ranking
│   │   ├── citations.py       # Citation formatting
│   │   ├── chunker.py         # Text chunking
│   │   ├── query_rewriting.py # Query rewriting
│   │   └── reranking.py       # Result reranking
│   ├── llm/                   # LLM integration
│   │   ├── __init__.py
│   │   ├── client.py          # OpenAI-compatible API client
│   │   ├── config.py          # LLM configuration
│   │   ├── embeddings.py      # Embedding generation
│   │   └── embedding_cache.py # Embedding cache
│   └── utils/                 # Utilities
│       └── retry.py           # Retry logic
├── docs/                      # Documentation
├── tests/                     # Test suite
├── pyproject.toml
└── README.md
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `mcp` | Model Context Protocol SDK |
| `httpx` | HTTP client |
| `beautifulsoup4` | HTML parsing |
| `trafilatura` | Content extraction |
| `readability` | Readability extractor |
| `playwright` | Browser automation |
| `plotly` | Chart generation |
| `kaleido` | Static image export |
| `mini-racer` | V8 JavaScript runtime |
| `numpy` | Numerical operations |
| `uvicorn` | ASGI server |
| `mem0ai` | Persistent memory storage |
| `langchain_huggingface` | HuggingFace embeddings |
| `chromadb` | Vector database |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Type check
uv run mypy src/

# Build for production
uv build
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
| [Knowledge Gatherer](docs/knowledge-gatherer.md) | AI-powered fact extraction and storage |
| [Development](docs/development.md) | Development setup and contributing |

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
