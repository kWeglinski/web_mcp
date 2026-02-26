"""Context optimization for web content extraction."""

import re
from typing import Optional

from .config import Config, get_config


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.
    
    Rough estimate: 1 token ≈ 4 characters
    This is a simplified estimation - actual token count varies by tokenizer.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Simple estimation: ~4 characters per token
    return len(text) // 4


def truncate_text(
    text: str, 
    max_tokens: int,
    config: Optional[Config] = None
) -> str:
    """Truncate text to fit within token limit.
    
    Args:
        text: Input text
        max_tokens: Maximum allowed tokens
        config: Optional configuration for truncation strategy
        
    Returns:
        Truncated text
    """
    if not config:
        config = get_config()
    
    estimated_tokens = estimate_tokens(text)
    
    # No truncation needed
    if estimated_tokens <= max_tokens:
        return text
    
    # Calculate how much to keep
    ratio = max_tokens / estimated_tokens
    
    if config.truncation_strategy == "smart":
        return _smart_truncate(text, ratio)
    else:
        return _simple_truncate(text, ratio)


def _simple_truncate(text: str, ratio: float) -> str:
    """Simple character-based truncation."""
    if not text:
        return text
    
    target_length = int(len(text) * ratio)
    return text[:target_length]


def _smart_truncate(text: str, ratio: float) -> str:
    """Smart truncation that preserves structure."""
    if not text:
        return text
    
    # Split into paragraphs
    paragraphs = re.split(r'\n\n+', text)
    
    # Calculate target paragraph count
    target_count = max(1, int(len(paragraphs) * ratio))
    
    # Keep first N paragraphs
    kept_paragraphs = paragraphs[:target_count]
    
    return '\n\n'.join(kept_paragraphs)


def optimize_content(
    text: str,
    max_tokens: int,
    config: Optional[Config] = None
) -> dict:
    """Optimize content for context window.
    
    Args:
        text: Extracted text
        max_tokens: Maximum allowed tokens
        config: Optional configuration
        
    Returns:
        Dict with optimized content and metadata
    """
    if not config:
        config = get_config()
    
    estimated_tokens = estimate_tokens(text)
    
    # Check if we need truncation
    needs_truncation = estimated_tokens > max_tokens
    
    if needs_truncation:
        optimized_text = truncate_text(text, max_tokens, config)
        optimization_info = {
            "original_tokens": estimated_tokens,
            "truncated_tokens": estimate_tokens(optimized_text),
            "truncated": True,
        }
    else:
        optimized_text = text
        optimization_info = {
            "original_tokens": estimated_tokens,
            "truncated": False,
        }
    
    return {
        "text": optimized_text,
        "optimization_info": optimization_info,
    }
