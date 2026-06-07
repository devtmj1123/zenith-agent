"""Reminders and scheduler tool.

Single entry point: reminders(action, ...) with actions:
  create     — one-shot reminder at specific time
  recurring  — repeating reminder (daily, weekly, monthly)
  list       — show upcoming reminders
  dismiss    — mark reminder as done
  delete     — remove reminder
"""
from __future__ import annotations
import json
import uuid
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path


REMINDERS_PATH = Path.home() / ".zenith" / "reminders.json"
_reminder_thread = None
_reminder_callbacks = []


def _ensure_background_checker():
    """Start background reminder checker if not running."""
    global _reminder_thread
    if _reminder_thread is None or not _reminder_thread.is_alive():
        _reminder_thread = threading.Thread(target=_check_reminders_loop, daemon=True)
        _reminder_thread.start()


def _check_reminders_loop():
    """Background loop that checks for due reminders and triggers notifications."""
    while True:
        try:
            data = _load()
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            updated = False

            for r in data.get("reminders", []):
                if r.get("status") == "pending" and r.get("datetime", "") <= now:
                    # Trigger notification callbacks
                    for callback in _reminder_callbacks:
                        try:
                            callback(r)
                        except Exception:
                            pass
                    updated = True

            if updated:
                _save(data)
        except Exception:
            pass

        time.sleep(30)  # Check every 30 seconds


def on_reminder_due(callback):
    """Register a callback for when a reminder is due. Callback receives reminder dict."""
    _reminder_callbacks.append(callback)


# Start background checker on import
_ensure_background_checker()


def _load() -> dict:
    if REMINDERS_PATH.exists():
        try:
            return json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"reminders": []}


def _save(data: dict) -> None:
    REMINDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REMINDERS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _next_occurrence(recurrence: str, from_date: str = "") -> str:
    """Calculate next occurrence based on recurrence pattern."""
    base = datetime.strptime(from_date, "%Y-%m-%d %H:%M") if from_date else datetime.now()
    if recurrence == "daily":
        return (base + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    elif recurrence == "weekly":
        return (base + timedelta(weeks=1)).strftime("%Y-%m-%d %H:%M")
    elif recurrence == "monthly":
        month = base.month + 1
        year = base.year
        if month > 12:
            month = 1
            year += 1
        return base.replace(year=year, month=month).strftime("%Y-%m-%d %H:%M")
    return ""


async def reminders(args: dict) -> dict:
    """Unified reminders/scheduler tool.

    Actions:
      create   — {title, datetime: "YYYY-MM-DD HH:MM", description?}
      recurring — {title, time: "HH:MM", recurrence: daily|weekly|monthly, description?}
      list     — {show_all?} (default: upcoming only)
      dismiss  — {reminder_id}
      delete   — {reminder_id}
    """
    action = args.get("action", "list")

    if action == "create":
        return await _create(args)
    elif action == "recurring":
        return await _recurring(args)
    elif action == "list":
        return await _list(args)
    elif action == "dismiss":
        return await _dismiss(args)
    elif action == "delete":
        return await _delete(args)
    else:
        return {"success": False, "error": f"Unknown action: {action}"}


async def _create(args: dict) -> dict:
    title = args.get("title", "")
    dt = args.get("datetime", "")
    if not title:
        return {"success": False, "error": "title is required"}
    if not dt:
        return {"success": False, "error": "datetime is required (YYYY-MM-DD HH:MM)"}

    data = _load()
    reminder = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "description": args.get("description", ""),
        "datetime": dt,
        "recurrence": None,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    data["reminders"].append(reminder)
    _save(data)
    return {"success": True, "reminder": reminder, "message": f"Reminder set: {title} at {dt}"}


async def _recurring(args: dict) -> dict:
    title = args.get("title", "")
    time_str = args.get("time", "")
    recurrence = args.get("recurrence", "")
    if not title or not time_str or recurrence not in ("daily", "weekly", "monthly"):
        return {"success": False, "error": "title, time (HH:MM), and recurrence (daily|weekly|monthly) required"}

    today = datetime.now().strftime("%Y-%m-%d")
    dt = f"{today} {time_str}"

    data = _load()
    reminder = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "description": args.get("description", ""),
        "datetime": dt,
        "recurrence": recurrence,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    data["reminders"].append(reminder)
    _save(data)
    return {"success": True, "reminder": reminder, "message": f"Recurring reminder: {title} {recurrence} at {time_str}"}


async def _list(args: dict) -> dict:
    show_all = args.get("show_all", False)
    data = _load()
    reminders_list = data.get("reminders", [])

    if not show_all:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        reminders_list = [r for r in reminders_list if r.get("status") == "pending"
                          and r.get("datetime", "") >= now]

    reminders_list.sort(key=lambda r: r.get("datetime", ""))
    return {"success": True, "reminders": reminders_list, "count": len(reminders_list)}


async def _dismiss(args: dict) -> dict:
    reminder_id = args.get("reminder_id", "")
    if not reminder_id:
        return {"success": False, "error": "reminder_id is required"}

    data = _load()
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            if r.get("recurrence"):
                # Recurring: schedule next occurrence
                r["datetime"] = _next_occurrence(r["recurrence"], r["datetime"])
                r["status"] = "pending"
            else:
                r["status"] = "dismissed"
            _save(data)
            return {"success": True, "reminder": r}
    return {"success": False, "error": f"Reminder not found: {reminder_id}"}


async def _delete(args: dict) -> dict:
    reminder_id = args.get("reminder_id", "")
    if not reminder_id:
        return {"success": False, "error": "reminder_id is required"}

    data = _load()
    original = len(data["reminders"])
    data["reminders"] = [r for r in data["reminders"] if r["id"] != reminder_id]
    if len(data["reminders"]) < original:
        _save(data)
        return {"success": True, "message": f"Deleted reminder {reminder_id}"}
    return {"success": False, "error": f"Reminder not found: {reminder_id}"}
