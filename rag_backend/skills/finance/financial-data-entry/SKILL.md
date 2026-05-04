---
name: financial-data-entry
description: >
  This skill should be used when the user wants to "record financial data",
  "enter transaction", "add revenue", "input expenses", "record income",
  "log financial record", "create financial entry", or "add financial figures".
  It guides the user through structured financial data entry and submission.
when_to_use: >
  Activate when the user needs to manually enter financial data into the system.
  The skill handles: collecting data from user, validating format and business rules,
  presenting summary for confirmation, and submitting to the backend database.
  NOT for Excel bulk uploads — direct the user to the upload feature instead.
metadata:
  author: internal-finance-team
  version: "2.0"
  domain: finance
compatibility: |
  Requires: python3
  Depends on: POST /api/v1/financial-data endpoint (create single record)
allowed-tools: Bash Read Write
---

# Financial Data Entry Skill

## Overview
Guide the user through entering a single financial data record into the system.
The skill follows a **collect → validate → confirm → submit** workflow.

The system stores financial data per fiscal year with revenue, expense, and tax breakdowns.
Each record belongs to a specific fiscal year and period type (yearly/quarterly/monthly).

## Workflow

### Step 1: Collect Basic Information
Ask the user for the following required information. If the user provides all info upfront, parse it directly.

**Fiscal Year** (required):
- Ask "Which fiscal year does this data belong to?" if not specified
- Must be between 2000 and 2100

**Period Type** (required):
- Options: `yearly` (default), `quarterly`, `monthly`
- If period type is quarterly, ask "Which quarter (Q1/Q2/Q3/Q4)?"
- If period type is monthly, ask "Which month (1-12)?"
- Default to `yearly` if user doesn't specify

**Period Dates** (auto-calculated):
- For `yearly`: period_start = {fiscal_year}-01-01, period_end = {fiscal_year}-12-31
- For `quarterly`: period_start = {fiscal_year}-{quarter_start}, period_end = {fiscal_year}-{quarter_end}
- For `monthly`: period_start = {fiscal_year}-{month}-01, period_end = {fiscal_year}-{month}-{last_day}

### Step 2: Collect Financial Figures
Ask for the following figures. Only collect what the user can provide — missing fields default to 0.

**Revenue (收入):**
- `total_revenue` — 营业收入总额 (required if entering revenue data)
- `taxable_sales` — 应税销售额 (optional, subset of revenue)
- `tax_free_sales` — 免税销售额 (optional, subset of revenue)

**Expenses (支出):**
- `total_expenses` — 总支出 (required if entering expense data)
- `deductible_expenses` — 可扣除费用 (optional)
- `non_deductible_expenses` — 不可扣除费用 (optional)

**Tax (税务):**
- `input_tax` — 进项税额 (optional)
- `output_tax` — 销项税额 (optional)
- `vat_rate` — 增值税率 (default: 0.13, range: 0-1)
- `taxable_income` — 应纳税所得额 (optional)
- `corporate_tax_rate` — 企业所得税率 (default: 0.25, range: 0-1)

**Payroll (工资):**
- `total_payroll` — 工资总额 (optional)
- `special_deductions` — 专项扣除 (optional)

**Invoice (发票):**
- `total_invoices` — 总发票数 (optional)
- `input_invoice_count` — 进项发票数 (optional)
- `output_invoice_count` — 销项发票数 (optional)

### Step 3: Validate Data
Run the validation script before submitting:

```bash
python scripts/validate_entry.py --params <param_file>
```

Pass all collected data as the params JSON. The script will:
- Validate field types and ranges
- Check business rules (revenue >= taxable_sales + tax_free_sales)
- Check tax rate ranges (0-1)
- Validate date/year consistency

If validation returns errors, show them to the user and ask for corrections.

### Step 4: Present Summary and Confirm
Show the user a structured summary:

```text
Financial Data Summary
======================
Fiscal Year: 2025
Period: Yearly (2025-01-01 ~ 2025-12-31)

Revenue:
  Total Revenue:    ¥500,000.00
  Taxable Sales:    ¥450,000.00
  Tax-Free Sales:   ¥50,000.00

Expenses:
  Total Expenses:   ¥300,000.00
  Deductible:       ¥250,000.00
  Non-Deductible:   ¥50,000.00

Tax:
  VAT Rate:         13%
  Output Tax:       ¥58,500.00
  Input Tax:        ¥30,000.00

Calculations:
  Gross Profit:     ¥200,000.00
  Estimated VAT:    ¥28,500.00

Confirm submission? (yes/no)
```

Ask the user to confirm. If they say no, ask what to change.

### Step 5: Submit to Backend
Once confirmed, submit the data:

```bash
python scripts/submit_entry.py --params <param_file>
```

The submit script includes auth context (tenant_id, user_id) passed from the orchestrator. It calls `POST /api/v1/financial-data` to create the record.

### Step 6: Report Result
Report the result back to the user:
- On success: Show the record ID and a confirmation message
- On failure: Show the error and suggest next steps

## Error Handling
- **Validation errors**: Show each error message clearly, ask user to correct
- **Duplicate record**: If a record for the same year/period already exists, inform the user and ask if they want to update it instead
- **API failure**: Retry once, then report the error with details. Do not lose the data — save it and ask user to try again later
- **Network error**: Ask user to check connection and retry

## Gotchas
- All amounts are in CNY (yuan), no decimals needed for display but accept up to 2 decimal places
- Revenue fields must be >= 0 and total_revenue >= taxable_sales + tax_free_sales
- Tax rates are expressed as decimals (0.13 = 13%), not percentages
- If the user says "I want to enter last year's data", calculate fiscal_year = current_year - 1
- For bulk data (many records at once), tell the user to use the Excel upload feature instead
- Always ask for confirmation before submitting — financial data is sensitive
- Never make up data; if the user doesn't know a value, default it to 0 or skip it
- If the user provides "profit" or "net income", calculate it from revenue - expenses, don't accept it as a direct input
