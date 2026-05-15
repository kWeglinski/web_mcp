from langchain_huggingface import HuggingFaceEmbeddings
from mem0 import Memory

from web_mcp.config import get_config


class Mem0Manager:
    """Manages the lifecycle and configuration of the Mem0 memory system."""

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
        embed_model = os.environ.get("WEB_MCP_MEM0_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
        api_key = os.environ.get("WEB_MCP_MEM0_API_KEY", "local-secret")
        chroma_path = os.environ.get("WEB_MCP_MEM0_CHROMA_PATH", "/app/chroma_db")

        # 1. Initialize local embedding model via LangChain
        embeddings_model = HuggingFaceEmbeddings(model_name=embed_model)

        # 2. Construct the hybrid configuration
        mem0_config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": llm_model,
                    "base_url": base_url,
                    "api_key": api_key,
                },
            },
            "embedder": {"provider": "langchain", "config": {"model": embeddings_model}},
            "vector_store": {
                "provider": "chroma",
                "config": {"path": chroma_path, "collection_name": "mcp_memories"},
            },
        }

        self._memory = Memory.from_config(mem0_config)
        return self._memory


# Singleton instance for the module
mem0_manager = Mem0Manager()
