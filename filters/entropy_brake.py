from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from core.types import RegulatorDecision, RegulatorVerdict


IRREVERSIBLE_PATTERNS = [
    "delete", "remove", "drop", "truncate", "destroy",
    "format", "wipe", "purge", "erase", "shred",
    "rm -rf", "rmdir", "del /f",
]


@dataclass
class EntropyBrakeResult:
    allowed: bool
    requires_confirmation: bool
    reason: str


class EntropyBrake:
    def check(self, action_token: str, params: dict,
              context: str = "") -> EntropyBrakeResult:
        action_lower = action_token.lower()
        params_str = str(params).lower()
        combined = f"{action_lower} {params_str}"

        for pattern in IRREVERSIBLE_PATTERNS:
            if pattern in combined:
                return EntropyBrakeResult(
                    allowed=False,
                    requires_confirmation=True,
                    reason=f"Irreversible action detected: '{pattern}' in {action_token}. "
                           f"Human confirmation required."
                )

        return EntropyBrakeResult(allowed=True, requires_confirmation=False, reason="OK")

    def verdict(self, action_token: str, params: dict) -> RegulatorVerdict:
        result = self.check(action_token, params)
        if result.requires_confirmation:
            return RegulatorVerdict(
                decision=RegulatorDecision.CONFIRM,
                reason=result.reason
            )
        return RegulatorVerdict(decision=RegulatorDecision.ALLOW, reason="Safe action")
