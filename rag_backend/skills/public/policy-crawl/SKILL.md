---
name: policy-crawl
description: >
  This skill should be used when the user wants to "crawl policies to local",
  "collect latest regulations", "sync tax policies from government websites",
  "update policy database", "fetch new policies from 国家税务总局",
  or "refresh policy knowledge base". It guides the Policy Notification Agent
  through crawling, storing, and processing government policy data.
when_to_use: >
  Activate when the user asks to collect, crawl, sync, or update policies
  from authoritative government sources (国家税务总局, 中国政府网, 财政部).
  Handles: trigger crawl → save to database → cross-reference with knowledge base
  → match against enterprise profiles → generate notifications.
  NOT for querying existing policies — use the policy search or match API.
metadata:
  author: internal-policy-team
  version: "1.1"
  domain: public
compatibility: |
  Requires: TAVILY_API_KEY (for web search), policy crawler service
  API: POST /api/v1/policy/collect (crawl), POST /api/v1/policy/sync (full pipeline)
  Agent API: POST /api/v1/policy-agent/status (health check)
allowed-tools: Bash Read Write search_web
---

# Policy Crawl Skill (政策通知智能体)

## Overview
Guides the **Policy Notification Agent** through the complete policy lifecycle:
1. Crawl policies from government sources
2. Save to local database
3. Match against enterprise profiles
4. Generate enterprise notifications
5. Report results

## Prerequisites
First, check if the Policy Notification Agent is healthy:
```bash
curl -X GET http://localhost:8000/api/v1/policy-agent/status
```

Expected response: `{"status": "healthy", "llm_available": true, ...}`

## Workflow

### Step 1: Confirm Crawl Parameters with User
Before crawling, confirm with the user:

- **Action**: Full sync or crawl only?
  - Full sync: crawl → save → match enterprises → generate notifications
  - Crawl only: just fetch and save policies
- **Keywords**: Specific tax/policy topics (e.g., "增值税", "小微企业", "高新技术企业")
- **Max per source**: How many policies per source (default 20)
- **Notify enterprises**: Automatically trigger matching after crawl? (default: yes)

Example confirmation:
> "I'll crawl the latest policies from government sources:
> 1. Fetch policies from 国家税务总局, 中国政府网, 财政部
> 2. Save new policies to the database
> 3. Cross-reference with existing knowledge
> 4. Match against enterprise profiles
> 5. Generate and push notifications
>
> Proceed? (yes/no)"

### Step 2: Trigger the Crawl
Execute the crawl. Two methods:

**Method A — Full pipeline (recommended):**
```bash
python scripts/crawl_policies.py --params <params.json>
```

**Params:**
```json
{
    "method": "sync",
    "max_per_source": 20,
    "notify_enterprises": true,
    "keywords": ["增值税", "企业所得税", "小微企业"],
    "api_base_url": "http://localhost:8000"
}
```

**Method B — Crawl only (no notifications):**
```bash
curl -X POST http://localhost:8000/api/v1/policy/collect \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["增值税", "企业所得税"], "max_per_source": 20}'
```

### Step 3: Cross-Reference Results
After crawling, cross-reference new policies against the existing knowledge base:
- Search the knowledge base for related policies on the same topics
- Identify any conflicts or updates between old and new policies
- Note policies that override or amend existing ones

### Step 4: Match Against Enterprises (if enabled)
If notifications are enabled, the system will automatically:
- Match new policies against registered enterprise profiles
- Generate personalized notification content
- Push notifications via SSE stream

You can also manually trigger matching:
```bash
curl -X POST http://localhost:8000/api/v1/policy-agent/match \
  -H "Content-Type: application/json" \
  -d '{"policy_id": "<policy_id>", "use_llm": true}'
```

### Step 5: Report Results
Present a structured summary:
```text
## Policy Crawl Results

**Agent**: Policy Notification Agent | **Time**: [timestamp]

### Crawl Summary
- Source: 国家税务总局 — [N] policies
- Source: 中国政府网 — [N] policies
- Source: 财政部 — [N] policies
- Total new: [N] | Updated: [N] | Errors: [N]

### Enterprise Matching
- Enterprises matched: [N]
- Notifications triggered: [N]
- High-priority alerts: [N]

### Next Steps
- New policies are available in the policy knowledge base
- Enterprise notifications have been queued for delivery
- Check `/api/v1/policy/notifications/{enterprise_id}` for details
```

## Error Handling
- **Crawl failure**: Retry once. If specific sources fail, report which sources succeeded and which failed
- **Empty results**: Try broader keywords. If still empty, government websites may be unavailable — try again later
- **LLM Agent unavailable**: If `/policy-agent/status` shows `llm_available: false`, rule-based matching will be used as fallback
- **Partial crawl**: Some sources may succeed while others fail — always report per-source status

## Gotchas
- Government websites enforce rate limiting — the crawler handles this automatically
- `robots.txt` is respected for all crawled sources
- Crawling all 3 sources takes approximately 30-60 seconds
- Duplicate detection uses title+source_name — identical policies won't be saved twice
- New policies are automatically embedded for vector search when saved
- The Policy Notification Agent processes policies via `PolicyNotificationService` singleton
- For scheduled daily/weekly crawling, use `POST /api/v1/policy/scheduler/config`
- Sample data (20 realistic Chinese tax policies) is available when online sources are unreachable
