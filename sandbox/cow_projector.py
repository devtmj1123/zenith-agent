"""Copy-on-Write Virtual File System Projector.

Agent reads from real filesystem. Agent writes go to shadow first.
Shadow writes only reach real disk after human approval (or autopilot).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List

SHADOW_ROOT = Path(".zenith/shadow")
SHADOW_META = Path(".zenith/shadow_meta.json")
AUDIT_LOG = Path(".zenith/audit.jsonl")


class ShadowStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass
class ShadowEntry:
    entry_id: str
    real_path: str
    shadow_path: str
    action: str  # write | delete | mkdir
    content_hash: str
    size_bytes: int
    status: ShadowStatus = ShadowStatus.PENDING
    created_at: float = field(default_factory=time.time)
    approved_at: float | None = None
    agent_reason: str = ""


class CowProjector:
    """Copy-on-Write projector. Intercepts all file writes, routes to shadow first."""

    def __init__(self):
        SHADOW_ROOT.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, ShadowEntry] = self._load_meta()

    # ── Agent-facing API ───────────────────────────────────────────────────

    def read(self, real_path: str) -> bytes:
        """Read always goes to real filesystem."""
        path = Path(real_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {real_path}")
        return path.read_bytes()

    def write(self, real_path: str, content: bytes,
              agent_reason: str = "") -> ShadowEntry:
        """Write goes to shadow first. Returns pending ShadowEntry."""
        shadow_path = self._to_shadow_path(real_path)
        shadow_path.parent.mkdir(parents=True, exist_ok=True)
        shadow_path.write_bytes(content)

        # Backup original if it exists (for rollback)
        real = Path(real_path)
        if real.exists():
            backup = Path(str(shadow_path) + ".original")
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(real), str(backup))

        entry = ShadowEntry(
            entry_id=str(uuid.uuid4())[:8],
            real_path=str(real_path),
            shadow_path=str(shadow_path),
            action="write",
            content_hash=hashlib.sha256(content).hexdigest()[:16],
            size_bytes=len(content),
            agent_reason=agent_reason,
        )
        self._entries[entry.entry_id] = entry
        self._save_meta()
        self._audit("shadow_write", entry)
        return entry

    def delete(self, real_path: str, agent_reason: str = "") -> ShadowEntry:
        """Delete is intercepted — marks as pending delete in shadow."""
        real = Path(real_path)
        backup_path = self._to_shadow_path(real_path + ".deleted_backup")
        if real.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(real), str(backup_path))

        entry = ShadowEntry(
            entry_id=str(uuid.uuid4())[:8],
            real_path=str(real_path),
            shadow_path=str(backup_path),
            action="delete",
            content_hash="DELETE",
            size_bytes=0,
            agent_reason=agent_reason,
        )
        self._entries[entry.entry_id] = entry
        self._save_meta()
        self._audit("shadow_delete", entry)
        return entry

    def list_dir(self, real_path: str) -> List[str]:
        """List always reads from real directory."""
        return [str(p) for p in Path(real_path).iterdir()]

    def exists(self, real_path: str) -> bool:
        """Check real filesystem."""
        return Path(real_path).exists()

    # ── Approval API ───────────────────────────────────────────────────────

    def approve(self, entry_id: str) -> bool:
        """Commit shadow entry to real disk."""
        entry = self._entries.get(entry_id)
        if not entry or entry.status != ShadowStatus.PENDING:
            return False

        try:
            if entry.action == "write":
                real = Path(entry.real_path)
                real.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry.shadow_path, str(real))
            elif entry.action == "delete":
                real = Path(entry.real_path)
                if real.exists():
                    real.unlink()

            entry.status = ShadowStatus.APPROVED
            entry.approved_at = time.time()
            self._save_meta()
            self._audit("approved", entry)
            return True
        except Exception as e:
            self._audit("approve_failed", entry, error=str(e))
            return False

    def approve_all_pending(self) -> int:
        """Approve all pending entries (autopilot mode)."""
        count = 0
        for entry_id in list(self._entries.keys()):
            if self._entries[entry_id].status == ShadowStatus.PENDING:
                if self.approve(entry_id):
                    count += 1
        return count

    def reject(self, entry_id: str) -> bool:
        """Discard shadow entry. Real file untouched."""
        entry = self._entries.get(entry_id)
        if not entry or entry.status != ShadowStatus.PENDING:
            return False

        shadow = Path(entry.shadow_path)
        if shadow.exists():
            shadow.unlink()

        entry.status = ShadowStatus.REJECTED
        self._save_meta()
        self._audit("rejected", entry)
        return True

    def rollback(self, entry_id: str) -> bool:
        """Rollback an APPROVED entry. Restores file to pre-agent state."""
        entry = self._entries.get(entry_id)
        if not entry or entry.status != ShadowStatus.APPROVED:
            return False

        try:
            if entry.action == "write":
                backup = Path(str(entry.shadow_path) + ".original")
                if backup.exists():
                    shutil.copy2(str(backup), entry.real_path)
                else:
                    real = Path(entry.real_path)
                    if real.exists():
                        real.unlink()
            elif entry.action == "delete":
                backup = Path(entry.shadow_path)
                if backup.exists():
                    shutil.copy2(str(backup), entry.real_path)

            entry.status = ShadowStatus.ROLLED_BACK
            self._save_meta()
            self._audit("rolled_back", entry)
            return True
        except Exception as e:
            self._audit("rollback_failed", entry, error=str(e))
            return False

    # ── Diff / Preview ─────────────────────────────────────────────────────

    def get_pending(self) -> List[ShadowEntry]:
        """All entries awaiting approval."""
        return [e for e in self._entries.values()
                if e.status == ShadowStatus.PENDING]

    def diff(self, entry_id: str) -> str:
        """Show unified diff between original and shadow version."""
        entry = self._entries.get(entry_id)
        if not entry:
            return "Entry not found"

        import difflib
        try:
            real = Path(entry.real_path)
            original = (real.read_text(encoding="utf-8", errors="replace").splitlines()
                        if real.exists() else [])
            shadow = Path(entry.shadow_path)
            shadow_text = (shadow.read_text(encoding="utf-8", errors="replace").splitlines()
                           if shadow.exists() else [])

            diff = list(difflib.unified_diff(
                original, shadow_text,
                fromfile=f"original: {entry.real_path}",
                tofile=f"shadow (pending): {entry.real_path}",
                lineterm=""
            ))
            return "\n".join(diff) if diff else "No changes (identical content)"
        except Exception as e:
            return f"Binary file or diff error: {e}"

    # ── Internal ───────────────────────────────────────────────────────────

    def _to_shadow_path(self, real_path: str) -> Path:
        """Map real path to shadow path.
        C:/Users/mjtan/project/main.py -> .zenith/shadow/C/Users/mjtan/project/main.py
        """
        p = Path(real_path)
        # Windows drive letter: C:\ or C:/
        if len(p.parts) > 0 and (p.parts[0].endswith(":") or p.parts[0].endswith(":\\")):
            drive = p.parts[0].rstrip(":\\")
            rest = Path(*p.parts[1:]) if len(p.parts) > 1 else Path("")
            return SHADOW_ROOT / drive / rest
        # UNC or Unix path
        return SHADOW_ROOT / str(p).lstrip("/\\")

    def _load_meta(self) -> Dict[str, ShadowEntry]:
        if not SHADOW_META.exists():
            return {}
        try:
            data = json.loads(SHADOW_META.read_text())
            entries = {}
            for k, v in data.items():
                v["status"] = ShadowStatus(v["status"])
                entries[k] = ShadowEntry(**v)
            return entries
        except Exception:
            return {}

    def _save_meta(self):
        SHADOW_META.write_text(
            json.dumps(
                {k: {**vars(v), "status": v.status.value}
                 for k, v in self._entries.items()},
                indent=2
            )
        )

    def _audit(self, event: str, entry: ShadowEntry, error: str = ""):
        record = {
            "ts": time.time(),
            "event": event,
            "entry_id": entry.entry_id,
            "action": entry.action,
            "real_path": entry.real_path,
            "reason": entry.agent_reason,
            "status": entry.status.value,
        }
        if error:
            record["error"] = error
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
