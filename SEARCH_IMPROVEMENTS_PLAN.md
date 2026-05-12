# Web Search Improvements — Implementation Plan

All 12 improvements identified during the codebase analysis, organized by priority.
Each item includes file targets, implementation steps, and test strategy.

---

## Phase 1: P0 — High Impact, Low Effort

### 1. Cache Search Results

**Files:** `src/web_mcp/searxng.py`
**Effort:** ~1 hour

#### Problem
Search results are never cached. Two identical `search_web` calls always hit the network,
even against public SearXNG instances that may rate-limit.

#### Implementation

Add an LRU cache keyed on `(query, max_results)` with a configurable TTL.
Reuse the existing `LRUCache` class from `cache.py`.

```python
# In searxng.py — add near the top with other globals:
from web_mcp.cache import LRUCache

_SEARCH_CACHE_TTL = 300  # 5 minutes — search results are time-sensitive
_search_cache: LRUCache | None = None

def _get_search_cache() -> LRUCache:
    global _search_cache
    if _search_cache is None:
        _search_cache = LRUCache(max_size=50)
    return _search_cache

# In the search() function, wrap before queue logic:
cache = _get_search_cache()
cache_key = f"{query}:{max_results}"

cached = cache.get(cache_key)
if cached is not None:
    logger.info(f"[SearXNG] Cache hit for query: {query}")
    return cached

# ... existing queue logic ...

result = await _search_impl(query, max_results)
cache.set(cache_key, result, ttl=_SEARCH_CACHE_TTL)
return result
```

#### Tests (`tests/test_searxng_cache.py`)
- `test_search_cached_result_returns_immediately` — call same query twice, assert second returns cached
- `test_search_cache_miss_evicts_lru` — exceed cache size, assert oldest entry evicted
- `test_search_cache_key_includes_max_results` — different max_results produces different keys
- `test_search_cache_expires_after_ttl` — simulate time passing, assert cache miss after TTL

---

### 2. Deduplicate Search Results

**Files:** `src/web_mcp/server.py`, `src/web_mcp/searxng.py`
**Effort:** ~30 minutes

#### Problem
SearXNG can return duplicate URLs when results come from multiple engines or fallback instances.
No deduplication happens before BM25 reranking, wasting fetch budget and skewing scores.

#### Implementation

Add a dedup function in `searxng.py` and call it in both `search_web` tools.

```python
# In searxng.py:
def deduplicate_results(results: list[dict]) -> list[dict]:
    """Remove duplicate URLs, keeping the highest-scored version."""
    seen: dict[str, int] = {}  # url -> index in result list
    for i, r in enumerate(results):
        url = r.get("url", "").rstrip("/")
        if not url:
            continue
        existing = seen.get(url)
        if existing is None:
            seen[url] = i
        else:
            # Keep the one with higher score/bm25_score
            existing_score = results[existing].get("score", 0) or results[existing].get("bm25_score", 0)
            new_score = r.get("score", 0) or r.get("bm25_score", 0)
            if new_score > existing_score:
                results[existing] = r
    return [results[i] for i in seen.values()]

# In server.py search_web tool — add after results = await search(query, 30):
if results:
    results = deduplicate_results(results)

# In server.py brave_search tool — after fetching:
if results:
    results = deduplicate_results(results)
```

#### Tests (`tests/test_searxng_dedup.py`)
- `test_deduplicate_removes_exact_duplicates` — same URL twice, keep one
- `test_deduplicate_keeps_highest_scored` — same URL with different scores, keep higher
- `test_deduplicate_preserves_order_of_first_occurrence` — order determined by first appearance
- `test_deduplicate_handles_empty_urls` — results without URLs are skipped gracefully
- `test_deduplicate_no_change_when_all_unique` — all unique URLs pass through unchanged

---

### 3. Wire Up Query Rewriting

**Files:** `src/web_mcp/research/pipeline.py`, `src/web_mcp/research/query_rewriting.py`
**Effort:** ~1 hour

#### Problem
The research pipeline calls `search(query)` directly. The query rewriting module has
`rewrite_query`, `generate_sub_queries`, and `parallel_search_queries` but none are wired in.

#### Implementation

Add an optional query rewriting step to the research pipeline, gated behind a config flag.

