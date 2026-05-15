"""Extract grounded facts from web content using LLM."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """A single grounded fact with source citation."""

    text: str  # The fact statement
    source_url: str  # URL the fact came from
    source_title: str = ""  # Page title
    confidence: float = 0.0  # 0.0-1.0 extracted confidence
    category: str = ""  # Category from taxonomy
    chunk_index: int = 0  # Which chunk this came from
    snippet: str = ""  # Context snippet (truncated source text)


@dataclass
class FactExtractionResult:
    """Result of fact extraction from a single source."""

    source_url: str
    source_title: str
    facts: list[Fact] = field(default_factory=list)
    chunks_processed: int = 0
    total_chunks: int = 0
    extraction_error: str | None = None


# Prompt for fact extraction
FACT_EXTRACTION_PROMPT = """You are a factual extraction engine. Extract all verifiable, specific facts from the provided text.

Rules:
- Extract only concrete, verifiable facts (numbers, names, dates, relationships, claims)
- Do NOT extract opinions, opinions, speculation, or marketing language
- Each fact must be independently verifiable
- If a fact mentions a statistic, include the number and what it refers to
- Keep facts concise (max 2 sentences each)
- Return ONLY a JSON array, no other text

Format each fact as:
{{
  "text": "factual statement",
  "confidence": 0.95,
  "category": "category_name"
}}

Categories to choose from (pick the most relevant):
{categories}

Text to extract from:
{text}
"""


async def extract_facts(
    text: str,
    source_url: str,
    source_title: str = "",
    chunk_index: int = 0,
    max_facts: int = 20,
    min_confidence: float = 0.0,
    llm_client=None,
    model: str | None = None,
) -> FactExtractionResult:
    """Extract facts from text using LLM.

    Args:
        text: The text to extract facts from
        source_url: Source URL for citation
        source_title: Source page title
        chunk_index: Which chunk this is (for tracking)
        max_facts: Maximum facts to extract
        min_confidence: Minimum confidence threshold
        llm_client: LLMClient instance (creates one if not provided)
        model: Override model name (uses config default if None)

    Returns:
        FactExtractionResult with extracted facts
    """
    from web_mcp.config import get_config
    from web_mcp.knowledge.categories import get_relevant_categories

    config = get_config()
    extract_model = model or config.knowledge_extract_model

    # Get relevant categories for this source
    categories = get_relevant_categories(source_url, source_title, text)
    cat_list = ", ".join(c.name for c in categories)

    # Build prompt with chunks
    # (text may already be chunked by the pipeline)
    prompt = FACT_EXTRACTION_PROMPT.format(
        categories=cat_list,
        text=text[:8000],  # Truncate very long text
    )

    messages = [{"role": "user", "content": prompt}]

    try:
        if llm_client is None:
            from web_mcp.llm.client import LLMClient

            llm_client = LLMClient()

        response = await llm_client.chat(messages, model=extract_model)

        # Parse JSON from response
        facts = _parse_facts(
            response, source_url, source_title, chunk_index, max_facts, min_confidence
        )

        return FactExtractionResult(
            source_url=source_url,
            source_title=source_title,
            facts=facts,
            chunks_processed=1,
            total_chunks=1,
        )
    except Exception as e:
        logger.error(f"Fact extraction failed for {source_url}: {e}")
        return FactExtractionResult(
            source_url=source_url,
            source_title=source_title,
            facts=[],
            chunks_processed=0,
            total_chunks=1,
            extraction_error=str(e),
        )


def _parse_facts(
    response: str,
    source_url: str,
    source_title: str,
    chunk_index: int,
    max_facts: int,
    min_confidence: float,
) -> list[Fact]:
    """Parse LLM response into Fact objects."""
    # Try to extract JSON from response
    json_match = re.search(r"\[.*\]", response, re.DOTALL)
    if not json_match:
        logger.warning("No JSON array found in fact extraction response")
        return []

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from fact extraction response")
        return []

    facts = []
    for item in data[:max_facts]:
        if not isinstance(item, dict):
            continue
        text = item.get("text", "")
        if not text or len(text) < 10:
            continue

        confidence = float(item.get("confidence", 0.8))
        if confidence < min_confidence:
            continue

        facts.append(
            Fact(
                text=text,
                source_url=source_url,
                source_title=source_title,
                confidence=confidence,
                category=item.get("category", ""),
                chunk_index=chunk_index,
            )
        )

    return facts
