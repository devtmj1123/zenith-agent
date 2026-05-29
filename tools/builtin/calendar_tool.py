"""Calendar tool — local JSON-based calendar management.

Single entry point: calendar(action, ...) with actions:
  create, list, update, delete, plan
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


CALENDAR_PATH = Path.home() / ".zenith" / "calendar.json"


def _load_calendar() -> dict:
    if CALENDAR_PATH.exists():
        try:
            return json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"events": []}


def _save_calendar(cal: dict) -> None:
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_PATH.write_text(json.dumps(cal, indent=2, ensure_ascii=False), encoding="utf-8")


async def calendar(args: dict) -> dict:
    """Unified calendar tool.

    Actions:
      create — {title, date, start_time, end_time?, description?, reminder_minutes?}
      list   — {date?, days?} (default: upcoming 7 days)
      update — {event_id, fields: {key: value}}
      delete — {event_id}
      plan   — {date?} (default: today)
    """
    action = args.get("action", "list")

    if action == "create":
        return await _create(args)
    elif action == "list":
        return await _list(args)
    elif action == "update":
        return await _update(args)
    elif action == "delete":
        return await _delete(args)
    elif action == "plan":
        return await _plan(args)
    else:
        return {"success": False, "error": f"Unknown action: {action}. Use: create, list, update, delete, plan"}


async def _create(args: dict) -> dict:
    title = args.get("title", "")
    date = args.get("date", "")
    if not title:
        return {"success": False, "error": "title is required"}
    if not date:
        return {"success": False, "error": "date is required (YYYY-MM-DD)"}

    cal = _load_calendar()
    event = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "date": date,
        "start_time": args.get("start_time", ""),
        "end_time": args.get("end_time", ""),
        "description": args.get("description", ""),
        "recurring": args.get("recurring"),
        "reminder_minutes": args.get("reminder_minutes", 0),
        "created_at": datetime.now().isoformat(),
    }
    cal["events"].append(event)
    _save_calendar(cal)
    return {"success": True, "event": event, "message": f"Created: {title} on {date}"}


async def _list(args: dict) -> dict:
    date_filter = args.get("date", "")
    days = args.get("days", 7)
    cal = _load_calendar()
    events = cal.get("events", [])

    if date_filter:
        filtered = [e for e in events if e.get("date") == date_filter]
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        filtered = [e for e in events if today <= e.get("date", "") <= end_date]

    filtered.sort(key=lambda e: (e.get("date", ""), e.get("start_time", "")))
    return {"success": True, "events": filtered, "count": len(filtered)}


async def _update(args: dict) -> dict:
    event_id = args.get("event_id", "")
    fields = args.get("fields", {})
    if not event_id:
        return {"success": False, "error": "event_id is required"}

    cal = _load_calendar()
    for event in cal["events"]:
        if event["id"] == event_id:
            for key, value in fields.items():
                if key in event and key != "id":
                    event[key] = value
            _save_calendar(cal)
            return {"success": True, "event": event}
    return {"success": False, "error": f"Event not found: {event_id}"}


async def _delete(args: dict) -> dict:
    event_id = args.get("event_id", "")
    if not event_id:
        return {"success": False, "error": "event_id is required"}

    cal = _load_calendar()
    original = len(cal["events"])
    cal["events"] = [e for e in cal["events"] if e["id"] != event_id]
    if len(cal["events"]) < original:
        _save_calendar(cal)
        return {"success": True, "message": f"Deleted event {event_id}"}
    return {"success": False, "error": f"Event not found: {event_id}"}


async def _plan(args: dict) -> dict:
    date = args.get("date", datetime.now().strftime("%Y-%m-%d"))
    cal = _load_calendar()
    day_events = [e for e in cal["events"] if e.get("date") == date]
    day_events.sort(key=lambda e: e.get("start_time", ""))

    lines = [f"Schedule for {date}:", ""]
    if not day_events:
        lines.append("  No events scheduled.")
    else:
        for e in day_events:
            t = e.get("start_time", "??:??")
            if e.get("end_time"):
                t += f"-{e['end_time']}"
            lines.append(f"  [{t}] {e['title']}")
            if e.get("description"):
                lines.append(f"    {e['description']}")

    return {"success": True, "date": date, "events": day_events, "count": len(day_events), "view": "\n".join(lines)}
