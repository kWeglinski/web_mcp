"""BM25 ranking algorithm for search result reranking."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class Document:
    """A document for BM25 ranking."""

    id: int
    text: str
    tokens: list[str]
    original: dict


def tokenize(text: str) -> list[str]:
    """Tokenize text preserving short tokens and handling Unicode."""
    if not text:
        return []
    tokens = re.findall(r"\w+|[A-Za-z]{2,}", text.lower())
    return [t for t in tokens if not t.isdigit()]


def _parse_result_date(result: dict) -> datetime | None:
    """Extract date from search result, trying multiple field names."""
    for key in ("published_date", "publishedDate", "date", "pubdate"):
        val = result.get(key) or ""
        if not val:
            continue
        try:
            if isinstance(val, str):
                if val.endswith("Z"):
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                if "T" in val:
                    return datetime.fromisoformat(val)
                return datetime.strptime(val[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return None


def _freshness_score(result: dict, now: datetime | None = None) -> float:
    """Calculate freshness bonus (0.0 to 1.0).

    Results from the last 24h get full bonus, halved after that.
    Older than 30 days gets no freshness bonus.

    Args:
        result: Search result dict with optional date field.
        now: Optional fixed 'now' time for testing. Defaults to current time.
    """
    dt = _parse_result_date(result)
    if not dt:
        return 0.5

    if now is None:
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now(UTC)

    # Normalize both to naive UTC for comparison
    if now.tzinfo is not None:
        now = now.astimezone(UTC).replace(tzinfo=None)
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)

    age_days = abs((now - dt).total_seconds()) / 86400

    if age_days <= 1:
        return 1.0
    elif age_days <= 7:
        return 0.8
    elif age_days <= 30:
        return 0.5
    else:
        return 0.2


class BM25:
    """BM25 ranking implementation.

    BM25 is a probabilistic ranking function that estimates the relevance
    of documents to a given search query. It's widely used in information
    retrieval and is particularly effective for short queries.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        """Initialize BM25 with tuning parameters.

        Args:
            k1: Term frequency saturation parameter (default: 1.5)
            b: Document length normalization (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        self.documents: list[Document] = []
        self.doc_freqs: dict[str, int] = {}
        self.avgdl: float = 0.0
        self.idf_cache: dict[str, float] = {}

    def fit(self, documents: list[dict], text_field: str = "text") -> None:
        """Index documents for ranking.

        Args:
            documents: List of document dictionaries
            text_field: Field to use for text (default: "text")
        """
        self.documents = []
        self.doc_freqs = {}
        total_len = 0

        for i, doc in enumerate(documents):
            text = doc.get(text_field, "")
            tokens = tokenize(text)

            self.documents.append(
                Document(
                    id=i,
                    text=text,
                    tokens=tokens,
                    original=doc,
                )
            )

            total_len += len(tokens)

            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        n_docs = len(self.documents)
        self.avgdl = total_len / n_docs if n_docs > 0 else 0

        self.idf_cache = {}

    def _idf(self, token: str) -> float:
        """Calculate IDF for a token with caching."""
        if token in self.idf_cache:
            return self.idf_cache[token]

        n_docs = len(self.documents)
        df = self.doc_freqs.get(token, 0)

        idf = 0.0 if df == 0 else math.log((n_docs - df + 0.5) / (df + 0.5) + 1)

        self.idf_cache[token] = idf
        return idf

    def _score_document(self, query_tokens: list[str], doc: Document) -> float:
        """Calculate BM25 score for a single document."""
        if not doc.tokens or self.avgdl == 0:
            return 0.0

        score = 0.0
        doc_len = len(doc.tokens)
        doc_term_freqs: dict[str, int] = {}

        for token in doc.tokens:
            doc_term_freqs[token] = doc_term_freqs.get(token, 0) + 1

        for token in query_tokens:
            if token not in doc_term_freqs:
                continue

            tf = doc_term_freqs[token]
            idf = self._idf(token)

            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)

            score += idf * numerator / denominator

        return score

    def rank(self, query: str) -> list[tuple]:
        """Rank documents by relevance to query.

        Args:
            query: Search query string

        Returns:
            List of (document, score) tuples sorted by relevance
        """
        query_tokens = tokenize(query)

        if not query_tokens:
            return [(doc.original, 0.0) for doc in self.documents]

        scored = []
        for doc in self.documents:
            score = self._score_document(query_tokens, doc)
            scored.append((doc.original, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


def rerank_search_results(
    results: list[dict],
    query: str,
    title_field: str = "title",
    snippet_field: str = "snippet",
    freshness_weight: float = 0.15,
) -> list[dict]:
    """Rerank search results using BM25 + optional freshness scoring.

    Combines title and snippet for ranking, with title weighted higher.
    When results have date fields, combines BM25 score with freshness bonus.

    Args:
        results: List of search result dictionaries
        query: Original search query
        title_field: Field name for title
        snippet_field: Field name for snippet/content
        freshness_weight: Weight for freshness component (0.0 to 1.0)

    Returns:
        Reranked list of search results with added 'bm25_score' and optionally
        'combined_score' fields
    """
    if not results or not query:
        return results

    documents = []
    for result in results:
        title = result.get(title_field, "")
        snippet = result.get(snippet_field, "")
        combined = f"{title} {title} {snippet}"
        documents.append({"text": combined, "original": result})

    bm25 = BM25(k1=1.5, b=0.75)
    bm25.fit(documents, text_field="text")

    ranked = bm25.rank(query)

    reranked = []
    for original, score in ranked:
        result = original["original"].copy()
        result["bm25_score"] = round(score, 4)
        reranked.append(result)

    if freshness_weight > 0 and any(_parse_result_date(r) is not None for r in reranked):
        max_bm25 = max((r.get("bm25_score", 0) for r in reranked), default=1) or 1
        for r in reranked:
            bm25_norm = r.get("bm25_score", 0) / max_bm25
            fresh = _freshness_score(r)
            combined = bm25_norm * (1 - freshness_weight) + fresh * freshness_weight
            r["combined_score"] = round(combined, 4)
        reranked.sort(key=lambda x: x["combined_score"], reverse=True)

    return reranked
