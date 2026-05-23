from __future__ import annotations
from types import MappingProxyType
from typing import Optional

_CONSTANTS = {
    "c":          {"value": 299_792_458,       "unit": "m/s",   "dim": (0,1,-1,0), "desc": "Speed of light"},
    "h":          {"value": 6.626_070_15e-34,  "unit": "J·s",   "dim": (1,2,-1,0), "desc": "Planck constant"},
    "hbar":       {"value": 1.054_571_817e-34, "unit": "J·s",   "dim": (1,2,-1,0), "desc": "Reduced Planck"},
    "k_B":        {"value": 1.380_649e-23,     "unit": "J/K",   "dim": (1,2,-2,0), "desc": "Boltzmann constant"},
    "e":          {"value": 1.602_176_634e-19, "unit": "C",     "dim": (0,0,1,1),  "desc": "Elementary charge"},
    "m_e":        {"value": 9.109_383_701_5e-31,"unit": "kg",   "dim": (1,0,0,0),  "desc": "Electron mass"},
    "m_p":        {"value": 1.672_621_923_69e-27,"unit":"kg",   "dim": (1,0,0,0),  "desc": "Proton mass"},
    "N_A":        {"value": 6.022_140_76e23,   "unit": "mol⁻¹", "dim": (0,0,0,0),  "desc": "Avogadro constant"},
    "eps_0":      {"value": 8.854_187_812_8e-12,"unit": "F/m",  "dim": (-1,-3,4,2),"desc": "Vacuum permittivity"},
    "mu_0":       {"value": 1.256_637_062_12e-6,"unit": "N/A²", "dim": (1,1,-2,-2),"desc": "Vacuum permeability"},
    "G":          {"value": 6.674_30e-11,      "unit": "m³/(kg·s²)","dim":(-1,3,-2,0),"desc":"Gravitational constant"},
    "R":          {"value": 8.314_462_618,     "unit": "J/(mol·K)","dim":(1,2,-2,0),"desc": "Gas constant"},
    "sigma_SB":   {"value": 5.670_374_419e-8,  "unit": "W/(m²·K⁴)","dim":(1,0,-3,0),"desc": "Stefan-Boltzmann"},
    "F":          {"value": 96_485.332_12,     "unit": "C/mol", "dim": (0,0,1,1),  "desc": "Faraday constant"},
}

PHYSICS_CONSTANTS: MappingProxyType = MappingProxyType(_CONSTANTS)

TOLERANCE_RIGID = 1e-6
TOLERANCE_SOFT  = 1e-2


def get_constant(name: str) -> dict:
    if name not in PHYSICS_CONSTANTS:
        raise KeyError(f"Unknown physics constant: {name}. Known: {list(PHYSICS_CONSTANTS.keys())}")
    return PHYSICS_CONSTANTS[name]


def get_si_dimension(unit_str: str) -> Optional[tuple]:
    for name, data in PHYSICS_CONSTANTS.items():
        if data["unit"] == unit_str:
            return data["dim"]
    return None
