from __future__ import annotations
import asyncio
import time
from typing import Callable, Optional


class SystemMonitor:
    def __init__(self):
        self.cpu_load: float = 0.0
        self.ram_available_gb: float = 0.0
        self.idle_seconds: float = 0.0
        self._last_activity: float = time.time()
        self._on_user_activity: Optional[Callable] = None
        self._on_idle: Optional[Callable] = None

    def register_callbacks(self, on_activity: Callable, on_idle: Callable):
        self._on_user_activity = on_activity
        self._on_idle = on_idle

    def signal_user_activity(self):
        self._last_activity = time.time()
        self.idle_seconds = 0.0
        if self._on_user_activity:
            asyncio.create_task(self._on_user_activity())

    async def start(self):
        asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        while True:
            try:
                import psutil
                self.cpu_load = psutil.cpu_percent(interval=1) / 100
                mem = psutil.virtual_memory()
                self.ram_available_gb = mem.available / (1024**3)
            except ImportError:
                self.cpu_load = 0.3

            self.idle_seconds = time.time() - self._last_activity
            await asyncio.sleep(10)
