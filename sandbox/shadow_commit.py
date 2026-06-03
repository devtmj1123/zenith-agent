"""Shadow Commit Manager.
Handles approve/reject/rollback flow from WebUI or CLI.
"""
from __future__ import annotations

from typing import List

from sandbox.cow_projector import CowProjector, ShadowStatus


class ShadowCommitManager:

    def __init__(self, projector: CowProjector):
        self.proj = projector

    def get_pending_summary(self) -> List[dict]:
        """Show pending changes for WebUI."""
        pending = self.proj.get_pending()
        return [
            {
                "entry_id": e.entry_id,
                "action": e.action,
                "real_path": e.real_path,
                "size_bytes": e.size_bytes,
                "reason": e.agent_reason,
                "created_at": e.created_at,
                "diff_preview": self.proj.diff(e.entry_id)[:300],
            }
            for e in pending
        ]

    def approve_one(self, entry_id: str) -> dict:
        success = self.proj.approve(entry_id)
        return {"entry_id": entry_id, "success": success,
                "message": "Committed to real disk" if success else "Failed"}

    def approve_all(self) -> dict:
        count = self.proj.approve_all_pending()
        return {"approved": count, "message": f"{count} changes committed"}

    def reject_one(self, entry_id: str) -> dict:
        success = self.proj.reject(entry_id)
        return {"entry_id": entry_id, "success": success,
                "message": "Discarded" if success else "Failed"}

    def reject_all(self) -> dict:
        pending = self.proj.get_pending()
        count = sum(1 for e in pending if self.proj.reject(e.entry_id))
        return {"rejected": count}

    def rollback(self, entry_id: str) -> dict:
        success = self.proj.rollback(entry_id)
        return {"entry_id": entry_id, "success": success,
                "message": "Rolled back" if success else "No backup available"}

    def full_diff(self, entry_id: str) -> str:
        return self.proj.diff(entry_id)
