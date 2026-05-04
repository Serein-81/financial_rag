---
name: enterprise-profile
description: >
  This skill should be used when the user wants to "build enterprise profile",
  "create company profile for tax matching", "analyze enterprise tax profile",
  "match enterprise against tax policies", "find applicable tax benefits",
  "check enterprise eligibility for tax incentives",
  or "generate enterprise compliance profile".
when_to_use: >
  Activate when the user needs to build or update an enterprise profile for
  tax policy matching. This skill collects enterprise characteristics (industry,
  region, scale, tax types, revenue, employees) and cross-references them against
  tax policies to identify applicable benefits, compliance obligations, and risks.
  NOT for one-off tax calculations — use the tax specialist directly for that.
metadata:
  author: internal-tax-policy-team
  version: "1.0"
  domain: public
compatibility: |
  Requires: TenantSettings (industry, region, scale, tax_types)
  API: GET /api/v1/tenant-settings/me (current tenant profile)
  API: POST /api/v1/policy/match (enterprise-policy matching)
  Service: PolicyRetrievalService.match_enterprise_policies()
allowed-tools: Bash Read Write search_web get_current_time_and_context
---

# Enterprise Tax Profile & Policy Matching Skill

## Overview
Builds a structured enterprise profile from available enterprise data and
cross-references it against tax policies to identify:
- Applicable tax benefits and incentives
- Compliance obligations and deadlines
- Risk areas needing attention
- Recommendations for tax optimization

## The Enterprise Profile Dimensions

The profile captures 6 key dimensions used for policy matching:

| Dimension | Examples | Source |
|-----------|----------|--------|
| **Industry** (行业) | 制造业, 信息技术, 金融, 医疗, 教育 | TenantSettings.industry |
| **Region** (地区) | 北京, 上海, 广东深圳, 海南 | TenantSettings.region |
| **Scale** (规模) | 大型, 中型, 小型, 微型 | TenantSettings.scale |
| **Tax Types** (税种) | 增值税, 企业所得税, 个人所得税 | TenantSettings.tax_types |
| **Business Scope** (经营范围) | 软件开发, 咨询服务, 贸易 | TenantSettings / user input |
| **Special Status** (特殊资质) | 高新技术企业, 小微企业, 软件企业, 集成电路 | User input or knowledge base |

## Workflow

### Step 1: Gather Enterprise Data
Collect the enterprise profile from available sources:

**Source A — Tenant Settings (recommended):**
Check the tenant's existing settings for industry, region, scale, and tax types.
```bash
curl -X GET http://localhost:8000/api/v1/tenant-settings/me \
  -H "Authorization: Bearer {token}"
```

**Source B — User input:**
Ask the user for any missing information:
- What industry does the enterprise operate in?
- What region/location?
- What is the enterprise scale (employee count, revenue)?
- Does it have any special qualifications (高新技术企业, 软件企业, etc.)?
- What are the main business activities?

### Step 2: Build Structured Profile
Combine all data into a structured enterprise profile:

```json
{
  "enterprise_id": "tenant_001",
  "name": "某某科技有限公司",
  "industry": "信息技术",
  "region": "广东深圳",
  "scale": "中型",
  "tax_types": ["增值税", "企业所得税"],
  "keywords": ["软件开发", "高新技术", "研发投入"],
  "business_scope": "计算机软件技术开发、技术咨询、技术服务",
  "special_qualifications": ["高新技术企业"],
  "estimated_revenue": "5000万-1亿元",
  "employee_count": "200-500人"
}
```

### Step 3: Match Against Tax Policies
Use the profile to find matching tax policies:

**Method A — Policy matching API:**
```bash
curl -X POST http://localhost:8000/api/v1/policy/match \
  -H "Content-Type: application/json" \
  -d '{
    "enterprise_profile": {
      "industry": "信息技术",
      "region": "广东深圳",
      "scale": "中型",
      "tax_types": ["增值税", "企业所得税"]
    }
  }'
```

**Method B — Keyword search in policy database:**
Search for policies matching the enterprise's industry, region, and tax types.
```bash
python scripts/match_policies.py --params <params.json>
```

### Step 4: Analyze Results
For each matched policy, determine:

1. **Eligibility**: Does the enterprise clearly qualify?
2. **Requirements**: What conditions must be met?
3. **Benefits**: What tax reduction or exemption is available?
4. **Deadlines**: When must action be taken?
5. **Risk**: What happens if requirements aren't met?

### Step 5: Present Compliance Profile
Format the results as a structured compliance profile:

```text
## Enterprise Tax Compliance Profile

**Company**: [Name] | **Industry**: [Industry] | **Region**: [Region]
**Generated**: [Date]

### Applicable Tax Benefits
| Policy | Benefit | Eligibility | Deadline | Status |
|--------|---------|-------------|----------|--------|
| 高新技术企业所得税优惠 | 15%税率(减10%) | ✅ 符合 | 每年汇算清缴 | 待申请 |
| 研发费用加计扣除 | 100%加计扣除 | ✅ 有研发投入 | 每年汇算清缴 | 需备查 |
| 小微企业减免 | 应纳税所得额减免 | ❌ 规模超标 | — | 不适用 |

### Compliance Obligations
- [Obligation] — [Frequency] — [Deadline] — [Status]

### Risk Alerts
- [Risk description] — [Severity] — [Recommended action]

### Recommended Actions
1. [Action] — [Priority] — [Expected benefit]
```

## Error Handling
- **No tenant settings found**: Ask the user to provide enterprise details directly
- **Policy API unavailable**: Use web search (search_web) to find applicable policies
- **Ambiguous match**: When eligibility is unclear, note the uncertainty and recommend consulting a tax professional
- **Incomplete profile**: Flag missing dimensions that would affect match accuracy

## References
- `references/policy_dimensions.md`: How enterprise dimensions map to policy matching criteria

## Gotchas
- Enterprise profile data comes from TenantSettings — if settings are incomplete, ask the user
- Policy matching is only as good as the profile data; more dimensions = better matches
- Special qualifications (高新技术企业, 软件企业) require valid certification — don't assume eligibility
- Regional policies (海南自贸港, 粤港澳大湾区) have strict location requirements
- Enterprise scale thresholds change periodically — check the latest regulations
- The profile should be refreshed periodically as the enterprise's situation changes
- Matched policies are informational; always verify with a tax professional before acting
- The `references/policy_dimensions.md` document provides the dimension-to-policy mapping reference
