"""
Pseudo multi-agent debate via sequential LLM calls with role-specific prompts.
Not separate agent processes — same LLM, different system prompts.
Practically achieves the same adversarial pressure.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class DebateResult:
    finding:    str
    researcher_view: str
    critic_view: str
    verdict:    str       # "supported" | "challenged" | "uncertain"
    confidence: float


class SequentialDebate:
    """
    Three-turn debate:
    1. Researcher (supports finding with evidence)
    2. Critic (challenges finding)
    3. Synthesizer (weighs both, gives verdict)
    """

    RESEARCHER_PROMPT = """You are a scientific researcher.
Given this finding, provide 2-3 supporting arguments with evidence.
Be specific. Cite mechanisms, not just opinions.
Finding: {finding}"""

    CRITIC_PROMPT = """You are a rigorous scientific critic.
Challenge this finding. Find weaknesses, alternative explanations, missing evidence.
Be specific. What would make this claim stronger or weaker?
Finding: {finding}
Researcher's support: {researcher_view}"""

    SYNTHESIZER_PROMPT = """You are a neutral scientific synthesizer.
Weigh the researcher's support against the critic's challenges.
Give a verdict: supported / challenged / uncertain.
One paragraph. Be direct.
Finding: {finding}
Support: {researcher_view}
Challenge: {critic_view}"""

    def __init__(self, llm_call):
        self.llm = llm_call   # async (messages) -> dict

    async def debate(self, finding: str) -> DebateResult:
        # Turn 1: Researcher
        researcher_view = await self._call(
            self.RESEARCHER_PROMPT.format(finding=finding)
        )

        # Turn 2: Critic
        critic_view = await self._call(
            self.CRITIC_PROMPT.format(
                finding=finding, researcher_view=researcher_view
            )
        )

        # Turn 3: Synthesizer
        verdict_text = await self._call(
            self.SYNTHESIZER_PROMPT.format(
                finding=finding,
                researcher_view=researcher_view,
                critic_view=critic_view,
            )
        )

        # Parse verdict
        v_lower = verdict_text.lower()
        if "supported" in v_lower:
            verdict, confidence = "supported", 0.8
        elif "challenged" in v_lower:
            verdict, confidence = "challenged", 0.4
        else:
            verdict, confidence = "uncertain", 0.5

        return DebateResult(
            finding=finding,
            researcher_view=researcher_view,
            critic_view=critic_view,
            verdict=verdict,
            confidence=confidence,
        )

    async def _call(self, prompt: str) -> str:
        try:
            result = await self.llm(
                [{"role": "user", "content": prompt}], tools=None
            )
            return result.get("content", "").strip()
        except Exception:
            return ""
