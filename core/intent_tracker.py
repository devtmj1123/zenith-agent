"""Intent Tracker — cross-session task continuity.

Configuration: ~/.zenith/intent_config.yaml
If missing, uses built-in defaults.
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from core.types import TaskNode

TASK_DB_PATH = Path.home() / ".zenith" / "task_tree.json"
CONFIG_PATH = Path.home() / ".zenith" / "intent_config.yaml"

DEFAULTS = {
    "task_max_age_hours": 24,
    "stale_task_hours": 2,
    "max_tasks": 20,
}


class IntentTracker:
    def __init__(self):
        self._tasks: Dict[str, TaskNode] = {}
        self._config = self._load_config()
        self._load()

    def _load_config(self) -> dict:
        """Load config from YAML or use defaults."""
        config = dict(DEFAULTS)
        if CONFIG_PATH.exists():
            try:
                import yaml
                user_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(user_config, dict):
                    config.update(user_config)
            except Exception:
                pass
        return config

    def _load(self):
        if TASK_DB_PATH.exists():
            try:
                data = json.loads(TASK_DB_PATH.read_text())
                for task_id, node_data in data.items():
                    self._tasks[task_id] = TaskNode(**node_data)
                # Auto-cleanup
                cutoff = time.time() - (self._config["stale_task_hours"] * 3600)
                stale = [tid for tid, t in self._tasks.items()
                         if t.status in ("completed", "abandoned") and t.updated_at < cutoff]
                for tid in stale:
                    del self._tasks[tid]
                # Limit total tasks
                max_tasks = self._config["max_tasks"]
                if len(self._tasks) > max_tasks:
                    sorted_tasks = sorted(self._tasks.items(),
                                          key=lambda x: x[1].updated_at, reverse=True)
                    self._tasks = dict(sorted_tasks[:max_tasks])
                    stale = ["overflow"]
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
        """Create a task. Cleanup handles stale/trivial ones."""
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
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
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
        max_age_hours = self._config["task_max_age_hours"]
        pending = self.get_pending_tasks(max_age_days=max_age_hours / 24)
        if not pending:
            return None

        # Auto-abandon stale tasks (no progress update)
        stale_hours = self._config["stale_task_hours"]
        stale_cutoff = time.time() - (stale_hours * 3600)

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
        if task_id in self._tasks:
            self._tasks[task_id].updated_at = time.time()
            self._tasks[task_id].progress_summary = ""
            self._save()

    def get_most_recent_pending_id(self) -> Optional[str]:
        pending = self.get_pending_tasks(max_age_days=3.0)
        if not pending:
            return None
        return max(pending, key=lambda t: t.updated_at).task_id
