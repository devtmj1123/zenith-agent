# core/ — Agent Brain

## Scope

Central orchestrator. Contains the ReAct loop, memory management, flow control, failure recovery, and all "intelligence" layers. This is where the agent thinks, decides, and learns.

## Module Responsibilities

| Module | Role |
|--------|------|
| `agent_loop.py` | Main ReAct orchestrator — reason → compile → brake → execute → observe |
| `types.py` | All shared dataclasses, exceptions, enums (single source of truth) |
| `flow_regulator.py` | Circuit breaker (3x = STOP) + token budget enforcement |
| `memory_compressor.py` | History compression + associative recall tracing |
| `codebook_compiler.py` | Intent → action token translation (<1ms, deterministic) |
| `failure_library.py` | 11 deterministic failure recovery chains |
| `manifest_builder.py` | Dynamic top-N action manifest for context |
| `safe_state.py` | Snapshot + rollback capability |
| `dream_controller.py` | Dual-track: fast-path (Ollama) + deep-path (cloud LLM) |
| `system_monitor.py` | CPU/idle detection for dream trigger |
| `intent_tracker.py` | Cross-session task tree persistence |
| `speculative_engine.py` | Branch prediction pre-warming |
| `emotional_engine.py` | Zero-token mood tracking + physical intuition |
| `environment_sensor.py` | Device/time/context sensing |
| `dual_channel.py` | Parallel TTS + tool execution |
| `tools_manager.py` | Tool registry + auto-discovery |
| `device_sync.py` | P2P cross-device memory sync (Syncthing) |
| `state_steerer.py` | Manifest-based steering hints |

## Local Rules

- **No LLM calls in this directory** — LLM interaction happens ONLY in agent_loop.py via the injected `llm_call` callable
- `types.py` must never import from other core modules (circular dependency prevention)
- All public methods in agent_loop.py must be async
- Flow regulator exceptions (`LocalLoopCircuitBreak`, `TokenBudgetExceeded`) are control flow, not errors — catch them explicitly
- Failure library patterns are REGEX strings — test with `re.search()` before adding new ones

## Data Flow

```
agent_loop.run(goal)
  → memory.compress_history()     # if tokens > 60%
  → llm_call(messages)            # get LLM response
  → _extract_tool_calls(content)  # parse ACT:TOKEN
  → codebook.compile(intent)      # intent → CompiledAction
  → entropy_brake.check()         # safety gate
  → regulator.check_action()      # budget + circuit breaker
  → tools.execute()               # run tool
  → failure_lib.get_recovery_hint() # if failed
  → memory.store_interaction()    # persist
```

## Testing

```bash
python -c "from core.agent_loop import AgentLoop; print('OK')"
python -c "from core.types import *; print('All types OK')"
python -c "from core.failure_library import FAILURE_TREE; print(len(FAILURE_TREE), 'patterns')"
```
