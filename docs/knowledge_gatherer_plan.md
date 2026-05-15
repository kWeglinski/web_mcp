# Knowledge Gatherer — Architecture & Implementation Plan

> **Goal**: An MCP tool that takes a knowledge topic (e.g., "React Server Components"), searches the web, fetches actual documentation/pages, processes the content, and stores it as structured, source-anchored memories in mem0 — preventing memory bleed, preventing overflow, and preserving URL references for user follow-up.

---

## 1. Problem Statement

Your existing `add_memory` tool is a **free-text passthrough** — it accepts arbitrary text and feeds it to mem0's internal LLM extractor with zero grounding. This is the "memory bleed" problem: facts come from the model's training data, not from what you actually searched and fetched.

**The gap**: You have search, fetch, chunk, embed, and mem0 — but no tool that orchestrates them into a *grounded* pipeline.

### What You Already Have (80%)

| Component | Status |
|---|---|
| SearXNG search + BM25 reranking | ✅ `tools/search.py` |
| Trafilatura + Playwright fetchers | ✅ `tools/fetching.py` |
| Content store with TTL | ✅ `content_store.py` |
| Chunker with source_url tracking | ✅ `research/chunker.py` |
| LLM client (temperature 0.1) | ✅ `llm/client.py` |
| Mem0 (ChromaDB + HuggingFace) | ✅ `mem0/` |
| Citations module | ✅ `research/citations.py` |

**Missing 20%**: The orchestration layer that ties it all together with source anchoring and anti-bleed guarantees.

---

## 2. Tool API Design

### 2.1 Primary Tool: `gather_knowledge`

One orchestrator tool — the pipeline (search → fetch → extract → chunk → store) is inherently sequential, and breaking it into separate tools creates state management complexity.

```python
async def gather_knowledge(
    topic: str,              # "React Server Components"
    max_sources: int = 5,    # search results to fetch
    max_memories: int = 10,  # memories to store per topic
    depth: str = "standard", # "quick" | "standard" | "deep"
    ttl_hours: int | None = None,  # None = permanent
    force_refresh: bool = False,   # bypass dedup cache
) -> dict:
```

**Return format** (structured JSON, not free text):

```json
{
  "topic": "React Server Components",
  "collection": "project:react-rsc",
  "memories_created": [
    {
      "id": "mem_abc123",
      "fact": "React Server Components (RSC) allow components to run exclusively on the server, enabling direct database access without API layers.",
      "category": "definition",
      "source_url": "https://react.dev/reference/rsc",
      "source_title": "React Server Components",
      "confidence": 0.92
    }
  ],
  "memories_skipped_dedup": 3,
  "sources_fetched": 5,
  "sources_failed": 1,
  "elapsed_ms": 12400
}
```

### 2.2 Query Tool: `search_knowledge`

```python
async def search_knowledge(
    query: str,
    collection: str | None = None,     # scope filter
    max_results: int = 5,
    min_confidence: float = 0.0,
    include_sources: bool = True,
) -> list[dict]:
```

Returns the same format as mem0's search but with source anchoring and optional collection scoping.

### 2.3 Admin Tool: `manage_knowledge_collection`

```python
async def manage_knowledge_collection(
    action: str,                       # "list" | "delete" | "stats" | "compact"
    collection: str | None = None,
    user_id: str | None = None,
) -> dict:
```

For cleanup, stats, and lifecycle management.

---

## 3. Memory Organization

### 3.1 Collection Hierarchy

```
Collection (top-level scope)
├── user_id: "project:react-rsc" (mem0's native grouping)
│   ├── fact_1: "RSC runs on server..."
│   ├── fact_2: "RSC enables streaming..."
│   └── ...
```

**Key design decision**: Use mem0's native `user_id` for the collection namespace, but add a **topic tag** stored as metadata in each memory. Mem0's ChromaDB supports custom metadata filters, so we can scope queries by topic.

```python
memory.add(
    content=f"[TOPIC:{topic}] {fact_text}",
    user_id=collection or f"project:{project_name}",
    metadata={
        "topic": topic,
        "source_url": url,
        "source_title": title,
        "source_domain": "react.dev",
        "category": "definition",
        "confidence": 0.92,
        "gathered_at": timestamp,
        "ttl_hours": ttl_hours,
        "chunk_index": 3,
        "fact_id": "fact_rsc_001",
    }
)
```

### 3.2 Topic Naming Convention

