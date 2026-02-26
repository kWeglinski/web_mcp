# Documentation

Welcome to the Web Browsing MCP Server documentation. This directory contains comprehensive guides for using and developing with the server.

## Documentation Structure

| Document | Description |
|----------|-------------|
| [`index.md`](./index.md) | Overview and quick start guide |
| [`architecture.md`](./architecture.md) | System architecture and module structure |
| [`configuration.md`](./configuration.md) | Configuration options and environment variables |
| [`usage.md`](./usage.md) | Tool usage examples and API reference |
| [`extractors.md`](./extractors.md) | Content extraction strategies |
| [`research.md`](./research.md) | Research pipeline and citation system |
| [`llm-integration.md`](./llm-integration.md) | LLM integration and configuration |
| [`development.md`](./development.md) | Development setup and contribution guide |

## Quick Start

### 1. Installation

```bash
uv init --name web-mcp
uv add mcp trafilatura httpx beautifulsoup4
```

### 2. Configuration

```bash
# Create .env file
cat > .env << EOF
WEB_MCP_CONTEXT_LIMIT=120000
WEB_MCP_SEARXNG_URL=https://searx.example.com
WEB_MCP_LLM_API_KEY=sk-...
EOF
```

### 3. Run Server

```bash
uv run python -m web_mcp.server
```

## Available Tools

| Tool | Description |
|------|-------------|
| `health` | Server health metrics |
| `fetch_url` | Fetch and extract web content |
| `web_search` | Search the web using SearXNG |
| `ask` | Research questions with AI |
| `ask_stream` | Stream research results |

## Key Features

- **Content Extraction**: Trafilatura, Readability, and custom extractors
- **Context Optimization**: Token estimation and smart truncation
- **Web Search**: SearXNG integration for privacy-focused search
- **Research Pipeline**: AI-powered research with citations
- **Caching**: LRU cache for efficient repeated fetches

## Need Help?

1. Check the [Usage Guide](./usage.md) for tool examples
2. Review the [Architecture Guide](./architecture.md) to understand the system
3. See [Development Guide](./development.md) for contributing

## Project Links

- Main README: [`../README.md`](../README.md)
- Source Code: [`../src/web_mcp/`](../src/web_mcp/)
- Plans: [`../plans/`](../plans/)
