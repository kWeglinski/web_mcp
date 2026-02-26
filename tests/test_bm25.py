"""Tests for BM25 ranking."""

import pytest

from web_mcp.research.bm25 import BM25, rerank_search_results, tokenize


class TestTokenize:
    def test_tokenize_basic(self):
        result = tokenize("Hello World")
        assert result == ["hello", "world"]
    
    def test_tokenize_with_punctuation(self):
        result = tokenize("Hello, World! How are you?")
        assert result == ["hello", "world", "how", "are", "you"]
    
    def test_tokenize_empty(self):
        result = tokenize("")
        assert result == []
    
    def test_tokenize_single_char_filtered(self):
        result = tokenize("a b c d")
        assert result == []
    
    def test_tokenize_numbers(self):
        result = tokenize("test123 abc456")
        assert "test123" in result
        assert "abc456" in result


class TestBM25:
    def test_fit_and_rank(self):
        bm25 = BM25()
        docs = [
            {"text": "python programming language", "id": 1},
            {"text": "java programming language", "id": 2},
            {"text": "cooking recipes", "id": 3},
        ]
        bm25.fit(docs)
        
        ranked = bm25.rank("python programming")
        
        assert len(ranked) == 3
        assert ranked[0][0]["id"] == 1
    
    def test_rank_empty_query(self):
        bm25 = BM25()
        docs = [{"text": "hello world", "id": 1}]
        bm25.fit(docs)
        
        ranked = bm25.rank("")
        
        assert len(ranked) == 1
        assert ranked[0][1] == 0.0
    
    def test_rank_no_matching_docs(self):
        bm25 = BM25()
        docs = [{"text": "cooking recipes", "id": 1}]
        bm25.fit(docs)
        
        ranked = bm25.rank("python programming")
        
        assert len(ranked) == 1
        assert ranked[0][1] == 0.0
    
    def test_empty_documents(self):
        bm25 = BM25()
        bm25.fit([])
        
        ranked = bm25.rank("test")
        
        assert ranked == []


class TestRerankSearchResults:
    def test_rerank_basic(self):
        results = [
            {"title": "Java Programming", "url": "http://example.com/java", "snippet": "Learn Java"},
            {"title": "Python Tutorial", "url": "http://example.com/python", "snippet": "Learn Python programming"},
            {"title": "Cooking Recipes", "url": "http://example.com/cook", "snippet": "Best recipes"},
        ]
        
        reranked = rerank_search_results(results, "python programming")
        
        assert len(reranked) == 3
        assert "bm25_score" in reranked[0]
        assert reranked[0]["title"] == "Python Tutorial"
    
    def test_rerank_empty_results(self):
        reranked = rerank_search_results([], "test query")
        assert reranked == []
    
    def test_rerank_empty_query(self):
        results = [{"title": "Test", "url": "http://example.com", "snippet": "Content"}]
        reranked = rerank_search_results(results, "")
        assert len(reranked) == 1
    
    def test_rerank_preserves_fields(self):
        results = [
            {"title": "Test", "url": "http://example.com", "snippet": "Content", "score": 0.9}
        ]
        reranked = rerank_search_results(results, "test")
        
        assert "score" in reranked[0]
        assert "bm25_score" in reranked[0]
    
    def test_rerank_title_weighted_higher(self):
        results = [
            {"title": "Python", "url": "http://a.com", "snippet": "Java programming"},
            {"title": "Java", "url": "http://b.com", "snippet": "Python programming"},
        ]
        
        reranked = rerank_search_results(results, "python")
        
        assert reranked[0]["title"] == "Python"
