# Docker Usage Guide

This guide covers everything you need to know about running Web MCP in Docker, from quick start to production deployment.

## Overview

Web MCP provides official Docker images with all dependencies pre-installed, including Playwright and Chromium for JavaScript-heavy pages.

### Available Tags

| Tag | Description | Use Case |
|-----|-------------|----------|
| `latest` | Most recent stable release | Development, testing |
| `1.0.0` | Specific version | Production (pinned) |
| `1.0` | Major version (latest patch) | Production (flexible) |
| `main` | Latest from main branch | Testing new features |
| `dev` | Development builds | Contributing |

### Supported Platforms

- **linux/amd64** - x86_64 (Intel/AMD)
- **linux/arm64** - ARM64 (Apple Silicon, AWS Graviton, Raspberry Pi 4+)

## Quick Start

### Pull the Image

```bash
# Pull latest version
docker pull ghcr.io/kweg/mcp-basics:latest

# Pull specific version
docker pull ghcr.io/kweg/mcp-basics:1.0.0
```

### Run the Container

```bash
# Basic run (HTTP transport on port 8000)
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  ghcr.io/kweg/mcp-basics:latest

# With environment variables
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  -e WEB_MCP_CONTEXT_LIMIT=120000 \
  -e WEB_MCP_SEARXNG_URL=http://searxng:8080 \
  ghcr.io/kweg/mcp-basics:latest
```

### Verify It's Running

```bash
# Check container status
docker ps

# Check health
docker inspect --format='{{.State.Health.Status}}' web-mcp

# View logs
docker logs -f web-mcp
```

## Docker Hub

### Image Location

Images are published to GitHub Container Registry:

```
ghcr.io/kweg/mcp-basics
```

### Finding Available Tags

```bash
# List all tags via GitHub API
curl -s https://ghcr.io/v2/kweg/mcp-basics/tags/list | jq

# Or check the packages page
# https://github.com/yourorg/web_mcp/pkgs/container/web-mcp
```

### Tag Strategy

| Branch/Event | Tag Pattern | Example |
|--------------|-------------|---------|
| Release | `v{version}` | `1.0.0`, `1.2.3` |
| Main branch | `main` | `main` |
| Development | `dev`, `dev-{sha}` | `dev`, `dev-abc123` |
| PRs | `pr-{number}` | `pr-42` |

## Configuration

### Environment Variables

Configure Web MCP using environment variables:

```bash
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  -e WEB_MCP_SERVER_HOST=0.0.0.0 \
  -e WEB_MCP_SERVER_PORT=8000 \
  -e WEB_MCP_CONTEXT_LIMIT=120000 \
  -e WEB_MCP_REQUEST_TIMEOUT=30 \
  -e WEB_MCP_DEFAULT_EXTRACTOR=trafilatura \
  -e WEB_MCP_INCLUDE_METADATA=true \
  -e WEB_MCP_SEARXNG_URL=http://searxng:8080 \
  -e WEB_MCP_PLAYWRIGHT_ENABLED=true \
  -e WEB_MCP_PLAYWRIGHT_TIMEOUT=30000 \
  ghcr.io/kweg/mcp-basics:latest
```

#### Complete Environment Reference

