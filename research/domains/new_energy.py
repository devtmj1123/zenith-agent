# research/domains/new_energy.py
"""
New Energy Research Domain.
Covers: Battery electrochemistry, Nuclear Fusion, Flux-Gain field.

Key physical quantities tracked:
  - Debye length L_D (electrolyte screening)
  - Activation energy E_a (reaction kinetics)
  - Lawson criterion n*tau*E (fusion ignition)
  - Energy density (Wh/kg, Wh/L)
  - Coulombic efficiency
  - Thermal runaway threshold
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BatteryAnalysis:
    material:         str
    energy_density_wh_kg: Optional[float]
    coulombic_efficiency: Optional[float]
    cycle_life:       Optional[int]
    debye_length_nm:  Optional[float]
    activation_energy_ev: Optional[float]
    thermal_runaway_temp_c: Optional[float]
    literature_sources: List[str] = None


@dataclass
class FusionAnalysis:
    confinement_type:  str         # tokamak | stellarator | ICF | other
    temperature_kev:   Optional[float]
    density_m3:        Optional[float]
    confinement_time_s: Optional[float]
    lawson_product:    Optional[float]    # n * tau * T
    q_factor:          Optional[float]   # energy output / input
    literature_sources: List[str] = None


class NewEnergyResearcher:

    # Lawson criterion for D-T fusion
    LAWSON_DT = 3e21  # n*T*T > 3e21 keV*s/m3

    # Theoretical max energy density (Li-S theoretical)
    LI_S_THEORETICAL_WH_KG = 2600

    def analyze_battery_claim(
        self, material: str, claimed_energy_density: float
    ) -> dict:
        """
        Validate battery energy density claim against known limits.
        Returns analysis with rebuttal if claim exceeds theoretical max.
        """
        results = {"material": material, "claimed": claimed_energy_density}

        theoretical_limits = {
            "li-ion":   387,    # Wh/kg theoretical max (LiCoO2)
            "li-s":     2600,   # Wh/kg theoretical
            "li-air":   11400,  # Wh/kg theoretical (but impractical)
            "solid-state": 500, # Wh/kg practical expectation
            "sodium-ion": 300,  # Wh/kg practical
            "flow":     70,     # Wh/kg typical
        }

        for battery_type, limit in theoretical_limits.items():
            if battery_type in material.lower():
                if claimed_energy_density > limit:
                    results["verdict"] = "EXCEEDS_THEORETICAL_LIMIT"
                    results["theoretical_max"] = limit
                    results["rebuttal"] = (
                        f"{material} theoretical energy density limit is ~{limit} Wh/kg. "
                        f"Claimed {claimed_energy_density} Wh/kg exceeds known thermodynamic limits. "
                        f"This may be measurement error, different test conditions, or needs recalculation."
                    )
                else:
                    results["verdict"] = "WITHIN_THEORETICAL_LIMITS"
                    results["margin_pct"] = round(
                        (limit - claimed_energy_density) / limit * 100, 1
                    )
                break

        return results

    def compute_debye_length(
        self,
        temperature_k: float,
        concentration_mol_L: float,
        charge_number: int = 1,
        relative_permittivity: float = 80.0,  # water at 25C
    ) -> float:
        """
        L_D = sqrt(eps_0 * eps_r * k_B * T / (2 * N_A * e^2 * I))
        Returns Debye length in nanometers.
        """
        try:
            from memory.hard_memory import PHYSICS_CONSTANTS
            eps_0 = PHYSICS_CONSTANTS["eps_0"]["value"]
            k_B   = PHYSICS_CONSTANTS["k_B"]["value"]
            e     = PHYSICS_CONSTANTS["e"]["value"]
            N_A   = PHYSICS_CONSTANTS["N_A"]["value"]
        except (ImportError, KeyError):
            # Fallback constants
            eps_0 = 8.8541878128e-12
            k_B   = 1.380649e-23
            e     = 1.602176634e-19
            N_A   = 6.02214076e23

        # Ionic strength (mol/m3)
        I = 0.5 * concentration_mol_L * 1000 * (charge_number ** 2)

        eps = eps_0 * relative_permittivity
        L_D = math.sqrt(eps * k_B * temperature_k / (2 * N_A * (e**2) * I))
        return L_D * 1e9  # Convert to nanometers

    def check_fusion_lawson(
        self,
        density_m3: float,
        confinement_s: float,
        temperature_kev: float,
    ) -> dict:
        """
        Check if fusion conditions meet Lawson criterion.
        Lawson for D-T: n*T*T > 3e21 keV*s/m3
        """
        product = density_m3 * confinement_s * temperature_kev
        meets = product >= self.LAWSON_DT
        ratio = product / self.LAWSON_DT

        return {
            "n_tau_T": product,
            "lawson_criterion": self.LAWSON_DT,
            "ratio": ratio,
            "meets_ignition": meets,
            "interpretation": (
                f"{'MEETS' if meets else 'DOES NOT MEET'} Lawson ignition criterion. "
                f"n*t*T = {product:.2e} keV*s/m3 "
                f"({'exceeds' if meets else 'below'} threshold by {ratio:.2f}x)"
            ),
        }

    def get_domain_constants(self) -> dict:
        """Return key physical quantities for new energy research."""
        return {
            "Debye length": {"symbol": "L_D", "unit": "nm", "significance": "electrolyte screening"},
            "Activation energy": {"symbol": "E_a", "unit": "eV", "significance": "reaction kinetics"},
            "Energy density": {"symbol": "E_d", "unit": "Wh/kg", "significance": "battery performance"},
            "Lawson product": {"symbol": "n*T*T", "unit": "keV*s/m3", "significance": "fusion ignition"},
            "Coulombic efficiency": {"symbol": "CE", "unit": "%", "significance": "battery cycle life"},
        }
