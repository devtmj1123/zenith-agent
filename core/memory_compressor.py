from __future__ import annotations
import json
import logging
from typing import Dict, List, Optional

from memory.hard_memory import PHYSICS_CONSTANTS
from memory.soft_memory import SoftMemory

log = logging.getLogger(__name__)


class MemoryCompressor:
    def __init__(self, soft_memory: Optional[SoftMemory] = None,
                 compress_llm_call=None):
        """
        Args:
            soft_memory: SoftMemory instance for persistence
            compress_llm_call: async callable for LLM compression.
                Injected from main.py — uses dedicated compressor model
                (fast local model like Ollama llama3.2:3b)
        """
        self.soft = soft_memory or SoftMemory()
        self._recall_trace: List[dict] = []
        self._compress_llm = compress_llm_call

    async def compress_history(self, messages: List[dict],
                                max_tokens: int = 2000) -> str:
        """Compress message history into summary using fast local model."""
        if not messages:
            return ""

        # Short history: no compression needed
        if len(messages) <= 5:
            return self._messages_to_text(messages)

        old = messages[:-5]
        recent = messages[-5:]

        # If we have a dedicated compressor LLM, use it for smart summarization
        if self._compress_llm:
            try:
                old_text = self._messages_to_text(old)
                prompt = [
                    {"role": "system", "content": (
                        "Compress this conversation history into a concise summary. "
                        "Keep key facts, decisions, and context. Max 200 words."
                    )},
                    {"role": "user", "content": old_text},
                ]
                result = await self._compress_llm(prompt)
                summary = result.get("content", "")
                if summary:
                    recent_text = self._messages_to_text(recent)
                    return f"History (compressed): {summary}\n\nRecent:\n{recent_text}"
            except Exception as e:
                log.warning("Compression LLM failed, falling back to extractive: %s", e)

        # Fallback: simple extractive compression
        summary_parts = []
        for msg in old:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                summary_parts.append(f"[{role}]: {content[:100]}")

        summary = " | ".join(summary_parts[-10:])
        recent_text = self._messages_to_text(recent)

        return f"History: {summary}\n\nRecent:\n{recent_text}"

    async def recall_with_trace(self, query: str, top_k: int = 5) -> List[dict]:
        """Recall from soft memory with associative reason tracing."""
        results = await self.soft.recall(query, top_k=top_k)

        for r in results:
            self._recall_trace.append({
                "memory_id": r["id"],
                "confidence": r["confidence"],
                "temporal_score": r["temporal_score"],
                "query": query[:100],
            })

        return results

    def get_recall_trace(self) -> List[dict]:
        return self._recall_trace.copy()

    def clear_trace(self):
        self._recall_trace.clear()

    async def store_interaction(self, user_msg: str, assistant_msg: str,
                                 session_id: str = ""):
        """Store interaction in soft memory for future recall."""
        content = f"User: {user_msg}\nAssistant: {assistant_msg}"
        await self.soft.write(
            content=content,
            session_id=session_id,
            layer="episodic",
            confidence=0.7
        )

    def _messages_to_text(self, messages: List[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                parts.append(f"{role}: {content[:200]}")
        return "\n".join(parts)