```python
def topic_to_collection(topic: str) -> str:
    """Convert topic to a valid mem0 collection/user_id."""
    slug = topic.lower().strip().replace(" ", "-")
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    return f"project:{slug[:50]}"  # truncate to avoid identifier limits
```

### 3.3 Memory Categories

The LLM determines the category during extraction. This makes `search_knowledge` smarter — you can filter by category.

| Category | Example |
|---|---|
| `definition` | "RSC are components that run exclusively on the server" |
| `capability` | "RSC can directly access databases" |
| `pattern` | "Use 'use client' directive to opt into client components" |
| `limitation` | "Server components cannot use browser APIs" |
| `comparison` | "RSC vs Suspense: RSC is the foundation, Suspense is the UI pattern" |
| `api` | "Server Actions are async functions defined in server components" |
| `ecosystem` | "Next.js 13+ has RSC enabled by default in App Router" |

### 3.4 Deterministic Fact IDs

```python
def generate_fact_id(topic: str, source_url: str, fact_text: str) -> str:
    """Deterministic ID for dedup across sessions."""
    raw = f"{topic}:{source_url}:{fact_text}"
    return f"fact_{hashlib.sha256(raw.encode()).hexdigest()[:8]}"
```

Same fact from same URL → same ID → cross-session dedup.

---

## 4. Anti-Bleed Mechanisms

This is the most important section. Five layers of protection.

### 4.1 Layer 1 — Mandatory Source Anchoring

**Rule**: No memory is stored without a source URL. The pipeline always produces facts from *extracted page content*, never from raw user text or the LLM's internal knowledge.

```
User says "gather knowledge about X"
  → search (SearXNG) → get URLs
  → fetch each URL → extract text (trafilatura)
  → LLM extracts facts FROM the extracted text only
  → each fact tagged with source_url
  → stored in mem0 with source metadata
```

**Never** do:
```python
add_memory(user_id, "some random text")  # ← current tool, dangerous
```

### 4.2 Layer 2 — Source-Locked Extraction Prompt

The LLM that extracts facts from content must be given an explicit prompt that prevents training-data bleed:

```
You are extracting factual information from the following SOURCE TEXT.

RULES:
1. Extract ONLY facts that appear in the source text below
2. Each fact must be traceable to a specific sentence in the source
3. Do NOT add information from your training data
4. If the source says "X does Y", state exactly that — do not elaborate
5. For each fact, provide: the fact text, a category, and confidence (0-1)
6. If a fact cannot be directly supported by the source text, omit it

SOURCE TEXT (from {url}):
{extracted_text}
```

### 4.3 Layer 3 — Confidence Scoring

The LLM outputs a confidence score per fact:

| Score | Meaning |
|---|---|
| `0.9–1.0` | Explicitly stated in source, unambiguous |
| `0.7–0.9` | Inferred from multiple statements in source |
| `0.5–0.7` | Weakly supported, partial match |
| `< 0.5` | Flagged for review, still stored but marked low-confidence |

Low-confidence memories are still stored (for completeness) but `search_knowledge` can filter by `min_confidence`.

### 4.4 Layer 4 — Source Text Sampling for Verification

For high-value collections, add a verification step:

```
1. Extract N facts from source text
2. Re-prompt LLM: "For each fact below, quote the exact source sentence it came from"
3. If the LLM cannot produce a matching quote, mark the fact as unverifiable
```

This adds a second LLM call per batch but dramatically reduces bleed. **Recommendation**: enable only when `depth="deep"` or for critical topics.

### 4.5 Layer 5 — Temperature Control

Use `temperature=0.1` (already the default in `llm/config.py`) for extraction. Never use high temperature for fact extraction.

---

## 5. Deduplication Strategy

### 5.1 Multi-Layer Dedup

| Layer | How | When |
|---|---|---|
| **URL dedup** | In-memory LRU cache of processed URLs | Always |
| **Semantic dedup** | Embed candidate fact, compare cosine similarity vs existing memories in collection (threshold 0.85) | Always |
| **Cross-collection** | Flag facts that also exist in other collections | Optional |

### 5.2 Semantic Dedup Implementation

```python
async def is_duplicate(fact_text: str, collection: str, threshold: float = 0.85) -> bool:
    """Check if a fact is too similar to existing memories in the collection."""
    mem = mem0_manager.get_memory()
    existing = mem.get_all(user_id=collection)
    candidate_embedding = await embed_single(fact_text)
    
    for memory in existing:
        if "embedding" in memory:
            similarity = cosine_similarity(candidate_embedding, memory["embedding"])
            if similarity > threshold:
                return True
    return False
```

