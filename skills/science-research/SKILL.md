---
name: science-research
description: Use when designing experiments, analyzing scientific data, reviewing literature, testing hypotheses, or conducting any scientific research
---

# Science Research

## Tools

`search` — academic databases, Google Scholar, arXiv, PubMed
`scrape` — extract full papers, supplementary materials, datasets
`fetch` — retrieve specific resources, API data
`code_exec` — statistical analysis, data visualization, modeling
`recall` — check existing knowledge and prior findings

## Methodology

### Literature Review
- Search with specific terms + "study" OR "research" OR "trial".
- Prioritize recent publications (last 5 years) unless historical context needed.
- Scrape full abstracts and methodology sections.
- Track: authors, year, sample size, methods, key findings, limitations.
- Identify gaps in existing research.

### Hypothesis Formation
- State the hypothesis clearly: "X causes Y under condition Z."
- Define independent, dependent, and control variables.
- Specify expected direction and magnitude of effect.
- Identify potential confounders upfront.

### Experimental Design
- Choose design: randomized controlled, observational, case-control, crossover.
- Calculate required sample size for desired power (use code_exec).
- Define primary and secondary endpoints.
- Plan statistical analysis before collecting data.
- Pre-register the hypothesis if possible.

### Data Analysis
- Use code_exec for: descriptive statistics, hypothesis testing, regression, ANOVA.
- Check assumptions: normality (Shapiro-Wilk), homoscedasticity (Levene's).
- Report effect sizes alongside p-values.
- Visualize data appropriately (scatter, bar, box, heatmap).
- Note: correlation ≠ causation always.

### Paper Writing Structure
1. Abstract — question, methods, key finding, significance
2. Introduction — background, gap, hypothesis
3. Methods — reproducible, detailed
4. Results — data first, interpretation second
5. Discussion — implications, limitations, future work

## Statistical Reference

- p < 0.05 — standard significance threshold
- Cohen's d: 0.2 small, 0.5 medium, 0.8 large
- R²: proportion of variance explained
- Confidence intervals preferred over p-values alone
- Bonferroni correction for multiple comparisons

## Quality Checks

- Is the sample representative?
- Are confounders controlled?
- Is the analysis appropriate for the data type?
- Are limitations acknowledged?
- Can the study be replicated from the methods section?
