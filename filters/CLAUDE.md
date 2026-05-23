# filters/ — Safety Layer

## Scope

Pre-execution validation. Filters run BEFORE any tool executes. They enforce physics laws, standardize units, and guard against irreversible actions. No LLM calls — pure deterministic logic.

## Module Responsibilities

| Module | Role |
|--------|------|
| `zero_error_filter.py` | Physics law enforcement (5 conservation laws) + PENDING_DEEP_CHECK queue |
| `unit_standardizer.py` | SI dimensional analysis — parse, convert, validate consistency |
| `entropy_brake.py` | Irreversible action detection (delete, format, wipe) → CONFIRM gate |

## Local Rules

- **No imports from core/agent_loop.py** — filters are leaf dependencies, never depend on orchestrator
- Zero-error filter validators must return `(bool, str)` tuple — pass/fail + reason
- Fundamental violations (energy, charge, momentum) ALWAYS reject — no tolerance relaxation
- Convergence errors (thermodynamics) allow with caveat — `TOLERANCE_SOFT = 1e-2`
- CPU-aware: when load > 70%, non-critical checks defer to PENDING_DEEP_CHECK queue
- Unit standardizer raises `DimensionMissingError` for unknown units — caller handles
- Entropy brake patterns are substring matches on `action_token + str(params)`

## Conservation Laws

| Law | Tolerance | Severity |
|-----|-----------|----------|
| Energy conservation | 1e-6 (rigid) | FUNDAMENTAL — reject |
| Charge conservation | 1e-6 (rigid) | FUNDAMENTAL — reject |
| Momentum conservation | 1e-6 (rigid) | FUNDAMENTAL — reject |
| Second law of thermodynamics | 1e-2 (soft) | Convergence — warn |
| Mass-energy equivalence | 1e-6 (rigid) | FUNDAMENTAL — reject |

## Entropy Brake Patterns

```
delete, remove, drop, truncate, destroy, format, wipe, purge, erase, shred, rm -rf, rmdir, del /f
```

## Testing

```bash
python -c "
from filters.zero_error_filter import ZeroErrorFilter
zef = ZeroErrorFilter()
r = zef.validate('energy_conservation', {'energy_before': 100, 'energy_after': 100})
print(f'Conservation check: {r.verdict}')
"

python -c "
from filters.unit_standardizer import UnitStandardizer
us = UnitStandardizer()
dim, scale = us.parse('m/s')
print(f'm/s dimension: {dim}')
"

python -c "
from filters.entropy_brake import EntropyBrake
eb = EntropyBrake()
r = eb.check('ACT:DELETE', {'file': 'x.txt'})
print(f'Irreversible: {r.requires_confirmation}')
"
```
