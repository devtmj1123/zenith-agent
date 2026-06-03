"""Dream Controller — Dual-track reasoning engine.

Fast-path: Ollama llama3.2:3b for quick local responses (<1s)
Deep-path: Full LLM for complex reasoning when fast-path insufficient

Integrates Desire Engine (what to think about) and
Unrelated Association Engine (how to connect ideas).

Dream mode activates during idle periods to:
1. Pursue high-intensity desires
2. Discover cross-domain associations
3. Generate novel hypotheses
4. Consolidate memories
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.desire_engine import DesireEngine, Desire, DesireType
from core.unrelated_association import UnrelatedAssociationEngine, Association

log = logging.getLogger(__name__)


@dataclass
class DreamResult:
    """Output from a dream cycle."""
    desires_pursued: int = 0
    associations_found: int = 0
    hypotheses_generated: int = 0
    memories_consolidated: int = 0
    novel_insights: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class DreamController:
    """Dual-track reasoning that runs during idle periods.

    Fast-path: Local Ollama model for quick pattern matching
    Deep-path: Full API LLM for complex reasoning

    The dream controller:
    1. Checks desire engine for high-intensity desires
    2. Uses association engine to find cross-domain connections
    3. Generates hypotheses about those connections
    4. Stores novel insights in soft memory
    """

    def __init__(
        self,
        desire_engine: DesireEngine,
        association_engine: UnrelatedAssociationEngine,
        llm_call: Optional[Callable] = None,
        fast_llm_call: Optional[Callable] = None,
        memory_compressor=None,
    ):
        self.desires = desire_engine
        self.associations = association_engine
        self.llm_call = llm_call          # Full LLM for deep reasoning
        self.fast_llm_call = fast_llm_call  # Ollama for quick matching
        self.memory = memory_compressor

        # Dream state
        self._is_dreaming = False
        self._dream_count = 0
        self._last_dream_time = 0.0

        # Configuration
        self.min_dream_interval = 300     # Minimum 5 minutes between dreams
        self.max_dream_duration = 60      # Max 60 seconds per dream cycle
        self.fast_path_timeout = 5        # 5s timeout for fast-path

    @property
    def is_dreaming(self) -> bool:
        return self._is_dreaming

    async def dream(self) -> DreamResult:
        """Run a dream cycle. Called by SystemMonitor during idle periods.

        Process:
        1. Gather high-intensity desires
        2. For each desire, find cross-domain associations
        3. Use LLM to generate hypotheses
        4. Store novel insights
        """
        # Respect minimum interval
        now = time.time()
        if now - self._last_dream_time < self.min_dream_interval:
            return DreamResult()

        self._is_dreaming = True
        self._last_dream_time = now
        start = time.time()
        result = DreamResult()

        try:
            # Phase 1: Generate desires from pending observations
            new_desires = self.desires.generate_desires()

            # Phase 2: Get desires worth pursuing
            dream_desires = self.desires.get_dream_desires()
            result.desires_pursued = len(dream_desires)

            # Phase 3: For each desire, find associations and generate insights
            for desire in dream_desires:
                # Time check
                if time.time() - start > self.max_dream_duration:
                    break

                insight = await self._pursue_desire(desire)
                if insight:
                    result.novel_insights.append(insight)
                    result.hypotheses_generated += 1

            # Phase 4: Random cross-domain association discovery
            random_insights = await self._discover_random_associations()
            result.associations_found = len(random_insights)
            result.novel_insights.extend(random_insights)

            # Phase 5: Consolidate dream insights into memory
            if result.novel_insights and self.memory:
                for insight in result.novel_insights:
                    try:
                        await self.memory.store_interaction(
                            f"Dream insight: {insight[:100]}",
                            insight,
                            session_id="dream",
                            tool_calls_made=0,
                            last_tool_token="dream_insight",
                        )
                        result.memories_consolidated += 1
                    except Exception as e:
                        log.warning(f"Failed to store dream insight: {e}")

        except Exception as e:
            log.error(f"Dream cycle error: {e}")
        finally:
            self._is_dreaming = False
            self._dream_count += 1
            result.duration_seconds = time.time() - start

        return result

    async def _pursue_desire(self, desire: Desire) -> Optional[str]:
        """Pursue a single desire through association and reasoning.

        Returns an insight string if one was generated, None otherwise.
        """
        # Use fast-path to find relevant concepts
        relevant_concepts = await self._fast_find_concepts(desire.target)
        if not relevant_concepts:
            return None

        # Find associations for the top concept
        top_concept = relevant_concepts[0]
        associations = self.associations.find_associations(top_concept, top_k=3)

        if not associations:
            return None

        # Use deep LLM to generate hypothesis from the best association
        best = associations[0]
        if best.innovation_score < 0.3:
            return None

        hypothesis = await self._generate_hypothesis(desire, best)
        if hypothesis:
            # Mark desire as partially satisfied
            self.desires.satisfy(desire.id, amount=0.3)

        return hypothesis

    async def _fast_find_concepts(self, query: str) -> List[str]:
        """Use fast-path LLM to find relevant concept names.

        Returns list of concept names from the association engine.
        """
        if not self.fast_llm_call:
            # Fallback: keyword matching
            query_lower = query.lower()
            matches = []
            for name, concept in self.associations.concepts.items():
                if any(w in name.lower() or w in concept.description.lower()
                       for w in query_lower.split() if len(w) > 3):
                    matches.append(name)
            return matches[:3]

        try:
            concept_list = list(self.associations.concepts.keys())[:30]
            prompt = (
                f"Given the query: '{query}'\n"
                f"Which of these concepts are most relevant? "
                f"Return ONLY a JSON array of concept names.\n"
                f"Concepts: {json.dumps(concept_list)}"
            )

            response = await asyncio.wait_for(
                self.fast_llm_call([{"role": "user", "content": prompt}]),
                timeout=self.fast_path_timeout,
            )

            content = response.get("content", "[]")
            # Parse JSON array from response
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])[:3]
        except Exception as e:
            log.debug(f"Fast-path concept finding failed: {e}")

        return []

    async def _generate_hypothesis(self, desire: Desire,
                                    association: Association) -> Optional[str]:
        """Use deep LLM to generate a hypothesis from an association."""
        if not self.llm_call:
            # Return a basic insight without LLM
            return (
                f"Potential connection: {association.concept_a} <-> {association.concept_b} "
                f"via {association.shared_pattern}. {association.analogy}"
            )

        try:
            prompt = (
                f"I have a desire to understand: '{desire.target}'\n\n"
                f"I found a structural analogy:\n"
                f"- Concept A: {association.concept_a}\n"
                f"- Concept B: {association.concept_b}\n"
                f"- Shared pattern: {association.shared_pattern}\n"
                f"- Innovation score: {association.innovation_score:.2f}\n"
                f"- Analogy: {association.analogy}\n\n"
                f"Generate a novel hypothesis or insight that combines these two domains. "
                f"Be specific and actionable. One paragraph max."
            )

            response = await asyncio.wait_for(
                self.llm_call([{"role": "user", "content": prompt}]),
                timeout=30,
            )

            content = response.get("content", "").strip()
            if content and len(content) > 20:
                return content

        except Exception as e:
            log.debug(f"Hypothesis generation failed: {e}")

        return None

    async def _discover_random_associations(self) -> List[str]:
        """Discover random cross-domain associations.

        Picks random concepts from different domains and checks for connections.
        """
        insights = []
        concepts = list(self.associations.concepts.values())

        if len(concepts) < 2:
            return insights

        # Pick concepts from different domains
        import random
        attempts = 0
        while attempts < 5 and len(insights) < 2:
            attempts += 1
            a, b = random.sample(concepts, 2)
            if a.domain == b.domain:
                continue

            assoc = self.associations._compute_association(a, b)
            if assoc and assoc.innovation_score > 0.4:
                insights.append(
                    f"[Random discovery] {assoc.analogy} "
                    f"(innovation score: {assoc.innovation_score:.2f})"
                )
                self.associations._store_association(assoc)

        return insights

    def get_stats(self) -> dict:
        """Return dream controller statistics."""
        return {
            "is_dreaming": self._is_dreaming,
            "total_dream_cycles": self._dream_count,
            "last_dream_time": self._last_dream_time,
            "desire_stats": self.desires.get_stats(),
            "association_stats": self.associations.get_stats(),
        }
