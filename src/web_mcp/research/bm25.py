"""BM25 ranking algorithm for search result reranking."""

import math
import re
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Document:
    """A document for BM25 ranking."""
    id: int
    text: str
    tokens: List[str]
    original: Dict


def tokenize(text: str) -> List[str]:
    """Simple tokenization: lowercase and split on non-alphanumeric."""
    if not text:
        return []
    return [t.lower() for t in re.findall(r'\w+', text) if len(t) > 1]


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
        self.documents: List[Document] = []
        self.doc_freqs: Dict[str, int] = {}
        self.avgdl: float = 0.0
        self.idf_cache: Dict[str, float] = {}
    
    def fit(self, documents: List[Dict], text_field: str = "text") -> None:
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
            
            self.documents.append(Document(
                id=i,
                text=text,
                tokens=tokens,
                original=doc,
            ))
            
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
        
        if df == 0:
            idf = 0.0
        else:
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
        
        self.idf_cache[token] = idf
        return idf
    
    def _score_document(self, query_tokens: List[str], doc: Document) -> float:
        """Calculate BM25 score for a single document."""
        if not doc.tokens or self.avgdl == 0:
            return 0.0
        
        score = 0.0
        doc_len = len(doc.tokens)
        doc_term_freqs: Dict[str, int] = {}
        
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
    
    def rank(self, query: str) -> List[tuple]:
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
    results: List[Dict],
    query: str,
    title_field: str = "title",
    snippet_field: str = "snippet",
) -> List[Dict]:
    """Rerank search results using BM25.
    
    Combines title and snippet for ranking, with title weighted higher.
    
    Args:
        results: List of search result dictionaries
        query: Original search query
        title_field: Field name for title
        snippet_field: Field name for snippet/content
        
    Returns:
        Reranked list of search results with added 'bm25_score' field
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
    
    return reranked
