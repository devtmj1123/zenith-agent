---
name: research
description: Use when finding information, learning about topics, comparing options, gathering data, or answering questions that need web sources
---

# Research

## Tools

`search` — web search (DuckDuckGo, returns snippets)
`scrape` — full article extraction (Firecrawl → markdown, falls back to fetch)
`fetch` — raw URL content extraction (HTML → text)
`recall` — check existing knowledge before searching

## Methodology

### Phase 1: Scope
- Clarify the research question. One sentence, specific.
- Check `recall` for existing knowledge on this topic.
- Identify what type of answer is needed: factual, comparative, analytical, or exploratory.

### Phase 2: Broad Survey
- `search` with 2-3 different query formulations.
- Scan snippets to identify the most relevant sources.
- Note which sources warrant deep reading.

### Phase 3: Deep Extraction
- `scrape` the top 2-3 sources for full content.
- If scrape fails, `fetch` as fallback.
- Extract specific data points, not just summaries.
- Record exact quotes with source URLs for claims.

### Phase 4: Synthesis
- Cross-reference claims across at least 2 sources.
- Separate established facts from opinions and speculation.
- Identify contradictions and note which source is more authoritative.
- Present findings structured by subtopic, not by source.

### Phase 5: Gaps and Follow-up
- Note what remains unclear or unverified.
- Suggest follow-up searches if needed.
- If data is insufficient, say so explicitly.

## Output Format

- Lead with the direct answer to the research question.
- Support with evidence and source URLs.
- End with confidence level and open questions.
- Never present a single source as definitive for important claims.

## Edge Cases

- For recent events (last 24h), search with date filters.
- For academic topics, prefer `.edu`, `.org`, peer-reviewed sources.
- For controversial topics, present multiple perspectives with sources.
- For technical topics, look for official documentation first.
