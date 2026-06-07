"""Tool router — selects relevant tools per query to save tokens.

Filters tools by keyword matching + recency boost.
Sends ~10-15 tools instead of all 43.
"""
from __future__ import annotations
import logging
import time
from typing import Dict, List

log = logging.getLogger(__name__)

# Tool → keyword groups for matching
TOOL_KEYWORDS = {
    "web_search": ["search", "find", "google", "look up", "query", "what is", "who is"],
    "fetch": ["fetch", "download", "get url", "retrieve"],
    "scrape": ["scrape", "extract", "parse html", "web page"],
    "browse_open": ["open", "browser", "website", "navigate", "url", "youtube", "chrome"],
    "browse_snapshot": ["snapshot", "page", "elements", "refs", "page structure"],
    "browse_click": ["click", "button", "link", "press"],
    "browse_fill": ["fill", "type", "input", "search box", "form", "enter"],
    "browse_screenshot": ["screenshot", "screen", "capture", "image"],
    "browse_eval": ["javascript", "eval", "js", "script"],
    "browse_wait": ["wait", "loading", "delay"],
    "browse_get": ["get text", "get url", "page title", "page content"],
    "browse_scroll": ["scroll", "swipe", "scroll down", "scroll up"],
    "browse_scroll_to": ["scroll to", "scroll element"],
    "browse_hover": ["hover", "mouse over", "dropdown", "tooltip"],
    "browse_right_click": ["right click", "context menu"],
    "browse_double_click": ["double click", "dblclick"],
    "browse_select": ["select", "dropdown", "choose option"],
    "browse_keypress": ["press key", "hotkey", "keyboard", "shortcut", "ctrl"],
    "browse_drag": ["drag", "drag and drop", "drop"],
    "browse_focus": ["focus element", "focus input"],
    "browse_highlight": ["highlight", "mark element"],
    "browse_get_links": ["get links", "list links", "extract links"],
    "browse_get_forms": ["get forms", "list forms", "form fields"],
    "browse_back": ["go back", "browser back", "history back"],
    "browse_forward": ["go forward", "browser forward"],
    "browse_refresh": ["refresh", "reload page"],
    "read_file": ["read", "file", "show", "view", "cat", "open file"],
    "write_file": ["write", "create file", "save", "new file"],
    "edit_file": ["edit", "modify", "change", "update file", "fix"],
    "list_dir": ["list", "directory", "ls", "dir", "folder", "files"],
    "glob_search": ["find files", "glob", "search files", "pattern"],
    "grep_search": ["grep", "search content", "find in files"],
    "run_command": ["run", "command", "shell", "terminal", "execute", "npm", "pip", "git", "python"],
    "recall": ["remember", "recall", "memory", "past", "previous", "before"],
    "store_memory": ["store", "save memory", "remember this", "note"],
    "pc_click": ["desktop click", "ui click", "app click"],
    "pc_fill": ["desktop type", "ui type", "app type"],
    "pc_get_ui_tree": ["ui tree", "accessibility", "desktop elements"],
    "pc_screenshot": ["desktop screenshot", "screen capture"],
    "dispatch_agent": ["agent", "delegate", "subagent", "parallel"],
    "dispatch_parallel": ["parallel tasks", "run simultaneously"],
    "get_time": ["time", "date", "today", "now"],
    "get_weather": ["weather", "temperature", "forecast"],
    "calendar": ["calendar", "schedule", "event", "meeting"],
    "goals": ["goal", "objective", "target"],
    "reminders": ["remind", "reminder", "alarm"],
    "spreadsheet": ["spreadsheet", "excel", "csv", "sheet"],
    "parse_document": ["document", "pdf", "docx", "parse doc"],
    "load_skill": ["skill", "technique", "how to"],
    "create_tool": ["create tool", "new tool", "dynamic tool"],
    # Science Research Engine
    "science_research": ["research", "science", "study", "investigate", "hypothesis",
                         "battery", "fusion", "drug", "molecule", "physics",
                         "新能源", "电池", "聚变", "药物", "分子", "科研"],
    "analyze_molecule": ["molecule", "smiles", "drug likeness", "lipinski", "admet",
                         "分子", "药物相似性"],
    "check_battery_claim": ["battery claim", "energy density", "wh/kg", "能量密度"],
    "check_fusion_lawson": ["fusion", "lawson", "ignition", "plasma", "聚变", "点火"],
    "compute_debye_length": ["debye", "electrolyte", "screening", "德拜", "电解质"],
}

# Always-included tools (safe, common)
ALWAYS_INCLUDE = {"recall", "store_memory", "get_time"}


class SemanticToolRouter:
    def __init__(self):
        self._tool_schemas: List[dict] = []
        self._tool_names: List[str] = []
        self._usage_history: Dict[str, float] = {}

    def set_encoder(self, encoder):
        pass

    def build_index(self, tools_schema: list[dict]):
        self._tool_schemas = tools_schema
        self._tool_names = [t.get("function", {}).get("name", "") for t in tools_schema]

    def select(self, user_message: str, top_k: int = 8) -> list[dict]:
        """Select relevant tools based on keyword matching + recency.

        Returns fewer tools for simple queries to save tokens.
        """
        msg_lower = user_message.lower()
        scored = []

        for i, schema in enumerate(self._tool_schemas):
            name = schema.get("function", {}).get("name", "")
            desc = schema.get("function", {}).get("description", "").lower()
            score = 0.0

            # Keyword match
            keywords = TOOL_KEYWORDS.get(name, [])
            for kw in keywords:
                if kw in msg_lower:
                    score += 2.0

            # Description match (partial)
            for word in msg_lower.split():
                if len(word) > 3 and word in desc:
                    score += 0.5

            # Recency boost
            last_used = self._usage_history.get(name, 0)
            if last_used > 0:
                age = time.time() - last_used
                if age < 300:  # Used in last 5 min
                    score += 1.0

            # Always-include bonus
            if name in ALWAYS_INCLUDE:
                score += 0.3

            scored.append((score, i, schema))

        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)

        # Dynamic top_k: if top score is high (clear match), use fewer tools
        max_score = scored[0][0] if scored else 0
        if max_score >= 4.0:
            # Strong match — only include highly relevant tools
            effective_k = min(5, top_k)
        elif max_score >= 2.0:
            effective_k = min(8, top_k)
        else:
            effective_k = top_k

        selected = [s[2] for s in scored[:effective_k]]

        # Always include ALWAYS_INCLUDE tools
        selected_names = {s.get("function", {}).get("name", "") for s in selected}
        for schema in self._tool_schemas:
            name = schema.get("function", {}).get("name", "")
            if name in ALWAYS_INCLUDE and name not in selected_names:
                selected.append(schema)

        return selected

    def record_usage(self, tool_name: str):
        self._usage_history[tool_name] = time.time()

    def set_context_hint(self, tool_name: str, boost: float = 1.0):
        pass

    def clear_context_hints(self):
        pass

    @property
    def tool_count(self) -> int:
        return len(self._tool_names)
