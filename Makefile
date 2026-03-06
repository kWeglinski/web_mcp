.PHONY: install install-dev test test-cov test-cov-html lint lint-fix format format-check typecheck check ci clean clean-all docker-build docker-run dev pre-commit-install help

SHELL := /bin/bash
PYTHON := uv run python
PYTEST := uv run pytest
PROJECT_NAME := web-mcp
DOCKER_IMAGE := $(PROJECT_NAME)

help:
	@echo "Available targets:"
	@echo ""
	@echo "Installation:"
	@echo "  make install        - Install dependencies with uv sync"
	@echo "  make install-dev    - Install dev dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run pytest"
	@echo "  make test-cov       - Run pytest with coverage report"
	@echo "  make test-cov-html  - Run pytest with HTML coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Run ruff check"
	@echo "  make lint-fix       - Run ruff check with auto-fix"
	@echo "  make format         - Run black to format code"
	@echo "  make format-check   - Check if code is formatted"
	@echo "  make typecheck      - Run mypy type checking"
	@echo ""
	@echo "Combined Quality:"
	@echo "  make check          - Run all checks (lint, format-check, typecheck, test)"
	@echo "  make ci             - Run CI-like checks"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Remove generated files"
	@echo "  make clean-all      - Deep clean including .venv"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   - Build docker image"
	@echo "  make docker-run     - Run docker container"
	@echo ""
	@echo "Development:"
	@echo "  make dev            - Run the server in development mode"
	@echo "  make pre-commit-install - Install pre-commit hooks"

install:
	uv sync

install-dev:
	uv sync --all-extras --dev

test:
	$(PYTEST)

test-cov:
	$(PYTEST) --cov=web_mcp --cov-report=term-missing

test-cov-html:
	$(PYTEST) --cov=web_mcp --cov-report=html
	@echo "Coverage report generated in htmlcov/"

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run black .

format-check:
	uv run black . --check

typecheck:
	uv run mypy src/

check: lint format-check typecheck test

ci: lint format-check typecheck test-cov

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true

clean-all: clean
	rm -rf .venv
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	rm -rf .eggs

docker-build:
	docker build -t $(DOCKER_IMAGE) .

docker-run:
	docker run -it --rm $(DOCKER_IMAGE)

dev:
	$(PYTHON) -m web_mcp.server

pre-commit-install:
	uv run pre-commit install
