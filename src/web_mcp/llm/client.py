"""LLM client for OpenAI-compatible APIs."""

import json
from typing import Any, AsyncIterator, List, Optional
import httpx

from web_mcp.llm.config import get_llm_config


class LLMError(Exception):
    """Error from LLM operations."""
    pass


class LLMClient:
    """Async client for OpenAI-compatible APIs."""

    def __init__(self):
        self._config = get_llm_config()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._config.request_timeout,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        client = await self._get_client()
        
        payload = {
            "input": texts,
            "model": self._config.embedding_model,
        }
        
        response = await client.post(
            f"{self._config.api_url}/embeddings",
            json=payload,
        )
        
        if response.status_code != 200:
            raise LLMError(f"Embedding failed: {response.status_code} - {response.text}")
        
        data = response.json()
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    async def chat(
        self,
        messages: List[dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate a chat completion."""
        client = await self._get_client()
        
        payload = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": max_tokens or self._config.max_tokens,
            "temperature": temperature if temperature is not None else self._config.temperature,
        }
        
        response = await client.post(
            f"{self._config.api_url}/chat/completions",
            json=payload,
        )
        
        if response.status_code != 200:
            raise LLMError(f"Chat failed: {response.status_code} - {response.text}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: List[dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion."""
        client = await self._get_client()
        
        payload = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": max_tokens or self._config.max_tokens,
            "temperature": temperature if temperature is not None else self._config.temperature,
            "stream": True,
        }
        
        async with client.stream(
            "POST",
            f"{self._config.api_url}/chat/completions",
            json=payload,
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                raise LLMError(f"Chat stream failed: {response.status_code} - {text}")
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
