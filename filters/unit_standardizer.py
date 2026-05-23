from __future__ import annotations
from typing import Tuple

from core.types import DimensionMissingError

SI_UNITS: dict = {
    "kg": (1,0,0,0), "g": (1,0,0,0),
    "m":  (0,1,0,0), "cm":(0,1,0,0), "mm":(0,1,0,0),
    "s":  (0,0,1,0), "ms":(0,0,1,0), "min":(0,0,1,0), "h":(0,0,1,0),
    "A":  (0,0,0,1), "mA":(0,0,0,1),
    "J":   (1,2,-2,0), "kJ":  (1,2,-2,0), "eV": (1,2,-2,0),
    "W":   (1,2,-3,0), "kW":  (1,2,-3,0),
    "N":   (1,1,-2,0),
    "Pa":  (1,-1,-2,0), "kPa": (1,-1,-2,0), "MPa":(1,-1,-2,0), "bar":(1,-1,-2,0),
    "V":   (1,2,-3,-1), "mV":  (1,2,-3,-1),
    "Hz":  (0,0,-1,0), "kHz": (0,0,-1,0), "MHz":(0,0,-1,0),
    "C":   (0,0,1,1), "mC":  (0,0,1,1),
    "ohm": (1,2,-3,-2), "kohm": (1,2,-3,-2),
    "F":   (-1,-2,4,2), "uF":  (-1,-2,4,2), "pF": (-1,-2,4,2),
    "H":   (1,2,-2,-2),
    "T":   (1,0,-2,-1),
    "Wb":  (1,2,-2,-1),
    "mol": (0,0,0,0),
    "K":   (0,0,0,0),
    "cd":  (0,0,0,0),
    "L_D": (0,1,0,0),
    "E_a": (1,2,-2,0),
    "Wh":  (1,2,-2,0),
    "Ah":  (0,0,1,1),
}

PREFIXES = {
    "k": 1e3, "M": 1e6, "G": 1e9, "m": 1e-3,
    "u": 1e-6, "n": 1e-9, "p": 1e-12,
}


class UnitStandardizer:
    def parse(self, expression: str) -> Tuple[tuple, float]:
        expr = expression.strip()

        if expr in SI_UNITS:
            return SI_UNITS[expr], 1.0

        for prefix, scale in PREFIXES.items():
            if expr.startswith(prefix):
                base = expr[len(prefix):]
                if base in SI_UNITS:
                    return SI_UNITS[base], scale

        if "/" in expr or "*" in expr:
            return self._parse_compound(expr)

        raise DimensionMissingError(
            f"[CONTEXT_DIMENSION_MISSING] Cannot parse unit: '{expression}'. "
            f"Transferring to Agent B for meta-metadata validation."
        )

    def _parse_compound(self, expr: str) -> Tuple[tuple, float]:
        parts = expr.replace("*", "*").split("/")
        if len(parts) != 2:
            raise DimensionMissingError(f"[CONTEXT_DIMENSION_MISSING] Complex compound: {expr}")

        num_dim, num_scale = self.parse(parts[0].strip())
        den_dim, den_scale = self.parse(parts[1].strip())
        result_dim = tuple(n - d for n, d in zip(num_dim, den_dim))
        return result_dim, num_scale / den_scale

    def validate_consistency(self, expr_a: str, expr_b: str) -> bool:
        try:
            dim_a, _ = self.parse(expr_a)
            dim_b, _ = self.parse(expr_b)
            return dim_a == dim_b
        except DimensionMissingError:
            return False