```python
# In llm/config.py — add to ResearchConfig:
rewrite_enabled: bool = field(
    default_factory=lambda: os.environ.get("WEB_MCP_REWRITE_ENABLED", "true").lower() == "true"
)

# In research/pipeline.py — modify the research() function:
from web_mcp.research.query_rewriting import rewrite_query, generate_sub_queries

# After fetching search results data:
effective_query = query
sub_queries = [query]

if research_config.rewrite_enabled and llm_config.is_configured:
    # Step 1: rewrite the original query for better search terms
    rewritten = await rewrite_query(client, query)
    if rewritten and rewritten != query:
        effective_query = rewritten

    # Step 2: generate sub-queries for complex questions
    sub_queries = await generate_sub_queries(client, query)

# Step 3: run parallel searches if we have multiple queries
all_search_results = []
if len(sub_queries) > 1:
    for sq in sub_queries:
        try:
            results = await search(sq, max(3, search_results // len(sub_queries)))
            all_search_results.extend(results)
        except SearXNGError:
            continue
else:
    all_search_results = await search(effective_query, search_results)

# Step 4: deduplicate
all_search_results = deduplicate_results(all_search_results)[:search_results]

# Use all_search_results for the rest of the pipeline...
```

#### Tests (`tests/test_research_pipeline.py`)
- `test_research_uses_original_query_when_rewrite_disabled` — env var off, original query used
- `test_research_uses_rewritten_query_when_enabled` — rewrite returns different text, that text is used
- `test_research_parallel_searches_multiple_queries` — generate_sub_queries returns 3 queries, all called
- `test_research_falls_back_on_rewrite_failure` — LLM error during rewrite, original query used
- `test_research_deduplicates_parallel_results` — parallel searches produce duplicates, they're removed

---

### 4. Fix BM25 Tokenizer

**Files:** `src/web_mcp/research/bm25.py`
**Effort:** ~30 minutes

#### Problem
The `tokenize()` function uses `\w+` which:
- Drops single-character tokens ("AI", "ML", "UK" become empty)
- Doesn't handle CJK or accented characters well

#### Implementation

```python
# In research/bm25.py — replace tokenize():
def tokenize(text: str) -> list[str]:
    """Tokenize text preserving short tokens and handling Unicode."""
    if not text:
        return []
    # Use a regex that matches word characters including Unicode, plus
    # sequences of 2+ Latin letters for short tokens like "AI", "ML"
    tokens = re.findall(r"\w+|[A-Za-z]{2,}", text.lower())
    # Filter out pure-numeric tokens (they're rarely useful for search)
    return [t for t in tokens if not t.isdigit()]
```

#### Tests (`tests/test_bm25.py`) — add new test cases
- `test_tokenize_preserves_short_latin_tokens` — "AI", "ML", "UK" are kept
- `test_tokenize_handles_unicode` — accented chars like "caf\u00e9" are preserved
- `test_tokenize_filters_pure_numbers` — "123" is dropped, but "abc123" is kept
- `test_tokenize_reranking_quality_improves` — query "AI models" returns better results than before

---

## Phase 2: P1 — Medium Impact, Medium Effort

### 5. Add Time-Range Filter

**Files:** `src/web_mcp/searxng.py`, `src/web_mcp/server.py`
**Effort:** ~1 hour

#### Problem
SearXNG supports time-range filtering (`time_range`: day/week/month/year) but it's not exposed
in the `search()` function or any MCP tool.

#### Implementation

```python
# In searxng.py — add time_range parameter:
async def search(
    query: str,
    max_results: int = 10,
    time_range: str | None = None,  # day, week, month, year
) -> list[dict]:

# In the _search_instance JSON params:
params = {
    "q": query,
    "format": "json",
    "pageno": 1,
    "num_results": max_results,
}
if time_range:
    params["time_range"] = time_range

# In server.py — add to search_web tool:
@mcp.tool(...)
async def search_web(
    query: str = Field(description="Search query"),
    time_range: str | None = Field(
        default=None, description="Time range filter: day, week, month, or year"
    ),
) -> str:
    results = await search(query, 30, time_range=time_range)

# Same for brave_search — add optional time_range param (Brave supports "fresh"/"very_fresh")
```

