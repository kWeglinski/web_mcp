from mcp.types import ToolAnnotations

from web_mcp.api_keys import get_current_user_id
from web_mcp.mem0 import mem0_manager


async def add_memory_tool(content: str) -> str:
    """
    Extracts and stores facts from the provided content for the authenticated user.

    Args:
        content: The text content to extract memories from.
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return "Error: No authenticated user. API key required."
        memory = mem0_manager.get_memory()
        memory.add(content, user_id=user_id)
        return "Memory added successfully"
    except Exception as e:
        return f"Error adding memory: {str(e)}"


async def search_memory_tool(query: str) -> str:
    """
    Performs semantic retrieval of relevant memory snippets for the authenticated user.

    Args:
        query: The semantic query to search for.
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return "Error: No authenticated user. API key required."
        memory = mem0_manager.get_memory()
        results = memory.search(query, filters={"user_id": user_id})
        if not results:
            return f"No memories found for query: '{query}'"
        lines = [f"Memory search results for: '{query}'\n"]
        for i, r in enumerate(results, 1):
            memory_text = r.get("memory", r.get("text", ""))
            lines.append(f"{i}. {memory_text}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching memories: {str(e)}"


async def get_user_memories_tool() -> str:
    """
    Provides the full history of stored facts/memories for the authenticated user.
    """
    try:
        user_id = get_current_user_id()
        if user_id is None:
            return "Error: No authenticated user. API key required."
        memory = mem0_manager.get_memory()
        result = memory.get_all(filters={"user_id": user_id})
        memories = result.get("results", []) if isinstance(result, dict) else result
        if not memories:
            return f"No memories found for user: '{user_id}'"
        lines = [f"Memories for user: '{user_id}'\n"]
        for i, mem in enumerate(memories, 1):
            memory_text = mem.get("memory", mem.get("text", ""))
            lines.append(f"{i}. {memory_text}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error getting user memories: {str(e)}"


# For registration in TOOL_REGISTRY and register_tools_for_path
MEM0_TOOLS = {
    "add_memory": (add_memory_tool, ToolAnnotations(openWorldHint=True), None),
    "search_memory": (search_memory_tool, ToolAnnotations(openWorldHint=True), None),
    "get_user_memories": (get_user_memories_tool, ToolAnnotations(openWorldHint=True), None),
}
