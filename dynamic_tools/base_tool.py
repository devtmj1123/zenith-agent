from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict

from core.types import ToolResult


class BaseTool(ABC):
    TIMEOUT = 5  # seconds — enforced by registry

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        ...

    @abstractmethod
    def schema(self) -> dict:
        ...

    async def run_with_timeout(self, params: dict) -> ToolResult:
        try:
            return await asyncio.wait_for(
                self.execute(params), timeout=self.TIMEOUT
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                tool_name=self.__class__.__name__,
                error=f"Timeout after {self.TIMEOUT}s"
            )