### 5.3 Dedup Cache

Since embedding is expensive, cache dedup decisions per topic:

```python
class DedupCache:
    """In-memory cache of which URLs have been processed."""
    def __init__(self, max_size: int = 1000):
        self._urls: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
    
    def has(self, url: str) -> bool: ...
    def add(self, url: str) -> None: ...
    def clear(self) -> None: ...
```

---

## 6. URL Reference Strategy

### 6.1 Metadata, Not Just Text

Every memory in mem0 gets enriched metadata:

```python
metadata = {
    "topic": topic,
    "source_url": "https://react.dev/reference/rsc",
    "source_title": "React Server Components",
    "source_domain": "react.dev",
    "category": "definition",
    "confidence": 0.95,
    "gathered_at": "2026-05-15T10:30:00Z",
    "ttl_hours": None,
    "chunk_index": 3,
    "fact_id": "fact_rsc_001",
}
```

### 6.2 Search Results Show Sources

When `search_knowledge` returns results:

```
Fact: "RSC can directly access databases"
Category: capability
Confidence: 0.92
Source: [React.dev](https://react.dev/reference/rsc) "React Server Components"
Memory ID: mem_abc123
```

The URL is clickable in MCP clients that support markdown links.

---

## 7. Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    gather_knowledge(topic)                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  1. QUERY REWRITE│
                    │  (optional)      │
                    │  sub-queries     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  2. WEB SEARCH   │
                    │  SearXNG + Brave │
                    │  dedup + BM25    │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │  3. URL FILTERING           │
              │  - skip docs if already     │
              │    in dedup cache           │
              │  - prioritize .edu, .gov,   │
              │    official docs            │
              │  - max N URLs to fetch      │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  4. PARALLEL FETCH          │
              │  - trafilatura (primary)    │
              │  - Playwright (fallback)    │
              │  - Content-Type routing     │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  5. CONTENT EXTRACTION      │
              │  - trafilatura HTML→text    │
              │  - chunk_text() with        │
              │    source_url tracking      │
              │  - merge_small_chunks()     │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  6. FACT EXTRACTION (per    │
              │     chunk or per page)      │
              │  - LLM prompt with source   │
              │    text locked              │
              │  - output: [fact, category, │
              │    confidence, source_ref]  │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  7. DEDUP CHECK             │
              │  - URL dedup (cache)        │
              │  - semantic similarity      │
              │    vs existing memories     │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  8. STORE IN MEM0           │
              │  - memory.add(content,      │
              │    user_id=collection,       │
              │    metadata={...})           │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼────────┐
                    │  9. RETURN      │
                    │  structured     │
                    │  summary        │
                    └─────────────────┘
```

### Depth Modes

| Mode | Sources | LLM Calls | Verification |
|---|---|---|---|
| `quick` | 3 | 1 total | No |
| `standard` | 5 | 1 per page | No |
| `deep` | 10 | 1 per page + verification | Yes |

### Concurrency Limits

```python
FETCH_SEMAPHORE = asyncio.Semaphore(5)    # max 5 concurrent fetches
EXTRACT_SEMAPHORE = asyncio.Semaphore(3)   # max 3 concurrent extractions
TOPIC_LOCKS: dict[str, asyncio.Lock]       # serialize same-topic calls
```

---

## 8. Overflow Prevention

### 8.1 Per-Collection Limits

```python
MAX_MEMORIES_PER_COLLECTION = 200
MAX_CHUNKS_PER_COLLECTION = 5000
```

When limits are hit, evict oldest (by `gathered_at` timestamp).

### 8.2 TTL on Memories

```python
# Configurable per topic
WEB_MCP_KNOWLEDGE_DEFAULT_TTL = "720"  # 30 days

# Can be overridden per gather_knowledge call
ttl_hours = 720  # or None for permanent
```

Mem0's ChromaDB doesn't natively support TTL, so implement a background cleanup task:

```python
async def knowledge_cleanup_loop():
    """Periodically evict expired memories."""
    while True:
        await asyncio.sleep(3600)  # every hour
        mem = mem0_manager.get_memory()
        all_memories = mem.get_all()
        expired = [
            m for m in all_memories
            if m.get("metadata", {}).get("ttl_hours")
            and time.time() > m.get("metadata", {}).get("gathered_at_ts", 0)
            + m["metadata"]["ttl_hours"] * 3600
        ]
        for m in expired:
            mem.delete(m["id"])
