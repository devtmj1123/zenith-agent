---
name: research
description: Use when finding information, learning about topics, comparing options, gathering data, or answering questions that need web sources
---

# Research — MANDATORY WORKFLOW

**You MUST follow this workflow for ANY research task. NO EXCEPTIONS.**

## Tools

`search` — web search (DuckDuckGo, returns snippets)
`scrape` — full article extraction (markdown)
`fetch` — raw URL content extraction (HTML → text)
`recall` — check existing knowledge before searching

## MANDATORY STEPS

### Step 1: Search (REQUIRED)
- Call `search` with 2-3 DIFFERENT query formulations
- NEVER skip this step
- NEVER write from LLM knowledge alone
- Example: `search({query: "quantum computing applications 2024"})`

### Step 2: Extract (REQUIRED)
- Call `scrape` on top 2-3 most relevant URLs from search results
- If scrape fails, call `fetch` as fallback
- Get FULL article content, not just snippets
- Example: `scrape({url: "https://example.com/article"})`

### Step 3: Synthesize (REQUIRED)
- Cross-reference claims across at least 2 sources
- Separate established facts from opinions
- Present findings with source URLs

### Step 4: Cite (REQUIRED)
- Include URL for EVERY claim
- If no source found, say "No reliable source found"
- NEVER make up citations

## Output Format

- Lead with direct answer
- Support with evidence and source URLs
- End with confidence level
- Note gaps and open questions

## RED FLAGS — STOP if you catch yourself:

- "Studies show..." without actual search results
- "According to research..." without citing URLs
- Writing from memory without searching first
- Making up statistics or data
- Claiming sources exist without verifying

**ALL OF THESE MEAN: Go back to Step 1 and SEARCH.**

## Example Workflow

User: "Write about quantum computing applications"

1. `search({query: "quantum computing applications 2024"})`
2. `search({query: "quantum computing real world use cases"})`
3. `scrape({url: "https://example.com/quantum-apps"})`
4. `scrape({url: "https://another-source.com/quantum"})`
5. Synthesize findings with citations
6. Present with source URLs