#### Tests (`tests/test_searxng_time_range.py`)
- `test_search_passes_time_range_to_searxng` — time_range param sent in request
- `test_search_without_time_range_works_as_before` — no time_range, default behavior
- `test_search_web_tool_accepts_time_range_param` — MCP tool accepts and passes time_range
- `test_search_invalid_time_range_falls_back_gracefully` — invalid value doesn't crash

---

### 6. Limit Concurrent URL Fetching in Research Pipeline

**Files:** `src/web_mcp/research/pipeline.py`
**Effort:** ~30 minutes

#### Problem
The research pipeline uses `asyncio.gather(*fetch_tasks)` with no concurrency limit.
If search returns 10 URLs, that's 10 simultaneous fetches — easy to trigger rate limits.

#### Implementation

```python
# In research/pipeline.py:
_FETCH_SEMAPHORE = asyncio.Semaphore(5)  # max 5 concurrent fetches

async def _fetch_and_extract(url: str, title: str) -> FetchedContent:
    async with _FETCH_SEMAPHORE:  # <-- add this line at the start of function
        config = get_config()
        try:
            html = await fetch_url(url, config)
            # ... rest of existing implementation unchanged
```

#### Tests (`tests/test_research_concurrency.py`)
- `test_fetch_semaphore_limits_concurrent_requests` — 10 URLs, assert max 5 fetching at once
- `test_fetch_semaphore_allows_next_batch` — after one completes, another starts
- `test_fetch_semaphore_with_failed_requests` — failures don't block semaphore

---

### 7. Clean Up Dead Code in Reranking

**Files:** `src/web_mcp/research/reranking.py`
**Effort:** ~10 minutes

#### Problem
Three versions of the same function exist: `select_diverse_chunks`,
`select_diverse_chunks_v2`, and `select_diverse_chunks_rerank`. Only the first is used.

#### Implementation

```python
# In reranking.py:
# 1. Delete select_diverse_chunks_v2 (lines ~169-223)
# 2. Delete select_diverse_chunks_rerank (lines ~225-271)
# 3. Rename select_diverse_chunks -> select_diverse_chunks_v2 (rename to the better version)
# 4. Update all callers in pipeline.py to use the new name

# The v2 version has better scoring (combined_score = score * diversity_bonus)
# so it should be the canonical version.

# After renaming, update the import in pipeline.py:
from web_mcp.research.reranking import rerank_chunks, select_diverse_chunks_v2 as select_diverse_chunks
```

#### Tests
- No new tests needed — existing test in `tests/test_reranking.py` covers the function
- Run full test suite to verify nothing breaks

---

### 8. Add Brave Search as Primary Option

**Files:** `src/web_mcp/server.py`, `src/web_mcp/brave.py`
**Effort:** ~1 hour

#### Problem
Brave is only used as a fallback. Users with `BRAVE_API_KEY` set can't make it their primary search provider.

#### Implementation

```python
# In server.py — add config check:
_SEARCH_PROVIDER = os.environ.get("WEB_MCP_SEARCH_PROVIDER", "searxng")  # searxng or brave

# Modify search_web tool to check provider:
@mcp.tool(...)
async def search_web(query: str = Field(description="Search query")) -> str:
    if _SEARCH_PROVIDER == "brave":
        return await _search_brave(query)
    else:
        return await _search_searxng(query)

async def _search_brave(query: str) -> str:
    """Primary Brave search implementation."""
    from web_mcp.brave import BraveSearchError, parse_brave_to_markdown
    from web_mcp.brave import search as brave_search_impl

    try:
        results = await brave_search_impl(query, max_results=5)
        if not results:
            return "*No search results found*"

        from web_mcp.research.bm25 import rerank_search_results
        results = rerank_search_results(results, query)

        json_data = {"web": {"results": results}}
        return parse_brave_to_markdown(json_data, query, max_results=5)

    except BraveSearchError as e:
        return f"*Brave Search failed: {e.message}*"

async def _search_searxng(query: str) -> str:
    """Primary SearXNG search with Brave fallback implementation."""
    # ... existing search_web logic ...

# Update brave_search tool description:
"""Search the web via Brave Search API (primary). Use WEB_MCP_SEARCH_PROVIDER=brave to make it default."""
```

