from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from core.types import TaskNode

TASK_DB_PATH = Path.home() / ".zenith" / "task_tree.json"


class IntentTracker:
    def __init__(self):
        self._tasks: Dict[str, TaskNode] = {}
        self._load()

    def _load(self):
        if TASK_DB_PATH.exists():
            try:
                data = json.loads(TASK_DB_PATH.read_text())
                for task_id, node_data in data.items():
                    self._tasks[task_id] = TaskNode(**node_data)
                # Auto-cleanup: remove completed/abandoned tasks older than 24h
                cutoff = time.time() - 86400
                stale = [tid for tid, t in self._tasks.items()
                         if t.status in ("completed", "abandoned") and t.updated_at < cutoff]
                for tid in stale:
                    del self._tasks[tid]
                if stale:
                    self._save()
            except Exception:
                self._tasks = {}

    def _save(self):
        TASK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {tid: vars(t) for tid, t in self._tasks.items()}
        TASK_DB_PATH.write_text(json.dumps(data, indent=2))

    def create_task(self, goal: str, session_id: str,
                    parent_id: Optional[str] = None) -> str:
        # Skip trivial messages — short inputs without action intent
        stripped = goal.strip()
        if len(stripped) < 8 and "?" not in stripped and "!" not in stripped:
            return ""

        task_id = str(uuid.uuid4())[:8]
        node = TaskNode(
            task_id=task_id,
            goal=goal,
            status="in_progress",
            parent_id=parent_id,
            session_ids=[session_id],
        )
        self._tasks[task_id] = node
        if parent_id and parent_id in self._tasks:
            self._tasks[parent_id].children.append(task_id)
        self._save()
        return task_id

    def update_progress(self, task_id: str, progress: str):
        if task_id in self._tasks:
            self._tasks[task_id].progress_summary = progress
            self._tasks[task_id].updated_at = time.time()
            self._save()

    def complete_task(self, task_id: str, summary: str):
        if task_id in self._tasks:
            self._tasks[task_id].status = "completed"
            self._tasks[task_id].progress_summary = summary
            self._tasks[task_id].updated_at = time.time()
            self._save()

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID (supports partial match)."""
        # Try exact match first
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
        # Try partial match (prefix)
        matches = [tid for tid in self._tasks if tid.startswith(task_id)]
        if len(matches) == 1:
            del self._tasks[matches[0]]
            self._save()
            return True
        return False

    def clear_completed(self):
        """Remove all completed tasks."""
        to_remove = [tid for tid, t in self._tasks.items() if t.status == "completed"]
        for tid in to_remove:
            del self._tasks[tid]
        if to_remove:
            self._save()

    def get_pending_tasks(self, max_age_days: float = 7.0) -> List[TaskNode]:
        cutoff = time.time() - (max_age_days * 86400)
        return [
            t for t in self._tasks.values()
            if t.status in ("pending", "in_progress")
            and t.updated_at >= cutoff
        ]

    def get_resume_prompt(self) -> Optional[str]:
        pending = self.get_pending_tasks(max_age_days=3.0)
        if not pending:
            return None

        # Auto-abandon stale tasks (no progress update for > 6 hours)
        stale_cutoff = time.time() - 21600
        active = []
        for t in pending:
            no_progress = not t.progress_summary or t.progress_summary == "(no progress recorded)"
            if t.updated_at < stale_cutoff and no_progress:
                t.status = "abandoned"
            else:
                active.append(t)
        self._save()

        if not active:
            return None

        most_recent = max(active, key=lambda t: t.updated_at)
        progress = most_recent.progress_summary or ""
        lines = [f'Last time: "{most_recent.goal}"']
        if progress and progress not in ("resumed by user", "(no progress recorded)"):
            lines.append(f'Progress: {progress}')
        lines.append('Continue?')
        return "\n".join(lines)

    def mark_resumed(self, task_id: str):
        """Mark task as resumed so it doesn't repeat in next briefing."""
        if task_id in self._tasks:
            self._tasks[task_id].updated_at = time.time()
            self._tasks[task_id].progress_summary = ""
            self._save()

    def get_most_recent_pending_id(self) -> Optional[str]:
        """Get the ID of the most recent pending task."""
        pending = self.get_pending_tasks(max_age_days=3.0)
        if not pending:
            return None
        most_recent = max(pending, key=lambda t: t.updated_at)
        return most_recent.task_id
