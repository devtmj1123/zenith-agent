from __future__ import annotations
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class DualChannel:
    def __init__(self, tts_engine=None):
        self._tts = tts_engine
        self._tts_task: Optional[asyncio.Task] = None
        self._playing = False

    def stop(self):
        """Stop current TTS playback."""
        import sys
        self._playing = False
        if sys.platform == "win32":
            try:
                import ctypes
                winmm = ctypes.windll.winmm
                winmm.mciSendStringW("stop zenith_audio", None, 0, 0)
                winmm.mciSendStringW("close zenith_audio", None, 0, 0)
            except Exception:
                pass
        # Cancel any pending TTS task
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()

    async def speak_while_executing(self, text: str, tool_coroutine):
        """Start TTS and tool execution in parallel. Return tool result."""
        tts_task = asyncio.create_task(self._speak(text))
        tool_task = asyncio.create_task(tool_coroutine)

        result = await tool_task

        if not tts_task.done():
            tts_task.cancel()
            try:
                await tts_task
            except asyncio.CancelledError:
                pass

        return result

    async def speak(self, text: str):
        """Public speak method — synthesize and play audio."""
        await self._speak(text)

    async def _speak(self, text: str):
        """TTS synthesis and playback."""
        if not self._tts:
            return

        try:
            audio_bytes = await self._tts.synthesize(text)
            if not audio_bytes:
                return

            # Save to temp file and play
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            self._playing = True
            await self._play_audio(tmp_path)
            self._playing = False

            # Cleanup
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
        except Exception as e:
            log.debug(f"TTS playback error: {e}")

    async def _play_audio(self, filepath: str):
        """Play audio file using system player."""
        import sys

        try:
            if sys.platform == "win32":
                await asyncio.get_event_loop().run_in_executor(
                    None, self._play_mci, filepath
                )
            elif sys.platform == "darwin":
                proc = await asyncio.create_subprocess_exec(
                    "afplay", filepath,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
            else:
                proc = await asyncio.create_subprocess_exec(
                    "mpv", "--no-video", filepath,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
        except Exception as e:
            log.debug(f"Audio playback error: {e}")

    @staticmethod
    def _play_mci(filepath: str):
        """Play audio using Windows MCI API (MP3/WAV, no dependencies)."""
        import ctypes
        import time

        winmm = ctypes.windll.winmm
        alias = "zenith_audio"

        # Try MP3 first, then WAV
        for audio_type in ("mpegvideo", "waveaudio"):
            cmd = f'open "{filepath}" type {audio_type} alias {alias}'
            if winmm.mciSendStringW(cmd, None, 0, 0) == 0:
                break
        else:
            return

        # Play
        winmm.mciSendStringW(f'play {alias}', None, 0, 0)

        # Wait until done
        buf = ctypes.create_unicode_buffer(128)
        for _ in range(6000):  # Max 300s (5 min)
            winmm.mciSendStringW(f'status {alias} mode', buf, 128, 0)
            if buf.value == 'stopped':
                break
            time.sleep(0.05)

        # Close
        winmm.mciSendStringW(f'close {alias}', None, 0, 0)