#### Tests (`tests/test_search_provider.py`)
- `test_search_uses_brave_when_configured` — env var set to brave, brave search called
- `test_search_uses_searxng_by_default` — no env var, searxng path taken
- `test_search_brave_fallback_when_key_missing` — brave configured but no API key, error message
- `test_brave_search_tool_always_uses_brave_api` — brave_search tool bypasses provider config

---

## Phase 3: P2 — Strategic Improvements

### 9. Add Content Freshness Scoring to BM25

**Files:** `src/web_mcp/research/bm25.py`
**Effort:** ~1.5 hours

#### Problem
BM25 scores don't consider result age. A 5-year-old article can outrank today's news for
time-sensitive queries like "Python release date" or "latest React version".

#### Implementation

```python
# In research/bm25.py — add freshness module-level function:
from datetime import datetime

def _parse_result_date(result: dict) -> datetime | None:
    """Extract date from search result, trying multiple field names."""
    for key in ("published_date", "publishedDate", "date", "pubdate"):
        val = result.get(key) or ""
        if not val:
            continue
        try:
            # Handle ISO format and "X ago" formats
            if val.endswith("Z"):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            if "T" in val:
                return datetime.fromisoformat(val)
            # Try YYYY-MM-DD
            return datetime.strptime(val[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return None

def _freshness_score(result: dict) -> float:
    """Calculate freshness bonus (0.0 to 1.0).

    Results from the last 24h get full bonus, halved after that.
    Older than 30 days gets no freshness bonus.
    """
    dt = _parse_result_date(result)
    if not dt:
        return 0.5  # neutral for unknown dates

    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.utcnow()
    age_days = (now - dt.replace(tzinfo=None)).total_seconds() / 86400

    if age_days <= 1:
        return 1.0
    elif age_days <= 7:
        return 0.8
    elif age_days <= 30:
        return 0.5
    else:
        return 0.2

# In rerank_search_results — combine BM25 score with freshness:
def rerank_search_results(
    results: list[dict],
    query: str,
    freshness_weight: float = 0.15,  # 15% weight to freshness
) -> list[dict]:
    if not results or not query:
        return results

    # ... existing BM25 logic to get bm25_scores ...

    # Normalize BM25 scores to 0-1 range
    max_bm25 = max(r.get("bm25_score", 0) for r in reranked) or 1

    # Combine with freshness
    final = []
    for r in reranked:
        bm25_norm = r.get("bm25_score", 0) / max_bm25
        fresh = _freshness_score(r)
        combined = bm25_norm * (1 - freshness_weight) + fresh * freshness_weight
        r["combined_score"] = round(combined, 4)

    final.sort(key=lambda x: x["combined_score"], reverse=True)
    return final
```

#### Tests (`tests/test_bm25_freshness.py`)
- `test_freshness_score_recent_result` — result from today gets score ~1.0
- `test_freshness_score_old_result` — result from 60 days ago gets low score
- `test_freshness_score_unknown_date` — no date field returns neutral 0.5
- `test_rerank_combines_bm25_and_freshness` — combined score is weighted mix
- `test_rerank_zero_freshweight_equals_bm25_only` — weight=0 gives same order as before

---

### 10. Multi-Query Search in Research Pipeline

**Files:** `src/web_mcp/research/pipeline.py`, `src/web_mcp/research/query_rewriting.py`
**Effort:** ~2 hours

#### Problem
The research pipeline only does a single search. Complex questions benefit from breaking
into sub-queries (e.g., "What are the pros and cons of React vs Vue?" needs separate searches
for React, Vue, and comparison).

#### Implementation

This builds on improvement #3 (wiring up query rewriting). Add the parallel search execution
and result merging:

```python
# In research/pipeline.py — after getting sub_queries from #3:

all_search_results = []
if len(sub_queries) > 1 and research_config.rewrite_enabled:
    # Execute sub-queries in parallel with concurrency limit
    semaphore = asyncio.Semaphore(3)

    async def bounded_search(q):
        async with semaphore:
            return await search(q, max(3, search_results // len(sub_queries)))

    tasks = [bounded_search(sq) for sq in sub_queries]
    search_responses = await asyncio.gather(*tasks, return_exceptions=True)

    for resp in search_responses:
        if isinstance(resp, list):
            all_search_results.extend(resp)
        elif isinstance(resp, Exception):
            logger.warning(f"Sub-query search failed: {resp}")

    # Deduplicate and limit
    all_search_results = deduplicate_results(all_search_results)
else:
    effective_query = await rewrite_query(client, query) or query
    all_search_results = await search(effective_query, search_results)

# Continue pipeline with all_search_results...
```

