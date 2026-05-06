# Web MCP Server - Agent Instructions

## Setup (do this first)
```
source $HOME/.local/bin/env    # required on this machine, or uv/dep commands fail
uv sync                         # install deps from uv.lock
uv run web-mcp-install          # install Playwright browsers (needed for JS-heavy pages)
```

## Run the server
```
uv run python -m web_mcp.server          # stdio (default, for MCP clients)
uv run python -m web_mcp.server --sse    # SSE transport
uv run python -m web_mcp.server --http   # HTTP transport
```

## Tests
```
uv run pytest                          # all tests
uv run pytest tests/test_cache.py -v   # single file
uv run pytest tests/test_cache.py::test_lru -v  # single test
```
- asyncio_mode is `auto` — no `@pytest.mark.asyncio` decorator needed
- conftest.py provides `mock_httpx_client`, `mock_trafilatura`, `mock_searxng_response`, `mock_llm_client`
- Coverage threshold: 45% local (`pyproject.toml`), 55% CI

## Lint / format / typecheck
```
make lint-fix    # ruff auto-fix
make format      # black
make typecheck   # mypy src/
make check       # lint + format-check + typecheck + test (full local CI)
```
- mypy is lenient: `tests.*`, `server`, `playwright_fetcher`, `fetcher`, `security`, `research.*`, `searxng`, `charts.generator`, `llm.*` all have `ignore_errors = true`
- pre-commit hooks run ruff --fix, black, and mypy --strict (stricter than CI)
- Line length: 100. Target: Python 3.12.

## Package layout
- Source code lives in `src/web_mcp/` (hatchling `package-dir = src`)
- Imports use `web_mcp.*` (e.g. `from web_mcp.fetcher import ...`)
- `test_fetch.py` at repo root uses broken `from src.web_mcp.*` imports — avoid
- Entry points: `web_mcp.server:main` (server), `web_mcp.playwright_fetcher:install_browsers` (browser install)

## Config
- All config via `WEB_MCP_*` env vars (see `.env.example`). No config files.
- `Config` is a singleton via `get_config()`. Use `reset_config()` in tests.
- SearXNG URL (`WEB_MCP_SEARXNG_URL`) is optional; search disabled if unset.

## Docker
- `make docker-build` / `make docker-run`
- Docker default is `--http` transport (not stdio)
- docker-compose includes optional SearXNG service (commented out)
