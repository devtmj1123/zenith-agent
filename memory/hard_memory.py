from __future__ import annotations
from types import MappingProxyType
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# PHYSICS CONSTANTS — CODATA 2018 (immutable, read-only)
# dim = (mass_M, length_L, time_T, current_I)  [mol, kelvin, candela omitted]
# ═══════════════════════════════════════════════════════════════

_CONSTANTS = {
    # ── Fundamental ──────────────────────────────────────────
    "c":          {"value": 299_792_458,            "unit": "m/s",        "dim": (0,1,-1,0),  "desc": "Speed of light in vacuum"},
    "h":          {"value": 6.626_070_15e-34,       "unit": "J*s",        "dim": (1,2,-1,0),  "desc": "Planck constant"},
    "hbar":       {"value": 1.054_571_817e-34,      "unit": "J*s",        "dim": (1,2,-1,0),  "desc": "Reduced Planck constant"},
    "G":          {"value": 6.674_30e-11,           "unit": "m3/(kg*s2)", "dim": (-1,3,-2,0), "desc": "Newtonian gravitational constant"},
    "alpha":      {"value": 7.297_352_569_3e-3,     "unit": "1",          "dim": (0,0,0,0),   "desc": "Fine-structure constant"},

    # ── Electromagnetic ──────────────────────────────────────
    "e":          {"value": 1.602_176_634e-19,      "unit": "C",          "dim": (0,0,1,1),   "desc": "Elementary charge"},
    "mu_B":       {"value": 9.274_010_078_3e-24,    "unit": "J/T",        "dim": (1,2,-2,-1), "desc": "Bohr magneton"},
    "mu_N":       {"value": 5.050_783_746_1e-27,    "unit": "J/T",        "dim": (1,2,-2,-1), "desc": "Nuclear magneton"},
    "Phi_0":      {"value": 2.067_833_848e-15,      "unit": "Wb",         "dim": (1,2,-2,-1), "desc": "Magnetic flux quantum"},
    "G_0":        {"value": 7.748_091_729e-5,       "unit": "S",          "dim": (-1,-2,3,2), "desc": "Conductance quantum"},
    "R_K":        {"value": 25_812.807_45,           "unit": "ohm",        "dim": (1,2,-3,-2), "desc": "Von Klitzing constant"},
    "eps_0":      {"value": 8.854_187_812_8e-12,    "unit": "F/m",        "dim": (-1,-3,4,2), "desc": "Vacuum permittivity"},
    "mu_0":       {"value": 1.256_637_062_12e-6,    "unit": "N/A2",       "dim": (1,1,-2,-2), "desc": "Vacuum permeability"},
    "Z_0":        {"value": 376.730_313_668,        "unit": "ohm",        "dim": (1,2,-3,-2), "desc": "Impedance of free space"},

    # ── Atomic and Nuclear ───────────────────────────────────
    "m_e":        {"value": 9.109_383_701_5e-31,    "unit": "kg",         "dim": (1,0,0,0),   "desc": "Electron mass"},
    "m_p":        {"value": 1.672_621_923_69e-27,   "unit": "kg",         "dim": (1,0,0,0),   "desc": "Proton mass"},
    "m_n":        {"value": 1.674_927_498_04e-27,   "unit": "kg",         "dim": (1,0,0,0),   "desc": "Neutron mass"},
    "m_u":        {"value": 1.660_539_066_60e-27,   "unit": "kg",         "dim": (1,0,0,0),   "desc": "Atomic mass unit"},
    "a_0":        {"value": 5.291_772_109_03e-11,   "unit": "m",          "dim": (0,1,0,0),   "desc": "Bohr radius"},
    "R_inf":      {"value": 10_973_731.568_160,     "unit": "m-1",        "dim": (0,-1,0,0),  "desc": "Rydberg constant"},
    "sigma_T":    {"value": 6.652_458_732_1e-29,    "unit": "m2",         "dim": (0,2,0,0),   "desc": "Thomson cross-section"},
    "lambda_C":   {"value": 2.426_310_238_67e-12,   "unit": "m",          "dim": (0,1,0,0),   "desc": "Compton wavelength"},
    "r_e":        {"value": 2.817_940_326_2e-15,    "unit": "m",          "dim": (0,1,0,0),   "desc": "Classical electron radius"},

    # ── Thermodynamic and Statistical ────────────────────────
    "k_B":        {"value": 1.380_649e-23,          "unit": "J/K",        "dim": (1,2,-2,0),  "desc": "Boltzmann constant"},
    "N_A":        {"value": 6.022_140_76e23,        "unit": "mol-1",      "dim": (0,0,0,0),   "desc": "Avogadro constant"},
    "R":          {"value": 8.314_462_618,          "unit": "J/(mol*K)",  "dim": (1,2,-2,0),  "desc": "Gas constant"},
    "sigma_SB":   {"value": 5.670_374_419e-8,       "unit": "W/(m2*K4)",  "dim": (1,0,-3,0),  "desc": "Stefan-Boltzmann constant"},
    "b_wien":     {"value": 2.897_771_955e-3,       "unit": "m*K",        "dim": (0,1,1,0),   "desc": "Wien wavelength displacement constant"},
    "c_1":        {"value": 3.741_771_852e-16,      "unit": "W*m2",       "dim": (1,2,-3,0),  "desc": "First radiation constant"},
    "c_2":        {"value": 1.438_776_877_5e-2,     "unit": "m*K",        "dim": (0,1,1,0),   "desc": "Second radiation constant"},

    # ── Chemistry and Electrochemistry ───────────────────────
    "F":          {"value": 96_485.332_12,          "unit": "C/mol",      "dim": (0,0,1,1),   "desc": "Faraday constant"},
    "eV":         {"value": 1.602_176_634e-19,      "unit": "J",          "dim": (1,2,-2,0),  "desc": "Electron volt"},

    # ── Astronomical and Reference ───────────────────────────
    "g_n":        {"value": 9.806_65,               "unit": "m/s2",       "dim": (0,1,-2,0),  "desc": "Standard gravity"},
    "atm":        {"value": 101_325,                "unit": "Pa",         "dim": (1,-1,-2,0), "desc": "Standard atmosphere"},
    "L_sun":      {"value": 3.828e26,               "unit": "W",          "dim": (1,2,-3,0),  "desc": "Solar luminosity"},
    "M_sun":      {"value": 1.989e30,               "unit": "kg",         "dim": (1,0,0,0),   "desc": "Solar mass"},
    "R_sun":      {"value": 6.957e8,                "unit": "m",          "dim": (0,1,0,0),   "desc": "Solar radius"},
    "AU":         {"value": 1.495_978_707e11,       "unit": "m",          "dim": (0,1,0,0),   "desc": "Astronomical unit"},
    "ly":         {"value": 9.460_730_472_580_8e15, "unit": "m",          "dim": (0,1,0,0),   "desc": "Light year"},
    "pc":         {"value": 3.085_677_581_491_367_3e16,"unit": "m",       "dim": (0,1,0,0),   "desc": "Parsec"},
}


