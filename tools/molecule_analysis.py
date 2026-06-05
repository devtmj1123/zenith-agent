"""Molecule analysis tool using RDKit."""

import json
import sys
from pathlib import Path

def analyze_molecule(smiles: str) -> dict:
    """Analyze a molecule for drug-likeness properties."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, Lipinski, TPSA
        
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"error": f"Invalid SMILES: {smiles}"}
        
        # Calculate properties
        mw = round(Descriptors.MolWt(mol), 2)
        logp = round(Descriptors.MolLogP(mol), 2)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        tpsa_val = round(TPSA.TPSA(mol), 2)
        rotatable = Lipinski.NumRotatableBonds(mol)
        
        # Lipinski Rule of Five
        lipinski_violations = 0
        if mw > 500: lipinski_violations += 1
        if logp > 5: lipinski_violations += 1
        if hbd > 5: lipinski_violations += 1
        if hba > 10: lipinski_violations += 1
        
        # Drug-likeness assessment
        drug_like = lipinski_violations <= 1
        
        return {
            "smiles": smiles,
            "name": GetMolName(mol),
            "molecular_weight": mw,
            "logp": logp,
            "hbd": hbd,
            "hba": hba,
            "tpsa": tpsa_val,
            "rotatable_bonds": rotatable,
            "lipinski_violations": lipinski_violations,
            "lipinski_passes": drug_like,
            "drug_likeness": "good" if drug_like else "poor"
        }
    except ImportError:
        return {"error": "RDKit not installed. Run: pip install rdkit"}
    except Exception as e:
        return {"error": str(e)}

def GetMolName(mol):
    """Try to get common name from molecule."""
    # Common drug names mapping (simplified)
    smiles_to_name = {
        "CC(=O)Oc1ccccc1C(=O)O": "Aspirin (Acetylsalicylic Acid)",
        "CC(=O)Nc1ccc(O)cc1": "Acetaminophen (Paracetamol)",
        "CC(=O)Nc1ccc(cc1)O": "Acetaminophen (Paracetamol)",
        "CC12CCC3C(CCC4CC(O)CCC34)C1CCC2O": "Testosterone",
        "c1ccc2c(c1)[nH]c1ccccc12": "Carbazole",
        "O=C(O)c1ccccc1O": "Salicylic Acid",
        "CC(=O)Oc1ccccc1C(=O)Oc1ccccc1C(=O)O": "Aspirin Dimer",
    }
    return smiles_to_name.get(mol.ToSmiles(), "Unknown")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        smiles = sys.argv[1]
        result = analyze_molecule(smiles)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python molecule_analysis.py <SMILES>")