| Variable | Default | Description |
|----------|---------|-------------|
| **Server** | | |
| `WEB_MCP_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `WEB_MCP_SERVER_PORT` | `8000` | Server port |
| **Content** | | |
| `WEB_MCP_CONTEXT_LIMIT` | `120000` | Max tokens in output |
| `WEB_MCP_REQUEST_TIMEOUT` | `30` | Request timeout (seconds) |
| `WEB_MCP_MAX_CONTENT_LENGTH` | `10485760` | Max content size (bytes) |
| `WEB_MCP_DEFAULT_EXTRACTOR` | `trafilatura` | Default extractor |
| `WEB_MCP_INCLUDE_METADATA` | `true` | Include metadata |
| `WEB_MCP_INCLUDE_LINKS` | `false` | Include links |
| `WEB_MCP_INCLUDE_COMMENTS` | `false` | Include comments |
| **Token Handling** | | |
| `WEB_MCP_ENABLE_TOKEN_ESTIMATION` | `true` | Enable token counting |
| `WEB_MCP_TRUNCATION_STRATEGY` | `smart` | Truncation method |
| **Playwright** | | |
| `WEB_MCP_PLAYWRIGHT_ENABLED` | `true` | Enable Playwright |
| `WEB_MCP_PLAYWRIGHT_TIMEOUT` | `30000` | Page load timeout (ms) |
| `WEB_MCP_PLAYWRIGHT_FALLBACK_THRESHOLD` | `500` | Content size threshold |
| **Cache** | | |
| `WEB_MCP_CACHE_TTL` | `3600` | Cache TTL (seconds) |
| `WEB_MCP_CONTENT_TTL` | `3600` | Content cache TTL |
| **JavaScript Security** | | |
| `WEB_MCP_JS_FETCH_MAX_RESPONSE_SIZE` | `5242880` | Max JS fetch response |
| `WEB_MCP_JS_FETCH_MAX_REQUESTS` | `10` | Max fetch calls |
| `WEB_MCP_JS_FETCH_MAX_TOTAL_BYTES` | `10485760` | Max total bytes |
| `WEB_MCP_JS_FETCH_TIMEOUT` | `10000` | Fetch timeout (ms) |
| `WEB_MCP_JS_EXECUTION_TIMEOUT` | `30000` | Execution timeout (ms) |
| `WEB_MCP_JS_FETCH_VERIFY_SSL` | `true` | Verify SSL certs |
| **Search** | | |
| `WEB_MCP_SEARXNG_URL` | - | SearXNG instance URL |
| **Security** | | |
| `WEB_MCP_AUTH_TOKEN` | - | API authentication token |
| `WEB_MCP_RATE_LIMIT_REQUESTS` | `10` | Requests per window |
| `WEB_MCP_RATE_LIMIT_WINDOW` | `60` | Rate limit window (s) |
| **LLM** | | |
| `WEB_MCP_LLM_API_KEY` | - | LLM API key |
| `WEB_MCP_LLM_API_URL` | `https://api.openai.com/v1` | LLM API URL |
| `WEB_MCP_LLM_MODEL` | `gpt-4o` | Model for generation |
| `WEB_MCP_LLM_EMBED_MODEL` | `text-embedding-3-small` | Embedding model |

### Volume Mounts

```bash
# Persist cache data
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  -v web-mcp-cache:/app/.cache \
  ghcr.io/kweg/mcp-basics:latest

# Mount custom configuration
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  -v ./config:/app/config:ro \
  ghcr.io/kweg/mcp-basics:latest

# Using named volumes
docker volume create web-mcp-cache
docker run -d \
  --name web-mcp \
  -p 8000:8000 \
  -v web-mcp-cache:/app/.cache \
  ghcr.io/kweg/mcp-basics:latest
```

### Port Mapping

```bash
# Default port mapping
-p 8000:8000

# Custom host port
-p 3000:8000

# Bind to specific interface
-p 127.0.0.1:8000:8000

# Multiple interfaces (for reverse proxy)
-p 127.0.0.1:8000:8000 \
-p 10.0.0.1:8000:8000
```

### Docker Compose Example

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    container_name: web-mcp-server
    ports:
      - "8000:8000"
    environment:
      - WEB_MCP_SERVER_HOST=0.0.0.0
      - WEB_MCP_SERVER_PORT=8000
      - WEB_MCP_CONTEXT_LIMIT=120000
      - WEB_MCP_REQUEST_TIMEOUT=30
      - WEB_MCP_SEARXNG_URL=http://searxng:8080
    volumes:
      - web-mcp-cache:/app/.cache
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/mcp"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    ports:
      - "8080:8080"
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
      - SEARXNG_SECRET=change-this-secret
    volumes:
      - searxng-data:/etc/searxng
    restart: unless-stopped

