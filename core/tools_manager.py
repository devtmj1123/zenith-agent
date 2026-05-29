from __future__ import annotations
import importlib
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.types import ToolResult


class ToolsManager:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._plugins: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable):
        self._tools[name] = fn

    def register_plugin(self, name: str, fn: Callable):
        self._plugins[name] = fn

    def get(self, name: str) -> Optional[Callable]:
        return self._tools.get(name) or self._plugins.get(name)

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())

    async def execute(self, name: str, params: dict) -> ToolResult:
        fn = self.get(name)
        if not fn:
            return ToolResult(
                success=False, tool_name=name,
                error=f"Tool '{name}' not found"
            )
        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(params)
            else:
                result = fn(params)
            # Tools return dicts with {success, data, error} — respect their verdict
            if isinstance(result, dict) and "success" in result:
                return ToolResult(
                    success=result["success"],
                    tool_name=name,
                    data=result.get("data"),
                    error=result.get("error"),
                )
            return ToolResult(success=True, tool_name=name, data=result)
        except Exception as e:
            return ToolResult(success=False, tool_name=name, error=str(e))

    def auto_discover(self, tools_dir: str = "tools/builtin"):
        """Auto-discover tools from builtin directory."""
        tools_path = Path(tools_dir)
        if not tools_path.exists():
            return
        for py_file in tools_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            module_name = f"tools.builtin.{py_file.stem}"
            try:
                mod = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(mod):
                    if inspect.isfunction(obj) and not name.startswith("_"):
                        self.register(f"{py_file.stem}.{name}", obj)
            except Exception:
                pass
