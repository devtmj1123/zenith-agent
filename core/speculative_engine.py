from __future__ import annotations
import hashlib
from typing import Dict, List

from core.types import CompiledAction


class SpeculativeEngine:
    def __init__(self):
        self._cache: Dict[str, dict] = {}

    def predict_next(self, current_action: CompiledAction,
                     history: List[CompiledAction]) -> List[str]:
        """Predict likely next actions based on current action and history."""
        predictions = []

        # Pattern: after NAVIGATE, likely GET_ELEMENTS or CLICK
        if current_action.token == "ACT:NAVIGATE":
            predictions.extend(["ACT:GET_ELEMENTS", "ACT:CLICK"])

        # Pattern: after CLICK, likely TYPE or GET_ELEMENTS
        if current_action.token == "ACT:CLICK":
            predictions.extend(["ACT:TYPE", "ACT:GET_ELEMENTS"])

        # Pattern: after TYPE, likely CLICK (submit)
        if current_action.token == "ACT:TYPE":
            predictions.append("ACT:CLICK")

        # Pattern: after error, likely retry or alternative
        if history and history[-1].token == "ACT:ERROR":
            predictions.append(history[-1].token)  # Retry

        return predictions[:3]

    def prewarm(self, predicted_actions: List[str]):
        """Pre-warm resources for predicted actions."""
        for action in predicted_actions:
            cache_key = hashlib.md5(action.encode()).hexdigest()[:8]
            if cache_key not in self._cache:
                self._cache[cache_key] = {"action": action, "prewarmed": True}
