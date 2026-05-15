"""Category taxonomy and classification for knowledge facts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Category:
    """A knowledge category."""

    name: str
    description: str
    keywords: list[str] = field(default_factory=list)
    parent: str | None = None
    priority: int = 10  # Lower = higher priority for matching


# Complete category taxonomy
CATEGORY_TAXONOMY: list[Category] = [
    Category(
        "api",
        "API specifications, endpoints, SDKs",
        ["api", "endpoint", "sdk", "rest", "graphql", "rpc", "webhook", "http"],
        priority=1,
    ),
    Category(
        "architecture",
        "System architecture, design patterns",
        [
            "architecture",
            "design pattern",
            "microservice",
            "monolith",
            "event-driven",
            "circuit breaker",
        ],
        priority=2,
    ),
    Category(
        "configuration",
        "Configuration, settings, environment",
        [
            "config",
            "configuration",
            "setting",
            "environment",
            "env",
            "properties",
            "yaml",
            "toml",
        ],
        priority=3,
    ),
    Category(
        "deployment",
        "Deployment, CI/CD, containers, cloud",
        [
            "deploy",
            "ci/cd",
            "docker",
            "kubernetes",
            "k8s",
            "cloud",
            "aws",
            "azure",
            "gcp",
            "pipeline",
        ],
        priority=4,
    ),
    Category(
        "security",
        "Security, authentication, authorization",
        [
            "security",
            "auth",
            "authentication",
            "authorization",
            "oauth",
            "jwt",
            "tls",
            "encryption",
            "vulnerability",
        ],
        priority=1,
    ),
    Category(
        "performance",
        "Performance, optimization, benchmarks",
        [
            "performance",
            "optimization",
            "benchmark",
            "latency",
            "throughput",
            "scalability",
            "caching",
        ],
        priority=5,
    ),
    Category(
        "database",
        "Databases, storage, queries",
        [
            "database",
            "sql",
            "nosql",
            "query",
            "schema",
            "migration",
            "index",
            "storage",
        ],
        priority=6,
    ),
    Category(
        "testing",
        "Testing, QA, coverage",
        [
            "test",
            "testing",
            "qa",
            "coverage",
            "unit test",
            "integration test",
            "e2e",
            "mock",
        ],
        priority=7,
    ),
    Category(
        "machine_learning",
        "ML, AI, models, training",
        [
            "machine learning",
            "ml",
            "ai",
            "model",
            "training",
            "inference",
            "neural network",
            "llm",
            "embedding",
        ],
        priority=8,
    ),
    Category(
        "networking",
        "Networking, protocols, DNS",
        [
            "network",
            "protocol",
            "dns",
            "tcp",
            "udp",
            "http",
            "websocket",
            "proxy",
        ],
        priority=9,
    ),
    Category(
        "language",
        "Programming language features",
        [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "syntax",
            "feature",
        ],
        priority=10,
    ),
    Category(
        "tooling",
        "Tools, CLI, IDE, development workflow",
        ["cli", "tool", "ide", "editor", "workflow", "debugging", "profiling"],
        priority=11,
    ),
    Category(
        "error_handling",
        "Error handling, logging, monitoring",
        [
            "error",
            "exception",
            "logging",
            "monitoring",
            "observability",
            "alerting",
            "debug",
        ],
        priority=12,
    ),
    Category(
        "data_format",
        "Data formats, serialization",
        [
            "json",
            "xml",
            "yaml",
            "protobuf",
            "avro",
            "csv",
            "format",
            "serialization",
        ],
        priority=13,
    ),
    Category(
        "concurrency",
        "Concurrency, async, threading",
        [
            "async",
            "await",
            "thread",
            "concurrent",
            "parallel",
            "goroutine",
            "coroutine",
        ],
        priority=14,
    ),
]

# URL-based category hints (domain -> likely categories)
URL_CATEGORY_HINTS: dict[str, list[str]] = {
    "docs.python.org": ["language", "tooling"],
    "developer.mozilla.org": ["language", "api"],
    "kubernetes.io": ["deployment", "architecture"],
    "docker.com": ["deployment"],
    "aws.amazon.com": ["deployment", "cloud"],
    "docs.github.com": ["tooling", "deployment"],
    "grpc.io": ["api", "networking"],
    "redis.io": ["database", "caching"],
    "postgresql.org": ["database"],
    "tensorflow.org": ["machine_learning"],
    "pytorch.org": ["machine_learning"],
    "fastapi.tiangolo.com": ["api", "framework"],
    "django.readthedocs.io": ["api", "framework"],
    "nextjs.org": ["framework", "deployment"],
    "react.dev": ["framework", "language"],
}


def classify_topic(url: str = "", title: str = "", text: str = "") -> list[Category]:
    """Classify content into relevant categories.

    Uses keyword matching with priority ordering. Returns categories
    that matched, sorted by priority.

    Args:
        url: Source URL
        title: Source title
        text: Source text content

    Returns:
        List of matching categories sorted by priority
    """
    combined = f"{url} {title} {text}".lower()

    matched = []
    for category in CATEGORY_TAXONOMY:
        score = 0
        for keyword in category.keywords:
            if keyword in combined:
                score += 1
        if score > 0:
            matched.append((score, category))

    # Sort by score (desc) then priority (asc)
    matched.sort(key=lambda x: (-x[0], x[1].priority))
    return [cat for _, cat in matched[:5]]  # Top 5 categories


def get_relevant_categories(url: str = "", title: str = "", text: str = "") -> list[Category]:
    """Get relevant categories for a source URL/title/text.

    Combines URL hints with keyword-based classification.
    """
    # Start with URL hints
    hinted = _get_url_category_hints(url)

    # Add keyword-based classification
    classified = classify_topic(url, title, text)

    # Merge: URL hints first, then classified, deduplicated by name
    seen = set()
    result = []
    for cat in hinted + classified:
        if cat.name not in seen:
            seen.add(cat.name)
            result.append(cat)

    return result


def _get_url_category_hints(url: str) -> list[Category]:
    """Get category hints based on URL domain."""
    hints = []
    for domain, cat_names in URL_CATEGORY_HINTS.items():
        if domain in url.lower():
            for cat in CATEGORY_TAXONOMY:
                if cat.name in cat_names:
                    hints.append(cat)
    return hints


def find_categories_by_name(names: list[str]) -> list[Category]:
    """Find categories by name (case-insensitive)."""
    names_lower = {n.lower() for n in names}
    return [cat for cat in CATEGORY_TAXONOMY if cat.name.lower() in names_lower]
