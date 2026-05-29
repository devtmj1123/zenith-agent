from .shell import run_command, check_background
from .file_ops import read_file, write_file, list_dir, edit_file, delete_file, glob_search, grep_search
from .web_search import search, fetch
from .web_scraper import scrape
from .memory_tools import recall, store_memory, set_soft_memory
from .document_parser import parse_document
from .spreadsheet_ops import spreadsheet
from .calendar_tool import calendar
from .goals_tool import goals
from .reminders_tool import reminders
from .weather import WeatherTool
from .browse_tool import (
    browse_open, browse_snapshot, browse_click, browse_fill,
    browse_get, browse_screenshot, browse_skills, browse_eval, browse_wait
)
from .pc_control import (
    pc_get_windows, pc_get_ui_tree, pc_click, pc_fill,
    pc_press, pc_screenshot, pc_launch, pc_focus
)
from .subagent import dispatch_agent, dispatch_parallel


async def get_time(params: dict) -> dict:
    """Get current date and time."""
    from datetime import datetime
    now = datetime.now()
    return {
        "success": True,
        "data": {
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day": now.strftime("%A"),
        },
    }


async def get_weather(params: dict) -> dict:
    """Get current weather for a location."""
    tool = WeatherTool()
    return await tool.execute(params)


# Dynamic tool creation — set by main.py after registry is initialized
_dynamic_registry = None

def set_dynamic_registry(registry):
    global _dynamic_registry
    _dynamic_registry = registry

# Skill loader — set by main.py after agent loop is initialized
_skill_loader = None

def set_skill_loader(loader):
    global _skill_loader
    _skill_loader = loader


async def load_skill(params: dict) -> dict:
    """Load a skill's full content by name.

    params: {name: str}
    Returns the skill's SKILL.md content so you can follow its instructions.
    """
    if not _skill_loader:
        return {"success": False, "error": "Skill loader not initialized"}
    name = params.get("name", "").strip()
    if not name:
        return {"success": False, "error": "Missing 'name' parameter"}
    content = _skill_loader.load_skill_content(name)
    return {"success": True, "data": {"content": content}}


async def create_tool(params: dict) -> dict:
    """Create a new tool at runtime. The agent generates tool code and registers it.

    params: {name, description, code, parameters?}
    """
    if not _dynamic_registry:
        return {"success": False, "error": "Dynamic tool registry not initialized"}
    name = params.get("name", "").strip()
    description = params.get("description", "").strip()
    code = params.get("code", "").strip()
    parameters = params.get("parameters", {})
    if not name or not code:
        return {"success": False, "error": "name and code are required"}
    result = _dynamic_registry.create_tool(name, description, code, parameters)
    return result.to_dict()


async def delete_dynamic_tool(params: dict) -> dict:
    """Delete a dynamically created tool.

    params: {name}
    """
    if not _dynamic_registry:
        return {"success": False, "error": "Dynamic tool registry not initialized"}
    name = params.get("name", "").strip()
    if not name:
        return {"success": False, "error": "name is required"}
    result = _dynamic_registry.delete_tool(name)
    return result.to_dict()


BUILTIN_TOOLS = {
    "run_command": run_command,
    "check_background": check_background,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "list_dir": list_dir,
    "glob_search": glob_search,
    "grep_search": grep_search,
    "search": search,
    "fetch": fetch,
    "scrape": scrape,
    "recall": recall,
    "store_memory": store_memory,
    "get_time": get_time,
    "get_weather": get_weather,
    "parse_document": parse_document,
    "spreadsheet": spreadsheet,
    "calendar": calendar,
    "goals": goals,
    "reminders": reminders,
    "create_tool": create_tool,
    "delete_dynamic_tool": delete_dynamic_tool,
    "load_skill": load_skill,
    # Browse.sh — browser automation
    "browse_open": browse_open,
    "browse_snapshot": browse_snapshot,
    "browse_click": browse_click,
    "browse_fill": browse_fill,
    "browse_get": browse_get,
    "browse_screenshot": browse_screenshot,
    "browse_skills": browse_skills,
    "browse_eval": browse_eval,
    "browse_wait": browse_wait,
    # PC Control — Windows UIA desktop automation
    "pc_get_windows": pc_get_windows,
    "pc_get_ui_tree": pc_get_ui_tree,
    "pc_click": pc_click,
    "pc_fill": pc_fill,
    "pc_press": pc_press,
    "pc_screenshot": pc_screenshot,
    "pc_launch": pc_launch,
    "pc_focus": pc_focus,
    # Subagent — parallel task dispatch
    "dispatch_agent": dispatch_agent,
    "dispatch_parallel": dispatch_parallel,
}
