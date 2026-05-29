"""Goals tool — track goals, milestones, and progress.

Single entry point: goals(action, ...) with actions:
  create, list, update, complete, add_milestone, update_milestone, delete
"""
from __future__ import annotations
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


GOALS_PATH = Path.home() / ".zenith" / "goals.json"


def _load_goals() -> dict:
    if GOALS_PATH.exists():
        try:
            return json.loads(GOALS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"goals": []}


def _save_goals(data: dict) -> None:
    GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOALS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


async def goals(args: dict) -> dict:
    """Unified goals tool.

    Actions:
      create          — {title, description?, deadline?, milestones?: [{title}]}
      list            — {status?} (default: all active)
      update          — {goal_id, fields: {key: value}}
      complete        — {goal_id}
      add_milestone   — {goal_id, title}
      update_milestone — {goal_id, milestone_id, status: done|pending}
      delete          — {goal_id}
    """
    action = args.get("action", "list")

    if action == "create":
        return await _create(args)
    elif action == "list":
        return await _list(args)
    elif action == "update":
        return await _update(args)
    elif action == "complete":
        return await _complete(args)
    elif action == "add_milestone":
        return await _add_milestone(args)
    elif action == "update_milestone":
        return await _update_milestone(args)
    elif action == "delete":
        return await _delete(args)
    else:
        return {"success": False, "error": f"Unknown action: {action}"}


async def _create(args: dict) -> dict:
    title = args.get("title", "")
    if not title:
        return {"success": False, "error": "title is required"}

    data = _load_goals()
    goal_id = str(uuid.uuid4())[:8]
    milestones = []
    for m in args.get("milestones", []):
        milestones.append({
            "id": str(uuid.uuid4())[:6],
            "title": m.get("title", ""),
            "status": "pending",
        })

    goal = {
        "id": goal_id,
        "title": title,
        "description": args.get("description", ""),
        "status": "active",
        "deadline": args.get("deadline", ""),
        "milestones": milestones,
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    data["goals"].append(goal)
    _save_goals(data)
    return {"success": True, "goal": goal, "message": f"Goal created: {title}"}


async def _list(args: dict) -> dict:
    status_filter = args.get("status", "")
    data = _load_goals()
    goals_list = data.get("goals", [])

    if status_filter:
        goals_list = [g for g in goals_list if g.get("status") == status_filter]
    else:
        goals_list = [g for g in goals_list if g.get("status") != "deleted"]

    return {"success": True, "goals": goals_list, "count": len(goals_list)}


async def _update(args: dict) -> dict:
    goal_id = args.get("goal_id", "")
    fields = args.get("fields", {})
    if not goal_id:
        return {"success": False, "error": "goal_id is required"}

    data = _load_goals()
    for goal in data["goals"]:
        if goal["id"] == goal_id:
            for key, value in fields.items():
                if key not in ("id", "created_at"):
                    goal[key] = value
            goal["updated_at"] = datetime.now().isoformat()
            _save_goals(data)
            return {"success": True, "goal": goal}
    return {"success": False, "error": f"Goal not found: {goal_id}"}


async def _complete(args: dict) -> dict:
    goal_id = args.get("goal_id", "")
    if not goal_id:
        return {"success": False, "error": "goal_id is required"}

    data = _load_goals()
    for goal in data["goals"]:
        if goal["id"] == goal_id:
            goal["status"] = "completed"
            goal["progress"] = 100
            goal["updated_at"] = datetime.now().isoformat()
            for m in goal.get("milestones", []):
                m["status"] = "done"
            _save_goals(data)
            return {"success": True, "goal": goal, "message": f"Goal completed: {goal['title']}"}
    return {"success": False, "error": f"Goal not found: {goal_id}"}


async def _add_milestone(args: dict) -> dict:
    goal_id = args.get("goal_id", "")
    title = args.get("title", "")
    if not goal_id or not title:
        return {"success": False, "error": "goal_id and title are required"}

    data = _load_goals()
    for goal in data["goals"]:
        if goal["id"] == goal_id:
            milestone = {"id": str(uuid.uuid4())[:6], "title": title, "status": "pending"}
            goal.setdefault("milestones", []).append(milestone)
            goal["updated_at"] = datetime.now().isoformat()
            _save_goals(data)
            return {"success": True, "goal": goal}
    return {"success": False, "error": f"Goal not found: {goal_id}"}


async def _update_milestone(args: dict) -> dict:
    goal_id = args.get("goal_id", "")
    milestone_id = args.get("milestone_id", "")
    status = args.get("status", "")
    if not goal_id or not milestone_id or status not in ("done", "pending"):
        return {"success": False, "error": "goal_id, milestone_id, and status (done|pending) required"}

    data = _load_goals()
    for goal in data["goals"]:
        if goal["id"] == goal_id:
            for m in goal.get("milestones", []):
                if m["id"] == milestone_id:
                    m["status"] = status
                    # Auto-calculate progress
                    total = len(goal["milestones"])
                    done = sum(1 for x in goal["milestones"] if x["status"] == "done")
                    goal["progress"] = int(done / total * 100) if total > 0 else 0
                    goal["updated_at"] = datetime.now().isoformat()
                    _save_goals(data)
                    return {"success": True, "goal": goal}
            return {"success": False, "error": f"Milestone not found: {milestone_id}"}
    return {"success": False, "error": f"Goal not found: {goal_id}"}


async def _delete(args: dict) -> dict:
    goal_id = args.get("goal_id", "")
    if not goal_id:
        return {"success": False, "error": "goal_id is required"}

    data = _load_goals()
    for goal in data["goals"]:
        if goal["id"] == goal_id:
            goal["status"] = "deleted"
            goal["updated_at"] = datetime.now().isoformat()
            _save_goals(data)
            return {"success": True, "message": f"Deleted goal: {goal['title']}"}
    return {"success": False, "error": f"Goal not found: {goal_id}"}
