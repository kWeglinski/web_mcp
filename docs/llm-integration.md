# LLM Integration Guide

## Overview

The Web Browsing MCP Server integrates with OpenAI-compatible APIs for chat completions and embeddings. This guide covers the LLM client, configuration, and usage.

## Architecture

```
LLM Client
    ↓
OpenAI-compatible API
    ↓
LLM Service (OpenAI, Anthropic, etc.)
```

## LLM Client ([`llm/client.py`](../src/web_mcp/llm/client.py))

### LLMClient Class

```python
from web_mcp.llm.client import LLMClient, get_llm_client

# Get client instance
client = get_llm_client()

# Use the client
result = await client.chat(messages)
```

### Methods

#### `chat(messages, max_tokens=None, temperature=None)`

Generate a chat completion.

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
]

result = await client.chat(messages)
print(result)  # Assistant's response
```

#### `chat_stream(messages, max_tokens=None, temperature=None)`

Stream a chat completion.

```python
async for chunk in client.chat_stream(messages):
    print(chunk, end="")
```

#### `embed(texts)`

Generate embeddings for a list of texts.

```python
texts = ["Hello", "World"]
embeddings = await client.embed(texts)
# Returns: List[List[float]]
```

## Configuration ([`llm/config.py`](../src/web_mcp/llm/config.py))

### Environment Variables

```bash
# API Key (required)
WEB_MCP_LLM_API_KEY=sk-...

# API Endpoint
WEB_MCP_LLM_API_URL=https://api.openai.com/v1

# Generation Model
WEB_MCP_LLM_MODEL=gpt-4o

# Embedding Model
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small

# Max Tokens
WEB_MCP_LLM_MAX_TOKENS=4096

# Temperature
WEB_MCP_LLM_TEMPERATURE=0.7

# Request Timeout
WEB_MCP_LLM_REQUEST_TIMEOUT=30
```

### Configuration Object

```python
from web_mcp.llm.config import get_llm_config, LLMConfig

config = get_llm_config()

print(f"API Key: {config.api_key}")
print(f"API URL: {config.api_url}")
print(f"Model: {config.model}")
print(f"Embed Model: {config.embedding_model}")
print(f"Is Configured: {config.is_configured}")
```

### LLMConfig Structure

```python
@dataclass
class LLMConfig:
    api_key: str              # API key for the service
    api_url: str             # Base URL of the API
    model: str               # Model for chat completions
    embedding_model: str     # Model for embeddings
    max_tokens: int          # Maximum tokens for generation
    temperature: float       # Temperature for generation
    request_timeout: int     # Request timeout in seconds
    
    @property
    def is_configured(self) -> bool:
        # Returns True if API key and URL are set
```

## Using the LLM Client

### Chat Completion

```python
from web_mcp.llm.client import get_llm_client

async def chat_example():
    client = get_llm_client()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is quantum computing?"}
    ]
    
    response = await client.chat(messages)
    print(response)
```

### Streaming Chat

```python
from web_mcp.llm.client import get_llm_client

async def stream_example():
    client = get_llm_client()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing."}
    ]
    
    async for chunk in client.chat_stream(messages):
        print(chunk, end="")
```

### Embeddings

```python
from web_mcp.llm.client import get_llm_client
from web_mcp.llm.embeddings import embed_query, find_most_relevant

async def embedding_example():
    client = get_llm_client()
    
    # Embed a single query
    query_embedding = await embed_query(client, "quantum computing")
    
    # Embed multiple texts
    texts = ["Quantum computing", "Classical computing"]
    embeddings = await client.embed(texts)
    
    # Find most relevant chunks
    relevant = find_most_relevant(query_embedding, embeddings, top_k=5)
```

## Supported LLM Services

### OpenAI

```bash
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
WEB_MCP_LLM_MODEL=gpt-4o
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small
```

### Anthropic (via OpenAI-compatible API)

```bash
WEB_MCP_LLM_API_URL=https://api.anthropic.com/v1
WEB_MCP_LLM_MODEL=claude-3-opus
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small
```

### Local LLMs (Ollama, vLLM, etc.)

```bash
WEB_MCP_LLM_API_URL=http://localhost:11434/v1
WEB_MCP_LLM_MODEL=llama3
WEB_MCP_LLM_EMBED_MODEL=nomic-embed-text
```

## Error Handling

### LLMError

```python
from web_mcp.llm.client import LLMError

try:
    result = await client.chat(messages)
except LLMError as e:
    print(f"LLM error: {e}")
```

### Common Errors

1. **Authentication Error**
   - Check API key
   - Verify API URL

2. **Rate Limit Error**
   - Implement retry logic
   - Reduce request rate

3. **Timeout Error**
   - Increase timeout
   - Check network connection

## Best Practices

1. **Cache embeddings** for repeated queries
2. **Use streaming** for long responses
3. **Handle errors gracefully**
4. **Set appropriate timeouts**
5. **Use temperature control** for different use cases

## Example: Research Pipeline

```python
from web_mcp.llm.client import get_llm_client
from web_mcp.llm.embeddings import embed_query, find_most_relevant

async def research_pipeline(query: str):
    client = get_llm_client()
    
    # Embed the query
    query_embedding = await embed_query(client, query)
    
    # Find relevant chunks (from research pipeline)
    relevant = find_most_relevant(query_embedding, embedded_chunks, top_k=10)
    
    # Build context
    context = "\n\n".join([c.text for c, _ in relevant])
    
    # Generate answer
    messages = [
        {"role": "system", "content": f"Answer based on context:\n{context}"},
        {"role": "user", "content": query}
    ]
    
    answer = await client.chat(messages)
    return answer
```

## Configuration Examples

### Production Setup

```bash
# OpenAI with GPT-4
WEB_MCP_LLM_API_KEY=sk-...
WEB_MCP_LLM_API_URL=https://api.openai.com/v1
WEB_MCP_LLM_MODEL=gpt-4o
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small
WEB_MCP_LLM_MAX_TOKENS=8192
WEB_MCP_LLM_TEMPERATURE=0.7
```

### Local Development

```bash
# Ollama with Llama 3
WEB_MCP_LLM_API_URL=http://localhost:11434/v1
WEB_MCP_LLM_MODEL=llama3
WEB_MCP_LLM_EMBED_MODEL=nomic-embed-text
```

### Custom LLM Service

```bash
# Self-hosted LLM
WEB_MCP_LLM_API_URL=http://localhost:8000/v1
WEB_MCP_LLM_MODEL=custom-model
WEB_MCP_LLM_EMBED_MODEL=custom-embed
```
