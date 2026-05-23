from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from core.types import TaskNode

TASK_DB_PATH = Path(".zenith/task_tree.json")


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
            except Exception:
                self._tasks = {}

    def _save(self):
        TASK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {tid: vars(t) for tid, t in self._tasks.items()}
        TASK_DB_PATH.write_text(json.dumps(data, indent=2))

    def create_task(self, goal: str, session_id: str,
                    parent_id: Optional[str] = None) -> str:
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
        most_recent = max(pending, key=lambda t: t.updated_at)
        progress = most_recent.progress_summary or "(no progress recorded)"
        return (
            f"你上次还有一个任务未完成：\"{most_recent.goal}\"\n"
            f"进度：{progress}\n"
            f"要继续吗？"
        )
