"""Validation for knowledge gathering: topic width and fact quality."""

from __future__ import annotations

import logging
import re

from web_mcp.knowledge.extractor import Fact

logger = logging.getLogger(__name__)

# Topic width limits
MAX_TOPIC_WORDS = 5
MIN_TOPIC_WORDS = 1
BROAD_TOPIC_PATTERNS = [
    r"\b(all|every|complete|full|overview|guide|tutorial|introduction|beginner)\b.*\b(topic|language|framework|technology|tool)\b",
    r"\b(what is|how to|introduction to)\b",
    r"\b(comprehensive|extensive|massive)\b",
]


def validate_topic_width(topic: str) -> dict:
    """Validate that a search topic is not too broad.

    Args:
        topic: The search topic/query string

    Returns:
        dict with 'valid' (bool), 'issues' (list of strings), 'suggestion' (str or None)
    """
    issues = []
    topic_lower = topic.lower().strip()
    words = topic_lower.split()

    # Check word count
    if len(words) < MIN_TOPIC_WORDS:
        issues.append("Topic is too short (minimum 1 word)")
    if len(words) > MAX_TOPIC_WORDS:
        issues.append(f"Topic is too broad ({len(words)} words, max {MAX_TOPIC_WORDS})")

    # Check for broad patterns
    for pattern in BROAD_TOPIC_PATTERNS:
        if re.search(pattern, topic_lower):
            issues.append(f"Topic matches broad pattern: {pattern}")

    # Check if topic is a single common word
    common_words = {
        "python",
        "javascript",
        "api",
        "web",
        "cloud",
        "database",
        "ai",
        "ml",
    }
    if len(words) == 1 and words[0] in common_words:
        issues.append(
            f"Topic '{words[0]}' is too generic — narrow it down (e.g., 'Python async best practices')"
        )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestion": _suggest_narrower_topic(topic) if issues else None,
    }


def validate_fact_quality(facts: list[Fact]) -> dict:
    """Validate quality of extracted facts.

    Args:
        facts: List of Fact objects to validate

    Returns:
        dict with 'valid' (bool), 'issues' (list), 'stats' (dict)
    """
    issues = []
    stats = {
        "total": len(facts),
        "avg_confidence": 0.0,
        "min_confidence": 0.0,
        "max_confidence": 0.0,
        "with_source": 0,
        "with_category": 0,
        "short_facts": 0,
    }

    if not facts:
        return {
            "valid": False,
            "issues": ["No facts extracted"],
            "stats": stats,
        }

    confidences = [f.confidence for f in facts]
    stats["avg_confidence"] = sum(confidences) / len(confidences)
    stats["min_confidence"] = min(confidences)
    stats["max_confidence"] = max(confidences)

    for fact in facts:
        if fact.source_url:
            stats["with_source"] += 1
        if fact.category:
            stats["with_category"] += 1
        if len(fact.text) < 20:
            stats["short_facts"] += 1

    if stats["avg_confidence"] < 0.5:
        issues.append(f"Low average confidence: {stats['avg_confidence']:.2f}")
    if stats["short_facts"] > len(facts) * 0.3:
        issues.append(f"Too many short facts: {stats['short_facts']}/{len(facts)}")
    if stats["with_source"] < len(facts) * 0.5:
        issues.append(f"Many facts missing source URLs: {stats['with_source']}/{len(facts)}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "stats": stats,
    }


def _suggest_narrower_topic(topic: str) -> str:
    """Suggest a narrower version of a broad topic."""
    topic_lower = topic.lower()
    if re.search(r"\b(what is|how to|introduction to)\b", topic_lower):
        # Remove the broad prefix
        narrowed = re.sub(r"\b(what is|how to|introduction to)\s+", "", topic_lower).strip()
        return f"Try: '{narrowed}'"
    if re.search(r"\b(comprehensive|complete|full)\b", topic_lower):
        narrowed = re.sub(r"\b(comprehensive|complete|full)\s+", "", topic_lower).strip()
        return f"Try: '{narrowed}'"
    return "Try narrowing the topic — e.g., add specifics about use case, version, or context"