volumes:
  web-mcp-cache:
  searxng-data:
```

Run with:

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Building Locally

### Basic Build

```bash
# Build from source
docker build -t web-mcp:local .

# Build with specific tag
docker build -t web-mcp:1.0.0-local .
```

### Multi-Platform Build

Build for multiple architectures using Docker Buildx:

```bash
# Create buildx builder (if not exists)
docker buildx create --name multiarch --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t web-mcp:local \
  --load \
  .

# Build and push to registry
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/kweg/mcp-basics:latest \
  --push \
  .
```

### Build Arguments

The Dockerfile supports these build arguments:

```bash
# Build with specific Python version
docker build \
  --build-arg PYTHON_VERSION=3.12 \
  -t web-mcp:local \
  .

# Build with specific uv version
docker build \
  --build-arg UV_VERSION=latest \
  -t web-mcp:local \
  .
```

### Build for Development

```bash
# Build with dev dependencies
docker build \
  --target development \
  -t web-mcp:dev \
  .

# Build with debugging tools
docker build \
  --build-arg INSTALL_DEBUG=1 \
  -t web-mcp:debug \
  .
```

## Security

### Using Secrets

Avoid passing sensitive values as environment variables. Use Docker secrets instead:

```yaml
# docker-compose.yml
version: '3.8'

secrets:
  llm_api_key:
    file: ./secrets/llm_api_key.txt
  auth_token:
    file: ./secrets/auth_token.txt

services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    secrets:
      - llm_api_key
      - auth_token
    environment:
      - WEB_MCP_LLM_API_KEY_FILE=/run/secrets/llm_api_key
      - WEB_MCP_AUTH_TOKEN_FILE=/run/secrets/auth_token
```

Create secret files:

```bash
# Create secrets directory
mkdir -p secrets

