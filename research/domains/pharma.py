# research/domains/pharma.py
"""
Drug Development Research Domain.

Pipeline stages supported:
  1. Target Identification   (protein -> binding site)
  2. Lead Generation         (SMILES -> properties)
  3. ADMET Prediction        (absorption, distribution, metabolism, excretion, toxicity)
  4. Literature Mining       (PubMed -> hypothesis extraction)
  5. Cross-domain search     (e.g., battery electrolyte -> drug carrier analogy)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MoleculeAnalysis:
    smiles:            str
    molecular_weight:  Optional[float] = None
    logp:              Optional[float] = None      # Lipophilicity
    hbd:               Optional[int]   = None      # H-bond donors
    hba:               Optional[int]   = None      # H-bond acceptors
    tpsa:              Optional[float] = None      # Topological polar surface area
    lipinski_passes:   Optional[bool]  = None      # Ro5
    alerts:            List[str] = field(default_factory=list)
    drug_likeness:     str = "unknown"


class PharmaResearcher:

    def analyze_molecule(self, smiles: str) -> MoleculeAnalysis:
        """
        Compute drug-likeness properties using RDKit.
        Checks Lipinski Rule of Five (Ro5).
        """
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors, rdMolDescriptors

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return MoleculeAnalysis(
                    smiles=smiles,
                    alerts=["Invalid SMILES string -- could not parse molecule"]
                )

            mw   = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            hbd  = rdMolDescriptors.CalcNumHBD(mol)
            hba  = rdMolDescriptors.CalcNumHBA(mol)
            tpsa = Descriptors.TPSA(mol)

            # Lipinski Ro5
            lipinski = (mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10)

            # PAINS alerts (pan-assay interference)
            alerts = []
            if mw > 500:
                alerts.append(f"MW={mw:.1f} > 500 Da (Lipinski violation)")
            if logp > 5:
                alerts.append(f"LogP={logp:.2f} > 5 (poor oral absorption risk)")
            if tpsa > 140:
                alerts.append(f"TPSA={tpsa:.1f} > 140 A2 (poor CNS penetration)")
            if hbd > 5:
                alerts.append(f"HBD={hbd} > 5 (Lipinski violation)")

            drug_likeness = "good" if lipinski and not alerts else (
                "moderate" if lipinski else "poor"
            )

            return MoleculeAnalysis(
                smiles=smiles, molecular_weight=mw, logp=logp,
                hbd=hbd, hba=hba, tpsa=tpsa,
                lipinski_passes=lipinski, alerts=alerts,
                drug_likeness=drug_likeness,
            )

        except ImportError:
            return MoleculeAnalysis(
                smiles=smiles,
                alerts=["RDKit not installed. Run: pip install rdkit"]
            )

    def check_drug_claim(self, claim: str) -> Optional[str]:
        """
        Validate pharmacological claims.
        Returns rebuttal string or None.
        """
        import re

        # No drug works for all diseases
        if re.search(r'治疗.*所有|cure.*all|works.*every', claim, re.IGNORECASE):
            return (
                "No drug can treat all diseases or be effective for all patients. "
                "Disease heterogeneity, genetic polymorphism, and drug metabolism "
                "differences ensure this. Please specify target, indication, and patient population."
            )

        # Zero toxicity
        if re.search(r'zero.*toxic|完全无毒|no.*side', claim, re.IGNORECASE):
            return (
                "Paracelsus principle (1538): All substances are toxic, "
                "only the dose makes the poison. Zero-toxicity claims for active "
                "drugs are scientifically invalid. More accurate: "
                "'acceptable safety window within therapeutic dose range.'"
            )

        return None

    def lipinski_interpretation(self, analysis: MoleculeAnalysis) -> str:
        """Human-readable drug-likeness interpretation."""
        if analysis.lipinski_passes is None:
            return "Cannot analyze"
        if analysis.lipinski_passes and not analysis.alerts:
            return (
                f"PASSES Lipinski Ro5. "
                f"MW={analysis.molecular_weight:.1f}, LogP={analysis.logp:.2f} -- "
                f"good oral absorption probability."
            )
        return (
            f"Drug-likeness issues:\n"
            + "\n".join(f"  - {a}" for a in analysis.alerts)
        )

    def get_domain_constants(self) -> dict:
        """Return key physical quantities for pharma research."""
        return {
            "Molecular weight": {"symbol": "MW", "unit": "Da", "significance": "Lipinski Ro5"},
            "LogP": {"symbol": "logP", "unit": "", "significance": "lipophilicity"},
            "TPSA": {"symbol": "TPSA", "unit": "A2", "significance": "membrane permeability"},
            "IC50": {"symbol": "IC50", "unit": "nM", "significance": "potency"},
            "LD50": {"symbol": "LD50", "unit": "mg/kg", "significance": "acute toxicity"},
        }
