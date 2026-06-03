"""Entropy Brake — Irreversibility Circuit Breaker.

Classifies actions by reversibility:
  REVERSIBLE:   Can be undone (edit file, create event)
  RECOVERABLE:  Hard to undo but possible (send email, git push)
  IRREVERSIBLE: Cannot be undone (delete without backup, wire transfer)

Zero LLM calls — pure pattern matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    RECOVERABLE = "recoverable"
    IRREVERSIBLE = "irreversible"


@dataclass
class BrakeResult:
    allow: bool
    reversibility: Reversibility
    reason: str
    require_human: bool = False
    warning_msg: str = ""


class EntropyBrake:
    """Hard physics of action reversibility. Zero LLM calls."""

    ACTION_SIGNATURES = [
        # IRREVERSIBLE
        (r"rm\s+-rf", Reversibility.IRREVERSIBLE, True),
        (r"delete\s+.*(permanent|forever|no.backup)", Reversibility.IRREVERSIBLE, True),
        (r"wire\s+transfer|send\s+money|transfer\s+funds", Reversibility.IRREVERSIBLE, True),
        (r"overwrite.*system|replace.*system", Reversibility.IRREVERSIBLE, True),
        (r"uninstall.*driver", Reversibility.IRREVERSIBLE, True),
        (r"DROP\s+(TABLE|DATABASE)", Reversibility.IRREVERSIBLE, True),
        (r"TRUNCATE\s+TABLE", Reversibility.IRREVERSIBLE, True),
        (r"mkfs|format\s+[a-z]:", Reversibility.IRREVERSIBLE, True),
        (r"git\s+push\s+--force\s+origin\s+main", Reversibility.IRREVERSIBLE, True),
        (r"publish.*npm|publish.*pypi", Reversibility.IRREVERSIBLE, True),
        # RECOVERABLE
        (r"git\s+push(?!\s+--force)", Reversibility.RECOVERABLE, False),
        (r"send\s+email|gmail.*send", Reversibility.RECOVERABLE, False),
        (r"post\s+tweet|publish\s+post", Reversibility.RECOVERABLE, False),
        (r"deploy\s+to\s+production", Reversibility.RECOVERABLE, True),
        (r"merge.*pull.request", Reversibility.RECOVERABLE, True),
        (r"npm\s+publish", Reversibility.RECOVERABLE, True),
        # REVERSIBLE
        (r"write.*file|edit.*file|create.*file", Reversibility.REVERSIBLE, False),
        (r"git\s+commit", Reversibility.REVERSIBLE, False),
        (r"create.*event|schedule.*meeting", Reversibility.REVERSIBLE, False),
    ]

    def check(
        self,
        action_description: str,
        context_source: str = "agent",
        autopilot: bool = False,
    ) -> BrakeResult:
        """Evaluate reversibility of an action."""
        text = action_description.lower()

        for pattern, reversibility, human_required in self.ACTION_SIGNATURES:
            if re.search(pattern, text, re.IGNORECASE):
                return self._evaluate(
                    reversibility, human_required,
                    context_source, autopilot, pattern
                )

        return BrakeResult(
            allow=True,
            reversibility=Reversibility.REVERSIBLE,
            reason="No irreversibility pattern matched",
        )

    def _evaluate(
        self,
        rev: Reversibility,
        human_required: bool,
        context_source: str,
        autopilot: bool,
        matched_pattern: str,
    ) -> BrakeResult:
        # External content → always require human for risky actions
        if context_source in ("external_web", "external_file"):
            if rev in (Reversibility.RECOVERABLE, Reversibility.IRREVERSIBLE):
                return BrakeResult(
                    allow=False,
                    reversibility=rev,
                    reason=f"External content triggered {rev} action",
                    require_human=True,
                    warning_msg=(
                        f"ENTROPY BRAKE: Action '{matched_pattern}' is {rev} "
                        f"and was triggered by external content. Manual approval required."
                    ),
                )

        # Irreversible → always require human
        if rev == Reversibility.IRREVERSIBLE:
            return BrakeResult(
                allow=False,
                reversibility=rev,
                reason=f"Irreversible action: {matched_pattern}",
                require_human=True,
                warning_msg=(
                    f"ENTROPY BRAKE: This action CANNOT be undone. "
                    f"Pattern: '{matched_pattern}'. Human approval required."
                ),
            )

        # Recoverable + human_required + no autopilot
        if rev == Reversibility.RECOVERABLE and human_required and not autopilot:
            return BrakeResult(
                allow=False,
                reversibility=rev,
                reason=f"Recoverable but risky: {matched_pattern}",
                require_human=True,
                warning_msg=(
                    f"This action is hard to reverse: '{matched_pattern}'. Confirm to proceed."
                ),
            )

        return BrakeResult(
            allow=True,
            reversibility=rev,
            reason=f"Allowed: {rev} action",
        )