```

### 8.3 Topic Width Limits

Reject topics that are too broad:

```python
BROAD_TOPIC_SIGNALS = [
    r"^(the|all|every|complete|full)\s+(history|story|guide|overview|basics)",
    r"^what is [^,]{50,}$",  # extremely long "what is" queries
]

async def validate_topic(topic: str) -> str | None:
    """Return error message if topic is too broad."""
    for pattern in BROAD_TOPIC_SIGNALS:
        if re.search(pattern, topic, re.IGNORECASE):
            return f"Topic is too broad. Be specific (e.g., 'React Server Components' not 'complete guide to React')"
    return None
```

---

## 9. Verification: LLM Using Gathered Content vs Training Data

### 9.1 At Gather Time (what the gatherer controls)

- **Source-locked extraction** — the LLM extracts from source text, not from its own knowledge
- **Fact quoting** — each fact must be traceable to a source sentence
- **Confidence scoring** — low-confidence facts are flagged

### 9.2 At Query Time (what the consumer does)

The `search_knowledge` tool should return memories with their source URLs. The consuming LLM (Claude, etc.) should be prompted:

```
You have access to gathered knowledge from web research.
Each memory has a source URL. Answer using ONLY the provided memories.
Cite the source URL for each factual claim.
If you cannot answer from the provided memories, say so.
```

### 9.3 Cross-Check Metric (Optional, Expensive)

```python
async def verify_answer_against_sources(answer: str, memories: list[dict]) -> dict:
    """Check if the answer's claims are supported by the source memories."""
    # LLM call: "For each claim in this answer, find the supporting memory"
    # Returns: {supported: [...], unsupported: [...]}
```

Useful for critical applications but adds an extra LLM call.

---

## 10. New Config Variables

```python
# Knowledge Gatherer settings
WEB_MCP_KNOWLEDGE_MAX_SOURCES = 5                  # search results to fetch
WEB_MCP_KNOWLEDGE_MAX_MEMORIES = 10               # memories to store per topic
WEB_MCP_KNOWLEDGE_DEFAULT_TTL = 720               # 30 days (hours)
WEB_MCP_KNOWLEDGE_DEDUP_THRESHOLD = 0.85          # cosine similarity threshold
WEB_MCP_KNOWLEDGE_VERIFY_ENABLED = False          # enable 2nd-pass verification
WEB_MCP_KNOWLEDGE_MAX_COLLECTION_SIZE = 200       # hard cap per collection
WEB_MCP_KNOWLEDGE_DEPTH_MODE = "standard"         # default depth
```

---

## 11. File Structure

```
src/web_mcp/
├── knowledge/
│   ├── __init__.py          # exports: gather_knowledge, search_knowledge
│   ├── pipeline.py          # orchestrates the full gather flow
│   ├── extractor.py         # LLM-based fact extraction from source text
│   ├── dedup.py             # DedupCache + semantic dedup
│   ├── categories.py        # category taxonomy + classification prompt
│   ├── validation.py        # topic width validation, broad topic detection
│   └── cleanup.py           # TTL cleanup background task
├── mem0/
│   ├── __init__.py          # (existing, add metadata support)
│   └── tools.py             # (existing, replace with knowledge wrappers)
```

---

## 12. Changes to Existing Code

| File | Change |
|---|---|
| `mem0/tools.py` | **Replace entirely** — old tools are a liability. New tools wrap `knowledge.pipeline` |
| `mem0/__init__.py` | Add `metadata` parameter passthrough to `memory.add()` |
| `server.py` | Register `gather_knowledge`, `search_knowledge`, `manage_knowledge_collection` |
| `config.py` | Add 7 new `WEB_MCP_KNOWLEDGE_*` env vars |

### Replacement for `mem0/tools.py`

```python
# New mem0/tools.py
from web_mcp.knowledge.pipeline import gather_knowledge, search_knowledge
from web_mcp.knowledge.cleanup import manage_collection

