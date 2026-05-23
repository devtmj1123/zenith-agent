from __future__ import annotations
import json
import math
import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Optional

DECAY_RATE = 0.01
REINFORCEMENT_BOOST = 0.5


class SoftMemory:
    DB_PATH = Path(".zenith/soft_memory.db")

    def __init__(self):
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    session_id TEXT,
                    layer TEXT DEFAULT 'episodic',
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    decay_resistance REAL DEFAULT 1.0,
                    confidence REAL DEFAULT 0.8,
                    version INTEGER DEFAULT 1,
                    superseded_by TEXT,
                    embedding BLOB,
                    physics_quantities TEXT DEFAULT '{}'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(content, content=memories, content_rowid=rowid,
                               tokenize='porter unicode61');
                CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content) VALUES(new.rowid, new.content);
                END;
            """)

    def temporal_score(self, created_at: float, access_count: int,
                       decay_resistance: float) -> float:
        days_ago = (time.time() - created_at) / 86400
        base = math.exp(-DECAY_RATE * days_ago)
        reinforcement = min(1.0 + (access_count - 1) * 0.1, 2.0)
        return base * reinforcement * decay_resistance

    async def write(self, content: str, session_id: str = "",
                    layer: str = "episodic", confidence: float = 0.8,
                    physics_quantities: dict = None) -> str:
        mid = str(uuid.uuid4())
        now = time.time()
        embedding = await self._encode(content)
        phys = json.dumps(physics_quantities or {})
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute(
                """INSERT INTO memories
                   (id,content,session_id,layer,created_at,last_accessed,
                    confidence,decay_resistance,physics_quantities,embedding)
                   VALUES (?,?,?,?,?,?,?,1.0,?,?)""",
                (mid, content, session_id, layer, now, now, confidence, phys, embedding)
            )
        return mid

    async def reinforce(self, memory_id: str) -> None:
        now = time.time()
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("""
                UPDATE memories SET
                    access_count = access_count + 1,
                    last_accessed = ?,
                    decay_resistance = MIN(decay_resistance + ?, 3.0)
                WHERE id = ?
            """, (now, REINFORCEMENT_BOOST, memory_id))

    async def recall(self, query: str, top_k: int = 5,
                     min_temporal_score: float = 0.1) -> List[dict]:
        import re
        safe = re.sub(r'[^\w\s]', '', query).strip()
        if not safe:
            return []
        words = [w for w in safe.lower().split() if len(w) > 1]
        if not words:
            return []
        fts_q = " OR ".join(words)

        with sqlite3.connect(str(self.DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT m.id, m.content, m.created_at, m.access_count,
                       m.decay_resistance, m.confidence, m.physics_quantities
                FROM memories_fts f
                JOIN memories m ON m.rowid = f.rowid
                WHERE memories_fts MATCH ? AND m.superseded_by IS NULL
                ORDER BY rank LIMIT ?
            """, (fts_q, top_k * 3)).fetchall()

        scored = []
        for row in rows:
            t_score = self.temporal_score(row[2], row[3], row[4])
            if t_score >= min_temporal_score:
                scored.append({
                    "id": row[0], "content": row[1],
                    "temporal_score": t_score, "confidence": row[5],
                    "physics_quantities": json.loads(row[6])
                })

        scored.sort(key=lambda x: x["temporal_score"], reverse=True)
        return scored[:top_k]

    async def update_with_version(self, old_id: str, new_content: str,
                                   confidence: float = 0.9) -> str:
        new_id = await self.write(new_content, confidence=confidence, layer="semantic")
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("UPDATE memories SET superseded_by = ? WHERE id = ?",
                         (new_id, old_id))
        return new_id

    async def _encode(self, text: str):
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            model = SentenceTransformer("all-MiniLM-L6-v2")
            vec = model.encode(text, normalize_embeddings=True)
            return vec.astype(np.float32).tobytes()
        except Exception:
            return None
