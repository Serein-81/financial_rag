---
name: tax-law-research
description: >
  This skill should be used when the user wants to "search tax regulations",
  "find latest tax laws", "look up tax policies", "check tax rates",
  "research tax compliance requirements", or "get current tax legal information".
  It uses real-time web search via Tavily to find current tax and legal information
  from authoritative government sources.
when_to_use: >
  Activate when the user asks about current tax rates, recent tax law changes,
  specific tax regulations, compliance deadlines, or any tax-related legal information
  that may have changed since the model's training data. NOT for general legal advice
  or internal company data analysis.
metadata:
  author: internal-legal-team
  version: "1.0"
  domain: legal
compatibility: |
  Requires: TAVILY_API_KEY configured in settings
  Depends on: MCP cloud_tool `search_web` or TavilyService
allowed-tools: Bash Read Write search_web
---

# Tax Law Research Skill

## Overview
Searches the web for current tax laws, regulations, rates, and policy changes using Tavily web search. Results are sourced from government and authoritative legal databases.

## Workflow

### Step 1: Understand the Query
Identify what the user needs:
- **Tax type**: Corporate income tax, VAT, personal income tax, stamp duty, etc.
- **Jurisdiction**: National (China), provincial, or specific city
- **Time relevance**: Current rates, recent changes, upcoming deadlines
- **Specific topic**: Deduction rules, exemption policies, filing requirements

If the query is vague, ask clarifying questions before searching.

### Step 2: Construct Search Queries
Build targeted Chinese-language search queries. Examples:

```
Search 1: "企业所得税 税率 2025 最新规定"
Search 2: "增值税 优惠政策 2025 国家税务总局"
Search 3: "个人所得税 专项附加扣除 最新标准"
Search 4: "{specific_tax_topic} 法规 2025"
```

Use the `search_web` MCP tool (or the fallback script) with each query.

### Step 3: Review and Synthesize Results
Review the search results:
- Prioritize results from `.gov.cn` domains (authoritative)
- Note the publication date of each result
- Cross-reference multiple sources for consistency
- **Always check the effective date** — tax laws change frequently

### Step 4: Present Findings
Format as a clear, structured response:

```text
## Tax Law Research Results

**Topic**: [Tax topic] | **Search Date**: [today]

### Current Status
- Rate/Requirement: [current value]
- Effective from: [date]
- Source: [URL]

### Recent Changes
- [Change description] — effective [date]
- Impact: [what this means]

### Key Deadlines
- [Deadline item]: [date]

### Caveats
- This information is from web search and may not reflect the most current changes
- Always verify with a qualified tax professional for binding advice
```

### Step 5: Handle Special Cases
- **Conflicting information**: Note the discrepancy and recommend verifying with the local tax bureau
- **No results found**: Broaden the search, try English keywords, or suggest the user contact tax authorities directly
- **Outdated information**: If search results are older than 6 months, flag them as potentially outdated

## Error Handling
- **Search API failure**: Retry once with simpler query. If still fails, inform the user that web search is temporarily unavailable
- **TAVILY_API_KEY not configured**: Inform the user that web search is not available and provide general tax knowledge
- **Rate limiting**: Wait before retrying; if persistent, suggest the user try again later

## Gotchas
- Chinese tax regulations can change at the start of each calendar year
- Local tax bureaus (省/市税务局) may have implementing rules that differ from national policy
- VAT rates vary by industry (e.g., 13% for goods, 9% for services, 6% for modern services)
- Small-scale taxpayers (小规模纳税人) have different rates and rules
- Always include "site:gov.cn" implicitly when searching Chinese regulations
- The `references/tax_terms.md` document provides reference for common Chinese tax terminology
