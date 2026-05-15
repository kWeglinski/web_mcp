from typing import Any

from mcp.types import ToolAnnotations

from web_mcp.mem0 import mem0_manager


async def add_memory_tool(user_id: str, content: str) -> str:
    """
    Extracts and stores facts from the provided content for a specific user.

    Args:
        user_id: Unique identifier for the user.
        content: The text content to extract memories from.
    """
    try:
        memory = mem0_manager.get_memory()
        memory.add(content, user_id=user_id)
        return "Memory added successfully"
    except Exception as e:
        return f"Error adding memory: {str(e)}"


async def search_memory_tool(user_id: str, query: str) -> list[dict[str, Any]]:
    """
    Performs semantic retrieval of relevant memory snippets for a specific user.

    Args:
        user_id: Unique identifier for the user.
        query: The semantic query to search for.
    """
    try:
        memory = mem0_manager.get_memory()
        results = memory.search(query, user_id=user_id)
        return results
    except Exception as e:
        return [{"error": str(e)}]


async def get_user_memories_tool(user_id: str) -> list[dict[str, Any]]:
    """
    Provides the full history of stored facts/memories for a specific user.

    Args:
        user_id: Unique identifier for the user.
    """
    try:
        memory = mem0_manager.get_memory()
        memories = memory.get_all(user_id=user_id)
        return memories
    except Exception as e:
        return [{"error": str(e)}]


# For registration in TOOL_REGISTRY and register_tools_for_path
MEM0_TOOLS = {
    "add_memory": (add_memory_tool, ToolAnnotations(openWorldHint=True), None),
    "search_memory": (search_memory_tool, ToolAnnotations(openWorldHint=True), None),
    "get_user_memories": (get_user_memories_tool, ToolAnnotations(openWorldHint=True), None),
}
