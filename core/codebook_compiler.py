from __future__ import annotations
import re
from typing import Optional

from core.types import CompiledAction


class CodebookCompiler:
    def __init__(self, codebook: dict = None):
        self._codebook = codebook or self._default_codebook()

    def compile(self, raw_intent: str) -> Optional[CompiledAction]:
        """Parse natural language intent into compiled action token."""
        intent_lower = raw_intent.lower().strip()

        for pattern, action_def in self._codebook.items():
            if re.search(pattern, intent_lower, re.IGNORECASE):
                return CompiledAction(
                    token=action_def["token"],
                    params=action_def.get("extract_params", lambda x: {})(raw_intent),
                    execution_target=action_def.get("target"),
                    confidence=action_def.get("confidence", 0.8),
                    raw_input=raw_intent,
                )
        return None

    def _default_codebook(self) -> dict:
        return {
            r"click|press|tap": {
                "token": "ACT:CLICK",
                "target": "webmcp",
                "confidence": 0.9,
                "extract_params": lambda x: {},
            },
            r"type|input|enter text": {
                "token": "ACT:TYPE",
                "target": "webmcp",
                "confidence": 0.9,
                "extract_params": lambda x: {"text": x},
            },
            r"scroll|swipe": {
                "token": "ACT:SCROLL",
                "target": "webmcp",
                "confidence": 0.8,
                "extract_params": lambda x: {"direction": "down"},
            },
            r"navigate|go to|open url": {
                "token": "ACT:NAVIGATE",
                "target": "webmcp",
                "confidence": 0.9,
                "extract_params": lambda x: {"url": x},
            },
            r"search|find|look up": {
                "token": "ACT:WEB_SEARCH",
                "target": "opencli",
                "confidence": 0.8,
                "extract_params": lambda x: {"query": x},
            },
            r"read file|open file": {
                "token": "ACT:READ_FILE",
                "target": "opencli",
                "confidence": 0.9,
                "extract_params": lambda x: {},
            },
            r"write|save|create file": {
                "token": "ACT:WRITE_FILE",
                "target": "opencli",
                "confidence": 0.9,
                "extract_params": lambda x: {},
            },
            r"run|execute|shell": {
                "token": "ACT:SHELL",
                "target": "opencli",
                "confidence": 0.8,
                "extract_params": lambda x: {"command": x},
            },
        }
