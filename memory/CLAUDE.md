# memory/ — Persistence Layer

## Scope

Three-tier memory architecture. Hard memory stores immutable physics constants. Soft memory stores evolving knowledge with temporal decay. Staging buffer isolates dream-mode outputs before commit.

## Module Responsibilities

| Module | Role | Storage |
|--------|------|---------|
| `hard_memory.py` | Immutable physics constants (14 CODATA 2018 values) | In-memory (MappingProxyType) |
| `soft_memory.py` | Evolving knowledge, temporal decay, BM25 recall | SQLite + FTS5 |
| `staging_buffer.py` | Dream output isolation before soft memory commit | JSONL + in-memory |

## Local Rules

- **hard_memory.py is READ-ONLY at runtime** — `PHYSICS_CONSTANTS` uses `MappingProxyType`, no write access
- Soft memory NEVER overwrites — always appends new version (`update_with_version()`)
- Staging buffer items must pass zero-error filter before `validate()` → `get_validated()` → commit
- All soft memory writes go through `staging_buffer.py` in dream mode — never direct write
- Temporal decay formula: `score = base × exp(-0.01 × days_ago) × reinforcement × decay_resistance`
- FTS5 tokenizer: `porter unicode61` (English stemming + Unicode support)

## Data Flow

```
Waking path:
  agent → soft_memory.write(content, layer="episodic")

Dream path:
  agent → staging_buffer.stage(content)
        → zero_error_filter.validate()
        → staging_buffer.validate(item_id)
        → staging_buffer.get_validated()
        → soft_memory.write(content, layer="semantic")
        → staging_buffer.clear_committed(ids)
```

## Schema

```sql
memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    session_id TEXT,
    layer TEXT DEFAULT 'episodic',        -- episodic | semantic
    created_at REAL NOT NULL,
    last_accessed REAL NOT NULL,
    access_count INTEGER DEFAULT 1,
    decay_resistance REAL DEFAULT 1.0,
    confidence REAL DEFAULT 0.8,
    version INTEGER DEFAULT 1,
    superseded_by TEXT,                    -- links to newer version
    embedding BLOB,                        -- sentence-transformers vector
    physics_quantities TEXT DEFAULT '{}'
)
```

## Testing

```bash
python -c "from memory.hard_memory import PHYSICS_CONSTANTS; print(len(PHYSICS_CONSTANTS), 'constants')"
python -c "from memory.soft_memory import SoftMemory; sm = SoftMemory(); print('DB OK')"
python -c "from memory.staging_buffer import StagingBuffer; sb = StagingBuffer(); print('Buffer OK')"
```
