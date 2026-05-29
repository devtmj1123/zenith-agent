"""Dynamic tool registry — manages self-created tools.

Registry is stored as JSON in dynamic_tools/registry.json.
Tool code lives in dynamic_tools/sandbox/<name>.py.

The agent can:
- create_tool(name, description, code) — register a new tool
- delete_tool(name) — remove a tool
- list_tools() — see all dynamic tools
- execute_tool(name, params) — run a dynamic tool
"""
from __future__ import annotations
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dynamic_tools.base_tool import BaseDynamicTool, DynamicToolResult, execute_with_timeout

log = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent / "registry.json"
SANDBOX_DIR = Path(__file__).parent / "sandbox"


class DynamicToolRegistry:
    def __init__(self):
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, BaseDynamicTool] = {}
        self._registry: Dict[str, dict] = {}
        self._load_registry()

    def _load_registry(self):
        """Load tool metadata from registry.json."""
        if not REGISTRY_PATH.exists():
            self._registry = {}
            return
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                self._registry = json.load(f)
        except (json.JSONDecodeError, IOError):
            self._registry = {}

    def _save_registry(self):
        """Persist registry to disk."""
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, indent=2, ensure_ascii=False)

    def _load_tool_module(self, name: str) -> Optional[BaseDynamicTool]:
        """Dynamically load a tool from sandbox/<name>.py."""
        tool_path = SANDBOX_DIR / f"{name}.py"
        if not tool_path.exists():
            return None

        try:
            spec = importlib.util.spec_from_file_location(f"dynamic_tools.sandbox.{name}", str(tool_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the tool class (must extend BaseDynamicTool)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseDynamicTool) and
                    attr is not BaseDynamicTool):
                    instance = attr()
                    if instance.validate():
                        return instance
            log.warning(f"Dynamic tool '{name}': no valid BaseDynamicTool subclass found")
            return None
        except Exception as e:
            log.warning(f"Dynamic tool '{name}' failed to load: {e}")
            return None

    def create_tool(self, name: str, description: str, code: str,
                    parameters: dict = None) -> DynamicToolResult:
        """Register a new dynamic tool.

        Args:
            name: unique tool name (alphanumeric + underscore)
            description: what the tool does
            code: Python code implementing the tool (must define a class extending BaseDynamicTool)
            parameters: JSON Schema for the tool's parameters
        """
        # Validate name
        if not name or not name.replace("_", "").isalnum():
            return DynamicToolResult(False, error="Invalid tool name (use alphanumeric + underscore)")

        # Check for conflicts with built-in tools
        from tools.builtin import BUILTIN_TOOLS
        if name in BUILTIN_TOOLS:
            return DynamicToolResult(False, error=f"Cannot override built-in tool '{name}'")

        # Save code to sandbox
        tool_path = SANDBOX_DIR / f"{name}.py"
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Try to load and validate
        tool = self._load_tool_module(name)
        if not tool:
            # Clean up invalid file
            tool_path.unlink(missing_ok=True)
            return DynamicToolResult(False, error=f"Tool code is invalid — must define a class extending BaseDynamicTool")

        # Register
        self._tools[name] = tool
        self._registry[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
            "file": f"sandbox/{name}.py",
        }
        self._save_registry()

        log.info(f"Dynamic tool '{name}' registered")
        return DynamicToolResult(True, data={"name": name, "description": description})

    def delete_tool(self, name: str) -> DynamicToolResult:
        """Remove a dynamic tool."""
        if name not in self._registry:
            return DynamicToolResult(False, error=f"Tool '{name}' not found")

        # Remove file
        tool_path = SANDBOX_DIR / f"{name}.py"
        tool_path.unlink(missing_ok=True)

        # Remove from registry
        del self._registry[name]
        self._save_registry()
        self._tools.pop(name, None)

        return DynamicToolResult(True, data={"deleted": name})

    def list_tools(self) -> List[dict]:
        """List all registered dynamic tools."""
        return [
            {"name": name, "description": info["description"]}
            for name, info in self._registry.items()
        ]

    def get(self, name: str) -> Optional[BaseDynamicTool]:
        """Get a loaded tool instance."""
        if name in self._tools:
            return self._tools[name]
        # Try loading from disk
        if name in self._registry:
            tool = self._load_tool_module(name)
            if tool:
                self._tools[name] = tool
                return tool
        return None

    async def execute(self, name: str, params: dict) -> DynamicToolResult:
        """Execute a dynamic tool with timeout."""
        tool = self.get(name)
        if not tool:
            return DynamicToolResult(False, error=f"Dynamic tool '{name}' not found")
        return await execute_with_timeout(tool, params)

    def get_tools_schema(self) -> list[dict]:
        """Generate OpenAI-compatible tool schemas for all dynamic tools."""
        schemas = []
        for name, info in self._registry.items():
            tool = self.get(name)
            if not tool:
                continue
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info.get("description", ""),
                    "parameters": info.get("parameters", {"type": "object", "properties": {}}),
                },
            })
        return schemas
