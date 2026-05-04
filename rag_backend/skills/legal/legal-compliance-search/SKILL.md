---
name: legal-compliance-search
description: >
  This skill should be used when the user wants to "search compliance regulations",
  "check legal requirements", "find relevant laws", "look up regulatory updates",
  "verify compliance obligations", "search registration requirements",
  "check business license needs", "find industry regulations",
  or "get compliance checklist for company registration".
when_to_use: >
  Activate when the user asks about legal/regulatory compliance, company registration
  requirements, industry-specific licensing, policy compliance, or regulatory frameworks.
  Uses real-time web search (Tavily) to find current regulations from government sources.
  NOT for contract review — that should use dedicated legal specialist tools instead.
metadata:
  author: internal-legal-team
  version: "2.0"
  domain: legal
compatibility: |
  Requires: python3
  Depends on: Tavily web search API (TAVILY_API_KEY configured in settings)
allowed-tools: Bash Read Write
---

# Legal Compliance Search Skill

## Overview
Searches for current legal and regulatory compliance information using real-time web search.
Results include company registration requirements, industry licenses, and compliance obligations
specific to the user's business profile.

The skill uses the **search_web** tool (Tavily) for real-time regulation searches, and the
**Enterprise Policy Matcher** for matching against the internal policy knowledge base.

## Workflow

### Step 1: Understand Business Context
Ask clarifying questions to establish the user's business profile. Be specific — the quality of results depends on the detail:

**Required context:**
- **Company type**: 有限责任公司 (LLC), 股份有限公司 (joint-stock), 外商独资企业 (WFOE), 合资企业 (JV), 个体工商户 (sole proprietor)
- **Industry/Sector**: Technology, finance, healthcare, manufacturing, education, food & beverage, e-commerce, etc.
- **Location**: Province and city of registration (e.g., "Beijing", "Shanghai", "Guangdong-Shenzhen")

**Additional context (helpful but not required):**
- **Company scale**: Small/medium/large, number of employees
- **Business scope**: What specific activities the company performs
- **Registration stage**: New registration, business scope change, annual review, etc.
- **Foreign investment**: Whether foreign shareholders are involved

If the user hasn't specified all required context, ask specific questions. Example:

> "To find the right compliance requirements, I need to know:
> 1. What type of company are you registering? (e.g., LLC, WFOE)
> 2. What industry are you in? (e.g., technology, finance)
> 3. Where are you located? (e.g., Beijing, Shanghai)"

### Step 2: Search Regulations via Web
Use the `search_web` tool to search for current regulations. Construct targeted search queries:

**For company registration:**
```
Search 1: "{company_type} registration requirements {location} 2025"
Search 2: "{industry} business license {location} requirements"
Search 3: "{industry} regulatory compliance China 2025"
```

**For compliance obligations:**
```
Search 1: "{industry} compliance requirements China 2025"
Search 2: "company registration process {location} steps documents"
Search 3: "{industry} license permit China regulations"
```

Review the search results and extract applicable regulations.

### Step 3: Cross-Reference with Internal Knowledge Base
Check the internal policy knowledge base (via Enterprise Policy Matcher tool) for matching policies.
Search with keywords relevant to the user's industry and business type.

Reference the background document `references/registration_requirements.md` for standard requirements
that don't change frequently (e.g., document checklists, registration steps).

### Step 4: Match Against Business Profile
Organize findings against the user's specific business context:

1. **Checklist format**: Create a structured compliance checklist
2. **Status markers**: For each requirement, determine if it appears to be:
   - ✅ Met — User has mentioned completing this
   - ⚠️ Review needed — Regulation likely applies, user should verify
   - ❌ Action needed — Clearly required but user hasn't mentioned it
   - ℹ️ Information — Optional but recommended
3. **Priority**: Label items as Critical / High / Medium / Low based on risk

### Step 5: Present Findings
Format as a structured compliance checklist:

```text
Compliance Checklist
====================
Company: [Type] | Industry: [Industry] | Location: [Location]

## Registration Requirements
1. [Requirement] — [Status] — [Details]
2. ...

## Licensing Requirements
1. [License name] — [Authority] — [Deadline] — [Risk: High]
2. ...

## Ongoing Compliance Obligations
1. [Obligation] — [Frequency] — [Deadline]

## Recommendations
1. [Action] — [Reason] — [Suggested timeline]
```

### Step 6: Caveats and Next Steps
Always include these disclaimers:
- "This information is based on web search results and may not reflect the most current regulations"
- "Regulations vary by location — check with local authorities for specific requirements"
- "Recommend consulting with a qualified legal professional for binding compliance advice"

Suggest concrete next actions with estimated timelines.

## Error Handling
- **No results found**: Try broader search terms, then suggest the user contact local authorities
- **Too many results**: Ask the user for more specific context to narrow down
- **Conflicting information**: Note the discrepancy and suggest verifying with the authority directly
- **Search timeout**: Fall back to the internal reference document, note that real-time data wasn't available

## Gotchas
- Regulations change frequently — always note the search date when presenting findings
- Location matters: Beijing, Shanghai, and Shenzhen often have additional local requirements
- The "Negative List" (外商投资负面清单) is critical for foreign-invested enterprises
- Small enterprises (< 50 employees) often have simplified compliance requirements
- For tax registration, always check with the local tax bureau (税务局) as procedures vary
- Never provide definitive legal opinions — always recommend consulting a lawyer for binding advice
- Social insurance (社保) and housing fund (公积金) registration deadlines are strict — missing them incurs penalties
- The `references/registration_requirements.md` document provides stable reference information that the web search supplements
