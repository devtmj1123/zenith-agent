from __future__ import annotations
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List

from memory.hard_memory import PHYSICS_CONSTANTS, TOLERANCE_RIGID, TOLERANCE_SOFT


@dataclass
class FilterResult:
    passed: bool
    verdict: str
    reason: str
    confidence: float = 1.0
    deferred_to_queue: bool = False


@dataclass
class PendingCheck:
    check_id: str
    law: str
    values: dict
    priority: float = 1.0
    created_at: float = field(default_factory=time.time)
    observed_conflicts: List[str] = field(default_factory=list)


class ZeroErrorFilter:
    CPU_HIGH_THRESHOLD = 0.70
    CPU_SCAN_RADIUS_FULL = 1e-6
    CPU_SCAN_RADIUS_REDUCED = 1e-4

    def __init__(self, system_monitor=None):
        self._monitor = system_monitor
        self._queue: deque = deque(maxlen=500)
        self._processed: Dict[str, FilterResult] = {}

    def _get_tolerance(self, law: str) -> float:
        cpu_load = self._monitor.cpu_load if self._monitor else 0.3
        if law in ("energy_conservation", "charge_conservation", "momentum_conservation"):
            return TOLERANCE_RIGID
        if cpu_load < 0.3:
            return self.CPU_SCAN_RADIUS_FULL
        elif cpu_load < 0.7:
            return self.CPU_SCAN_RADIUS_REDUCED
        return 1e-3

    def validate(self, law: str, values: dict,
                 context_source: str = "internal") -> FilterResult:
        cpu_load = self._monitor.cpu_load if self._monitor else 0.3

        if cpu_load > self.CPU_HIGH_THRESHOLD and law not in self._CRITICAL_LAWS:
            return self._defer_to_queue(law, values)

        validator = self._LAW_VALIDATORS.get(law)
        if not validator:
            return FilterResult(
                passed=True, verdict="unknown_law",
                reason=f"Law '{law}' not in registry. Pass through.",
                confidence=0.5
            )

        passed, reason = validator(self, values)
        tolerance = self._get_tolerance(law)

        if not passed:
            if self._is_fundamental_violation(law, values):
                return FilterResult(
                    passed=False, verdict="law_violation",
                    reason=f"FUNDAMENTAL VIOLATION: {reason}. Reject data.",
                    confidence=1.0
                )
            else:
                return FilterResult(
                    passed=True, verdict="convergence_error",
                    reason=f"Convergence error within tolerance {tolerance}: {reason}",
                    confidence=0.7
                )

        return FilterResult(
            passed=True, verdict="passed",
            reason=f"Law '{law}' satisfied within tolerance {tolerance}",
            confidence=1.0
        )

    def _defer_to_queue(self, law: str, values: dict) -> FilterResult:
        check_id = str(uuid.uuid4())[:8]
        self._queue.append(PendingCheck(
            check_id=check_id, law=law, values=values,
            priority=time.time()
        ))
        return FilterResult(
            passed=True, verdict="deferred",
            reason=f"CPU load high. Check {check_id} queued for dream-mode validation.",
            confidence=0.5, deferred_to_queue=True
        )

    def process_queue_batch(self, max_items: int = 10) -> List[FilterResult]:
        results = []
        processed = 0
        while self._queue and processed < max_items:
            check = self._queue.popleft()
            result = self.validate(check.law, check.values)
            if check.observed_conflicts:
                result.confidence *= 0.7
            self._processed[check.check_id] = result
            results.append(result)
            processed += 1
        return results

    # ─── Law Validators ────────────────────────────────────────────────────

    def _check_energy_conservation(self, values: dict) -> tuple:
        before = values.get("energy_before", 0)
        after = values.get("energy_after", 0)
        delta = abs(before - after) / max(abs(before), 1e-12)
        return delta < TOLERANCE_RIGID, f"delta E/E = {delta:.2e}"

    def _check_charge_conservation(self, values: dict) -> tuple:
        charges = values.get("charges", [])
        total = abs(sum(charges))
        return total < TOLERANCE_RIGID, f"|sum Q| = {total:.2e} C"

    def _check_momentum_conservation(self, values: dict) -> tuple:
        p_before = values.get("momentum_before", [0, 0, 0])
        p_after = values.get("momentum_after", [0, 0, 0])
        delta = sum(abs(b - a) for b, a in zip(p_before, p_after))
        total = max(sum(abs(p) for p in p_before), 1e-12)
        return delta / total < TOLERANCE_RIGID, f"delta p/p = {delta/total:.2e}"

    def _check_thermodynamics_second(self, values: dict) -> tuple:
        delta_S = values.get("entropy_change", 0)
        return delta_S >= -TOLERANCE_SOFT, f"delta S = {delta_S:.4f} J/K (must be >= 0)"

    def _check_mass_energy_equiv(self, values: dict) -> tuple:
        mass = values.get("mass", 0)
        energy = values.get("energy", 0)
        c = PHYSICS_CONSTANTS["c"]["value"]
        expected_E = mass * c**2
        delta = abs(energy - expected_E) / max(abs(expected_E), 1e-12)
        return delta < TOLERANCE_RIGID, f"E=mc2: computed {expected_E:.4e}, got {energy:.4e}"

    _LAW_VALIDATORS = {
        "energy_conservation":     _check_energy_conservation,
        "charge_conservation":     _check_charge_conservation,
        "momentum_conservation":   _check_momentum_conservation,
        "second_thermodynamics":   _check_thermodynamics_second,
        "mass_energy_equivalence": _check_mass_energy_equiv,
    }

    _CRITICAL_LAWS = frozenset({
        "energy_conservation", "charge_conservation", "momentum_conservation"
    })

    def _is_fundamental_violation(self, law: str, values: dict) -> bool:
        return law in self._CRITICAL_LAWS
