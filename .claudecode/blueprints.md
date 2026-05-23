# Zenith-OS — Engineering Blueprints

## LSP Configuration

### Primary: Pyright (Python)

```bash
npm install -g pyright
```

**pyrightconfig.json** (create at project root):
```json
{
  "pythonVersion": "3.10",
  "pythonPlatform": "Linux",
  "venvPath": ".",
  "extraPaths": ["."],
  "include": ["core/", "memory/", "filters/", "config/", "api/", "tools/", "dynamic_tools/", "tts/"],
  "exclude": ["__pycache__", ".zenith", "*.egg-info", "dist", "build"],
  "reportMissingImports": true,
  "reportMissingTypeStubs": false,
  "typeCheckingMode": "basic",
  "useLibraryCodeForTypes": true
}
```

### Secondary: Jedi (fallback)

```bash
pip install jedi
```

Jedi is used by most Python LSP servers as the backend. Pyright gives better type analysis; Jedi gives better completion for dynamic code.

### Symbol Hopping

With Pyright configured, Claude Code can:
- Go-to-definition on any import
- Find all references to a function/class
- Rename symbols across files
- Type inference on `dataclass` fields

---

## Recommended Hooks

### Pre-commit Hook: Type Check

```bash
# .claude/hooks/pre-commit-typecheck.sh
#!/bin/bash
pyright --outputjson core/ memory/ filters/ 2>/dev/null | jq '.generalDiagnostics | length'
```

**Purpose:** Catch type errors before they reach the repo.

### Pre-commit Hook: Import Validation

```bash
# .claude/hooks/pre-commit-imports.sh
#!/bin/bash
python -c "
from core.types import *
from memory.hard_memory import PHYSICS_CONSTANTS
from memory.soft_memory import SoftMemory
from filters.zero_error_filter import ZeroErrorFilter
from filters.unit_standardizer import UnitStandardizer
from filters.entropy_brake import EntropyBrake
from core.agent_loop import AgentLoop
print('All imports OK')
"
```

**Purpose:** Detect circular imports or missing modules immediately.

### Post-edit Hook: Syntax Check

```bash
# .claude/hooks/post-edit-syntax.sh
#!/bin/bash
FILE=$1
python -m py_compile "$FILE" 2>&1
```

**Purpose:** Validate syntax after every file edit.

---

## Recommended Skills to Build

### 1. `physics-validation` Skill

**Trigger:** When editing any file in `filters/` or `memory/hard_memory.py`

**Behavior:**
- Run the zero-error filter test suite after every edit
- Verify conservation law tolerances haven't changed
- Confirm hard_memory constants are still immutable

### 2. `agent-loop-safety` Skill

**Trigger:** When editing `core/agent_loop.py` or `core/flow_regulator.py`

**Behavior:**
- Verify circuit breaker threshold is still 3
- Confirm entropy brake is called before execution
- Check token budget enforcement is active

### 3. `memory-schema-migration` Skill

**Trigger:** When modifying `memory/soft_memory.py` schema

**Behavior:**
- Generate migration SQL for schema changes
- Back up existing `.zenith/soft_memory.db`
- Validate FTS5 trigger integrity

### 4. `auto-lint` Skill

**Trigger:** On every file save

**Behavior:**
- Run `pyright` on changed file
- Run `py_compile` for syntax
- Report errors inline

---

## Build & Test Matrix

| Command | Purpose | When |
|---------|---------|------|
| `zenith check` | Health check | Before every commit |
| `python -m py_compile main.py` | Syntax validation | After editing main.py |
| `python -c "from core.types import *"` | Import validation | After editing core/ |
| `python -c "from memory.hard_memory import PHYSICS_CONSTANTS"` | Physics integrity | After editing memory/ |
| `python -m pytest tests/ -q` | Full test suite | Before PR |

---

## Dependency Graph

```
main.py
  └── config/settings.py
  └── core/agent_loop.py
        ├── core/types.py (leaf — no core imports)
        ├── core/flow_regulator.py → core/types.py
        ├── core/safe_state.py → core/types.py
        ├── core/tools_manager.py → core/types.py
        ├── core/memory_compressor.py → memory/*
        ├── core/codebook_compiler.py → core/types.py
        ├── core/failure_library.py (standalone)
        └── filters/entropy_brake.py → core/types.py

filters/zero_error_filter.py → memory/hard_memory.py
filters/unit_standardizer.py → core/types.py
memory/soft_memory.py (standalone — SQLite)
memory/staging_buffer.py (standalone — JSONL)
memory/hard_memory.py (standalone — immutable)
```

**Critical invariant:** `core/types.py` is the leaf. It must NEVER import from `core/`, `memory/`, or `filters/`.
