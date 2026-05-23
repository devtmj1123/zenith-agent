# Zenith-OS

> Super Agent Operating System — Physics-aware autonomous agent with deterministic reasoning.

**Status: Under Active Development**

Zenith-OS goes beyond typical ReAct agents. It separates reasoning (LLM) from execution (deterministic systems), enforcing physics laws, safety guards, and failure recovery at every step.

## Quick Start

```bash
git clone https://github.com/devtmj1123/zenith-agent.git
cd zenith-agent
pip install -e .

# Configure your LLM provider
cp .env.example .env
# Edit .env — add your API key

# Run
zenith chat
```

## Architecture

```
User --> LLM (reasons) --> Codebook Compiler --> Entropy Brake --> Flow Regulator --> Execute
  ^                          ^                      |                 |
  |                          |               (blocks dangerous)  (budget + circuit break)
  |                          +------------------------------------+
  |                          Failure Library (deterministic recovery)
  +---------------------------- Memory (temporal decay + cross-session)
```

**Core principle:** LLM reasons ONLY. Deterministic systems handle safety, recovery, and execution.

### Why Zenith is Different

| Feature | Vanilla Agent | Zenith |
|---------|:---:|:---:|
| Failure recovery | LLM guesses | Deterministic recovery tree |
| Loop prevention | None | Circuit breaker (3x = STOP) |
| Token efficiency | Context explodes | Budget + auto-compress |
| Safety | None | Entropy brake (irreversible guard) |
| Physics validity | None | Zero-error filter (conservation laws) |
| Cross-session memory | None | Temporal decay + BM25 recall |

## CLI Commands

```bash
zenith chat                         # Interactive chat (default: groq)
zenith chat --provider nvidia       # Use NVIDIA NIM
zenith chat --provider ollama       # Use local Ollama (no key needed)
zenith check                        # Health check + API test
zenith server                       # WebSocket server on :8765
zenith providers                    # List available LLM providers
```

## LLM Providers

| Provider | Speed | Cost | Default Model |
|----------|-------|------|---------------|
| **Groq** | Fastest | Free tier | `llama-3.3-70b-versatile` |
| **NVIDIA NIM** | Fast | Free tier | `meta/llama-3.3-70b-instruct` |
| **OpenAI** | Medium | Paid | `gpt-4o-mini` |
| **Ollama** | Local | Free | `llama3.2:3b` |

## Project Structure

```
zenith/
├── core/                    # Agent brain
│   ├── agent_loop.py        #   ReAct orchestrator
│   ├── types.py             #   Shared dataclasses
│   ├── flow_regulator.py    #   Circuit breaker + token budget
│   ├── memory_compressor.py #   History compression + recall tracing
│   ├── codebook_compiler.py #   Intent -> action token (<1ms)
│   ├── failure_library.py   #   11 deterministic recovery chains
│   ├── dream_controller.py  #   Dual-track reasoning (fast + deep)
│   ├── intent_tracker.py    #   Cross-session task continuity
│   ├── safe_state.py        #   Snapshot + rollback
│   └── ...                  #   16 modules total
│
├── memory/                  # Persistence layer
│   ├── hard_memory.py       #   14 immutable physics constants
│   ├── soft_memory.py       #   SQLite + FTS5 with temporal decay
│   └── staging_buffer.py    #   Dream output isolation
│
├── filters/                 # Safety layer
│   ├── zero_error_filter.py #   Physics law enforcement (5 laws)
│   ├── unit_standardizer.py #   SI dimensional analysis
│   └── entropy_brake.py     #   Irreversible action guard
│
├── config/                  # Configuration
│   ├── settings.py          #   Multi-provider settings
│   ├── principles.yaml      #   Agent soul + rules
│   └── permissions.yaml     #   Permission rules
│
├── tools/builtin/           # Built-in tools
├── dynamic_tools/           # Plugin system (BaseTool, 5s timeout)
├── api/                     # FastAPI WebSocket server
├── tts/                     # Text-to-speech (edge-tts, Kokoro)
├── skills/                  # Agent skill definitions
├── main.py                  # Entry point
└── pyproject.toml           # Package config
```

## Environment Variables

```bash
# .env
ZENITH_PROVIDER=groq          # groq|nvidia|openai|ollama
ZENITH_MODEL=                 # leave blank for provider default
GROQ_API_KEY=gsk_...          # your API key
ZENITH_DEBUG=false
```

## How It Works

### 1. Reasoning (LLM)
The LLM receives the user goal and a compressed context. It outputs natural language intent.

### 2. Compilation (Codebook)
The codebook compiler translates intent to action tokens in <1ms. No JSON formatting errors.

### 3. Safety (Entropy Brake)
Before execution, the entropy brake checks for irreversible actions (delete, format, wipe). Dangerous actions require human confirmation.

### 4. Execution (Flow Regulator)
The flow regulator enforces token budget and circuit breaker. Same action 3 times = automatic stop.

### 5. Recovery (Failure Library)
If a tool fails, the failure library provides 11 pre-defined recovery chains. No LLM guessing.

### 6. Memory (Soft Memory)
Interactions are stored with temporal decay. Recent memories score higher. Reinforced memories decay slower.

## Development

```bash
# Install dev dependencies
pip install -e ".[server,tts]"

# Health check
zenith check

# Run with debug logging
zenith --debug chat
```

## License

MIT License — see [LICENSE](LICENSE).

## Links

- GitHub: https://github.com/devtmj1123/zenith-agent
- Issues: https://github.com/devtmj1123/zenith-agent/issues
