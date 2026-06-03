"""Unrelated Association Innovation Engine.

Discovers innovations by connecting semantically distant but structurally similar concepts.
Uses structural pattern library to find analogies across domains.

Innovation score = semantic_distance x structural_similarity
"""
from __future__ import annotations
import json
import logging
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# Structural patterns that can be recognized across domains
STRUCTURAL_PATTERNS = {
    "exponential_decay": {
        "formula": "y = A * e^(-lambda * t)",
        "description": "Quantity decreases proportionally to its current value",
        "domains": ["physics", "biology", "economics", "chemistry", "psychology"],
        "examples": [
            "Radioactive decay", "RC circuit discharge", "Drug concentration in blood",
            "Memory forgetting curve", "Population decline", "Cooling (Newton's law)"
        ],
        "signature": "rate proportional to current value, negative direction"
    },
    "oscillation_stability": {
        "formula": "x(t) = A * cos(omega*t + phi) * e^(-gamma*t)",
        "description": "System oscillates around equilibrium with damping",
        "domains": ["physics", "engineering", "biology", "economics"],
        "examples": [
            "Spring-mass system", "Pendulum with friction", "Heart rhythm",
            "Business cycles", "Predator-prey dynamics", "Neural oscillations"
        ],
        "signature": "periodic motion with restoring force and energy loss"
    },
    "network_percolation": {
        "formula": "p_c = 1/<k> (critical threshold)",
        "description": "Phase transition in network connectivity at critical density",
        "domains": ["physics", "epidemiology", "social science", "materials"],
        "examples": [
            "Water seeping through rock", "Disease spreading", "Information cascades",
            "Composite conductivity", "Forest fire spread", "Social tipping points"
        ],
        "signature": "sudden global change from local connectivity threshold"
    },
    "energy_landscape": {
        "formula": "F = -grad(V), transitions at saddle points",
        "description": "System navigates potential energy surface, trapped in local minima",
        "domains": ["chemistry", "biology", "optimization", "economics"],
        "examples": [
            "Protein folding", "Chemical reactions", "Simulated annealing",
            "Market equilibria", "Neural network loss surfaces", "Evolutionary fitness"
        ],
        "signature": "multiple stable states, barriers between them, thermal activation"
    },
    "self_assembly": {
        "formula": "Local rules -> global order (no central control)",
        "description": "Ordered structure emerges from simple local interactions",
        "domains": ["chemistry", "biology", "robotics", "social science"],
        "examples": [
            "Crystal growth", "Cell membrane formation", "Ant colony nests",
            "Market prices from individual trades", "Language emergence", "Swarm robotics"
        ],
        "signature": "decentralized, local rules, emergent global pattern"
    },
    "feedback_amplification": {
        "formula": "gain = A / (1 - A*beta) for positive feedback beta",
        "description": "Output feeds back to input, amplifying signal",
        "domains": ["electronics", "biology", "economics", "climate"],
        "examples": [
            "Microphone squeal", "Cancer growth", "Compound interest",
            "Ice-albedo feedback", "Viral content spread", "Arms races"
        ],
        "signature": "small perturbation grows exponentially, runaway or saturation"
    },
    "selective_permeability": {
        "formula": "J = -D * dc/dx (Fick's law) with selectivity filter",
        "description": "Barrier allows some entities through but not others",
        "domains": ["biology", "chemistry", "economics", "computer science"],
        "examples": [
            "Cell membrane", "Kidney filtration", "Ion channels", "Blood-brain barrier",
            "Firewall rules", "Trade tariffs", "Selective attention"
        ],
        "signature": "boundary with differential passage based on properties"
    },
    "competitive_exclusion": {
        "formula": "dN_i/dt = r_i * N_i * (1 - sum(alpha_ij * N_j)/K)",
        "description": "Species competing for same resource cannot coexist",
        "domains": ["ecology", "economics", "evolution", "social science"],
        "examples": [
            "Two bird species same niche", "Market competition", "Language death",
            "Competing technologies", "Political parties", "Bacterial competition"
        ],
        "signature": "similar competitors, one wins, niche differentiation enables coexistence"
    },
    "emergent_hierarchy": {
        "formula": "Scale-free: P(k) ~ k^(-gamma)",
        "description": "Simple agents self-organize into hierarchical structure",
        "domains": ["biology", "social science", "computer science", "economics"],
        "examples": [
            "Ant colonies", "Neural circuits", "Corporate structures", "Internet topology",
            "City size distribution", "Food webs", "Modular software"
        ],
        "signature": "bottom-up organization, power-law distribution, nested modules"
    },
    "homeostasis": {
        "formula": "dx/dt = -k(x - x_setpoint) + disturbance",
        "description": "System maintains stable internal state despite external changes",
        "domains": ["biology", "engineering", "economics", "psychology"],
        "examples": [
            "Body temperature regulation", "Blood sugar control", "Thermostat",
            "Currency stabilization", "Emotional regulation", "Supply-demand balance"
        ],
        "signature": "setpoint, negative feedback, disturbance rejection"
    },
}


