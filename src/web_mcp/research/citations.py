"""Citation formatting utilities."""

from dataclasses import dataclass
from typing import List, Optional, Dict
import re


@dataclass
class Source:
    """A source with citation info."""
    index: int
    url: str
    title: str
    snippet: Optional[str] = None


def extract_urls_from_text(text: str) -> List[str]:
    """Extract URLs mentioned in text."""
    if not text:
        return []
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return list(set(re.findall(url_pattern, text)))


def format_sources(sources: List[Source]) -> str:
    """Format sources as a numbered list.
    
    Args:
        sources: List of Source objects
    
    Returns:
        Formatted string with numbered sources
    """
    if not sources:
        return ""
    
    lines = []
    for source in sources:
        line = f"[{source.index}] {source.title}"
        if source.url:
            line += f"\n    {source.url}"
        lines.append(line)
    
    return "\n\n".join(lines)


def build_context_with_citations(
    chunks: List,
    max_context_chars: int = 120000,
) -> tuple[str, List[Source]]:
    """Build context string from chunks with citation markers.
    
    Args:
        chunks: List of (chunk, similarity) tuples
        max_context_chars: Maximum context size
    
    Returns:
        Tuple of (context_string, sources_list)
    """
    if not chunks:
        return "", []
    
    seen_urls = {}
    sources = []
    context_parts = []
    total_chars = 0
    
    for chunk, _score in chunks:
        url = chunk.source_url
        title = chunk.source_title or url
        
        if url not in seen_urls:
            idx = len(sources) + 1
            seen_urls[url] = idx
            sources.append(Source(
                index=idx,
                url=url,
                title=title,
                snippet=chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
            ))
        else:
            idx = seen_urls[url]
        
        citation_marker = f"[{idx}]"
        part = f"{citation_marker} {chunk.text}\n\n"
        
        if total_chars + len(part) > max_context_chars:
            break
        
        context_parts.append(part)
        total_chars += len(part)
    
    return "".join(context_parts), sources


def renumber_citations(text: str, sources: List[Source]) -> str:
    """Ensure citations in text match the sources list.
    
    This is a safety measure to ensure citation numbers are correct.
    Replaces invalid or outdated citation markers with valid ones based
    on the provided sources list.
    
    Args:
        text: Text containing citation markers like [1], [2]
        sources: List of Source objects with valid indices
        
    Returns:
        Text with corrected citation markers
    """
    if not sources:
        return text
    
    # Get valid source indices
    valid_indices = {s.index for s in sources}
    max_index = max(valid_indices) if valid_indices else 0
    
    # Find all citation markers in the text
    citation_pattern = r'\[(\d+)\]'
    matches = list(re.finditer(citation_pattern, text))
    
    if not matches:
        return text
    
    # Build a mapping of old indices to new valid indices
    # First, track which sources are referenced in the text
    referenced_indices = set()
    for match in matches:
        idx = int(match.group(1))
        if 1 <= idx <= max_index:
            referenced_indices.add(idx)
    
    # Create mapping: if LLM used wrong numbers, map them to valid ones
    # This handles cases where the LLM generates [1], [2] but sources are different
    # For now, we'll just validate and mark invalid citations
    
    result = text
    for match in matches:
        idx = int(match.group(1))
        
        # Check if this citation is valid
        if idx < 1 or idx > max_index:
            # Invalid citation - replace with placeholder
            result = result.replace(f'[{idx}]', '[?]')
    
    return result


def validate_citations(text: str, sources: List[Source]) -> dict:
    """Validate citations in text against available sources.
    
    Args:
        text: Text containing citation markers
        sources: List of Source objects
        
    Returns:
        Dictionary with validation results
    """
    if not sources:
        return {
            'valid': True,
            'invalid_count': 0,
            'missing_sources': [],
        }
    
    valid_indices = {s.index for s in sources}
    max_index = max(valid_indices) if valid_indices else 0
    
    # Find all citation markers
    citation_pattern = r'\[(\d+)\]'
    matches = list(re.finditer(citation_pattern, text))
    
    invalid = []
    missing_sources = []
    
    for match in matches:
        idx = int(match.group(1))
        
        if idx < 1 or idx > max_index:
            invalid.append(idx)
    
    # Check for missing sources (sources not cited but available)
    cited_indices = {int(m.group(1)) for m in matches}
    for source in sources:
        if source.index not in cited_indices:
            missing_sources.append(source)
    
    return {
        'valid': len(invalid) == 0,
        'invalid_count': len(invalid),
        'invalid_indices': invalid,
        'missing_sources': missing_sources,
    }


