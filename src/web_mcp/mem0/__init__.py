from __future__ import annotations

from typing import Any

from mem0 import Memory

from web_mcp.config import get_config

_DEFAULT_USER_ID = "knowledge"


class Mem0Manager:
    """Manages the lifecycle and configuration of the Mem0 memory system.

    Provides wrapper methods around mem0.Memory to handle common patterns
    such as adding memories with metadata (which requires a user_id on
    the underlying mem0 client) and listing memories (which mem0 exposes
    via get_all with filters).
    """

    def __init__(self):
        self._memory: Memory | None = None

    def _get_config(self):
        """Get the project's centralized config."""
        return get_config()

    def get_memory(self) -> Memory:
        """Initializes and returns a Mem0 Memory instance using project configuration."""
        if self._memory is not None:
            return self._memory

        self._get_config()

        # Mapping project environment variables to Mem0 config
        # Note: We use 'WEB_MCP_MEM0_*' prefix to avoid collisions in the main Config class
        # but we can also add these directly to the project's config if desired.
        import os

        llm_model = os.environ.get("WEB_MCP_MEM0_LLM_MODEL", "llama3:8b")
        base_url = os.environ.get("WEB_MCP_MEM0_BASE_URL", "http://host.docker.internal:1234/v1")
        embed_model = os.environ.get("WEB_MCP_MEM0_EMBED_MODEL", "text-embedding-3-small")
        api_key = os.environ.get("WEB_MCP_MEM0_API_KEY", "local-secret")
        chroma_path = os.environ.get("WEB_MCP_MEM0_CHROMA_PATH", "/app/chroma_db")

        mem0_config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": llm_model,
                    "base_url": base_url,
                    "api_key": api_key,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": embed_model,
                    "openai_base_url": base_url,
                    "api_key": api_key,
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {"path": chroma_path, "collection_name": "mcp_memories"},
            },
        }

        self._memory = Memory.from_config(mem0_config)
        return self._memory

    def add_with_metadata(self, message: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Add a memory with metadata to the knowledge store.

        This is the preferred method for the knowledge pipeline. It wraps
        mem0.Memory.add() which requires one of user_id/agent_id/run_id,
        using a default 'knowledge' user_id for system-generated facts.

        Args:
            message: The memory/fact text to store.
            metadata: A dict of metadata to associate with the memory
                      (e.g. source_url, confidence, category).

        Returns:
            The raw result dict from mem0.Memory.add(), typically
            {"results": [{"id": "...", "memory": "...", "event": "ADD"}]}.
        """
        memory = self.get_memory()
        return memory.add(
            messages=message,
            user_id=_DEFAULT_USER_ID,
            metadata=metadata,
        )

    def add(
        self,
        messages: str | list[dict[str, str]] | None = None,
        *,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Add a memory, delegating to the underlying mem0.Memory.add().

        Accepts both 'messages' and 'message' as keyword arguments for
        compatibility with existing callers that use the singular form.

        Args:
            messages: The message content or list of message dicts.
            user_id: Required by mem0. Defaults to 'knowledge' if not given.
            metadata: Optional metadata dict to store with the memory.
            **kwargs: Additional keyword args passed through to mem0.Memory.add().

        Returns:
            The result dict from mem0.Memory.add().
        """
        memory = self.get_memory()

        effective_user_id = user_id or _DEFAULT_USER_ID

        # Alias 'message' -> 'messages' for caller compatibility
        # 'message' in kwargs takes precedence over positional 'messages'
        if "message" in kwargs:
            kwargs["messages"] = kwargs.pop("message")

        # Build kwargs dict to avoid duplicate 'messages' keyword
        add_kwargs: dict[str, Any] = {
            "user_id": effective_user_id,
            "metadata": metadata,
        }
        if "messages" in kwargs:
            add_kwargs["messages"] = kwargs.pop("messages")
        elif messages is not None:
            add_kwargs["messages"] = messages
        add_kwargs.update(kwargs)

        return memory.add(**add_kwargs)

    def list(
        self,
        user_id: str | None = None,
        top_k: int = 100,
    ) -> list[dict[str, Any]]:
        """List all memories, returning just the results list.

        mem0.Memory does not have a 'list' method; this wraps get_all()
        with a default user_id filter and returns only the 'results' list
        (not the full {"results": [...]} dict).

        Args:
            user_id: Entity ID to filter by. Defaults to 'knowledge'.
            top_k: Maximum number of memories to return.

        Returns:
            A list of memory dicts (each with 'id', 'memory', etc.).
        """
        memory = self.get_memory()
        effective_user_id = user_id or _DEFAULT_USER_ID
        result = memory.get_all(
            filters={"user_id": effective_user_id},
            top_k=top_k,
        )
        return result.get("results", [])

    def delete(self, memory_id: str) -> None:
        """Delete a memory by ID.

        Args:
            memory_id: The ID of the memory to delete.
        """
        memory = self.get_memory()
        memory.delete(memory_id)


# Singleton instance for the module
mem0_manager = Mem0Manager()