#### Tests (`tests/test_research_multi_query.py`)
- `test_research_uses_single_search_for_simple_queries` — no sub-queries generated
- `test_research_parallelizes_sub_queries` — 3 sub-queries, 3 search calls made
- `test_research_merges_parallel_results` — results from all sub-queries combined
- `test_research_handles_partial_failure` — 1 of 3 sub-query searches fails, others succeed
- `test_research_deduplicates_across_sub_queries` — overlapping results deduped

---

### 11. Add Search Analytics / Metrics

**Files:** `src/web_mcp/server.py`, `src/web_mcp/searxng.py`
**Effort:** ~1.5 hours

#### Problem
No visibility into search provider success rates, latency, or result quality.
Hard to diagnose why searches fail or which provider is most reliable.

#### Implementation

```python
# In searxng.py — add analytics tracking:
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class SearchMetrics:
    total_queries: int = 0
    cache_hits: int = 0
    provider_success: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    provider_failures: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    latencies: list[tuple[str, float]] = field(default_factory=list)  # (provider, ms)

_search_metrics = SearchMetrics()
_MAX_LATENCY_HISTORY = 100  # keep last 100 latency samples

def _record_search(provider: str, success: bool, latency_ms: float) -> None:
    _search_metrics.total_queries += 1
    if success:
        _search_metrics.provider_success[provider] += 1
    else:
        _search_metrics.provider_failures[provider] += 1

    _search_metrics.latencies.append((provider, latency_ms))
    if len(_search_metrics.latencies) > _MAX_LATENCY_HISTORY:
        _search_metrics.latencies.pop(0)

def get_search_metrics() -> dict:
    """Get search analytics as a serializable dict."""
    total = _search_metrics.total_queries or 1
    return {
        "total_queries": _search_metrics.total_queries,
        "cache_hit_rate": round(_search_metrics.cache_hits / total, 3),
        "provider_success_rates": {
            p: round(_search_metrics.provider_success[p] / total, 3)
            for p in _search_metrics.provider_success
        },
        "provider_failures": dict(_search_metrics.provider_failures),
        "avg_latency_ms": round(
            sum(l for _, l in _search_metrics.latencies) / len(_search_metrics.latencies), 1
        ) if _search_metrics.latencies else None,
    }

# In search() function:
import time as _time
start = _time.time()

# ... existing search logic ...

elapsed_ms = (_time.time() - start) * 1000
if result:
    _record_search("searxng", True, elapsed_ms)
else:
    _record_search("searxng", False, elapsed_ms)

# In server.py — add metrics tool:
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def search_metrics() -> dict:
    """Get search analytics: provider success rates, cache hit rate, avg latency."""
    return get_search_metrics()

# Also add to health endpoint:
def get_health_metrics() -> dict:
    metrics = { ... existing fields ... }
    metrics["search"] = get_search_metrics()
    return metrics
```

#### Tests (`tests/test_search_analytics.py`)
- `test_record_search_tracks_provider_success` — successful search recorded under provider key
- `test_record_search_tracks_failure` — failed search recorded in provider_failures
- `test_get_metrics_returns_all_fields` — all expected keys present in output dict
- `test_search_analytics_in_health_endpoint` — health tool includes search metrics section

---

### 12. Smarter Instance Selection for SearXNG Fallbacks

**Files:** `src/web_mcp/searxng.py`
**Effort:** ~1.5 hours

#### Problem
Public SearXNG fallback instances are selected via `random.shuffle()`. No tracking of which
instances are fast or reliable. Users waste time on slow/dead instances.

#### Implementation