# Old add_memory/search_memory/get_user_memories are gone.
# They were free-text passthroughs with zero grounding.
```

---

## 13. Edge Cases and Failure Modes

| Scenario | Handling |
|---|---|
| **SearXNG unavailable** | Skip search, require explicit URLs via fallback `gather_from_urls` tool |
| **All fetches fail** | Return early with error, no partial memories stored |
| **LLM extraction fails** | Retry once with backoff; if still failing, skip that source |
| **Page has no extractable text** (JS-only, captcha) | Skip to next source; log warning |
| **Dedup cache full** | LRU eviction of oldest entries |
| **Collection at max size** | Evict oldest memories by `gathered_at` |
| **Memory store (ChromaDB) unavailable** | Return error; no partial writes |
| **Topic is too broad** | Reject with suggestion to be more specific |
| **Source URL is malicious/unsafe** | SSRF protection (already in `security.py`) |
| **Extraction produces 0 facts** | Log warning, return empty result |
| **Concurrent gather calls for same topic** | Use `asyncio.Lock` per topic to serialize |
| **Large page (>1MB text)** | Chunk and process in parallel; cap at N chunks |
| **mem0 returns conflicting facts** | Store both with different confidence scores; newer one wins on update |

---

## 14. Implementation Priority

| Phase | Module | Depends On | Why First |
|---|---|---|---|
| 1 | `knowledge/extractor.py` | — | The anti-bleed core; everything else depends on it |
| 2 | `knowledge/pipeline.py` | extractor | Orchestrates the full flow, reuses existing search/fetch/chunk |
| 3 | `knowledge/dedup.py` | pipeline | URL cache + semantic dedup |
| 4 | `knowledge/categories.py` | pipeline | Classification prompt + taxonomy |
| 5 | `knowledge/validation.py` | pipeline | Topic width guardrails |
| 6 | `knowledge/cleanup.py` | pipeline | TTL background task |
| 7 | Update `mem0/tools.py` | pipeline | Replace old tools with knowledge wrappers |
| 8 | Update `server.py` + `config.py` | pipeline | Register tools, add env vars |
| 9 | Tests | All modules | Unit + integration tests |

---

## 15. Key Tradeoffs

| Decision | Choice | Rationale |
|---|---|---|
| Single orchestrator tool vs. pipeline tools | **Single tool** | Pipeline is inherently sequential; separate tools create state complexity |
| Store full text vs. extracted facts | **Facts only** | Full text is huge; facts are precise and queryable |
| Semantic dedup vs. textual hash | **Semantic** | Better accuracy across paraphrased facts |
| Verification step (2nd LLM call) | **Only in deep mode** | 2x cost, but dramatically reduces bleed for critical topics |
| TTL on memories | **Default 30 days** | Prevents unbounded growth; overrideable to `None` for permanent |
| Per-topic collections vs. flat user_id | **Per-topic** | Better organization, queryable by topic/category |

---

## 16. Example User Flow

```
User: "Gather knowledge about React Server Components"

→ gather_knowledge(topic="React Server Components", depth="standard")

→ Search: 5 URLs from SearXNG
→ Fetch: 5 pages via trafilatura (1 Playwright fallback)
→ Extract: ~15 facts from source text (source-locked LLM)
→ Dedup: 3 skipped (already seen or too similar)
→ Store: 12 memories in mem0, collection "project:react-rsc"

Return:
  memories_created: 12
  memories_skipped_dedup: 3
  sources_fetched: 5
  sources_failed: 0
  collection: "project:react-rsc"

---

User: "What do I know about RSC capabilities?"

→ search_knowledge(query="RSC capabilities", collection="project:react-rsc")

Return:
  [
    {
      "fact": "RSC can directly access databases without API layers",
      "category": "capability",
      "confidence": 0.95,
      "source_url": "https://react.dev/reference/rsc",
      "source_title": "React Server Components"
    },
    {
      "fact": "RSC can read files and query databases directly",
      "category": "capability",
      "confidence": 0.92,
      "source_url": "https://nextjs.org/docs/app/building-your-application/data-fetching/server-components",
      "source_title": "Next.js Server Components Docs"
    }
  ]
```

---

## 17. Non-Goals (Out of Scope)

These are intentionally excluded from v1:

- **Browser automation for JS-heavy docs** — use Playwright fallback only when trafilatura returns empty content
- **Automatic topic expansion** — don't guess related topics; let the user guide
- **Multi-language support** — assume English sources for v1
- **Real-time sync** — no incremental updates; re-gather to refresh
- **Collaborative collections** — single-user scoped per mem0 `user_id`
- **Vector index optimization** — ChromaDB handles embeddings; no custom index needed
