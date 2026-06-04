"""Unit Standardizer — converts mixed units to SI for comparison.

Stub implementation. Expand as needed.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class StandardizedValue:
    value: float
    unit: str
    original: str


# Common conversions to SI base units
_CONVERSIONS = {
    # Energy
    "ev": 1.602176634e-19,
    "kev": 1.602176634e-16,
    "mev": 1.602176634e-13,
    "kwh": 3.6e6,
    "wh": 3600,
    "kcal": 4184,
    "cal": 4.184,
    "btu": 1055.06,
    # Mass
    "mg": 1e-6,
    "g": 1e-3,
    "kg": 1,
    "lb": 0.453592,
    "oz": 0.0283495,
    "amu": 1.66054e-27,
    # Length
    "nm": 1e-9,
    "um": 1e-6,
    "mm": 1e-3,
    "cm": 1e-2,
    "m": 1,
    "km": 1e3,
    "ang": 1e-10,
    # Time
    "ns": 1e-9,
    "us": 1e-6,
    "ms": 1e-3,
    "s": 1,
    "min": 60,
    "h": 3600,
    # Temperature (offset handled separately)
    "k": 1,
    # Pressure
    "pa": 1,
    "kpa": 1e3,
    "mpa": 1e6,
    "gpa": 1e9,
    "atm": 101325,
    "bar": 1e5,
    "psi": 6894.76,
    "torr": 133.322,
    # Concentration
    "m": 1,      # mol/L
    "mm": 1e-3,
    "um": 1e-6,
    "nm": 1e-9,
    "ppm": 1e-6,
    "ppb": 1e-9,
}


class UnitStandardizer:
    """Converts values with mixed units to SI base units."""

    def standardize(self, value: float, unit: str) -> StandardizedValue:
        """Convert a value+unit to SI base unit."""
        unit_lower = unit.lower().strip()

        # Direct match
        if unit_lower in _CONVERSIONS:
            return StandardizedValue(
                value=value * _CONVERSIONS[unit_lower],
                unit=self._si_base(unit_lower),
                original=f"{value} {unit}",
            )

        # Try stripping common prefixes
        for prefix, factor in [("kilo", 1e3), ("mega", 1e6), ("giga", 1e9),
                                ("milli", 1e-3), ("micro", 1e-6), ("nano", 1e-9)]:
            if unit_lower.startswith(prefix[:3]):
                base = unit_lower[len(prefix[:3]):]
                if base in _CONVERSIONS:
                    return StandardizedValue(
                        value=value * factor * _CONVERSIONS[base],
                        unit=self._si_base(base),
                        original=f"{value} {unit}",
                    )

        # No conversion found — return as-is
        return StandardizedValue(value=value, unit=unit, original=f"{value} {unit}")

    def _si_base(self, unit: str) -> str:
        """Return the SI base unit symbol for a given unit category."""
        energy = {"ev", "kev", "mev", "kwh", "wh", "kcal", "cal", "btu"}
        mass = {"mg", "g", "kg", "lb", "oz", "amu"}
        length = {"nm", "um", "mm", "cm", "m", "km", "ang"}
        time = {"ns", "us", "ms", "s", "min", "h"}
        pressure = {"pa", "kpa", "mpa", "gpa", "atm", "bar", "psi", "torr"}

        if unit in energy:
            return "J"
        if unit in mass:
            return "kg"
        if unit in length:
            return "m"
        if unit in time:
            return "s"
        if unit in pressure:
            return "Pa"
        return unit
