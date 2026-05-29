"""Tool router — passes all tools to the LLM.

With ~20 tools, no need for semantic selection.
The LLM decides which tools to use based on descriptions.
Keeps record_usage for debugging/observability.
"""
from __future__ import annotations
import logging
import time
from typing import Dict, List

log = logging.getLogger(__name__)


class SemanticToolRouter:
    def __init__(self):
        self._tool_schemas: List[dict] = []
        self._tool_names: List[str] = []
        self._usage_history: Dict[str, float] = {}

    def set_encoder(self, encoder):
        """No-op — kept for backward compatibility."""
        pass

    def build_index(self, tools_schema: list[dict]):
        """Store tool schemas for reference."""
        self._tool_schemas = tools_schema
        self._tool_names = [t.get("function", {}).get("name", "") for t in tools_schema]

    def select(self, user_message: str, top_k: int = 8) -> list[dict]:
        """Return ALL tools — let the LLM decide which to use."""
        return self._tool_schemas

    def record_usage(self, tool_name: str):
        """Record tool usage for observability."""
        self._usage_history[tool_name] = time.time()

    def set_context_hint(self, tool_name: str, boost: float = 1.0):
        pass

    def clear_context_hints(self):
        pass

    @property
    def tool_count(self) -> int:
        return len(self._tool_names)
