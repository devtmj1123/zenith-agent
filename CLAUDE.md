# Zenith-OS — Claude Code Project Instructions

## Project Overview
Zenith-OS is a Python-based Super Agent Operating System. Entry point: `python main.py [chat|server|check]` or `zenith [chat|server|check]`.

## Directory Structure
```
core/           — Agent loop, memory compressor, flow regulator, failure library
memory/         — Hard memory (physics constants), soft memory (SQLite + temporal decay), staging buffer
filters/        — Zero-error filter, unit standardizer, entropy brake
config/         — Settings, principles, permissions
tools/builtin/  — Built-in tool implementations
dynamic_tools/  — Plugin system with BaseTool (5s timeout enforced)
api/            — FastAPI WebSocket + HTTP server
tts/            — Text-to-speech (edge-tts, Kokoro)
skills/         — Agent skill definitions (.md files)
```

## Key Architecture Decisions
- LLM reasons ONLY — codebook compiler translates intent to action tokens (<1ms)
- Entropy brake blocks irreversible actions BEFORE execution
- Flow regulator enforces circuit breaker (3x repeat = STOP) + token budget
- Failure library provides deterministic recovery chains (11 patterns) — LLM never guesses recovery
- Physics constants in hard_memory are IMMUTABLE at runtime
- Soft memory uses temporal decay + BM25 recall (SQLite FTS5)

## Running
```bash
zenith check        # Health check (imports + config)
zenith chat         # Interactive mode (needs ZENITH_API_KEY)
zenith server       # WebSocket server on :8765
```

## Environment Variables
- `ZENITH_API_KEY` — LLM API key (or OPENAI_API_KEY)
- `ZENITH_BASE_URL` — API endpoint (default: OpenAI)
- `ZENITH_MODEL` — Model name (default: gpt-4o-mini)
- `ZENITH_DEBUG` — Enable debug logging

## Search Exclusions
When searching code, skip these paths:
- `.zenith/` — runtime data (SQLite DB, task tree)
- `__pycache__/` — bytecode cache
- `*.egg-info/` — package metadata
- `.git/` — version control
- `dist/`, `build/` — build artifacts
