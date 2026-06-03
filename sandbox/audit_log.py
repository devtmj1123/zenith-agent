"""Immutable append-only audit trail.
Every action the agent attempts is logged here.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

AUDIT_PATH = Path(".zenith/audit.jsonl")


class AuditLog:

    @staticmethod
    def record(
        event: str,
        tool_name: str,
        params: dict,
        decision: str,
        reason: str,
        session_id: str = "",
        entry_id: str = "",
    ) -> None:
        """Append-only. Never deletes. Never modifies existing entries."""
        record = {
            "ts": time.time(),
            "event": event,
            "tool": tool_name,
            "params": {k: str(v)[:100] for k, v in params.items()},
            "decision": decision,
            "reason": reason,
            "session_id": session_id,
            "entry_id": entry_id,
        }
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")

    @staticmethod
    def read_recent(n: int = 50) -> list:
        if not AUDIT_PATH.exists():
            return []
        lines = AUDIT_PATH.read_text().strip().split("\n")
        return [json.loads(line) for line in lines[-n:] if line.strip()]
