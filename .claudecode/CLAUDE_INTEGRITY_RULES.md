# Zenith-OS — Claude Code Architectural Integrity Rules
> Rule Status: CRITICAL ENFORCEMENT. Violations will result in architecture rejection.

## 1. ABSOLUTE ZERO HARDCODING POLICY
* **No Magic Numbers**: Any numeric threshold (e.g., string lengths `< 30`, timeouts, token limits) must NEVER be hardcoded in conditional logic. They must be loaded dynamically from `config/settings.py` or inferred via system state (e.g., CPU load, Token Bucket capacity).
* **No Static Regex Classifiers**: You are prohibited from writing static string lists or rigid regular expressions (e.g., `r'\b(file|run|command)\b'`) to perform semantic routing, memory filtering, or intent classification.

## 2. DYNAMIC REGISTRY INTERSECTION RULE
Whenever you need to identify if a user input or assistant response contains "high-value concepts", "system commands", or "actions", you MUST use **Registry Intersection**:
* Query the `CodebookRegistry` (via `CodebookCompiler.get_actions_for_manifest()`) to verify if a token matches a dynamically registered tool pointer.
* Query the `PhysicsQuantityRegistry` (via `PHYSICS_CONSTANTS` from `memory/hard_memory.py`) to check if a term matches registered physical dimensions or constants (e.g., $L_D$, $E_a$, flux).
* Query the user's active asset/business state profiles.
If an entry does not exist in the registries, it does not exist in the system's runtime reality. Do not create local vocabulary patches.

**Implementation:** `core/query_classifier.py` — `QueryClassifier` class performs dynamic registry intersection. It builds action keywords from codebook tokens/descriptions/params, compiles codebook YAML regex patterns into `_action_patterns`, builds physics terms from `PHYSICS_CONSTANTS`, and checks `IntentTracker` for multi-turn context. No hardcoded word lists.

## 3. MULTI-TURN CONTEXT MOORING
* Never evaluate a single-turn message (`messages[0]`) in isolation to make routing or compression decisions.
* You must inspect the `IntentTracker` state and the `last_tool_token` pipeline status. If the system is in an unfulfilled multi-turn tool transaction, routing or memory filtering must preserve the continuity of the core reasoning model (NVIDIA NIM Mistral).
* After tool execution, `agent_loop` rewrites messages with `"Goal:"` and `"Tool result:"` prefixes. The router MUST detect these structural markers to maintain multi-turn coherence.

**Implementation:** `QueryClassifier.is_multi_turn_active()` checks `IntentTracker.get_pending_tasks()`. `classify()` returns `REASONING` if multi-turn is active, if tools were just executed, or if registry overlap is detected.

## 4. SMART ROUTING VIA GROQ SPECULATION
* The fast path is ONLY for queries with ZERO registry overlap and NO active multi-turn context.
* For ambiguous cases where registry intersection is clean but the query might still need reasoning, use Groq (Llama 3.1 8B) for ultra-fast 1-token routing speculation.
* Never use hardcoded word lists, string length gates, or static regex to determine routing.

**Implementation:** `QueryClassifier.classify_with_speculation()` — if `classify()` returns `FAST`, optionally confirm with a Groq speculation call. If Groq says `REASONING`, override to `REASONING`.

## 5. CONTEXT-AWARE MEMORY FILTERING
* Tool-calling interactions (where `tool_calls_made > 0`) MUST always be stored — they form the audit trail.
* Pure noise ("hi", "hello", "ok") without tool context MAY be skipped.
* Never use hardcoded string lists to determine what to remember. Use structural signals: `tool_calls_made`, `last_tool_token`, and action-referencing patterns.

**Implementation:** `MemoryCompressor.store_interaction()` uses a 5-rule context-aware filter. Rules are based on structural signals (tool calls, action verbs), not hardcoded vocabulary.

## 6. CODE SMELL CHECKLIST BEFORE COMMIT
Before declaring a task finished, audit your code for:
1. `import re` used for **heuristic semantic parsing** -> **REJECT** (regex for structural parsing like ACT:TOKEN extraction is allowed)
2. Explicit string constants used as **state boundaries** -> **REJECT**
3. Parameter mismatch (parameters accepted but unused in logic, like `last_tool_token`) -> **REJECT**
4. Hardcoded word lists for routing/classification/filtering -> **REJECT**
5. Magic numbers in conditional logic not loaded from config -> **REJECT**
6. Components instantiated but never called at runtime -> **REJECT** (all modules must be wired)

## 7. MODULE WIRING COMPLETENESS
Every Python module in `core/`, `filters/`, `memory/`, and `tts/` MUST be:
1. Imported in `main.py` or `core/agent_loop.py`
2. Instantiated with proper dependency injection
3. Actually called at runtime (not just instantiated)

**Currently wired modules (as of 2026-05-24):**
- `core/agent_loop.py` — Main orchestrator (imports + uses all below)
- `core/query_classifier.py` — Dynamic registry-based routing
- `core/codebook_compiler.py` — Intent → Action Token compilation
- `core/manifest_builder.py` — Dynamic 15-action context selection
- `core/flow_regulator.py` — Circuit breaker + token budget
- `core/safe_state.py` — Snapshot + rollback
- `core/tools_manager.py` — Tool execution + plugin registry
- `core/memory_compressor.py` — Dual-LLM memory compression
- `core/failure_library.py` — Deterministic failure tree + recovery
- `core/emotional_engine.py` — Zero-token emotion + physical intuition
- `core/state_steerer.py` — Manifest-based steering hints
- `core/speculative_engine.py` — Branch prediction pre-warming
- `core/system_monitor.py` — CPU load + idle detection
- `core/dual_channel.py` — Parallel TTS + tool execution
- `core/dream_controller.py` — Idle-time memory consolidation
- `core/device_sync.py` — P2P cross-device memory sync
- `core/environment_sensor.py` — Time/location context
- `core/intent_tracker.py` — Cross-session task tree
- `filters/entropy_brake.py` — Irreversible action guard
- `filters/zero_error_filter.py` — Physics law enforcement
- `filters/unit_standardizer.py` — Dimensional analysis
- `memory/soft_memory.py` — Evolving knowledge with temporal decay
- `memory/hard_memory.py` — Immutable physics constants
- `memory/staging_buffer.py` — Dream output isolation
- `tts/zenith_tts.py` — TTS engine (Edge/Kokoro)
