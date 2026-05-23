from __future__ import annotations
import asyncio
from typing import Optional


class DualChannel:
    def __init__(self, tts_engine=None):
        self._tts = tts_engine
        self._tts_task: Optional[asyncio.Task] = None

    async def speak_while_executing(self, text: str, tool_coroutine):
        """Start TTS and tool execution in parallel. Return tool result."""
        tts_task = asyncio.create_task(self._speak(text))
        tool_task = asyncio.create_task(tool_coroutine)

        # Wait for tool to finish (TTS may still be going)
        result = await tool_task

        # Cancel TTS if still running
        if not tts_task.done():
            tts_task.cancel()
            try:
                await tts_task
            except asyncio.CancelledError:
                pass

        return result

    async def _speak(self, text: str):
        """TTS synthesis and playback."""
        if self._tts:
            await self._tts.synthesize(text)
        else:
            # Fallback: just wait proportional to text length
            await asyncio.sleep(len(text) * 0.05)
