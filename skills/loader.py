"""Skill loader — discovers and loads SKILL.md files into agent context.

Semantic matching using description embeddings (intent-focused).
Falls back to BM25-only when encoder is unavailable.
"""
from __future__ import annotations
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


class Skill:
    def __init__(self, name: str, description: str, content: str, path: Path):
        self.name = name
        self.description = description
        self.content = content
        self.path = path
        # BM25 tokenization
        self._tokens = self._tokenize(f"{name} {description} {content}")
        self._token_counts = Counter(self._tokens)
        self._doc_len = len(self._tokens)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Lowercase alphanumeric tokens, 3+ chars."""
        return re.findall(r'[a-z0-9_]{3,}', text.lower())

    def bm25_score(self, query_tokens: List[str], avg_dl: float,
                   idf: Dict[str, float], k1: float = 1.5, b: float = 0.75) -> float:
        """BM25 score for this skill against a tokenized query."""
        if not query_tokens:
            return 0.0
        score = 0.0
        dl = self._doc_len
        for qt in query_tokens:
            if qt not in self._token_counts:
                continue
            tf = self._token_counts[qt]
            doc_len_norm = 1 - b + b * (dl / avg_dl) if avg_dl > 0 else 1.0
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * doc_len_norm)
            score += idf.get(qt, 0.0) * tf_norm
        return score

    def keyword_score(self, query: str) -> float:
        """Simple keyword overlap (legacy fallback)."""
        query_words = set(re.findall(r'[a-z0-9_]{2,}', query.lower()))
        if not query_words:
            return 0.0
        doc_words = set(self._tokens)
        return len(query_words & doc_words) / len(query_words)


class SkillLoader:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Skill] = {}
        self._encoder = None
        self._desc_embeddings: Optional[np.ndarray] = None
        self._skill_names: List[str] = []
        # BM25 corpus stats
        self._avg_dl: float = 0.0
        self._idf: Dict[str, float] = {}

    def set_encoder(self, encoder):
        """Set SentenceTransformer encoder for semantic matching."""
        self._encoder = encoder

    def load_all(self):
        """Discover and load all SKILL.md files."""
        if not self.skills_dir.exists():
            return

        for skill_file in self.skills_dir.rglob("SKILL.md"):
            try:
                raw = skill_file.read_text(encoding="utf-8")
                name, description, content = self._parse_skill(raw, skill_file)
                if name:
                    self._skills[name] = Skill(name, description, content, skill_file)
            except Exception:
                continue

        self._skill_names = list(self._skills.keys())
        self._compute_bm25_stats()
        log.info(f"SkillLoader: loaded {len(self._skills)} skills")

    def _compute_bm25_stats(self):
        """Pre-compute IDF and average document length for BM25."""
        n = len(self._skills)
        if n == 0:
            return
        # Document frequency
        df: Counter = Counter()
        total_len = 0
        for skill in self._skills.values():
            unique_tokens = set(skill._tokens)
            for t in unique_tokens:
                df[t] += 1
            total_len += skill._doc_len
        self._avg_dl = total_len / n
        # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        self._idf = {}
        for term, freq in df.items():
            self._idf[term] = math.log((n - freq + 0.5) / (freq + 0.5) + 1.0)

    def build_index(self):
        """Build semantic index for all skills. Call after set_encoder()."""
        if not self._encoder or not self._skills:
            return

        # Embed descriptions only — they capture "when to use" intent
        # and are more focused than full content
        desc_texts = [s.description for s in self._skills.values()]
        try:
            self._desc_embeddings = self._encoder.encode(
                desc_texts, normalize_embeddings=True, show_progress_bar=False
            )
            log.info(f"SkillLoader: indexed {len(desc_texts)} skills semantically")
        except Exception as e:
            log.warning(f"SkillLoader: failed to build index: {e}")
            self._desc_embeddings = None

    def _parse_skill(self, raw: str, path: Path) -> tuple:
        """Parse SKILL.md frontmatter + content."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', raw, re.DOTALL)
        if not match:
            name = path.parent.name
            return name, "", raw

        frontmatter = match.group(1)
        content = match.group(2)

        name_match = re.search(r'name:\s*(.+)', frontmatter)
        desc_match = re.search(r'description:\s*(.+)', frontmatter)

        name = name_match.group(1).strip() if name_match else path.parent.name
        description = desc_match.group(1).strip() if desc_match else ""

        return name, description, content

    def get_relevant_context(self, query: str, max_skills: int = 2,
                             min_score: float = 0.0) -> str:
        """Return relevant skill content using semantic matching.

        Uses description-only embeddings with absolute threshold to reject
        irrelevant queries. Falls back to BM25 when no encoder is available.
        """
        if not self._skills:
            return ""

        # Semantic scores (preferred)
        sem_scores: Dict[str, float] = {}
        if self._encoder and self._desc_embeddings is not None:
            try:
                query_vec = self._encoder.encode(
                    query, normalize_embeddings=True, show_progress_bar=False
                )
                raw_sem = self._desc_embeddings @ query_vec
                for i, name in enumerate(self._skill_names):
                    sem_scores[name] = float(raw_sem[i])  # raw cosine [-1, 1]
            except Exception as e:
                log.warning(f"SkillLoader: semantic match failed: {e}")

        if sem_scores:
            # Semantic-only: use raw cosine similarity
            # Description embeddings produce cleaner signal than full content
            # because they focus on "when to use" intent
            ABSOLUTE_THRESHOLD = 0.05
            final_scores = sem_scores

            max_score = max(final_scores.values())
            if max_score < ABSOLUTE_THRESHOLD:
                return ""

            # Return skills above the absolute threshold, best first
            scored = [(s, name) for name, s in final_scores.items()
                      if s >= ABSOLUTE_THRESHOLD]
            scored.sort(key=lambda x: x[0], reverse=True)
        else:
            # Fallback: BM25-only when no encoder
            query_tokens = Skill._tokenize(query)
            bm25_scores = {}
            for name, skill in self._skills.items():
                bm25_scores[name] = skill.bm25_score(
                    query_tokens, self._avg_dl, self._idf)

            if not bm25_scores or max(bm25_scores.values()) <= 0:
                return ""

            # Relative threshold for BM25 fallback
            max_score = max(bm25_scores.values())
            threshold = max_score * 0.7
            scored = [(s, name) for name, s in bm25_scores.items()
                      if s >= threshold]
            scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            return ""

        parts = []
        for score, name in scored[:max_skills]:
            skill = self._skills[name]
            content = skill.content[:2000]
            if len(skill.content) > 2000:
                content += "\n[...truncated]"
            parts.append(f"## {skill.name}\n{content}")

        return "\n\n".join(parts)

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
