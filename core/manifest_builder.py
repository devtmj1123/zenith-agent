from __future__ import annotations
from typing import List

from core.types import CompiledAction, ExecutionState


class ManifestBuilder:
    MAX_ACTIONS = 15

    def build(self, state: ExecutionState,
              available_actions: List[str]) -> str:
        """Build dynamic manifest of top-N relevant actions for current context."""
        # Score actions by relevance to current goal
        scored = []
        goal_words = set(state.goal.lower().split())

        for action in available_actions:
            action_words = set(action.lower().replace("_", " ").split())
            overlap = len(goal_words & action_words)
            scored.append((action, overlap))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_actions = scored[:self.MAX_ACTIONS]

        lines = ["=== AVAILABLE ACTIONS ==="]
        for action, score in top_actions:
            lines.append(f"  - {action}")

        return "\n".join(lines)

    def build_compact(self, actions: List[str]) -> str:
        """Minimal manifest for context-constrained situations."""
        return "Actions: " + ", ".join(actions[:self.MAX_ACTIONS])
