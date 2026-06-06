"""Dynamic Tool Registry — runtime tool creation and persistence.

Stores user-created tools in ~/.zenith/dynamic_tools/ as Python modules.
Tools survive across sessions.
"""
from __future__ import annotations
import importlib.util
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

DYNAMIC_TOOLS_DIR = Path.home() / ".zenith" / "dynamic_tools"


@dataclass
class ToolMeta:
    name: str
    description: str
    parameters: dict
    created_at: float
    file_path: str


@dataclass
class CreateResult:
    success: bool
    tool_name: str
    error: str = ""

    def to_dict(self):
        return {"success": self.success, "tool_name": self.tool_name, "error": self.error}


class DynamicToolRegistry:
    """Manages runtime-created tools with persistence.

    Tools are stored as Python files in ~/.zenith/dynamic_tools/
    and reloaded on startup.
    """

    def __init__(self):
        DYNAMIC_TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, Callable] = {}
        self._meta: Dict[str, ToolMeta] = {}
        self._load_existing()

    def _load_existing(self):
        """Load all existing dynamic tools from disk."""
        for py_file in DYNAMIC_TOOLS_DIR.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                self._load_tool_file(py_file)
            except Exception as e:
                log.warning(f"Failed to load dynamic tool {py_file.name}: {e}")

    def _load_tool_file(self, file_path: Path):
        """Load a single tool file."""
        module_name = file_path.stem
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the main function (same name as module)
        if hasattr(module, module_name):
            fn = getattr(module, module_name)
            if callable(fn):
                self._tools[module_name] = fn
                # Load metadata
                meta_path = file_path.with_suffix(".json")
                if meta_path.exists():
                    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                    self._meta[module_name] = ToolMeta(**meta_data)
                log.info(f"Loaded dynamic tool: {module_name}")

    def create_tool(self, name: str, description: str, code: str,
                    parameters: dict = None) -> CreateResult:
        """Create a new dynamic tool.

        Args:
            name: Tool name (must be valid Python identifier)
            description: What the tool does
            code: Python code implementing the tool function
            parameters: JSON schema for parameters

        Returns:
            CreateResult with success status
        """
        # Validate name
        if not name.isidentifier():
            return CreateResult(False, name, f"Invalid tool name: {name}")

        # Wrap code in a module if it's just a function body
        if not code.strip().startswith("def "):
            code = f"async def {name}(params: dict) -> dict:\n"
            # Indent the body
            for line in code.split("\n"):
                if line.strip():
                    code += f"    {line}\n"
                else:
                    code += "\n"

        # Add return dict wrapper if not present
        if "return {" not in code and "return {" not in code:
            # Find the last line and wrap it
            lines = code.rstrip().split("\n")
            if lines:
                last = lines[-1].strip()
                if not last.startswith("return"):
                    lines[-1] = f"    return {last}"
                code = "\n".join(lines)

        # Write to file
        file_path = DYNAMIC_TOOLS_DIR / f"{name}.py"
        try:
            file_path.write_text(code, encoding="utf-8")
        except Exception as e:
            return CreateResult(False, name, f"Failed to write file: {e}")

        # Write metadata
        meta = ToolMeta(
            name=name,
            description=description,
            parameters=parameters or {},
            created_at=time.time(),
            file_path=str(file_path),
        )
        meta_path = DYNAMIC_TOOLS_DIR / f"{name}.json"
        try:
            meta_path.write_text(json.dumps(vars(meta), indent=2), encoding="utf-8")
        except Exception as e:
            log.warning(f"Failed to write metadata: {e}")

        # Load the tool
        try:
            self._load_tool_file(file_path)
            self._meta[name] = meta
            return CreateResult(True, name)
        except Exception as e:
            return CreateResult(False, name, f"Failed to load tool: {e}")

    def delete_tool(self, name: str) -> CreateResult:
        """Delete a dynamic tool."""
        if name not in self._tools:
            return CreateResult(False, name, f"Tool '{name}' not found")

        # Remove from memory
        del self._tools[name]
        if name in self._meta:
            del self._meta[name]

        # Remove files
        py_path = DYNAMIC_TOOLS_DIR / f"{name}.py"
        json_path = DYNAMIC_TOOLS_DIR / f"{name}.json"

        try:
            if py_path.exists():
                py_path.unlink()
            if json_path.exists():
                json_path.unlink()
            return CreateResult(True, name)
        except Exception as e:
            return CreateResult(False, name, f"Failed to delete files: {e}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a dynamic tool by name."""
        return self._tools.get(name)

    def get_meta(self, name: str) -> Optional[ToolMeta]:
        """Get tool metadata."""
        return self._meta.get(name)

    def list_tools(self) -> list:
        """List all dynamic tool names."""
        return list(self._tools.keys())

    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all dynamic tools as a dict."""
        return dict(self._tools)
