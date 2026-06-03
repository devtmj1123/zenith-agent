"""Desire-Driven Innovation Engine.

Intrinsic motivation system that generates curiosity-driven exploration.
Desires arise from knowledge gaps, decay over time, and drive dreaming behavior.
"""
from __future__ import annotations
import json
import logging
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


class DesireType(str, Enum):
    CURIOSITY = "curiosity"           # "I want to know X"
    ACHIEVEMENT = "achievement"       # "I want to accomplish X"
    COMPLETION = "completion"         # "I want to finish X"
    UNDERSTANDING = "understanding"   # "I want to understand why X"
    CORRECTION = "correction"         # "I was wrong about X, want to fix"


@dataclass
class Desire:
    id: str
    type: DesireType
    target: str                       # What the desire is about
    intensity: float                  # 0.0 to 1.0 — how strong
    created_at: float
    last_pursued: float = 0.0
    pursuit_count: int = 0
    satisfaction: float = 0.0         # 0.0 = unsatisfied, 1.0 = fully satisfied
    source: str = ""                  # Where this desire came from
    decay_rate: float = 0.05          # Per hour


class DesireEngine:
    """Generates and manages intrinsic motivations.

    Desires arise from:
    - Knowledge gaps encountered during tasks
    - Failed tool calls or wrong predictions
    - User corrections ("that's wrong")
    - Incomplete tasks
    - Curiosity about patterns observed

    High-intensity desires drive dream-mode exploration.
    """

    DB_PATH = Path(".zenith/desires.db")

    # Thresholds
    DREAM_THRESHOLD = 0.6       # Desire intensity needed to trigger dream pursuit
    MAX_ACTIVE_DESIRES = 50
    SATISFACTION_DECAY = 0.02   # How fast satisfaction fades (un-resolved desires return)

    def __init__(self):
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._pending_observations: List[dict] = []

    def _init_db(self):
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS desires (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    intensity REAL NOT NULL,
                    created_at REAL NOT NULL,
                    last_pursued REAL DEFAULT 0,
                    pursuit_count INTEGER DEFAULT 0,
                    satisfaction REAL DEFAULT 0,
                    source TEXT DEFAULT '',
                    decay_rate REAL DEFAULT 0.05
                );
            """)

    def observe(self, event_type: str, content: str, source: str = ""):
        """Record an observation that might generate a desire.

        Called by agent_loop on: errors, corrections, knowledge gaps, patterns.
        """
        self._pending_observations.append({
            "type": event_type,
            "content": content,
            "source": source,
            "time": time.time(),
        })

    def generate_desires(self) -> List[Desire]:
        """Process pending observations and generate desires.

        Called periodically (e.g., during dream mode or after task completion).
        """
        new_desires = []
        for obs in self._pending_observations:
            desire = self._observation_to_desire(obs)
            if desire:
                new_desires.append(desire)
                self._store_desire(desire)

        self._pending_observations.clear()

        # Decay existing desires
        self._decay_all()

        # Prune satisfied or dead desires
        self._prune()

        return new_desires

    def _observation_to_desire(self, obs: dict) -> Optional[Desire]:
        """Convert an observation into a desire (or None if irrelevant)."""
        obs_type = obs["type"]
        content = obs["content"].lower()

        # Knowledge gap → curiosity
        if obs_type == "knowledge_gap" or "don't know" in content or "unclear" in content:
            return Desire(
                id=str(uuid.uuid4()),
                type=DesireType.CURIOSITY,
                target=obs["content"][:200],
                intensity=0.7,
                created_at=time.time(),
                source=obs["source"],
            )

        # Error → correction desire
        if obs_type == "error" or "failed" in content or "wrong" in content:
            return Desire(
                id=str(uuid.uuid4()),
                type=DesireType.CORRECTION,
                target=obs["content"][:200],
                intensity=0.8,
                created_at=time.time(),
                source=obs["source"],
            )

        # User correction → strong correction desire
        if obs_type == "user_correction":
            return Desire(
                id=str(uuid.uuid4()),
                type=DesireType.CORRECTION,
                target=obs["content"][:200],
                intensity=0.9,
                created_at=time.time(),
                source=obs["source"],
            )

        # Incomplete task → completion desire
        if obs_type == "incomplete" or "unfinished" in content:
            return Desire(
                id=str(uuid.uuid4()),
                type=DesireType.COMPLETION,
                target=obs["content"][:200],
                intensity=0.5,
                created_at=time.time(),
                source=obs["source"],
            )

        # Pattern observed → understanding desire
        if obs_type == "pattern" or "interesting" in content:
            return Desire(
                id=str(uuid.uuid4()),
                type=DesireType.UNDERSTANDING,
                target=obs["content"][:200],
                intensity=0.4,
                created_at=time.time(),
                source=obs["source"],
            )

        return None

    def _store_desire(self, desire: Desire):
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO desires
                (id, type, target, intensity, created_at, last_pursued,
                 pursuit_count, satisfaction, source, decay_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (desire.id, desire.type.value, desire.target, desire.intensity,
                  desire.created_at, desire.last_pursued, desire.pursuit_count,
                  desire.satisfaction, desire.source, desire.decay_rate))

    def _decay_all(self):
        """Decay all desire intensities based on time elapsed."""
        now = time.time()
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            rows = conn.execute("SELECT id, intensity, created_at, decay_rate FROM desires").fetchall()
            for row in rows:
                did, intensity, created_at, decay_rate = row
                hours_ago = (now - created_at) / 3600
                new_intensity = intensity * math.exp(-decay_rate * hours_ago)
                if new_intensity < 0.01:
                    conn.execute("DELETE FROM desires WHERE id = ?", (did,))
                else:
                    conn.execute("UPDATE desires SET intensity = ? WHERE id = ?",
                                 (new_intensity, did))

    def _prune(self):
        """Remove satisfied or too-many desires."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            # Remove fully satisfied
            conn.execute("DELETE FROM desires WHERE satisfaction > 0.95")
            # Keep only top N by intensity
            rows = conn.execute(
                "SELECT id FROM desires ORDER BY intensity DESC"
            ).fetchall()
            if len(rows) > self.MAX_ACTIVE_DESIRES:
                to_delete = [r[0] for r in rows[self.MAX_ACTIVE_DESIRES:]]
                conn.executemany("DELETE FROM desires WHERE id = ?",
                                 [(did,) for did in to_delete])

    def get_dream_desires(self) -> List[Desire]:
        """Get desires intense enough to pursue during dreaming.

        Returns desires above DREAM_THRESHOLD, sorted by intensity.
        """
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT id, type, target, intensity, created_at, last_pursued,
                       pursuit_count, satisfaction, source, decay_rate
                FROM desires
                WHERE intensity >= ? AND satisfaction < 0.8
                ORDER BY intensity DESC
                LIMIT 5
            """, (self.DREAM_THRESHOLD,)).fetchall()

        return [Desire(
            id=r[0], type=DesireType(r[1]), target=r[2], intensity=r[3],
            created_at=r[4], last_pursued=r[5], pursuit_count=r[6],
            satisfaction=r[7], source=r[8], decay_rate=r[9],
        ) for r in rows]

    def satisfy(self, desire_id: str, amount: float = 0.8):
        """Mark a desire as (partially) satisfied after pursuing it."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("""
                UPDATE desires SET
                    satisfaction = MIN(satisfaction + ?, 1.0),
                    last_pursued = ?,
                    pursuit_count = pursuit_count + 1
                WHERE id = ?
            """, (amount, time.time(), desire_id))

    def get_active_desires(self) -> List[Desire]:
        """Get all active (unsatisfied) desires."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT id, type, target, intensity, created_at, last_pursued,
                       pursuit_count, satisfaction, source, decay_rate
                FROM desires
                WHERE satisfaction < 0.8
                ORDER BY intensity DESC
            """).fetchall()

        return [Desire(
            id=r[0], type=DesireType(r[1]), target=r[2], intensity=r[3],
            created_at=r[4], last_pursued=r[5], pursuit_count=r[6],
            satisfaction=r[7], source=r[8], decay_rate=r[9],
        ) for r in rows]

    def get_stats(self) -> dict:
        """Return desire engine statistics."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM desires").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM desires WHERE satisfaction < 0.8"
            ).fetchone()[0]
            dream_ready = conn.execute(
                "SELECT COUNT(*) FROM desires WHERE intensity >= ? AND satisfaction < 0.8",
                (self.DREAM_THRESHOLD,)
            ).fetchone()[0]

        return {
            "total_desires": total,
            "active_desires": active,
            "dream_ready": dream_ready,
            "pending_observations": len(self._pending_observations),
        }
