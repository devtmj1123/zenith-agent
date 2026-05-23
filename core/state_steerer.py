from __future__ import annotations
from typing import List

from core.types import CompiledAction, ExecutionState


class StateSteerer:
    def steer(self, state: ExecutionState,
              available_actions: List[str]) -> dict:
        """
        Generate steering signals based on manifest.
        Returns hints for the LLM about what to do next.
        """
        hints = []

        if state.iteration > state.max_iterations * 0.8:
            hints.append("Approaching iteration limit. Consider wrapping up.")

        if state.tokens_used > state.token_budget * 0.8:
            hints.append("Approaching token budget. Compress or conclude.")

        if state.tool_calls_made == 0 and state.iteration > 2:
            hints.append("No tools used yet. Consider using available actions.")

        return {
            "hints": hints,
            "iteration": state.iteration,
            "tokens_remaining": state.token_budget - state.tokens_used,
        }
