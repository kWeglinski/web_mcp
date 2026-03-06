# Contributing to Web MCP

Thank you for your interest in contributing to Web MCP! We appreciate your time and effort to help improve this project. This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)
- [License](#license)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Development Setup

### Prerequisites

- **Python 3.12+** - This project requires Python 3.12 or higher
- **uv** - Fast Python package manager ([install uv](https://docs.astral.sh/uv/))

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-username/web_mcp.git
cd web_mcp

# Install dependencies
make install

# Install development dependencies (includes testing and linting tools)
make install-dev
```

### Install Pre-commit Hooks

We use pre-commit hooks to ensure code quality before commits:

```bash
make pre-commit-install
```

This will automatically run linting, formatting checks, and type checking on each commit.

## Development Workflow

### 1. Create a Branch

Create a feature branch from `main`:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

Write your code following the [Code Style](#code-style) guidelines below.

### 3. Run Tests

Always run tests to ensure your changes don't break existing functionality:

```bash
# Run all tests
make test

# Run tests with coverage report
make test-cov
```

### 4. Run Quality Checks

Before submitting, run all quality checks:

```bash
# Run linting
make lint

# Auto-fix linting issues
make lint-fix

# Format code with Black
make format

# Check formatting without changes
make format-check

# Run type checking
make typecheck

# Run all checks at once
make check
```

## Code Style

We maintain high code quality standards. Please follow these guidelines:

### Formatting with Black

We use [Black](https://black.readthedocs.io/) for code formatting:

```bash
make format
```

Configuration (see `pyproject.toml`):
- Line length: 100 characters
- Target Python version: 3.12

### Linting with Ruff

We use [Ruff](https://docs.astral.sh/ruff/) for linting:

```bash
make lint          # Check for issues
make lint-fix      # Auto-fix issues
```

Enabled rules include:
- `E`, `F` - Pyflakes and pycodestyle errors
- `I` - isort (import sorting)
- `N` - pep8-naming
- `W` - pycodestyle warnings
- `UP` - pyupgrade
- `B` - flake8-bugbear
- `C4` - flake8-comprehensions
- `SIM` - flake8-simplify

### Type Hints

**Type hints are required for all code.** We use mypy in strict mode:

```bash
make typecheck
```

Guidelines:
- All function parameters must have type annotations
- All function return types must be annotated
- Use `typing` module for complex types
- Use `TYPE_CHECKING` for imports that are only needed for type hints

Example:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

def process_items(items: Sequence[str]) -> dict[str, int]:
    """Process items and return counts."""
    return {item: len(item) for item in items}
```

### Docstrings

Write docstrings for all public APIs:

```python
def fetch_url(
    url: str,
    max_tokens: int = 120000,
    include_metadata: bool = True,
) -> FetchResult:
    """Fetch and extract content from a URL.

    Args:
        url: The URL to fetch.
        max_tokens: Maximum tokens in output.
        include_metadata: Whether to include metadata.

    Returns:
        FetchResult containing extracted content and metadata.

    Raises:
        ValueError: If the URL is invalid.
        httpx.HTTPError: If the request fails.
    """
    ...
```

## Testing

### Write Tests for New Features

All new features and bug fixes should include tests:

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use pytest fixtures for common setup

### Test Coverage

We require **60%+ code coverage**. The CI will fail if coverage drops below this threshold.

```bash
# Run tests with coverage
make test-cov

# Generate HTML coverage report
make test-cov-html
# Open htmlcov/index.html to view
```

### Test Structure

```python
import pytest
from web_mcp.fetcher import URLFetcher


class TestURLFetcher:
    """Tests for URLFetcher class."""

    @pytest.fixture
    def fetcher(self) -> URLFetcher:
        """Create a URLFetcher instance for testing."""
        return URLFetcher(timeout=30)

    async def test_fetch_valid_url(self, fetcher: URLFetcher) -> None:
        """Test fetching a valid URL."""
        result = await fetcher.fetch("https://example.com")
        assert result is not None
        assert len(result) > 0
```

## Pull Request Process

### PR Checklist

Before submitting your PR, ensure:

- [ ] Code follows the project's style guidelines
- [ ] All tests pass (`make test`)
- [ ] Coverage is at least 60% (`make test-cov`)
- [ ] Type checking passes (`make typecheck`)
- [ ] Linting passes (`make lint`)
- [ ] Code is formatted (`make format-check`)
- [ ] Docstrings are added for new public APIs
- [ ] Commit messages follow conventional commits format

### Required Checks

All CI checks must pass before merging:

1. **Lint** - Ruff linting
2. **Format** - Black formatting check
3. **Typecheck** - mypy strict mode
4. **Tests** - pytest with coverage

Run locally with:

```bash
make ci
```

### Code Review Process

1. Submit your PR
2. Wait for CI to complete
3. Address any review feedback
4. Once approved, a maintainer will merge your PR

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting, etc.)
- `refactor` - Code refactoring
- `test` - Adding or updating tests
- `chore` - Maintenance tasks

**Examples:**

```
feat(extractors): add support for PDF extraction

Add a new PDF extractor that uses pdfplumber to extract
text content from PDF files.

Closes #123
```

```
fix(fetcher): handle timeout errors gracefully

Wrap httpx requests in try-except to properly handle
timeout exceptions and return meaningful error messages.
```

```
docs: update installation instructions for uv
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description** - Clear description of the bug
2. **Steps to Reproduce** - Minimal code example
3. **Expected Behavior** - What you expected to happen
4. **Actual Behavior** - What actually happened
5. **Environment** - Python version, OS, package versions
6. **Logs** - Relevant error messages or stack traces

Use the bug report template when creating an issue.

### Feature Requests

For feature requests, please include:

1. **Problem Statement** - What problem does this solve?
2. **Proposed Solution** - How should it work?
3. **Alternatives** - Other solutions you've considered
4. **Additional Context** - Any other relevant information

### Security Issues

**Do not report security vulnerabilities through public issues.**

Please report security issues by following the instructions in [SECURITY.md](SECURITY.md).

## License

By contributing to this project, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

Thank you for contributing to Web MCP! 🎉
