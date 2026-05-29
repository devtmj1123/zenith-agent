from __future__ import annotations
import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)


class ZenithTTS:
    """TTS engine with multiple backends: Edge (default), Kokoro, CosyVoice2."""

    # Voice presets
    VOICES = {
        "female": "en-US-AvaNeural",
        "male": "en-US-GuyNeural",
        "female_zh": "zh-CN-XiaoxiaoNeural",
        "male_zh": "zh-CN-YunxiNeural",
    }

    def __init__(self, engine: str = "edge", language: str = "en", voice: str = ""):
        self.engine = engine
        self.language = language
        # Voice selection: explicit voice name or gender
        if voice:
            if voice in self.VOICES:
                self._edge_voice = self.VOICES[voice]
            else:
                self._edge_voice = voice  # Direct voice name
        else:
            self._edge_voice = self.VOICES.get("female" if language == "en" else "female_zh")
        # Natural speech parameters
        self._rate = "-3%"       # Slightly slower = more natural
        self._pitch = "-1Hz"     # Slightly lower = warmer tone

    @staticmethod
    def _strip_emoji(text: str) -> str:
        """Clean text for natural TTS reading. Only keeps speakable content."""
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "♀-♂☀-⭕‍⏏⏩⌚️〰⤴⤵"
            "]+",
            flags=re.UNICODE,
        )
        text = emoji_pattern.sub("", text).strip()

        # Remove entire markdown tables (header + separator + rows)
        text = re.sub(r'^\s*\|.+\|\s*$', '', text, flags=re.MULTILINE)
        # Remove table separator rows (---|---|---)
        text = re.sub(r'^\s*[-=─|:]{3,}\s*$', '', text, flags=re.MULTILINE)

        # Remove code blocks entirely
        text = re.sub(r'```[\s\S]*?```', '', text)
        # Inline code → remove (file paths, commands, variable names)
        text = re.sub(r'`[^`]+`', '', text)
        # Remove file paths (C:\..., /usr/..., ./src/...)
        text = re.sub(r'[A-Za-z]:\\[^\s]+', '', text)
        text = re.sub(r'\.{0,2}/[a-zA-Z_][^\s]*', '', text)
        # Remove timestamps like [09:43:14]
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
        # Remove ALL tool call output lines (browse_open: ..., search: ..., etc.)
        text = re.sub(r'\b(browse_open|browse_snapshot|browse_click|browse_fill|browse_get|browse_screenshot|browse_eval|browse_wait|browse_skills|run_command|read_file|write_file|edit_file|list_dir|grep_search|glob_search|search|scrape|fetch|recall|store_memory|calendar|spreadsheet|parse_document|get_time|get_weather):\s*[^\n]*', '', text)
        # Remove "Command done" / "Error:" / "Command failed" / "OK" lines
        text = re.sub(r'Command done.*', '', text)
        text = re.sub(r'Command failed.*', '', text)
        text = re.sub(r'Error:.*', '', text)
        # Remove JSON/dict results like {'result': '...'} or {"success": true, ...}
        text = re.sub(r"\{['\"]result['\"]:\s*['\"][^}]*\}", '', text)
        text = re.sub(r"\{['\"]success['\"][^}]*\}", '', text)
        text = re.sub(r'\{[^{}]{5,}\}', '', text)
        # Remove angle bracket tool tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove box-drawing table separators (─, ┬, ┴, ┤, ├, ┼, │, ╰, ╭, ╮, ╯)
        text = re.sub(r'[─┬┴┤├┼│╭╮╰╯━┳┻┫┣╋┃]+', '', text)
        # Remove table separator rows
        text = re.sub(r'^\s*[-=─]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        # Links → just the text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Headers → remove marker
        text = re.sub(r'#{1,6}\s+', '', text)

        # Tables → extract just the cell text, skip separator rows
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
                continue
            if '|' in line and line.strip().startswith('|'):
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    cleaned_lines.append(', '.join(cells))
                continue
            cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

        # Numbered lists
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        # Bullet points
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)

        # Multiple newlines → pause
        text = re.sub(r'\n{2,}', '. ', text)
        # Single newline → space
        text = re.sub(r'\n', ' ', text)
        # Multiple spaces
        text = re.sub(r'\s{2,}', ' ', text)

        return text.strip()

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes."""
        text = self._strip_emoji(text)
        if not text.strip():
            return b""

        if self.engine == "edge":
            return await self._edge_tts(text)
        elif self.engine == "kokoro":
            return await self._kokoro_tts(text)
        elif self.engine == "cosyvoice":
            return await self._cosyvoice_tts(text)
        else:
            log.warning(f"Unknown TTS engine: {self.engine}, falling back to edge")
            return await self._edge_tts(text)

    async def _edge_tts(self, text: str) -> bytes:
        """Microsoft Edge TTS (free, no API key). Uses native rate/pitch params."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text, self._edge_voice,
                rate=self._rate,
                pitch=self._pitch,
            )
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data
        except ImportError:
            log.error("edge-tts not installed. Run: pip install edge-tts")
            return b""
        except Exception as e:
            log.error(f"Edge TTS error: {e}")
            return b""

    async def _kokoro_tts(self, text: str) -> bytes:
        """Kokoro TTS (local, fast, 82M params). Requires kokoro package."""
        try:
            # Kokoro uses a different API - try importing
            from kokoro import KPipeline
            import soundfile as sf
            import io

            pipeline = KPipeline(lang_code='a')  # 'a' for auto-detect
            generator = pipeline(text, voice='af_heart')
            audio_chunks = []
            for i, (gs, ps, audio) in enumerate(generator):
                audio_chunks.append(audio)

            if audio_chunks:
                import numpy as np
                full_audio = np.concatenate(audio_chunks)
                # Convert to WAV bytes
                buf = io.BytesIO()
                sf.write(buf, full_audio, 24000, format='WAV')
                return buf.getvalue()
            return b""
        except ImportError:
            log.warning("kokoro not installed. Run: pip install kokoro")
            return b""
        except Exception as e:
            log.error(f"Kokoro TTS error: {e}")
            return b""

    async def _cosyvoice_tts(self, text: str) -> bytes:
        """CosyVoice2 TTS (Chinese-optimized). Requires cosyvoice package."""
        try:
            # CosyVoice2 has a complex setup - try basic import
            from cosyvoice.cli.cosyvoice import CosyVoice
            import torchaudio
            import io

            model = CosyVoice('CosyVoice-300M-SFT')
            # Generate audio
            output = model.inference_sft(text, '中文女')
            audio = output['tts_speech']

            # Convert to WAV bytes
            buf = io.BytesIO()
            torchaudio.save(buf, audio, 22050, format='WAV')
            return buf.getvalue()
        except ImportError:
            log.warning("cosyvoice not installed. CosyVoice2 requires manual setup.")
            return b""
        except Exception as e:
            log.error(f"CosyVoice2 TTS error: {e}")
            return b""
