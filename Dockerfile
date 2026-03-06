# Multi-platform Dockerfile for web-mcp
# Supports: linux/amd64, linux/arm64
# Build with: docker buildx build --platform linux/amd64,linux/arm64 -t web-mcp .

# Use Python 3.12 slim image (supports amd64 and arm64)
FROM python:3.12-slim

# Platform argument for multi-platform builds (automatically set by buildx)
ARG TARGETPLATFORM
ARG TARGETARCH

# Set working directory
WORKDIR /app

# Install uv (Python package manager - supports both platforms)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy all project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install dependencies and the package itself
RUN uv sync --frozen

# Install Playwright system dependencies and browser
# Playwright auto-detects the target platform and installs correct chromium binary
# Must be done as root before creating user
RUN uv run playwright install-deps chromium && \
    uv run playwright install chromium

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose the server port
EXPOSE 8000

# Set entrypoint - run with --http transport by default
CMD ["uv", "run", "--no-dev", "python", "-m", "web_mcp", "--http"]
