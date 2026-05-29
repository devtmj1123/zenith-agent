"""Base class for dynamically created tools.

Dynamic tools are created by the agent at runtime when it identifies
a repeated pattern that would benefit from a dedicated tool.

Lifecycle:
1. Agent identifies need (e.g., "I keep doing X")
2. Agent generates tool code following this base class
3. Code saved to dynamic_tools/sandbox/<name>.py
4. Registered in dynamic_tools/registry.json
5. Loaded and available in subsequent requests

Safety:
- All dynamic tools run in sandbox/ (isolated from core)
- timeout=5s enforced on all executions
- Registry is JSON — no arbitrary code execution on load
- Tools must pass validate() before registration
"""
from __future__ import annotations
import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

# Maximum execution time for any dynamic tool
TOOL_TIMEOUT = 5.0


class DynamicToolResult:
    def __init__(self, success: bool, data: Any = None, error: str = ""):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data, "error": self.error}


class BaseDynamicTool:
    """Base class all dynamic tools must extend.

    Subclasses must define:
        name: str — unique tool name
        description: str — what the tool does
        parameters: dict — JSON Schema for parameters

    And implement:
        async execute(params: dict) -> DynamicToolResult
    """
    name: str = ""
    description: str = ""
    parameters: dict = {}

    async def execute(self, params: dict) -> DynamicToolResult:
        raise NotImplementedError

    def validate(self) -> bool:
        """Check that this tool is properly defined."""
        if not self.name:
            return False
        if not self.description:
            return False
        if not callable(getattr(self, 'execute', None)):
            return False
        return True

    def to_codebook_entry(self) -> dict:
        """Convert to codebook format for tool schema generation."""
        return {
            "token": f"ACT:{self.name.upper()}",
            "patterns": [],
            "target": "dynamic",
            "description": self.description,
            "params_schema": self.parameters.get("properties", {}),
            "risk_level": "medium",
        }


async def execute_with_timeout(tool: BaseDynamicTool, params: dict,
                                timeout: float = TOOL_TIMEOUT) -> DynamicToolResult:
    """Execute a dynamic tool with timeout enforcement."""
    try:
        result = await asyncio.wait_for(
            tool.execute(params),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        return DynamicToolResult(
            success=False,
            error=f"Tool '{tool.name}' timed out after {timeout}s"
        )
    except Exception as e:
        return DynamicToolResult(
            success=False,
            error=f"Tool '{tool.name}' error: {e}"
        )
