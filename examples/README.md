# Web MCP Examples

This directory contains example scripts demonstrating how to use the Web Browsing MCP Server. Each example focuses on a specific use case to help you get started quickly.

## Overview

| Example | Description | Difficulty |
|---------|-------------|------------|
| `basic_usage.py` | Basic URL fetching and content extraction | Beginner |
| `custom_extractor.py` | Creating custom content extractors | Intermediate |
| `docker-compose.yml` | Docker Compose setup for deployment | Beginner |

## Prerequisites

Before running the examples, ensure you have the following installed:

### Required

- **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
- **uv** - Python package manager
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/YOUR_USERNAME/web_mcp.git
   cd web_mcp
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Source the environment (required before running any code):
   ```bash
   source $HOME/.local/bin/env
   ```

### Optional

- **Docker & Docker Compose** - For containerized deployment
  - [Install Docker](https://docs.docker.com/get-docker/)
  - [Install Docker Compose](https://docs.docker.com/compose/install/)
- **SearXNG instance** - For web search functionality
- **OpenAI API key** - For research/ask features with LLM integration

---

## Basic Usage

The `basic_usage.py` example demonstrates the fundamental operations of the Web MCP server.

### What it does

- Fetches content from URLs
- Extracts clean text with metadata
- Demonstrates different extractor options
- Shows token estimation

### Running the example

```bash
# Make sure you've sourced the environment first
source $HOME/.local/bin/env

# Run the basic usage example
uv run python examples/basic_usage.py
```

### Example code structure

```python
import asyncio
from web_mcp.fetcher import Fetcher
from web_mcp.extractors import TrafilaturaExtractor

async def main():
    # Create a fetcher instance
    fetcher = Fetcher()
    
    # Fetch a URL
    result = await fetcher.fetch("https://example.com")
    
    print(f"Title: {result.title}")
    print(f"Content: {result.text[:500]}...")
    print(f"Tokens: {result.estimated_tokens}")

asyncio.run(main())
```

### Expected output

```
Fetching: https://example.com
Title: Example Domain
Content: This domain is for use in illustrative examples...
Tokens: 42
Truncated: False
```

---

## Custom Extractor

The `custom_extractor.py` example shows how to create your own content extractor for specific websites.

### When to use custom extractors

- Websites with unique HTML structures
- When you need specific CSS selectors
- For sites where default extractors don't work well
- When you want to extract custom metadata fields

### Running the example

```bash
source $HOME/.local/bin/env
uv run python examples/custom_extractor.py
```

### Creating a custom extractor

```python
from web_mcp.extractors.base import ContentExtractor, ExtractedContent
from bs4 import BeautifulSoup

class BlogExtractor(ContentExtractor):
    """Custom extractor for blog posts."""
    
    name = "blog_extractor"
    
    async def extract(self, html: str, url: str) -> ExtractedContent:
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title from h1 or title tag
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        
        # Extract author from common patterns
        author_tag = (
            soup.find(class_="author") or
            soup.find(class_="byline") or
            soup.find(rel="author")
        )
        author = author_tag.get_text(strip=True) if author_tag else None
        
        # Extract publication date
        date_tag = (
            soup.find("time") or
            soup.find(class_="date") or
            soup.find(class_="published")
        )
        date = date_tag.get("datetime") if date_tag else None
        
        # Extract main content
        content_tag = (
            soup.find("article") or
            soup.find(class_="content") or
            soup.find(class_="post-body")
        )
        text = content_tag.get_text(strip=True, separator="\n") if content_tag else ""
        
        return ExtractedContent(
            title=title,
            author=author,
            date=date,
            language=None,
            text=text,
            url=url,
            metadata={"extractor": self.name}
        )
```

### Registering your extractor

Add your extractor to `src/web_mcp/extractors/__init__.py`:

```python
from .blog_extractor import BlogExtractor

__all__ = [
    "TrafilaturaExtractor",
    "ReadabilityExtractor",
    "CustomSelectorExtractor",
    "BlogExtractor",  # Add your extractor here
]
```

### Using your custom extractor

```python
from web_mcp.fetcher import Fetcher
from examples.custom_extractor import BlogExtractor

async def main():
    fetcher = Fetcher(extractor=BlogExtractor())
    result = await fetcher.fetch("https://blog.example.com/post")
    print(result.text)

asyncio.run(main())
```

---

## Docker Compose

The `docker-compose.yml` example provides a complete containerized setup.

### What's included

- Web MCP server container
- Optional SearXNG search engine
- Environment configuration
- Volume mounts for persistence

### Running with Docker Compose

1. Create a `.env` file:
   ```bash
   cat > .env << EOF
   WEB_MCP_CONTEXT_LIMIT=120000
   WEB_MCP_REQUEST_TIMEOUT=30
   WEB_MCP_DEFAULT_EXTRACTOR=trafilatura
   WEB_MCP_INCLUDE_METADATA=true
   WEB_MCP_SEARXNG_URL=http://searxng:8080
   WEB_MCP_LLM_API_KEY=your-api-key-here
   WEB_MCP_LLM_API_URL=https://api.openai.com/v1
   EOF
   ```

2. Start the services:
   ```bash
   docker-compose up -d
   ```

3. Check logs:
   ```bash
   docker-compose logs -f web-mcp
   ```

4. Stop services:
   ```bash
   docker-compose down
   ```

### Docker Compose configuration

```yaml
version: '3.8'

services:
  web-mcp:
    build:
      context: ..
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - WEB_MCP_CONTEXT_LIMIT=${WEB_MCP_CONTEXT_LIMIT:-120000}
      - WEB_MCP_REQUEST_TIMEOUT=${WEB_MCP_REQUEST_TIMEOUT:-30}
      - WEB_MCP_DEFAULT_EXTRACTOR=${WEB_MCP_DEFAULT_EXTRACTOR:-trafilatura}
      - WEB_MCP_INCLUDE_METADATA=${WEB_MCP_INCLUDE_METADATA:-true}
      - WEB_MCP_SEARXNG_URL=${WEB_MCP_SEARXNG_URL:-http://searxng:8080}
      - WEB_MCP_LLM_API_KEY=${WEB_MCP_LLM_API_KEY}
      - WEB_MCP_LLM_API_URL=${WEB_MCP_LLM_API_URL:-https://api.openai.com/v1}
    depends_on:
      - searxng
    restart: unless-stopped

  searxng:
    image: searxng/searxng:latest
    ports:
      - "8888:8080"
    environment:
      - BASE_URL=http://localhost:8888/
      - INSTANCE_NAME=web-mcp-search
    restart: unless-stopped
```

### Building the Docker image manually

```bash
# Build the image
docker build -t web-mcp ..

# Run the container
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  --env-file .env \
  web-mcp
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "command not found: uv"

**Problem:** The `uv` package manager is not installed or not in your PATH.

**Solution:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Source the environment
source $HOME/.local/bin/env
```

#### 2. "ModuleNotFoundError: No module named 'web_mcp'"

**Problem:** Dependencies are not installed.

**Solution:**
```bash
# Install dependencies
uv sync

# Make sure you're in the project root directory
cd /path/to/web_mcp
```

#### 3. "Connection refused" or timeout errors

**Problem:** Network connectivity issues or firewall blocking.

**Solution:**
```bash
# Increase timeout
export WEB_MCP_REQUEST_TIMEOUT=60

# Check if the URL is accessible
curl -I https://example.com
```

#### 4. "No content extracted"

**Problem:** The extractor couldn't find content on the page.

**Solutions:**
- Try a different extractor:
  ```python
  result = await fetcher.fetch(url, extractor="readability")
  ```
- The page may require JavaScript (use Playwright fetcher)
- Check if the URL returns valid HTML

#### 5. "SearXNG connection failed"

**Problem:** SearXNG is not running or not accessible.

**Solution:**
```bash
# Check if SearXNG is running
curl http://localhost:8080

# Start SearXNG with Docker
docker run -d -p 8080:8080 searxng/searxng:latest

# Or update the URL in your .env
WEB_MCP_SEARXNG_URL=http://localhost:8080
```

#### 6. "LLM API error" or "Invalid API key"

**Problem:** LLM integration is misconfigured.

**Solution:**
```bash
# Verify your API key is set
echo $WEB_MCP_LLM_API_KEY

# Set it in .env
WEB_MCP_LLM_API_KEY=sk-your-key-here
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
```

#### 7. Docker build fails

**Problem:** Missing dependencies or Docker issues.

**Solution:**
```bash
# Prune Docker cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache

# Check Docker logs
docker-compose logs web-mcp
```

#### 8. "Token estimation failed"

**Problem:** Token estimation is disabled or broken.

**Solution:**
```bash
# Enable token estimation
export WEB_MCP_ENABLE_TOKEN_ESTIMATION=true
export WEB_MCP_TRUNCATION_STRATEGY=smart
```

### Getting Help

If you encounter issues not covered here:

1. Check the [main documentation](../docs/index.md)
2. Search [existing issues](https://github.com/YOUR_USERNAME/web_mcp/issues)
3. Open a new issue with:
   - Your Python version (`python --version`)
   - Your OS
   - Full error message and stack trace
   - Steps to reproduce

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set log level
export WEB_MCP_LOG_LEVEL=DEBUG

# Run with debug output
uv run python -m web_mcp.server --debug
```

---

## Additional Resources

- [Main Documentation](../docs/index.md) - Complete documentation
- [Configuration Guide](../docs/configuration.md) - All configuration options
- [Usage Guide](../docs/usage.md) - Detailed tool usage
- [Extractors Guide](../docs/extractors.md) - Extractor documentation
- [Architecture Overview](../docs/architecture.md) - System design

## Contributing

Have an example you'd like to share? Contributions are welcome!

1. Fork the repository
2. Add your example to the `examples/` directory
3. Update this README with a description
4. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.