# ═══════════════════════════════════════════════════════════════
# PHYSICAL LAWS — structural relationships
# INVARIANT rules for validating reasoning.
# ═══════════════════════════════════════════════════════════════

PHYSICAL_LAWS = {
    # ── Conservation Laws ────────────────────────────────────
    "conservation_energy": {
        "statement": "Energy cannot be created or destroyed, only transformed.",
        "equation": "E_total = constant  |  dE/dt = 0 (isolated system)",
        "domain": "universal",
        "check": "Verify energy_in == energy_out for any process.",
    },
    "conservation_momentum": {
        "statement": "Total momentum of an isolated system is constant.",
        "equation": "p_total = sum(m_i * v_i) = constant  |  F_net = dp/dt",
        "domain": "mechanics",
        "check": "Verify sum(p_before) == sum(p_after) for collisions/explosions.",
    },
    "conservation_charge": {
        "statement": "Electric charge is conserved in any process.",
        "equation": "Q_total = constant  |  sum(Q_in) = sum(Q_out)",
        "domain": "electromagnetism",
        "check": "Verify total charge before == after in any reaction.",
    },
    "conservation_angular_momentum": {
        "statement": "Angular momentum is constant when no external torque.",
        "equation": "L = I*w = constant  |  tau_ext = dL/dt",
        "domain": "mechanics",
        "check": "Verify L_before == L_after when tau_ext = 0.",
    },
    "conservation_mass_energy": {
        "statement": "Mass and energy are equivalent; total mass-energy is conserved.",
        "equation": "E = mc2  |  delta_E = delta_m * c2",
        "domain": "relativity",
        "check": "In nuclear/chemical reactions: mass_defect * c2 = energy_released.",
    },

    # ── Newton's Laws ────────────────────────────────────────
    "newton_first": {
        "statement": "An object remains at rest or in uniform motion unless acted upon by a force.",
        "equation": "F_net = 0  ->  v = constant",
        "domain": "mechanics",
        "check": "If no net force, velocity must not change.",
    },
    "newton_second": {
        "statement": "Force equals mass times acceleration.",
        "equation": "F = m*a  |  F = dp/dt",
        "domain": "mechanics",
        "check": "Verify F/m == a for any object.",
    },
    "newton_third": {
        "statement": "Every action has an equal and opposite reaction.",
        "equation": "F_12 = -F_21",
        "domain": "mechanics",
        "check": "Forces between two objects must be equal and opposite.",
    },
    "newton_gravitation": {
        "statement": "Gravitational force between two masses.",
        "equation": "F = G*m1*m2/r2",
        "domain": "gravitation",
        "check": "Verify gravitational force uses correct G, masses, distance.",
    },

    # ── Thermodynamics ───────────────────────────────────────
    "thermo_first": {
        "statement": "Internal energy change equals heat added minus work done by system.",
        "equation": "delta_U = Q - W",
        "domain": "thermodynamics",
        "check": "Energy balance: Q_in = delta_U + W_out.",
    },
    "thermo_second": {
        "statement": "Entropy of an isolated system never decreases.",
        "equation": "delta_S >= 0  |  S = k_B * ln(Omega)",
        "domain": "thermodynamics",
        "check": "Verify entropy change is non-negative for isolated systems.",
    },
    "thermo_third": {
        "statement": "Entropy approaches zero as temperature approaches absolute zero.",
        "equation": "lim(T->0) S = 0",
        "domain": "thermodynamics",
        "check": "At T=0, perfect crystal has S=0.",
    },
    "ideal_gas": {
        "statement": "Pressure times volume equals nRT for ideal gases.",
        "equation": "PV = nRT  |  PV = Nk_BT",
        "domain": "thermodynamics",
        "check": "Verify P*V == n*R*T for gas calculations.",
    },

    # ── Electromagnetism (Maxwell) ───────────────────────────
    "gauss_electric": {
        "statement": "Electric flux through closed surface = enclosed charge / eps_0.",
        "equation": "integral(E*dA) = Q_enc/eps_0",
        "domain": "electromagnetism",
        "check": "Verify electric flux matches enclosed charge.",
    },
    "gauss_magnetic": {
        "statement": "No magnetic monopoles; magnetic flux through closed surface is zero.",
        "equation": "integral(B*dA) = 0",
        "domain": "electromagnetism",
        "check": "Magnetic field lines always form closed loops.",
    },
    "faraday_law": {
        "statement": "Changing magnetic flux induces EMF.",
        "equation": "EMF = -d(Phi_B)/dt",
        "domain": "electromagnetism",
        "check": "Verify induced EMF matches rate of flux change.",
    },
    "ampere_law": {
        "statement": "Magnetic field around closed loop = current + displacement current.",
        "equation": "integral(B*dl) = mu_0*(I + eps_0*d(Phi_E)/dt)",
        "domain": "electromagnetism",
        "check": "Verify magnetic field circulation matches current.",
    },
    "coulomb": {
        "statement": "Electrostatic force between two charges.",
        "equation": "F = k_e*q1*q2/r2  |  k_e = 1/(4*pi*eps_0)",
        "domain": "electromagnetism",
        "check": "Verify force uses correct constant and distance.",
    },
    "ohm": {
        "statement": "Voltage = current times resistance.",
        "equation": "V = I*R",
        "domain": "circuits",
        "check": "Verify V, I, R relationship in circuit analysis.",
    },

    # ── Quantum Mechanics ────────────────────────────────────
    "schrodinger": {
        "statement": "Time evolution of quantum state.",
        "equation": "i*hbar*d(psi)/dt = H_hat*psi",
        "domain": "quantum",
        "check": "Wave function evolution must satisfy this equation.",
    },
    "heisenberg_uncertainty": {
        "statement": "Cannot simultaneously know exact position and momentum.",
        "equation": "delta_x * delta_p >= hbar/2",
        "domain": "quantum",
        "check": "Verify uncertainty product >= hbar/2.",
    },
    "de_broglie": {
        "statement": "Matter has wave-like properties.",
        "equation": "lambda = h/p = h/(m*v)",
        "domain": "quantum",
        "check": "Verify wavelength from momentum.",
    },
    "photoelectric": {
        "statement": "Photon energy = work function + kinetic energy of electron.",
        "equation": "E_photon = h*v = phi + KE_max",
        "domain": "quantum",
        "check": "Verify energy balance in photoelectric effect.",
    },
    "bohr_frequency": {
        "statement": "Photon energy equals energy difference between levels.",
        "equation": "h*v = E_2 - E_1",
        "domain": "quantum",
        "check": "Verify photon energy matches level transition.",
    },

    # ── Relativity ───────────────────────────────────────────
    "special_relativity_time": {
        "statement": "Time dilation for moving objects.",
        "equation": "delta_t' = delta_t/gamma  |  gamma = 1/sqrt(1 - v2/c2)",
        "domain": "relativity",
        "check": "Verify time dilation factor gamma >= 1.",
    },
    "special_relativity_length": {
        "statement": "Length contraction for moving objects.",
        "equation": "L' = L/gamma",
        "domain": "relativity",
        "check": "Verify contracted length <= rest length.",
    },
    "special_relativity_mass": {
        "statement": "Relativistic mass increases with velocity.",
        "equation": "m' = gamma*m_0",
        "domain": "relativity",
        "check": "Verify relativistic mass >= rest mass.",
    },
    "mass_energy": {
        "statement": "Mass-energy equivalence.",
        "equation": "E = mc2  |  E2 = (pc)2 + (mc2)2",
        "domain": "relativity",
        "check": "Verify mass-energy conversion uses c2.",
    },
    "general_relativity": {
        "statement": "Mass-energy curves spacetime; objects follow geodesics.",
        "equation": "G_uv + Lambda*g_uv = (8*pi*G/c4)*T_uv",
        "domain": "relativity",
        "check": "Spacetime curvature sourced by stress-energy tensor.",
    },

    # ── Waves and Optics ─────────────────────────────────────
    "wave_equation": {
        "statement": "Wave speed = frequency times wavelength.",
        "equation": "v = f*lambda",
        "domain": "waves",
        "check": "Verify v == f * lambda for any wave.",
    },
    "snell_law": {
        "statement": "Refraction at interface between media.",
        "equation": "n1*sin(theta1) = n2*sin(theta2)",
        "domain": "optics",
        "check": "Verify refraction angles and indices.",
    },
    "diffraction_limit": {
        "statement": "Minimum resolvable angle for optical aperture.",
        "equation": "theta_min = 1.22*lambda/D",
        "domain": "optics",
        "check": "Verify diffraction limit for given aperture.",
    },

    # ── Fluid Mechanics ──────────────────────────────────────
    "bernoulli": {
        "statement": "Total pressure is constant along streamline.",
        "equation": "P + 0.5*rho*v2 + rho*g*h = constant",
        "domain": "fluids",
        "check": "Verify pressure + dynamic + hydrostatic = constant.",
    },
    "continuity": {
        "statement": "Mass flow rate is constant in incompressible flow.",
        "equation": "A1*v1 = A2*v2",
        "domain": "fluids",
        "check": "Verify A*v is constant along pipe.",
    },
    "archimedes": {
        "statement": "Buoyant force = weight of displaced fluid.",
        "equation": "F_b = rho_fluid * V_displaced * g",
        "domain": "fluids",
        "check": "Verify buoyancy from displaced volume.",
    },

    # ── Nuclear and Particle ─────────────────────────────────
    "radioactive_decay": {
        "statement": "Activity decreases exponentially.",
        "equation": "N(t) = N_0*e^(-lambda*t)  |  T_half = ln(2)/lambda",
        "domain": "nuclear",
        "check": "Verify half-life and decay constant relationship.",
    },
    "mass_defect": {
        "statement": "Binding energy from mass difference.",
        "equation": "E_b = delta_m*c2  |  delta_m = Z*m_p + N*m_n - m_nucleus",
        "domain": "nuclear",
        "check": "Verify binding energy from constituent masses.",
    },
}


PHYSICS_CONSTANTS: MappingProxyType = MappingProxyType(_CONSTANTS)
PHYSICAL_LAWS_MAP: MappingProxyType = MappingProxyType(PHYSICAL_LAWS)

TOLERANCE_RIGID = 1e-6
TOLERANCE_SOFT  = 1e-2


def get_constant(name: str) -> dict:
    if name not in PHYSICS_CONSTANTS:
        raise KeyError(f"Unknown physics constant: {name}. Known: {list(PHYSICS_CONSTANTS.keys())}")
    return PHYSICS_CONSTANTS[name]


def get_law(name: str) -> dict:
    if name not in PHYSICAL_LAWS:
        raise KeyError(f"Unknown physical law: {name}. Known: {list(PHYSICAL_LAWS.keys())}")
    return PHYSICAL_LAWS[name]


def get_si_dimension(unit_str: str) -> Optional[tuple]:
    for name, data in PHYSICS_CONSTANTS.items():
        if data["unit"] == unit_str:
            return data["dim"]
    return None


def get_laws_for_domain(domain: str) -> list:
    return [law for law in PHYSICAL_LAWS.values() if law["domain"] == domain]