def fix_citation_renumbering(text: str, sources: List[Source]) -> str:
    """Fix citation numbers in text to match the actual source indices.
    
    This function creates a proper mapping between LLM-generated citation numbers
    and the actual source indices, then renumbers all citations accordingly.
    
    Args:
        text: Text containing citation markers like [1], [2]
        sources: List of Source objects with valid indices
        
    Returns:
        Text with properly renumbered citation markers
    """
    if not sources:
        return text
    
    # Create a mapping from old citation numbers to new ones
    # The LLM might generate [1], [2] but our sources might be different
    # We need to map LLM numbers to actual source indices
    
    # Find all unique citation numbers in the text
    citation_pattern = r'\[(\d+)\]'
    matches = list(re.finditer(citation_pattern, text))
    
    if not matches:
        return text
    
    # Get valid source indices
    valid_indices = {s.index for s in sources}
    
    # Create a mapping from LLM numbers to actual source indices
    # We'll map based on which sources are actually cited in the text
    cited_sources = [s for s in sources if s.index in valid_indices]
    
    # If LLM used numbers that don't match our sources, we need to fix
    # Find which source indices are actually referenced in the text
    cited_source_indices = set()
    for match in matches:
        idx = int(match.group(1))
        if 1 <= idx <= max(valid_indices) if valid_indices else 0:
            cited_source_indices.add(idx)
    
    # Create a mapping from LLM numbers to actual source indices
    # This is tricky - we need to figure out which LLM number maps to which source
    # For now, we'll use a simple approach: if LLM uses [1], map to first source
    # This assumes the LLM follows the order of sources in the context
    
    if not cited_source_indices:
        # No valid citations found, return as-is
        return text
    
    # Create a mapping: LLM number -> actual source index
    # We'll use the order of sources in the context to determine this
    source_list = list(sources)
    
    # Find all unique LLM numbers used in the text
    max_valid = max(valid_indices) if valid_indices else 0
    llm_numbers = sorted(set(int(m.group(1)) for m in matches if 1 <= int(m.group(1)) <= max_valid))
    
    # Map LLM numbers to actual source indices
    # If we have fewer sources than LLM numbers, map accordingly
    mapping = {}
    for i, llm_num in enumerate(llm_numbers):
        if i < len(source_list):
            mapping[llm_num] = source_list[i].index
        else:
            # No corresponding source, mark as invalid
            mapping[llm_num] = None
    
    # Replace citations in text
    result = text
    for match in matches:
        old_idx = int(match.group(1))
        if old_idx in mapping:
            new_idx = mapping[old_idx]
            if new_idx is not None:
                result = result.replace(f'[{old_idx}]', f'[{new_idx}]')
            else:
                result = result.replace(f'[{old_idx}]', '[?]')
    
    return result


def normalize_citation_numbers(text: str) -> str:
    """Normalize citation numbers in text to be sequential starting from 1.
    
    This is useful when the LLM generates citations that don't match
    the actual source indices, by renumbering them sequentially.
    
    Args:
        text: Text containing citation markers like [1], [2]
        
    Returns:
        Text with normalized sequential citation numbers
    """
    # Find all unique citation numbers in the text
    citation_pattern = r'\[(\d+)\]'
    matches = list(re.finditer(citation_pattern, text))
    
    if not matches:
        return text
    
    # Extract all unique citation numbers
    cited_numbers = sorted(set(int(m.group(1)) for m in matches))
    
    # Create a mapping from original numbers to sequential numbers
    number_map = {old: new for new, old in enumerate(cited_numbers, start=1)}
    
    # Replace citations in text
    result = text
    for match in matches:
        old_idx = int(match.group(1))
        new_idx = number_map.get(old_idx, old_idx)
        result = result.replace(f'[{old_idx}]', f'[{new_idx}]')
    
    return result
