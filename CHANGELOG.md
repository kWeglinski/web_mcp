# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT LICENSE file
- Comprehensive .gitignore for Python projects
- Development tools configuration (Ruff, Black, Mypy)
- Pre-commit hooks for code quality enforcement
- Makefile with convenient development commands
- EditorConfig for consistent coding style
- CI/CD pipeline with GitHub Actions
- Code quality checks (linting, formatting, type checking)
- Coverage reporting with 60% minimum threshold
- Issue and PR templates
- Contributing guidelines
- Security policy
- Docker Hub automatic publishing workflow
- Multi-platform Docker images (linux/amd64, linux/arm64)
- Docker badges in README
- Comprehensive Docker documentation (docs/docker.md)
- Optimized .dockerignore for faster builds

### Changed
- Replaced print() statements with proper logging
- Updated development dependencies to use dependency groups
- Enhanced pyproject.toml with tool configurations

### Fixed
- Print statements in playwright_fetcher.py and __main__.py now use logging

## [1.0.0] - 2026-03-06

### Added
- Initial release of Web MCP Server
- MCP server with 7 tools (get_page, search_web, create_chart_tool, render_html, current_datetime, health, run_javascript)
- Content extraction with Trafilatura, Readability, and Custom extractors
- Playwright fallback for JavaScript-heavy pages
- SearXNG integration for web search
- LLM integration with embeddings support
- Research pipeline with citations
- Chart generation with Plotly
- Content caching with TTL support
- SSRF protection and security features
- Rate limiting
- Docker support
- Comprehensive test suite (237 tests)
- Documentation (architecture, usage, configuration, extractors, research, LLM integration)
