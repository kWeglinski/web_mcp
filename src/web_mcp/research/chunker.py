"""Content chunking utilities."""

import re
from dataclasses import dataclass

# Common abbreviations that should not cause sentence splits
ABBREVIATIONS = {
    "dr",
    "mr",
    "mrs",
    "ms",
    "prof",
    "sr",
    "jr",
    "vs",
    "etc",
    "inc",
    "corp",
    "ltd",
    "co",
    "est",
    "vol",
    "no",
    "pp",
    "usa",
    "uk",
    "eu",
    "un",
    "api",
    "sdk",
    "url",
    "http",
    "https",
    "www",
    "fig",
    "figs",
    "table",
    "tables",
    "ed",
    "eds",
    "e.g",
    "i.e",
    "cf",
    "viz",
    "al",
    "ca",
    "v",
}

# Additional abbreviations for improved sentence splitting
ADDITIONAL_ABBREVIATIONS = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sr",
    "jr",
    "vs",
    "etc",
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "e.g",
    "i.e",
    "cf",
    "viz",
    "al",
    "ca",
    "v",
    "no.",
    "ed.",
    "eds.",
}

# Common sentence terminators
SENTENCE_TERMINATORS = {".", "!", "?"}

# Common sentence start patterns
SENTENCE_STARTERS = {
    "The",
    "A",
    "An",
    "This",
    "That",
    "These",
    "Those",
    "He",
    "She",
    "It",
    "We",
    "They",
    "You",
    "I",
    "He's",
    "She's",
    "It's",
    "We're",
    "They're",
    "You're",
    "He'll",
    "She'll",
    "It'll",
    "We'll",
    "They'll",
    "You'll",
    "He'd",
    "She'd",
    "It'd",
    "We'd",
    "They'd",
    "You'd",
    "He've",
    "She've",
    "We've",
    "They've",
    "Has",
    "Have",
    "Had",
    "Does",
    "Do",
    "Did",
    "Will",
    "Would",
    "Can",
    "Could",
    "Should",
    "May",
    "Might",
    "Must",
    "When",
    "Where",
    "Why",
    "How",
    "Who",
    "Which",
    "If",
    "Because",
    "Although",
    "While",
    "Since",
    "Until",
    "But",
    "Or",
    "And",
}


@dataclass
class Chunk:
    """A chunk of text with source information."""

    text: str
    source_url: str
    source_title: str
    index: int


def chunk_text(
    text: str,
    source_url: str,
    source_title: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[Chunk]:
    """Split text into overlapping chunks.

    Tries to split on sentence boundaries when possible.

    Args:
        text: The text to chunk
        source_url: URL of the source
        source_title: Title of the source
        chunk_size: Target size of each chunk in characters
        overlap: Overlap between chunks in characters

    Returns:
        List of Chunk objects
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_chunk = []
    current_size = 0
    chunk_index = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # Check if adding this sentence would exceed chunk size
        if current_size + sentence_len > chunk_size and current_chunk:
            # Finalize the current chunk
            chunk_text_content = " ".join(current_chunk)

            # Check if this is a valid chunk
            if len(chunk_text_content.strip()) > 0:
                chunks.append(
                    Chunk(
                        text=chunk_text_content,
                        source_url=source_url,
                        source_title=source_title,
                        index=chunk_index,
                    )
                )
                chunk_index += 1

            # Calculate overlap - try to preserve sentence boundaries
            if len(current_chunk) > 1:
                # Keep last few sentences for overlap
                overlap_sentences = []
                overlap_size = 0
                for sent in reversed(current_chunk):
                    if overlap_size + len(sent) <= overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_size += len(sent) + 1
                    else:
                        break
                current_chunk = overlap_sentences if overlap_sentences else [current_chunk[-1]]
            else:
                # Single sentence - use text-based overlap
                current_chunk = [current_chunk[-1]]

            current_size = sum(len(s) + 1 for s in current_chunk)

        current_chunk.append(sentence)
        current_size += sentence_len + 1

    # Add final chunk if valid
    if current_chunk:
        final_text = " ".join(current_chunk)
        if len(final_text.strip()) > 0:
            chunks.append(
                Chunk(
                    text=final_text,
                    source_url=source_url,
                    source_title=source_title,
                    index=chunk_index,
                )
            )

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences with improved handling of abbreviations.

    Protects common abbreviations from causing incorrect sentence splits,
    and handles edge cases like code snippets and non-English text.

    Args:
        text: The text to split

    Returns:
        List of sentence strings
    """
    if not text:
        return []

    # Protect abbreviations by replacing them temporarily
    protected = text

    # Handle common abbreviations with periods - more comprehensive list
    for abbr in ADDITIONAL_ABBREVIATIONS:
        # Match "abbr." but not at end of sentence
        protected = re.sub(
            rf"\b{re.escape(abbr)}\.\s+", f"{abbr}__DOT__ ", protected, flags=re.IGNORECASE
        )

    # Split on sentence boundaries with improved patterns
    # Look for .!? followed by space and uppercase letter or digit
    sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s+(?=\d)|(?<=\n)\s*"
    parts = re.split(sentence_pattern, protected)

    # Restore abbreviations and clean up
    sentences = []
    for part in parts:
        restored = part.replace("__DOT__", ".")
        # Clean up whitespace
        cleaned = " ".join(restored.split())

        # Only add if it looks like a valid sentence
        if cleaned.strip():
            # Check for minimum length and valid sentence structure
            if len(cleaned) > 0:
                sentences.append(cleaned.strip())

    # Fallback: return original text as single chunk if no sentences found
    if not sentences:
        return [text.strip()] if text.strip() else []

    # Post-processing: merge very short sentences with neighbors
    return _post_process_sentences(sentences)


def _post_process_sentences(sentences: list[str]) -> list[str]:
    """Post-process sentences to merge very short ones with neighbors.

    Args:
        sentences: List of sentence strings

    Returns:
        Post-processed list of sentences
    """
    if len(sentences) <= 1:
        return sentences

    result = []
    i = 0
    while i < len(sentences):
        current = sentences[i]

        # Check if this sentence is very short (less than 10 words)
        word_count = len(current.split())

        if word_count < 5 and i > 0:
            # Merge with previous sentence
            result[-1] = result[-1] + " " + current
        else:
            result.append(current)

        i += 1

    return result


def merge_small_chunks(chunks: list[Chunk], min_size: int = 200) -> list[Chunk]:
    """Merge chunks that are too small with their neighbors.

    Args:
        chunks: List of chunks to potentially merge
        min_size: Minimum size for a chunk

    Returns:
        List of chunks with small ones merged
    """
    if not chunks:
        return []

    merged = []
    current = None

    for chunk in chunks:
        if current is None:
            current = chunk
        elif current.source_url != chunk.source_url:
            if len(current.text.strip()) >= min_size or not merged:
                merged.append(current)
            current = chunk
        elif len(current.text) < min_size:
            current = Chunk(
                text=current.text + " " + chunk.text,
                source_url=current.source_url,
                source_title=current.source_title,
                index=current.index,
            )
        else:
            merged.append(current)
            current = chunk

    if current:
        merged.append(current)

    return merged
