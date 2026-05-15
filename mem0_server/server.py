import os
from typing import List, Dict, Any

from mcp.server.fastmcp import FastMCP
from mem0 import Memory
from langchain_huggingface import HuggingFaceEmbeddings

# Initialize FastMCP server
mcp = FastMCP("mem0-server")

def get_mem0_memory() -> Memory:
    """Initializes and returns a Mem0 Memory instance with local configuration."""
    
    # Load environment variables or use defaults from implementation plan
    llm_model = os.getenv("MEM0_LLM_MODEL", "llama3:8b")
    base_url = os.getenv("MEM0_BASE_URL", "http://host.docker.internal:1234/v1")
    embed_model = os.getenv("MEM0_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    api_key = os.getenv("MEM0_API_KEY", "local-secret")
    chroma_path = os.getenv("MEM0_CHROMA_PATH", "./chroma_db")

    # 1. Initialize local embedding model via LangChain
    embeddings_model = HuggingFaceEmbeddings(model_name=embed_model)

    # 2. Construct the hybrid configuration
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "base_url": base_url,
                "api_key": api_key,
            }
        },
        "embedder": {
            "provider": "langchain",
            "config": {
                "model": embeddings_model
            }
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "path": chroma_path,
                "collection_name": "mcp_memories"
            }
        }
    }

    return Memory.from_config(config)

# Global memory instance (initialized once on server start)
try:
    memory = get_mem0_memory()
except Exception as e:
    # In a real production environment, we'd handle this more gracefully
    print(f"Error initializing Mem0: {e}")
    raise

@mcp.tool()
def add_memory(user_id: str, content: str) -> str:
    """
    Extracts and stores facts from the provided content for a specific user.
    
    Args:
        user_id: Unique identifier for the user.
        content: The text content to extract memories from.
    """
    try:
        memory.add(content, user_id=user_id)
        return "Memory added successfully"
    except Exception as e:
        return f"Error adding memory: {str(e)}"

@mcp.tool()
def search_memory(user_id: str, query: str) -> List[Dict[str, Any]]:
    """
    Performs semantic retrieval of relevant memory snippets for a specific user.
    
    Args:
        user_id: Unique identifier for the user.
        query: The semantic query to search for.
    """
    try:
        results = memory.search(query, user_id=user_id)
        return results
    except Exception as e:
        # Returning a list containing an error message for tool output consistency
        return [{"error": str(e)}]

@mcp.tool()
def get_user_memories(user_id: str) -> List[Dict[str, Any]]:
    """
    Provides the full history of stored facts/memories for a specific user.
    
    Args:
        user_id: Unique identifier for the user.
    """
    try:
        # Mem0 doesn't have a direct 'get_all' in some versions, 
        # but we can use the internal storage or search with empty query if supported.
        # For now, let's use the get_all pattern if available or search with a broad query.
        # In recent versions of mem0, memory.get_all(user_id=user_id) is common.
        memories = memory.get_all(user_id=user_id)
        return memories
    except Exception as e:
        return [{"error": str(e)}]

if __name__ == "__main__":
    mcp.run()
