---
name: corporate-tax-check
description: >
  This skill should be used when the user wants to "calculate corporate income tax",
  "企业所得税计算", "算企业所得税", "所得税应缴多少", "企业所得税合规检查",
  "小微企业所得税优惠", "高新技术企业税率", "企业税务合规审查".
  It calculates the exact corporate income tax payable, applies preferential rates
  for small/high-tech enterprises, and checks compliance.
when_to_use: >
  Activate when the user needs a deterministic corporate income tax (企业所得税) calculation
  or wants to verify their enterprise's tax compliance status.
  The skill: identifies enterprise type → queries financial data → computes tax → checks compliance.
  NOT for VAT questions — use the vat-calculation skill instead.
metadata:
  author: internal-tax-team
  version: "1.0"
  domain: tax
compatibility: |
  Tools: tax_calculator, query_user_financial_data, tax_compliance_checker
allowed-tools: Bash Read
---

# Corporate Income Tax Check Skill

## Overview
Calculate enterprise income tax (企业所得税) with automatic preferential rate detection,
then run a compliance check and generate an actionable summary.

Use tools for all numeric computations — never guess tax amounts.

## Workflow

### Step 1: Identify Enterprise Type
Ask the user or infer from context:

| Type | Chinese | Default Rate | Preferential Rate |
|------|---------|-------------|-------------------|
| Standard | 一般企业 | 25% | — |
| Small/low-profit | 小型微利企业 | 25% | 5% (≤300万) |
| High-tech | 高新技术企业 | 15% | — |
| Non-profit preferred | 符合条件非营利 | 0% | — |

### Step 2: Get Taxable Income
Option A — User provides the taxable income directly → proceed to Step 3.
Option B — User wants to calculate from financials → call `query_user_financial_data`:

```json
{
  "user_id": "<from context>",
  "tenant_id": "<from context>",
  "fiscal_year": <year or null>
}
```

Extract `taxable_income` and `corporate_tax_rate` from the result.

### Step 3: Calculate Tax
Call `tax_calculator` with `tax_type="corporate_income_tax"`:

```json
{
  "tax_type": "corporate_income_tax",
  "taxable_income": <value>,
  "tax_rate": <applicable rate>,
  "tenant_id": "<tenant_id>"
}
```

Or `calculate_tax` for more detailed small-enterprise logic:

```json
{
  "tax_type": "corporate_income",
  "taxable_amount": <value>,
  "tax_rate": 0.25,
  "is_small_enterprise": <true/false>
}
```

### Step 4: Compliance Check
Always call `tax_compliance_checker` to catch issues:

```json
{
  "tax_data": {
    "corporate_tax": {
      "rate": <applied_rate>,
      "income": <taxable_income>
    }
  },
  "tenant_id": "<tenant_id>"
}
```

### Step 5: Present Result

```
企业所得税计算结果
==================
企业类型：    {enterprise_type}
应纳税所得额：¥{taxable_income:,.2f}
适用税率：    {rate*100:.0f}%
应缴所得税：  ¥{tax_payable:,.2f}

合规检查：{compliance_level}（{compliance_score}分）
{issues_if_any}

节税提示：{opportunities}
```

## Error Handling
- No financial data in DB → ask user to provide taxable income manually or use `financial-data-entry` skill first.
- Taxable income is negative (亏损) → inform user: "本期亏损可在未来5年内弥补，无需缴纳企业所得税。"

## Gotchas
- 小型微利企业优惠：应纳税所得额≤300万时适用5%，超过部分仍按25%（非一刀切）。
- 高新技术企业需持有认定证书，每三年重新认定。提示用户核实资质有效期。
- 研发费用加计扣除最高100%，若用户未提及，主动询问是否有研发支出。
