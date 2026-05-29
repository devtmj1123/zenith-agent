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
    DB_PATH = Path.home() / ".zenith" / "soft_memory.db"

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
                     min_relevance: float = 0.15) -> List[dict]:
        """Hybrid recall: BM25 (FTS5) + semantic (embedding cosine similarity).

        Combines both scores with configurable weights:
        - BM25: keyword matching (fast, exact terms)
        - Semantic: embedding similarity (slow, captures meaning)
        - Temporal: recency boost (always applied)

        Returns empty list if no memory exceeds min_relevance threshold.
        """
        import re

        safe = re.sub(r'[^\w\s]', '', query).strip()
        if not safe:
            return []

        # --- BM25 path (FTS5) ---
        words = [w for w in safe.lower().split() if len(w) > 1]
        bm25_results = {}
        if words:
            fts_q = " OR ".join(words)
            with sqlite3.connect(str(self.DB_PATH)) as conn:
                rows = conn.execute("""
                    SELECT m.id, m.content, m.created_at, m.access_count,
                           m.decay_resistance, m.confidence, m.physics_quantities,
                           m.embedding, f.rank
                    FROM memories_fts f
                    JOIN memories m ON m.rowid = f.rowid
                    WHERE memories_fts MATCH ? AND m.superseded_by IS NULL
                    ORDER BY f.rank LIMIT ?
                """, (fts_q, top_k * 3)).fetchall()

            if rows:
                ranks = [r[8] for r in rows]
                best, worst = min(ranks), max(ranks)
                for r in rows:
                    bm25_norm = 1.0 if best == worst else 1.0 - (r[8] - best) / (worst - best)
                    bm25_results[r[0]] = {
                        "id": r[0], "content": r[1], "created_at": r[2],
                        "access_count": r[3], "decay_resistance": r[4],
                        "confidence": r[5], "physics_quantities": r[6],
                        "embedding": r[7], "bm25": bm25_norm,
                    }

        # --- Semantic path (embedding cosine similarity) ---
        semantic_results = {}
        query_vec = await self._encode(query)
        if query_vec is not None:
            import numpy as np
            q = np.frombuffer(query_vec, dtype=np.float32)
            with sqlite3.connect(str(self.DB_PATH)) as conn:
                all_rows = conn.execute("""
                    SELECT id, content, created_at, access_count,
                           decay_resistance, confidence, physics_quantities,
                           embedding
                    FROM memories WHERE superseded_by IS NULL AND embedding IS NOT NULL
                """).fetchall()

            for r in all_rows:
                try:
                    vec = np.frombuffer(r[7], dtype=np.float32)
                    sim = float(np.dot(q, vec))  # normalized → dot = cosine
                    if sim > 0.2:  # threshold for semantic relevance
                        semantic_results[r[0]] = {
                            "id": r[0], "content": r[1], "created_at": r[2],
                            "access_count": r[3], "decay_resistance": r[4],
                            "confidence": r[5], "physics_quantities": r[6],
                            "embedding": r[7], "semantic": sim,
                        }
                except Exception:
                    continue

        # --- Merge BM25 + Semantic ---
        all_ids = set(bm25_results.keys()) | set(semantic_results.keys())
        if not all_ids:
            return []

        scored = []
        for mid in all_ids:
            bm = bm25_results.get(mid, {})
            sem = semantic_results.get(mid, {})
            data = bm or sem

            bm25_score = bm.get("bm25", 0.0)
            sem_score = sem.get("semantic", 0.0)
            t_score = self.temporal_score(
                data["created_at"], data["access_count"], data["decay_resistance"]
            )

            # Hybrid: 40% BM25 + 40% semantic + 20% temporal
            combined = bm25_score * 0.4 + sem_score * 0.4 + t_score * 0.2

            if combined >= min_relevance:
                scored.append({
                    "id": data["id"], "content": data["content"],
                    "temporal_score": t_score, "confidence": data["confidence"],
                    "physics_quantities": json.loads(data["physics_quantities"]),
                    "bm25_score": bm25_score, "semantic_score": sem_score,
                    "combined_score": combined,
                })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored[:top_k]

    async def recall_recent(self, top_k: int = 3) -> List[dict]:
        """Recall most recent memories (no search query needed).

        Used for proactive context — when the agent needs to know
        what was discussed recently without a specific search.
        """
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT id, content, created_at, access_count,
                       decay_resistance, confidence, physics_quantities
                FROM memories WHERE superseded_by IS NULL
                ORDER BY created_at DESC LIMIT ?
            """, (top_k,)).fetchall()

        return [
            {
                "id": r[0], "content": r[1],
                "temporal_score": self.temporal_score(r[2], r[3], r[4]),
                "confidence": r[5],
                "physics_quantities": json.loads(r[6]),
            }
            for r in rows
        ]

    async def update_with_version(self, old_id: str, new_content: str,
                                   confidence: float = 0.9) -> str:
        new_id = await self.write(new_content, confidence=confidence, layer="semantic")
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("UPDATE memories SET superseded_by = ? WHERE id = ?",
                         (new_id, old_id))
        return new_id

    async def upsert(self, content: str, session_id: str = "",
                     confidence: float = 0.8) -> str:
        """Store memory, updating existing similar memory instead of duplicating.

        If a highly similar memory exists (>0.7 similarity), supersedes it.
        Otherwise creates a new entry.
        """
        # Check for existing similar memories
        existing = await self.recall(content, top_k=1, min_relevance=0.5)
        if existing:
            top = existing[0]
            # High similarity = same fact, update it
            if top.get("relevance", 0) > 0.7:
                return await self.update_with_version(top["id"], content, confidence)
        # No similar memory found, create new
        return await self.write(content, session_id=session_id, confidence=confidence)

    _embedding_model = None  # Class-level cache — load once
    _model_ready_event = None  # threading.Event set when background load completes

    async def _encode(self, text: str):
        try:
            import numpy as np
            if SoftMemory._embedding_model is None:
                # Wait for background preload if it's running
                if SoftMemory._model_ready_event is not None:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, SoftMemory._model_ready_event.wait, 30)
                # If still not loaded (timeout or no background thread), load now
                if SoftMemory._embedding_model is None:
                    from sentence_transformers import SentenceTransformer
                    SoftMemory._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            vec = SoftMemory._embedding_model.encode(text, normalize_embeddings=True)
            return vec.astype(np.float32).tobytes()
        except Exception:
            return None

    def list_all(self, limit: int = 50) -> List[dict]:
        """List all memories (for user inspection)."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT id, content, layer, created_at, access_count, confidence
                FROM memories WHERE superseded_by IS NULL
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        return [
            {
                "id": r[0], "content": r[1], "layer": r[2],
                "created_at": r[3], "access_count": r[4], "confidence": r[5],
            }
            for r in rows
        ]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    def export_to_text(self, filepath: str = None) -> str:
        """Export all memories to a human-readable text file."""
        if filepath is None:
            filepath = str(self.DB_PATH.parent / "memories.txt")

        memories = self.list_all(limit=200)
        lines = [
            "# Zenith Memory Export",
            f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Total: {len(memories)} memories",
            "",
        ]
        for m in memories:
            from datetime import datetime
            ts = datetime.fromtimestamp(m["created_at"]).strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] ({m['layer']}) {m['content']}")
            lines.append("")

        text = "\n".join(lines)
        Path(filepath).write_text(text, encoding="utf-8")
        return filepath
