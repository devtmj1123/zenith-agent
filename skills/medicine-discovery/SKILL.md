---
name: medicine-discovery
description: Use when analyzing drug interactions, molecular structures, clinical data, pharmacokinetics, or any pharmaceutical and medical research task
---

# Medicine Discovery

## Tools

`search` — medical databases, PubMed, clinical trials
`scrape` — extract full papers, drug monographs, clinical reports
`fetch` — retrieve specific medical resources
`code_exec` — molecular analysis, statistical calculations, data processing
`recall` — check existing medical knowledge

## Methodology

### Drug Information Lookup
- Search DrugBank, PubChem, or FDA databases for compound data.
- Scrape drug monographs for complete pharmacokinetic profiles.
- Record: mechanism of action, half-life, metabolism pathway, contraindications.

### Drug Interaction Analysis
- Identify all compounds involved.
- Search interaction databases (Drugs.com, Medscape, FDA labels).
- Classify interaction severity: minor, moderate, major, contraindicated.
- Note the mechanism: pharmacokinetic (CYP450, transporters) or pharmacodynamic (additive, antagonistic).
- Provide clinical significance and recommended actions.

### Molecular Analysis
- Use code_exec for SMILES parsing, molecular weight calculation, LogP estimation.
- Search for structure-activity relationships (SAR) in literature.
- Compare molecular structures against known active compounds.

### Clinical Data Review
- Search ClinicalTrials.gov for relevant studies.
- Extract endpoints, sample size, efficacy results, adverse events.
- Assess study quality: randomization, blinding, dropout rates.
- Note statistical significance vs clinical significance.

## Safety Rules

- Always recommend consulting a healthcare professional for treatment decisions.
- Never provide dosage recommendations without explicit physician context.
- Flag when data is from animal studies vs human trials.
- Distinguish between approved indications and off-label use.
- Note when information may be outdated (check publication dates).

## Sources Priority

1. FDA/EMA approved labeling (highest authority)
2. Peer-reviewed clinical trials (PubMed)
3. Drug interaction databases (DrugBank, Drugs.com)
4. Medical textbooks and guidelines
5. Case reports and observational studies (lowest authority)
