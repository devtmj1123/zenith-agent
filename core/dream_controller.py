from __future__ import annotations
import asyncio
from enum import Enum
from typing import Optional

from memory.staging_buffer import StagingBuffer
from filters.zero_error_filter import ZeroErrorFilter


class SystemState(Enum):
    WAKING = "waking"
    DREAMING = "dreaming"


class DreamController:
    IDLE_THRESHOLD = 300
    CPU_THRESHOLD = 0.30
    SUSPEND_TIMEOUT = 0.05

    def __init__(self, settings, memory_compressor, zero_error_filter: ZeroErrorFilter,
                 staging_buffer: StagingBuffer):
        self.settings = settings
        self.mem = memory_compressor
        self.zef = zero_error_filter
        self.staging = staging_buffer
        self.state = SystemState.WAKING
        self._suspend_event = asyncio.Event()
        self._dream_task: Optional[asyncio.Task] = None
        self._fast_model_client = None

    async def start_monitoring(self, system_monitor):
        self._monitor = system_monitor
        asyncio.create_task(self._dream_loop())

    async def wakeup_interrupt(self):
        if self.state == SystemState.DREAMING:
            self._suspend_event.set()
            self.staging.dump_suspended()
            self.state = SystemState.WAKING
            if self._dream_task and not self._dream_task.done():
                self._dream_task.cancel()
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._dream_task), timeout=self.SUSPEND_TIMEOUT
                    )
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

    async def fast_path_respond(self, goal: str, context: str) -> str:
        if not self._fast_model_client:
            self._fast_model_client = await self._init_ollama()

        if not self._fast_model_client:
            return ""

        prompt = f"Context: {context[:500]}\nQuestion: {goal}\nBrief answer (1-2 sentences):"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "llama3.2:3b", "prompt": prompt, "stream": False}
                )
                return resp.json().get("response", "")
        except Exception:
            return ""

    async def _init_ollama(self):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                models = [m["name"] for m in resp.json().get("models", [])]
                return "llama3.2:3b" in models or "llama3.2" in models
        except Exception:
            return None

    async def _dream_loop(self):
        while True:
            try:
                await asyncio.sleep(60)
                if not self._monitor:
                    continue
                if self._monitor.idle_seconds < self.IDLE_THRESHOLD:
                    continue
                if self._monitor.cpu_load > self.CPU_THRESHOLD:
                    continue

                self._suspend_event.clear()
                self.state = SystemState.DREAMING
                self._dream_task = asyncio.create_task(self._deep_analysis())

                try:
                    await self._dream_task
                except asyncio.CancelledError:
                    pass
                finally:
                    self.state = SystemState.WAKING
            except Exception:
                pass

    async def _deep_analysis(self):
        from memory.soft_memory import SoftMemory
        soft_mem = SoftMemory()

        results = self.zef.process_queue_batch(max_items=20)

        for result in results:
            if self._suspend_event.is_set():
                break
            if result.verdict == "passed":
                item_id = self.staging.stage(
                    content=f"Validated: {result.reason}",
                    confidence=result.confidence
                )
                self.staging.validate(item_id)

        validated = self.staging.get_validated()
        committed_ids = []
        for item in validated:
            if self._suspend_event.is_set():
                break
            await soft_mem.write(
                content=item.content,
                layer="semantic",
                confidence=item.confidence
            )
            committed_ids.append(item.item_id)

        self.staging.clear_committed(committed_ids)
