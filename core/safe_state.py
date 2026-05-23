from __future__ import annotations
import uuid
from typing import List, Optional

from core.types import SafeStateSnapshot, ExecutionState


class SafeState:
    def __init__(self):
        self._snapshots: List[SafeStateSnapshot] = []
        self._max_snapshots = 10

    def capture(self, state: ExecutionState) -> SafeStateSnapshot:
        snapshot = SafeStateSnapshot(
            id=str(uuid.uuid4())[:8],
            completed_summary=state.final_response[:200] if state.final_response else "",
            pending_action="",
            message_history_length=len(state.messages),
            tool_calls_made=state.tool_calls_made,
            tokens_used=state.tokens_used,
        )
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)
        return snapshot

    def rollback(self, snapshot_id: str) -> Optional[SafeStateSnapshot]:
        for snap in self._snapshots:
            if snap.id == snapshot_id:
                return snap
        return None

    def latest(self) -> Optional[SafeStateSnapshot]:
        return self._snapshots[-1] if self._snapshots else None