@dataclass
class ConceptNode:
    """A concept with its semantic embedding and domain."""
    id: str
    name: str
    domain: str
    description: str
    structural_features: List[str]  # Which structural patterns it exhibits
    semantic_vector: Optional[List[float]] = None  # Embedding if available
    created_at: float = field(default_factory=time.time)


@dataclass
class Association:
    """A discovered association between two distant concepts."""
    id: str
    concept_a: str                    # Name of concept A
    concept_b: str                    # Name of concept B
    semantic_distance: float          # 0.0 (same) to 1.0 (totally unrelated)
    structural_similarity: float      # 0.0 (different) to 1.0 (same pattern)
    shared_pattern: str               # Which structural pattern connects them
    innovation_score: float           # semantic_distance * structural_similarity
    analogy: str                      # Human-readable explanation
    created_at: float = field(default_factory=time.time)
    verified: bool = False


class UnrelatedAssociationEngine:
    """Discovers innovations by connecting semantically distant concepts.

    Process:
    1. Extract structural features from two concepts
    2. Find shared structural patterns
    3. Compute semantic distance (embedding or domain-based)
    4. Innovation score = semantic_distance * structural_similarity
    5. Generate analogy explaining the connection

    High scores = concepts that are semantically far but structurally similar
    = most likely to yield novel insights.
    """

    DB_PATH = Path(".zenith/associations.db")

    # Domain distance matrix (0 = same, 1 = maximally different)
    DOMAIN_DISTANCE = {
        ("physics", "biology"): 0.6,
        ("physics", "chemistry"): 0.3,
        ("physics", "economics"): 0.8,
        ("physics", "psychology"): 0.9,
        ("physics", "computer_science"): 0.7,
        ("biology", "economics"): 0.7,
        ("biology", "psychology"): 0.5,
        ("biology", "chemistry"): 0.3,
        ("biology", "computer_science"): 0.7,
        ("economics", "psychology"): 0.4,
        ("economics", "computer_science"): 0.6,
        ("psychology", "computer_science"): 0.8,
        ("chemistry", "economics"): 0.8,
        ("chemistry", "psychology"): 0.9,
        ("chemistry", "computer_science"): 0.7,
    }

    def __init__(self):
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.concepts: Dict[str, ConceptNode] = {}
        self._load_structural_patterns()

    def _init_db(self):
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    description TEXT,
                    structural_features TEXT,
                    created_at REAL
                );
                CREATE TABLE IF NOT EXISTS associations (
                    id TEXT PRIMARY KEY,
                    concept_a TEXT NOT NULL,
                    concept_b TEXT NOT NULL,
                    semantic_distance REAL,
                    structural_similarity REAL,
                    shared_pattern TEXT,
                    innovation_score REAL,
                    analogy TEXT,
                    created_at REAL,
                    verified INTEGER DEFAULT 0
                );
            """)

    def _load_structural_patterns(self):
        """Load structural patterns into memory for fast matching."""
        self._patterns = STRUCTURAL_PATTERNS

    def add_concept(self, name: str, domain: str, description: str,
                    structural_features: List[str] = None) -> ConceptNode:
        """Add a concept to the knowledge base.

        Args:
            name: Concept name (e.g., "radioactive decay")
            domain: Domain (e.g., "physics", "biology")
            description: What this concept is
            structural_features: Which structural patterns it exhibits
        """
        concept = ConceptNode(
            id=str(uuid.uuid4()),
            name=name,
            domain=domain,
            description=description,
            structural_features=structural_features or [],
        )
        self.concepts[name] = concept

        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO concepts (id, name, domain, description, structural_features, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (concept.id, name, domain, description,
                  json.dumps(structural_features or []), concept.created_at))

        return concept

    def find_associations(self, concept_name: str, top_k: int = 5) -> List[Association]:
        """Find the most innovative associations for a given concept.

        Returns associations sorted by innovation_score (highest first).
        """
        concept = self.concepts.get(concept_name)
        if not concept:
            # Try loading from DB
            concept = self._load_concept(concept_name)
            if not concept:
                return []

        associations = []
        for other_name, other in self.concepts.items():
            if other_name == concept_name:
                continue

            assoc = self._compute_association(concept, other)
            if assoc and assoc.innovation_score > 0.1:
                associations.append(assoc)

        # Sort by innovation score
        associations.sort(key=lambda a: a.innovation_score, reverse=True)

        # Store top results
        for assoc in associations[:top_k]:
            self._store_association(assoc)

        return associations[:top_k]

    def find_cross_domain_analogies(self, source_concept: str,
                                     target_domain: str) -> List[Association]:
        """Find analogies between a source concept and all concepts in a target domain.

        Useful for: "How is protein folding like market dynamics?"
        """
        source = self.concepts.get(source_concept)
        if not source:
            source = self._load_concept(source_concept)
            if not source:
                return []

        associations = []
        for name, concept in self.concepts.items():
            if concept.domain != target_domain:
                continue
            assoc = self._compute_association(source, concept)
            if assoc and assoc.structural_similarity > 0.3:
                associations.append(assoc)

        associations.sort(key=lambda a: a.innovation_score, reverse=True)
        return associations[:5]

    def _compute_association(self, a: ConceptNode, b: ConceptNode) -> Optional[Association]:
        """Compute association between two concepts."""
        # Find shared structural patterns
        shared = set(a.structural_features) & set(b.structural_features)
        if not shared:
            # Try fuzzy matching on patterns
            shared = self._fuzzy_pattern_match(a, b)
        if not shared:
            return None

        structural_sim = len(shared) / max(len(a.structural_features), len(b.structural_features), 1)

        # Semantic distance
        sem_dist = self._semantic_distance(a, b)

        # Innovation score
        innovation = sem_dist * structural_sim

        # Generate analogy
        pattern_name = list(shared)[0]
        analogy = self._generate_analogy(a, b, pattern_name)

        return Association(
            id=str(uuid.uuid4()),
            concept_a=a.name,
            concept_b=b.name,
            semantic_distance=sem_dist,
            structural_similarity=structural_sim,
            shared_pattern=pattern_name,
            innovation_score=innovation,
            analogy=analogy,
        )

    def _semantic_distance(self, a: ConceptNode, b: ConceptNode) -> float:
        """Compute semantic distance between two concepts.

        Uses domain distance matrix. Same domain = low distance.
        """
        if a.domain == b.domain:
            return 0.2  # Same domain, low distance

        key = tuple(sorted([a.domain, b.domain]))
        return self.DOMAIN_DISTANCE.get(key, 0.7)  # Default: fairly distant

    def _fuzzy_pattern_match(self, a: ConceptNode, b: ConceptNode) -> set:
        """Try to find shared patterns through description matching."""
        shared = set()
        a_desc = (a.description + " " + " ".join(a.structural_features)).lower()
        b_desc = (b.description + " " + " ".join(b.structural_features)).lower()

        for pattern_name, pattern in self._patterns.items():
            # Check if both descriptions mention pattern-related keywords
            sig_words = pattern["signature"].lower().split()
            a_matches = sum(1 for w in sig_words if w in a_desc)
            b_matches = sum(1 for w in sig_words if w in b_desc)
            if a_matches >= 2 and b_matches >= 2:
                shared.add(pattern_name)

        return shared

    def _generate_analogy(self, a: ConceptNode, b: ConceptNode, pattern: str) -> str:
        """Generate human-readable analogy explaining the connection."""
        pattern_info = self._patterns.get(pattern, {})
        pattern_desc = pattern_info.get("description", pattern)

        return (
            f"Both '{a.name}' ({a.domain}) and '{b.name}' ({b.domain}) "
            f"exhibit the '{pattern}' pattern: {pattern_desc}. "
            f"This structural similarity suggests that insights from one domain "
            f"may transfer to the other."
        )

    def _load_concept(self, name: str) -> Optional[ConceptNode]:
        """Load a concept from the database."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            row = conn.execute(
                "SELECT id, name, domain, description, structural_features, created_at FROM concepts WHERE name = ?",
                (name,)
            ).fetchone()
        if not row:
            return None
        concept = ConceptNode(
            id=row[0], name=row[1], domain=row[2], description=row[3],
            structural_features=json.loads(row[4]), created_at=row[5],
        )
        self.concepts[name] = concept
        return concept

    def _store_association(self, assoc: Association):
        """Store an association in the database."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO associations
                (id, concept_a, concept_b, semantic_distance, structural_similarity,
                 shared_pattern, innovation_score, analogy, created_at, verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (assoc.id, assoc.concept_a, assoc.concept_b, assoc.semantic_distance,
                  assoc.structural_similarity, assoc.shared_pattern, assoc.innovation_score,
                  assoc.analogy, assoc.created_at, int(assoc.verified)))

    def seed_basic_concepts(self):
        """Seed the knowledge base with fundamental concepts from multiple domains.

        Called once at startup to ensure there's always something to associate.
        """
        seeds = [
            # Physics
            ("radioactive decay", "physics", "Unstable atom emits radiation and transforms",
             ["exponential_decay"]),
            ("pendulum", "physics", "Object swings under gravity with restoring force",
             ["oscillation_stability"]),
            ("heat conduction", "physics", "Thermal energy flows from hot to cold regions",
             ["selective_permeability"]),
            ("phase transition", "physics", "Matter changes state at critical temperature",
             ["network_percolation"]),
            ("gravity", "physics", "Force of attraction between masses",
             ["feedback_amplification"]),

            # Biology
            ("population dynamics", "biology", "Species populations change through birth, death, competition",
             ["oscillation_stability", "competitive_exclusion"]),
            ("cell membrane", "biology", "Barrier controlling what enters and exits cell",
             ["selective_permeability"]),
            ("protein folding", "biology", "Polypeptide chain finds minimum energy 3D structure",
             ["energy_landscape"]),
            ("immune response", "biology", "Body detects and eliminates foreign substances",
             ["feedback_amplification", "homeostasis"]),
            ("neural plasticity", "biology", "Brain rewires connections based on experience",
             ["self_assembly", "homeostasis"]),
            ("epidemic spread", "biology", "Disease propagates through population contact network",
             ["network_percolation"]),

            # Chemistry
            ("chemical equilibrium", "chemistry", "Forward and reverse reaction rates equalize",
             ["homeostasis"]),
            ("crystal growth", "chemistry", "Atoms arrange into periodic lattice structure",
             ["self_assembly"]),
            ("catalysis", "chemistry", "Substance lowers activation energy of reaction",
             ["energy_landscape"]),
            ("osmosis", "chemistry", "Solvent moves through semipermeable membrane",
             ["selective_permeability"]),

            # Economics
            ("supply and demand", "economics", "Price adjusts until quantity supplied equals demanded",
             ["homeostasis", "oscillation_stability"]),
            ("market bubble", "economics", "Positive feedback drives prices far above fundamental value",
             ["feedback_amplification"]),
            ("network effects", "economics", "Product value increases with number of users",
             ["network_percolation", "feedback_amplification"]),
            ("creative destruction", "economics", "Innovation replaces old industries with new ones",
             ["competitive_exclusion"]),

            # Psychology
            ("classical conditioning", "psychology", "Neutral stimulus becomes associated with response",
             ["feedback_amplification"]),
            ("flow state", "psychology", "Optimal engagement when challenge matches skill",
             ["homeostasis"]),
            ("cognitive dissonance", "psychology", "Mental discomfort from conflicting beliefs",
             ["energy_landscape"]),
            ("habit formation", "psychology", "Repeated behavior becomes automatic through reinforcement",
             ["self_assembly", "feedback_amplification"]),

            # Computer Science
            ("cache invalidation", "computer_science", "Deciding when stored data is too old to use",
             ["homeostasis", "selective_permeability"]),
            ("load balancing", "computer_science", "Distributing work across multiple processors",
             ["self_assembly", "homeostasis"]),
            ("recursive algorithm", "computer_science", "Function calls itself with smaller input",
             ["emergent_hierarchy"]),
            ("distributed consensus", "computer_science", "Multiple nodes agree on shared state",
             ["network_percolation", "self_assembly"]),
        ]

        for name, domain, desc, features in seeds:
            if name not in self.concepts:
                self.add_concept(name, domain, desc, features)

        log.info(f"Seeded {len(seeds)} basic concepts across 6 domains")

    def get_stats(self) -> dict:
        """Return engine statistics."""
        with sqlite3.connect(str(self.DB_PATH)) as conn:
            concepts = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
            associations = conn.execute("SELECT COUNT(*) FROM associations").fetchone()[0]
            verified = conn.execute("SELECT COUNT(*) FROM associations WHERE verified = 1").fetchone()[0]

        return {
            "total_concepts": concepts,
            "total_associations": associations,
            "verified_associations": verified,
            "loaded_in_memory": len(self.concepts),
            "structural_patterns": len(self._patterns),
        }