# Create secret files (restrict permissions)
echo "sk-your-api-key" > secrets/llm_api_key.txt
echo "your-secure-token" > secrets/auth_token.txt
chmod 600 secrets/*.txt
```

### Running as Non-Root User

The container runs as `appuser` (UID 1000) by default. To customize:

```bash
# Run as specific user
docker run -d \
  --name web-mcp \
  --user 1000:1000 \
  -p 8000:8000 \
  ghcr.io/kweg/mcp-basics:latest

# Fix volume permissions
docker run --rm \
  -v web-mcp-cache:/app/.cache \
  alpine chown -R 1000:1000 /app/.cache
```

### Network Security

```yaml
# docker-compose.yml with network isolation
version: '3.8'

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access

services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    networks:
      - frontend
      - backend
    ports:
      - "8000:8000"

  searxng:
    image: searxng/searxng:latest
    networks:
      - backend  # Only accessible from web-mcp
    # No ports exposed - internal only
```

### Resource Limits

```yaml
services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check logs
docker logs web-mcp

# Common causes:
# 1. Port already in use
lsof -i :8000

# 2. Permission issues
docker run --user root ...  # Temporarily for debugging

# 3. Missing environment variables
docker inspect web-mcp | jq '.[0].Config.Env'
```

#### Playwright/Chromium Issues

```bash
# Check if Chromium is installed
docker exec web-mcp which chromium

# Reinstall Playwright browsers
docker exec web-mcp uv run playwright install chromium

# Check system dependencies
docker exec web-mcp uv run playwright install-deps
```

#### Memory Issues

```bash
# Check container memory usage
docker stats web-mcp

# Increase memory limit
docker update --memory 2g web-mcp

# Check for memory leaks
docker exec web-mcp ps aux --sort=-%mem
```

#### Network Connectivity

```bash
# Test DNS resolution
docker exec web-mcp nslookup google.com

# Test HTTP connectivity
docker exec web-mcp curl -I https://example.com

# Check network configuration
docker network inspect bridge
```

### Logs

```bash
# Follow logs
docker logs -f web-mcp

# Last 100 lines
docker logs --tail 100 web-mcp

# Logs with timestamps
docker logs -t web-mcp

# Logs since specific time
docker logs --since 1h web-mcp
docker logs --since "2024-01-01T00:00:00" web-mcp

# Filter logs
docker logs web-mcp 2>&1 | grep -i error

# Export logs
docker logs web-mcp > web-mcp.log 2>&1
```

### Health Checks

```bash
# Check health status
docker inspect --format='{{json .State.Health}}' web-mcp | jq

# Manual health check
docker exec web-mcp curl -f http://localhost:8000/mcp

# View health check history
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' web-mcp
```

### Debugging

```bash
# Interactive shell
docker exec -it web-mcp /bin/bash

# Run with debug output
docker run -it --rm \
  -e PYTHONUNBUFFERED=1 \
  ghcr.io/kweg/mcp-basics:latest

# Check Python version and packages
docker exec web-mcp python --version
docker exec web-mcp uv pip list
```

## Examples

### Development Setup

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  web-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: web-mcp-dev
    ports:
      - "8000:8000"
    environment:
      - WEB_MCP_SERVER_HOST=0.0.0.0
      - WEB_MCP_SERVER_PORT=8000
      - WEB_MCP_CONTEXT_LIMIT=120000
      - WEB_MCP_SEARXNG_URL=http://searxng:8080
      # Enable verbose logging for development
      - PYTHONUNBUFFERED=1
    volumes:
      # Mount source code for hot reload
      - ./src:/app/src:ro
      - ./pyproject.toml:/app/pyproject.toml:ro
    restart: unless-stopped

  searxng:
    image: searxng/searxng:latest
    container_name: searxng-dev
    ports:
      - "8080:8080"
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
      - SEARXNG_SECRET=dev-secret-key
      - SEARXNG_LOG_LEVEL=DEBUG
    restart: unless-stopped
```

Run development environment:

```bash
# Start with hot reload
docker-compose -f docker-compose.dev.yml up -d

# Watch logs
docker-compose -f docker-compose.dev.yml logs -f web-mcp

# Rebuild after dependency changes
docker-compose -f docker-compose.dev.yml up -d --build
```

### Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'

networks:
  web-mcp-network:
    driver: bridge

volumes:
  web-mcp-cache:
  searxng-data:

services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:1.0.0
    container_name: web-mcp-prod
    hostname: web-mcp
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - WEB_MCP_SERVER_HOST=0.0.0.0
      - WEB_MCP_SERVER_PORT=8000
      - WEB_MCP_CONTEXT_LIMIT=200000
      - WEB_MCP_REQUEST_TIMEOUT=60
      - WEB_MCP_SEARXNG_URL=http://searxng:8080
      - WEB_MCP_AUTH_TOKEN=${WEB_MCP_AUTH_TOKEN}
      - WEB_MCP_LLM_API_KEY=${WEB_MCP_LLM_API_KEY}
      - WEB_MCP_LLM_API_URL=https://api.openai.com/v1
      - WEB_MCP_RATE_LIMIT_REQUESTS=100
      - WEB_MCP_RATE_LIMIT_WINDOW=60
    volumes:
      - web-mcp-cache:/app/.cache
    networks:
      - web-mcp-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/mcp"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    depends_on:
      searxng:
        condition: service_healthy
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  searxng:
    image: searxng/searxng:latest
    container_name: searxng-prod
    hostname: searxng
    # No external ports - internal only
    expose:
      - "8080"
    environment:
      - SEARXNG_BASE_URL=https://search.yourdomain.com/
      - SEARXNG_SECRET=${SEARXNG_SECRET}
      - SEARXNG_LOG_LEVEL=WARNING
      - SEARXNG_LIMITER=true
      - SEARXNG_IMAGE_PROXY=true
    volumes:
      - searxng-data:/etc/searxng
    networks:
      - web-mcp-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Run production environment:

```bash
# Create .env file with secrets
cat > .env.prod << EOF
WEB_MCP_AUTH_TOKEN=$(openssl rand -hex 32)
WEB_MCP_LLM_API_KEY=sk-your-api-key
SEARXNG_SECRET=$(openssl rand -hex 32)
EOF

# Start production stack
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Verify health
docker-compose -f docker-compose.prod.yml ps
```

### With SearXNG

Complete setup with SearXNG for web search:

```yaml
# docker-compose.searxng.yml
version: '3.8'

networks:
  search-network:
    driver: bridge

volumes:
  searxng-config:
  searxng-data:

services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    container_name: web-mcp
    ports:
      - "8000:8000"
    environment:
      - WEB_MCP_SERVER_HOST=0.0.0.0
      - WEB_MCP_SERVER_PORT=8000
      - WEB_MCP_SEARXNG_URL=http://searxng:8080
    networks:
      - search-network
    depends_on:
      searxng:
        condition: service_healthy
    restart: unless-stopped

  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    ports:
      - "8080:8080"
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
      - SEARXNG_SECRET=your-secret-key-change-me
      - SEARXNG_INSTANCE_NAME=Web MCP Search
      - SEARXNG_LOG_LEVEL=INFO
      - SEARXNG_LIMITER=true
      - SEARXNG_IMAGE_PROXY=true
      - SEARXNG_HTTP_COMPRESSION=true
      - SEARXNG_AUTOCOMPLETE=duckduckgo
    volumes:
      - searxng-config:/etc/searxng
    networks:
      - search-network
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

### With Reverse Proxy

#### Nginx

```yaml
# docker-compose.nginx.yml
version: '3.8'

networks:
  proxy-network:
    driver: bridge

services:
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    networks:
      - proxy-network
    depends_on:
      - web-mcp
    restart: unless-stopped

  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    container_name: web-mcp
    expose:
      - "8000"
    environment:
      - WEB_MCP_SERVER_HOST=0.0.0.0
      - WEB_MCP_SERVER_PORT=8000
      - WEB_MCP_PUBLIC_URL=https://yourdomain.com
    networks:
      - proxy-network
    restart: unless-stopped
```

Nginx configuration (`nginx.conf`):

```nginx
events {
    worker_connections 1024;
}

http {
    upstream web-mcp {
        server web-mcp:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://web-mcp;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
```

#### Traefik

```yaml
# docker-compose.traefik.yml
version: '3.8'

networks:
  traefik-network:
    external: true

services:
  web-mcp:
    image: ghcr.io/kweg/mcp-basics:latest
    container_name: web-mcp
    environment:
      - WEB_MCP_SERVER_HOST=0.0.0.0
      - WEB_MCP_SERVER_PORT=8000
      - WEB_MCP_PUBLIC_URL=https://mcp.yourdomain.com
    networks:
      - traefik-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.web-mcp.rule=Host(`mcp.yourdomain.com`)"
      - "traefik.http.routers.web-mcp.entrypoints=websecure"
      - "traefik.http.routers.web-mcp.tls.certresolver=letsencrypt"
      - "traefik.http.services.web-mcp.loadbalancer.server.port=8000"
      # Rate limiting
      - "traefik.http.middlewares.web-mcp-ratelimit.ratelimit.average=10"
      - "traefik.http.middlewares.web-mcp-ratelimit.ratelimit.burst=20"
      - "traefik.http.routers.web-mcp.middlewares=web-mcp-ratelimit"
    restart: unless-stopped
```

---

## Additional Resources

- [Configuration Guide](./configuration.md) - All environment variables
- [Architecture](./architecture.md) - System design
- [Development](./development.md) - Contributing guide
- [Docker Documentation](https://docs.docker.com/)
- [SearXNG Documentation](https://docs.searxng.org/)
