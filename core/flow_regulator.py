from __future__ import annotations
import hashlib
import time
from collections import defaultdict
from typing import Dict

from core.types import (
    LocalLoopCircuitBreak, TokenBudgetExceeded,
    RegulatorDecision, RegulatorVerdict, ExecutionState
)


class FlowRegulator:
    CIRCUIT_BREAK_THRESHOLD = 3
    ACTION_HISTORY_WINDOW = 10

    def __init__(self):
        self._action_hashes: Dict[str, int] = defaultdict(int)
        self._action_timestamps: Dict[str, list] = defaultdict(list)

    def check_action(self, state: ExecutionState, action_token: str,
                     params: dict) -> RegulatorVerdict:
        # Token budget check
        if state.tokens_used >= state.token_budget:
            raise TokenBudgetExceeded(
                f"Token budget {state.token_budget} exceeded: {state.tokens_used}"
            )

        # Iteration limit check
        if state.iteration >= state.max_iterations:
            return RegulatorVerdict(
                decision=RegulatorDecision.DENY,
                reason=f"Max iterations ({state.max_iterations}) reached"
            )

        # Circuit breaker: same action repeated too many times
        action_hash = hashlib.md5(
            f"{action_token}:{sorted(params.items())}".encode()
        ).hexdigest()[:16]

        self._action_hashes[action_hash] += 1
        self._action_timestamps[action_hash].append(time.time())

        # Clean old timestamps
        cutoff = time.time() - 30
        self._action_timestamps[action_hash] = [
            t for t in self._action_timestamps[action_hash] if t > cutoff
        ]

        if self._action_hashes[action_hash] >= self.CIRCUIT_BREAK_THRESHOLD:
            raise LocalLoopCircuitBreak(action_hash, self._action_hashes[action_hash])

        return RegulatorVerdict(decision=RegulatorDecision.ALLOW, reason="OK")

    def reset(self):
        self._action_hashes.clear()
        self._action_timestamps.clear()
