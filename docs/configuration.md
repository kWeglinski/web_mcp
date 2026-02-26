# Configuration Guide

## Overview

The Web Browsing MCP Server is configured entirely through environment variables. No configuration files are required.

## Environment Variables

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_SERVER_HOST` | `0.0.0.0` | Server host address |
| `WEB_MCP_SERVER_PORT` | `8000` | Server port |

### Context Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_CONTEXT_LIMIT` | `120000` | Maximum tokens in output (1k-1M) |
| `WEB_MCP_REQUEST_TIMEOUT` | `30` | Request timeout in seconds (1-300) |
| `WEB_MCP_DEFAULT_EXTRACTOR` | `trafilatura` | Default extractor: `trafilatura`, `readability`, or `custom` |
| `WEB_MCP_INCLUDE_METADATA` | `true` | Include title, author, date in results |
| `WEB_MCP_INCLUDE_LINKS` | `false` | Include links in extraction |
| `WEB_MCP_INCLUDE_COMMENTS` | `false` | Include comments in extraction |

### Token Estimation

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_ENABLE_TOKEN_ESTIMATION` | `true` | Enable token estimation |
| `WEB_MCP_TRUNCATION_STRATEGY` | `smart` | Truncation strategy: `smart` or `simple` |

### Search Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_SEARXNG_URL` | - | SearXNG instance URL (optional) |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_RATE_LIMIT_REQUESTS` | `10` | Maximum requests per window |
| `WEB_MCP_RATE_LIMIT_WINDOW` | `60` | Time window in seconds |

### LLM Configuration (for research features)

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_LLM_API_KEY` | - | API key for LLM service |
| `WEB_MCP_LLM_API_URL` | `https://api.openai.com/v1` | API endpoint |
| `WEB_MCP_LLM_MODEL` | `gpt-4o` | Model for generation |
| `WEB_MCP_LLM_EMBED_MODEL` | `text-embedding-3-small` | Model for embeddings |
| `WEB_MCP_LLM_MAX_TOKENS` | `4096` | Maximum tokens for generation |
| `WEB_MCP_LLM_TEMPERATURE` | `0.7` | Temperature for generation |

## Configuration Examples

### Basic Setup

```bash
# Create .env file
cat > .env << EOF
WEB_MCP_CONTEXT_LIMIT=120000
WEB_MCP_REQUEST_TIMEOUT=30
WEB_MCP_DEFAULT_EXTRACTOR=trafilatura
WEB_MCP_INCLUDE_METADATA=true
WEB_MCP_SEARXNG_URL=https://searx.example.com
EOF

# Run server with .env
export $(cat .env | xargs) && uv run python -m web_mcp.server
```

### Production Setup

```bash
cat > .env << EOF
# Server settings
WEB_MCP_SERVER_HOST=0.0.0.0
WEB_MCP_SERVER_PORT=8000

# Context settings (larger context for complex tasks)
WEB_MCP_CONTEXT_LIMIT=200000
WEB_MCP_REQUEST_TIMEOUT=60

# Extractor settings
WEB_MCP_DEFAULT_EXTRACTOR=trafilatura
WEB_MCP_INCLUDE_METADATA=true
WEB_MCP_INCLUDE_LINKS=false

# Search settings
WEB_MCP_SEARXNG_URL=https://searx.mydomain.com

# LLM settings
WEB_MCP_LLM_API_KEY=sk-...
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
WEB_MCP_LLM_MODEL=gpt-4o
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small

# Rate limiting
WEB_MCP_RATE_LIMIT_REQUESTS=100
WEB_MCP_RATE_LIMIT_WINDOW=60
EOF

# Start server
uv run python -m web_mcp.server
```

### Docker Setup

```bash
# Create .env file
cat > .env << EOF
WEB_MCP_CONTEXT_LIMIT=120000
WEB_MCP_SEARXNG_URL=https://searx.example.com
WEB_MCP_LLM_API_KEY=sk-...
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
EOF

# Run with docker-compose
docker-compose up -d

# Or run directly
docker build -t web-mcp .
docker run --env-file .env -p 8000:8000 web-mcp
```

## Configuration Validation

The server validates all configuration values:

```python
from web_mcp.config import validate_config, get_config

# Validate configuration
try:
    validate_config()
except ValueError as e:
    print(f"Configuration error: {e}")

# Get config instance
config = get_config()
print(f"Context limit: {config.max_tokens}")
```

## Default Values

When environment variables are not set:

| Setting | Default Value |
|---------|---------------|
| Context Limit | 120,000 tokens |
| Request Timeout | 30 seconds |
| Default Extractor | Trafilatura |
| Include Metadata | true |
| Token Estimation | enabled |
| Truncation Strategy | smart |

## Environment File Template

See [`.env.example`](../.env.example) for a complete template:

```bash
# Web MCP Server Configuration

# Context limit in tokens (default 120k)
WEB_MCP_CONTEXT_LIMIT=120000

# Request timeout in seconds
WEB_MCP_REQUEST_TIMEOUT=30

# Default extractor: trafilatura, readability, or custom
WEB_MCP_DEFAULT_EXTRACTOR=trafilatura

# Include metadata in extraction results
WEB_MCP_INCLUDE_METADATA=true

# Include links in extraction results
WEB_MCP_INCLUDE_LINKS=false

# Include comments in extraction results
WEB_MCP_INCLUDE_COMMENTS=false

# Enable token estimation
WEB_MCP_ENABLE_TOKEN_ESTIMATION=true

# Truncation strategy: smart or simple
WEB_MCP_TRUNCATION_STRATEGY=smart

# SearXNG URL (optional)
WEB_MCP_SEARXNG_URL=

# Rate limiting
WEB_MCP_RATE_LIMIT_REQUESTS=10
WEB_MCP_RATE_LIMIT_WINDOW=60

# LLM settings (for research features)
WEB_MCP_LLM_API_KEY=
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
WEB_MCP_LLM_MODEL=gpt-4o
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small
```

## Runtime Configuration

Configuration is loaded once at server startup and cached globally:

```python
from web_mcp.config import get_config, reset_config

# Get current config
config = get_config()

# Reset config (for testing)
reset_config()
```

## Best Practices

1. **Set appropriate context limits** based on your use case
2. **Configure rate limiting** to prevent abuse
3. **Use SearXNG** for privacy-focused web search
4. **Enable token estimation** for accurate truncation
5. **Set request timeouts** based on network conditions
