---
name: vat-calculation
description: >
  This skill should be used when the user wants to "calculate VAT", "compute value-added tax",
  "算增值税", "计算应缴增值税", "增值税计算", "帮我算增值税", "VAT计算",
  "进项销项税额计算", "增值税应纳税额", "抵扣后增值税".
  It collects sales amount, VAT rate, and input tax, then computes the exact payable VAT
  with a risk assessment and filing recommendations.
when_to_use: >
  Activate when the user needs a deterministic VAT calculation, not a general policy explanation.
  The skill: collects parameters → calls tax_calculator tool for exact figures → validates compliance
  → returns a structured summary with payable amount and risk flags.
  NOT for general questions about VAT policy — answer those directly from domain knowledge.
metadata:
  author: internal-tax-team
  version: "1.0"
  domain: tax
compatibility: |
  Requires: python3
  Tools: tax_calculator, tax_compliance_checker, execute_python
allowed-tools: Bash Read
---

# VAT Calculation Skill

## Overview
Guide the user through a precise, auditable VAT (增值税) calculation.
Follow the **collect → calculate → validate → report** workflow.

All calculations use the `tax_calculator` tool — **never compute tax amounts from memory**.

## Workflow

### Step 1: Collect Required Parameters
Ask the user (or extract from context):

| Parameter | Chinese | Required | Default | Validation |
|-----------|---------|----------|---------|-----------|
| `sales_amount` | 含税销售额 | ✅ | — | > 0 |
| `vat_rate` | 增值税率 | ✅ | 0.13 | one of 0.13 / 0.09 / 0.06 / 0.03 / 0.01 |
| `input_vat` | 进项税额 | optional | 0.0 | >= 0 |

If the user provides a rate as a percentage (e.g. "13%"), convert to decimal (0.13).
If the user says "一般纳税人" without specifying a rate, default to 0.13.
If the user says "小规模纳税人", use 0.03.

### Step 2: Calculate Using Tool
Call `tax_calculator` with `tax_type="vat"`:

```json
{
  "tax_type": "vat",
  "sales_amount": <collected value>,
  "vat_rate": <collected value>,
  "input_vat": <collected value or 0>
}
```

The tool returns:
- `output_vat` — 销项税额
- `input_vat` — 进项税额 (echo)
- `payable_vat` — 应缴增值税（= 销项 - 进项）
- `risk_issues` — 合规风险提示列表
- `recommendations` — 建议列表

### Step 3: Compliance Check (if risk_issues non-empty)
If the tool returns any `risk_issues`, call `tax_compliance_checker` for a full compliance report:

```json
{
  "tax_data": {
    "vat": {
      "rate": <vat_rate>,
      "output_vat": <output_vat>,
      "input_vat": <input_vat>
    }
  },
  "tenant_id": "<tenant_id from context>"
}
```

### Step 4: Present Result
Show a structured summary:

```
增值税计算结果
==============
销售额（含税）：¥{sales_amount:,.2f}
增值税率：      {vat_rate*100:.0f}%
销项税额：      ¥{output_vat:,.2f}
进项税额：      ¥{input_vat:,.2f}
────────────────────────────────
应缴增值税：    ¥{payable_vat:,.2f}

{risk_summary}
{recommendations}

免责声明：以上计算仅供参考，具体以税务机关认定为准。
```

If `payable_vat < 0`, show: "存在留抵税额 ¥{abs(payable_vat):,.2f}，可结转下期抵扣。"

### Step 5: Follow-up
Ask if the user wants to:
- 计算企业所得税（推荐使用 `corporate-tax-check` 技能）
- 查询最新增值税政策（调用 search_web）
- 导出计算明细（用 execute_python 格式化并输出 CSV）

## Error Handling
- **Invalid rate**: If user provides a rate not in {0.01, 0.03, 0.06, 0.09, 0.13}, warn them:
  "该税率不在法定范围内（1%/3%/6%/9%/13%），请确认业务类型。"
- **sales_amount = 0**: Ask "请提供具体的销售额，无法对零金额计算。"
- **Tool failure**: Fall back to `execute_python` with the formula directly:
  `output_vat = sales_amount * vat_rate; payable_vat = output_vat - input_vat`

## Gotchas
- 含税销售额 ≠ 不含税销售额。本技能使用含税销售额直接乘以税率（简易计税法）。
  若用户提供的是不含税销售额，提示区别并换算。
- 小规模纳税人通常无进项抵扣资格（3%税率），若 input_vat > 0 请提示风险。
- 出口退税、免税销售等特殊场景超出本技能范围，提示用户咨询专业人士。
