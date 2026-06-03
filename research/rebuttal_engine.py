# research/rebuttal_engine.py
"""
Socratic Rebuttal Engine.

Core principle: Agent challenges user claims when EVIDENCE contradicts them.
NOT opinion-based. NEVER lectures. Always shows its work.

Four rebuttal levels:
  L1 PHYSICS    -> Mathematical proof (conservation laws, dimensional analysis)
  L2 LITERATURE -> Published studies contradict the claim
  L3 LOGIC      -> User's own premises are self-contradictory
  L4 UNCERTAIN  -> Evidence is mixed -- present both sides honestly

The agent MUST:
  - Show the source/calculation
  - Acknowledge what it does NOT know
  - Distinguish "proven wrong" from "evidence suggests otherwise"
  - Respect user autonomy (present evidence, never moralize)

The agent MUST NOT:
  - Rebut based on LLM training data alone (needs external evidence)
  - Dismiss novel ideas without checking literature
  - Pretend certainty where uncertainty exists
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RebuttalLevel(str, Enum):
    NONE        = "none"          # No rebuttal needed
    PHYSICS     = "physics"       # Hard math contradiction
    LITERATURE  = "literature"    # Published evidence contradicts
    LOGIC       = "logic"         # Self-contradiction
    UNCERTAIN   = "uncertain"     # Mixed evidence, present both


@dataclass
class RebuttalResult:
    level:      RebuttalLevel
    claim:      str               # What the user claimed
    evidence:   List[str]         # Sources / calculations
    rebuttal:   str               # What to say to user
    confidence: float             # 0.0 - 1.0
    alternative: Optional[str] = None  # Better framing of user's idea


class SocraticRebuttal:
    """
    Checks user claims before the agent responds.
    Runs in parallel with the main response generation.
    If rebuttal found -> prepend to response.
    """

    def __init__(self, hard_memory=None, arxiv_client=None, pubmed_client=None,
                 zero_error_filter=None, unit_standardizer=None):
        self.hard_mem  = hard_memory
        self.arxiv     = arxiv_client
        self.pubmed    = pubmed_client
        self.zef       = zero_error_filter
        self.units     = unit_standardizer

    async def check(self, user_message: str) -> RebuttalResult:
        """
        Main entry. Check user message for challengeable claims.
        Returns RebuttalResult with level=NONE if nothing to rebut.
        """
        # L1: Physics violation check (zero LLM, pure math)
        physics_result = self._check_physics(user_message)
        if physics_result.level != RebuttalLevel.NONE:
            return physics_result

        # L2: Literature check (async, hits APIs)
        lit_result = await self._check_literature(user_message)
        if lit_result.level != RebuttalLevel.NONE:
            return lit_result

        # L3: Logic check (local, fast)
        logic_result = self._check_logic(user_message)
        if logic_result.level != RebuttalLevel.NONE:
            return logic_result

        return RebuttalResult(
            level=RebuttalLevel.NONE,
            claim=user_message,
            evidence=[],
            rebuttal="",
            confidence=0.0,
        )

    # -- L1: Physics Violation -------------------------------------------------

    def _check_physics(self, text: str) -> RebuttalResult:
        """
        Detect claims that violate fundamental physics.
        Zero LLM, pure pattern matching + hard memory constants.
        """
        violations = []

        # Faster-than-light claims
        ftl_patterns = [
            r'超过.*光速|faster.than.light|exceed.*speed.*light|FTL',
            r'负.*能量.*输入|negative.*energy.*input',
            r'永动机|perpetual.*motion|free.*energy.*machine',
            r'效率.*超过.*100|efficiency.*over.*100.*percent',
            r'超.*卡诺|exceed.*carnot',
        ]
        for pattern in ftl_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(
                    "Violates: speed of light c = 299792458 m/s (SI 2019 definitional)"
                )

        # Energy conservation violation
        energy_patterns = [
            r'产生.*比.*输入.*更多.*能量|produces.*more.*energy.*than.*input',
            r'能量.*凭空.*产生|energy.*from.*nothing',
            r'COP.*无限|infinite.*COP',
        ]
        for pattern in energy_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(
                    "Violates: First Law of Thermodynamics -- "
                    "energy cannot be created or destroyed (dE = 0 in isolated system)"
                )

        # Entropy violation
        entropy_patterns = [
            r'自发.*降低.*熵|spontaneous.*entropy.*decrease',
            r'热量.*自发.*从冷.*到热|heat.*spontaneous.*cold.*to.*hot',
        ]
        for pattern in entropy_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(
                    "Violates: Second Law of Thermodynamics -- "
                    "entropy of isolated system never spontaneously decreases (dS >= 0)"
                )

        if not violations:
            return RebuttalResult(
                level=RebuttalLevel.NONE, claim=text,
                evidence=[], rebuttal="", confidence=0.0
            )

        rebuttal = self._format_physics_rebuttal(text, violations)
        return RebuttalResult(
            level=RebuttalLevel.PHYSICS,
            claim=text,
            evidence=violations,
            rebuttal=rebuttal,
            confidence=1.0,  # Physics is certain
        )

    def _format_physics_rebuttal(self, claim: str, violations: List[str]) -> str:
        return (
            "PHYSICS VIOLATION DETECTED\n\n"
            "Your claim contradicts confirmed physical laws:\n\n"
            + "\n".join(f"- {v}" for v in violations)
            + "\n\nThese are SI definitional laws, not theories. "
            "Any violation is impossible within our known physics framework.\n\n"
            "If you are exploring boundary conditions (quantum scale, extreme pressure corrections), "
            "I can help analyze existing literature on limit cases."
        )

    # -- L2: Literature Check --------------------------------------------------

    async def _check_literature(self, text: str) -> RebuttalResult:
        """
        Search relevant literature for contradicting evidence.
        Only rebuts if finds 2+ independent sources disagreeing.
        """
        if not self.arxiv and not self.pubmed:
            return RebuttalResult(
                level=RebuttalLevel.NONE, claim=text,
                evidence=[], rebuttal="", confidence=0.0
            )

        claim_keywords = self._extract_claim_keywords(text)
        if not claim_keywords:
            return RebuttalResult(
                level=RebuttalLevel.NONE, claim=text,
                evidence=[], rebuttal="", confidence=0.0
            )

        # Search arXiv + PubMed in parallel
        arxiv_results = []
        pubmed_results = []

        if self.arxiv:
            try:
                arxiv_results = await self.arxiv.search(
                    f"{claim_keywords} contradicting evidence refutation", max_results=5
                )
            except Exception:
                pass

        if self.pubmed:
            try:
                pubmed_results = await self.pubmed.search(
                    f"{claim_keywords} systematic review meta-analysis", max_results=5
                )
            except Exception:
                pass

        contradicting = [
            r for r in (arxiv_results + pubmed_results)
            if self._is_contradicting(r, text)
        ]

        if len(contradicting) < 2:
            return RebuttalResult(
                level=RebuttalLevel.NONE, claim=text,
                evidence=[], rebuttal="", confidence=0.0
            )

        evidence = [f"{r.get('title', 'Unknown')} ({r.get('year', '?')}) -- {r.get('source', '?')}"
                    for r in contradicting[:3]]
        confidence = min(0.9, 0.5 + len(contradicting) * 0.1)

        rebuttal = (
            "LITERATURE CONTRADICTION FOUND\n\n"
            "Published research challenges your claim:\n\n"
            + "\n".join(f"- {e}" for e in evidence)
            + "\n\nThis does not mean you are wrong -- science evolves. "
            "But these results should be considered in your analysis. "
            "Want me to analyze these studies in detail?"
        )

        return RebuttalResult(
            level=RebuttalLevel.LITERATURE,
            claim=text, evidence=evidence,
            rebuttal=rebuttal, confidence=confidence,
        )

    # -- L3: Logic Check -------------------------------------------------------

    def _check_logic(self, text: str) -> RebuttalResult:
        """
        Detect self-contradictions in user's own premises.
        """
        contradictions = []

        # No side effects + metabolic change
        if (re.search(r'没有.*副作用|no.*side.effect', text, re.IGNORECASE) and
                re.search(r'代谢|metabolism|细胞|cellular', text, re.IGNORECASE)):
            contradictions.append(
                "Any substance that changes cell metabolism has side effects by definition "
                "(side effect = effect on non-target cells or pathways)"
            )

        # 100% selectivity claim
        if re.search(r'100%.*选择性|perfectly.*selective|absolute.*specificity',
                     text, re.IGNORECASE):
            contradictions.append(
                "Absolute 100% selectivity does not exist in biological systems -- "
                "molecular binding is probability-based with off-target effects"
            )

        # Zero toxicity claim for active compounds
        if (re.search(r'无毒|zero.*toxic|non.*toxic', text, re.IGNORECASE) and
                re.search(r'active.*compound|活性化合物|药效', text, re.IGNORECASE)):
            contradictions.append(
                "Paracelsus principle (1538): All substances are toxins, "
                "only the dose makes the poison -- sola dosis facit venenum"
            )

        if not contradictions:
            return RebuttalResult(
                level=RebuttalLevel.NONE, claim=text,
                evidence=[], rebuttal="", confidence=0.0
            )

        rebuttal = (
            "LOGICAL CONTRADICTION DETECTED\n\n"
            "Your statement contains contradictory premises:\n\n"
            + "\n".join(f"- {c}" for c in contradictions)
            + "\n\nI want to help you express this idea more precisely. "
            "What is your core argument? We can rebuild from there."
        )

        return RebuttalResult(
            level=RebuttalLevel.LOGIC,
            claim=text, evidence=contradictions,
            rebuttal=rebuttal, confidence=0.85,
        )

    # -- Helpers ---------------------------------------------------------------

    def _extract_claim_keywords(self, text: str) -> str:
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be",
                      "been", "being", "have", "has", "had", "do", "does",
                      "did", "will", "would", "could", "should", "may",
                      "might", "can", "shall", "that", "this", "these",
                      "those", "it", "its"}
        words = re.findall(r'\b\w{3,}\b', text)
        keywords = [w for w in words if w.lower() not in stop_words]
        return " ".join(keywords[:6])

    def _is_contradicting(self, paper: dict, claim: str) -> bool:
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        contradicting_words = [
            "refutes", "contradicts", "disproves", "challenges",
            "no evidence", "failed to", "ineffective", "null result",
        ]
        text = title + " " + abstract
        return any(w in text for w in contradicting_words)