```python
# In searxng.py — replace global blacklist with a full instance tracker:

@dataclass
class InstanceStats:
    url: str
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0

_instance_stats: dict[str, InstanceStats] = {}
_INSTANCE_CACHE_TTL = 3600

def _get_instance_score(instance_url: str) -> float:
    """Calculate a score for instance selection (higher = better).

    Combines success rate and average latency.
    """
    stats = _instance_stats.get(instance_url)
    if not stats:
        return 1.0  # neutral for unknown instances

    total = stats.success_count + stats.failure_count
    if total < 3:
        return 1.0  # not enough data yet

    success_rate = stats.success_count / total
    avg_latency = stats.total_latency_ms / total

    # Penalize slow instances: 1.0 at <500ms, 0.5 at 2000ms, 0.1 at 5000ms+
    latency_score = max(0.1, 1.0 - (avg_latency - 500) / 4500)

    return success_rate * latency_score

def _record_instance_result(url: str, success: bool, latency_ms: float) -> None:
    if url not in _instance_stats:
        _instance_stats[url] = InstanceStats(url=url)

    stats = _instance_stats[url]
    if success:
        stats.success_count += 1
    else:
        stats.failure_count += 1
    stats.total_latency_ms += latency_ms

# In _search_impl — replace random.shuffle with weighted selection:
if available_fallbacks:
    # Score and sort instances by reliability + speed
    scored = [(u, _get_instance_score(u)) for u in available_fallbacks]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top N, shuffle within same score tier to distribute load
    top_instances = [u for u, _ in scored[:MAX_RETRIES]]

    # Add some randomness: 20% chance to try a lower-ranked instance
    if len(scored) > MAX_RETRIES and random.random() < 0.2:
        lower = [u for u, s in scored[MAX_RETRIES:] if s > 0.5]
        if lower:
            top_instances[random.randint(0, len(top_instances) - 1)] = random.choice(lower)

    for attempt, instance_url in enumerate(top_instances):
        start = time.time()
        try:
            result = await _search_instance(instance_url, query, max_results, force_html=True)
            elapsed_ms = (time.time() - start) * 1000
            _record_instance_result(instance_url, True, elapsed_ms)
            logger.info(f"[SearXNG] Success from fallback - got {len(result)} results")
            return result
        except SearXNGError as e:
            elapsed_ms = (time.time() - start) * 1000
            _record_instance_result(instance_url, False, elapsed_ms)
            logger.warning(f"[SearXNG] Fallback failed: {e.message}")

# Also record for configured instance and DuckDuckGo
```

#### Tests (`tests/test_instance_selection.py`)
- `test_get_instance_score_unknown_returns_neutral` — no stats, score is 1.0
- `test_get_instance_score_high_success_rate` — mostly successful instance scores high
- `test_get_instance_score_slow_penalized` — slow instance gets lower score than fast one
- `test_search_prefers_higher_scored_instances` — top-scoring instances tried first
- `test_instance_stats_recorded_after_use` — stats updated after successful/failed request

---

## Summary Table

| # | Improvement | Priority | Effort | Files Changed |
|---|-------------|----------|--------|---------------|
| 1 | Cache search results | P0 | 1h | `searxng.py` |
| 2 | Deduplicate search results | P0 | 30m | `searxng.py`, `server.py` |
| 3 | Wire up query rewriting | P0 | 1h | `pipeline.py`, `query_rewriting.py` |
| 4 | Fix BM25 tokenizer | P0 | 30m | `bm25.py` |
| 5 | Add time-range filter | P1 | 1h | `searxng.py`, `server.py` |
| 6 | Limit concurrent URL fetching | P1 | 30m | `pipeline.py` |
| 7 | Clean up dead code | P1 | 10m | `reranking.py` |
| 8 | Brave as primary provider | P1 | 1h | `server.py`, `brave.py` |
| 9 | Freshness scoring in BM25 | P2 | 1.5h | `bm25.py` |
| 10 | Multi-query search in research | P2 | 2h | `pipeline.py`, `query_rewriting.py` |
| 11 | Search analytics / metrics | P2 | 1.5h | `server.py`, `searxng.py` |
| 12 | Smarter instance selection | P2 | 1.5h | `searxng.py` |

**Total estimated effort: ~12 hours**

---

## Recommended Execution Order

Run phases sequentially since later items build on earlier ones:

1. **Phase 1** (items 1-4) — quick wins, no dependencies between them
2. **Phase 2** (items 5-8) — can run in parallel with each other
3. **Phase 3** (items 9-12) — item #10 depends on #3, run after Phase 1

After each phase, run `make check` to verify lint + format + typecheck + tests pass.
