# Zenith-OS

> Super Agent Operating System — Python-based autonomous agent with physics-aware reasoning.

## System Overview

```
User → LLM (reasons) → Codebook Compiler (<1ms) → Entropy Brake → Flow Regulator → Execute
  ▲                        ▲                            │                │
  │                        │                     (blocks dangerous)  (budget+break)
  │                        └────────────────────────────┘
  │                        Failure Library (deterministic recovery)
  └──────────────────────── Memory (temporal decay + cross-session)
```

**Core principle:** LLM reasons ONLY. Deterministic systems handle safety, recovery, and execution.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| LLM Client | httpx (async) |
| Database | SQLite + FTS5 |
| Server | FastAPI + uvicorn |
| TTS | edge-tts, Kokoro |
| Config | PyYAML, Pydantic |

## Directory Map

```
core/           Agent brain — loop, memory, flow control, failure recovery (16 modules)
memory/         Persistence — hard (physics), soft (SQLite+FTS5), staging buffer
filters/        Safety — physics validation, dimensional analysis, entropy brake
config/         Settings, principles, permissions
tools/builtin/  Built-in tool implementations
dynamic_tools/  Plugin system with BaseTool (5s timeout enforced)
api/            FastAPI WebSocket + HTTP server
tts/            Text-to-speech engines
skills/         Agent skill definitions (.md)
```

## CLI Commands

```bash
zenith check                    # Health check (imports + config)
zenith chat                     # Interactive mode
zenith server                   # WebSocket server on :8765

# Dev commands
python -m pytest tests/ -q      # Run tests
python -m py_compile main.py    # Syntax check
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ZENITH_API_KEY` | LLM API key | — |
| `ZENITH_BASE_URL` | API endpoint | `https://api.openai.com/v1` |
| `ZENITH_MODEL` | Model name | `gpt-4o-mini` |
| `ZENITH_DEBUG` | Debug logging | `false` |

## Coding Standards

- Type hints on all public functions
- `from __future__ import annotations` at top of every module
- Dataclasses over dicts for structured data
- Async-first: all I/O operations are async
- No LLM calls in filter/memory layers — only in agent_loop
- Physics constants are IMMUTABLE (MappingProxyType)
- All tools must inherit BaseTool with 5s timeout

## Search Exclusions

Skip these paths in all searches: `.zenith/`, `__pycache__/`, `*.egg-info/`, `.git/`, `dist/`, `build/`
