"""Memory tools — recall and store memories.

These tools allow the agent to query and store memories on demand.
The recall tool is the key to intelligent memory injection:
instead of dumping memories into context, the model decides when it needs them.
"""
from __future__ import annotations
from typing import Any, Dict


# These will be set by main.py when building the agent
_soft_memory = None


def set_soft_memory(memory):
    """Set the soft memory instance for memory tools."""
    global _soft_memory
    _soft_memory = memory


async def recall(params: Dict[str, Any]) -> Dict[str, Any]:
    """Recall information from memory.

    The model calls this when it needs context about past interactions,
    user preferences, or previous decisions.
    """
    if _soft_memory is None:
        return {"success": False, "error": "Memory system not initialized"}

    query = params.get("query", "")
    if not query:
        return {"success": False, "error": "No query specified"}

    try:
        results = await _soft_memory.recall(query, top_k=3)
        if not results:
            return {"success": True, "data": "No relevant memories found."}

        # Format memories — keep short to save tokens
        formatted = []
        for r in results:
            formatted.append(f"- {r['content'][:150]}")

        return {
            "success": True,
            "data": "\n".join(formatted),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def store_memory(params: Dict[str, Any]) -> Dict[str, Any]:
    """Store information in memory.

    The model calls this when the user asks to remember something,
    or when an important decision/fact should be preserved.
    """
    if _soft_memory is None:
        return {"success": False, "error": "Memory system not initialized"}

    content = params.get("content", "")
    if not content:
        return {"success": False, "error": "No content specified"}

    try:
        memory_id = await _soft_memory.upsert(
            content=content,
            confidence=0.8,
        )
        # Auto-sync to text file for user visibility
        try:
            _soft_memory.export_to_text()
        except Exception:
            pass
        return {
            "success": True,
            "data": f"Stored in memory (id: {memory_id[:8]}...)",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
