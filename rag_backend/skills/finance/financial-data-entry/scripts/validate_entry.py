#!/usr/bin/env python3
"""
Financial Data Entry Validator

Validates financial data against the UserFinancialData schema before submission.
Aligns with the real DB model fields (fiscal_year, period_type, revenue/expense/tax breakdowns).

Usage:
    python validate_entry.py --params <params.json>

Params JSON format:
    {
        "fiscal_year": 2025,
        "period_type": "yearly",
        "total_revenue": 500000,
        "total_expenses": 300000,
        "taxable_sales": 450000,
        "tax_free_sales": 50000,
        "deductible_expenses": 250000,
        "non_deductible_expenses": 50000,
        "input_tax": 30000,
        "output_tax": 58500,
        "vat_rate": 0.13,
        "taxable_income": 200000,
        "corporate_tax_rate": 0.25,
        "total_payroll": 0,
        "special_deductions": 0,
        "total_invoices": 0,
        "input_invoice_count": 0,
        "output_invoice_count": 0
    }

Output:
    JSON with validation result
"""

import json
import sys
import re
from datetime import date

ALLOWED_PERIOD_TYPES = ("yearly", "quarterly", "monthly")

VALIDATION_RULES = {
    "fiscal_year": {"type": "int", "min": 2000, "max": 2100, "required": True},
    "period_type": {"type": "enum", "values": ALLOWED_PERIOD_TYPES, "required": True},
    "total_revenue": {"type": "float", "min": 0, "required": False},
    "total_expenses": {"type": "float", "min": 0, "required": False},
    "taxable_sales": {"type": "float", "min": 0, "required": False},
    "tax_free_sales": {"type": "float", "min": 0, "required": False},
    "deductible_expenses": {"type": "float", "min": 0, "required": False},
    "non_deductible_expenses": {"type": "float", "min": 0, "required": False},
    "input_tax": {"type": "float", "min": 0, "required": False},
    "output_tax": {"type": "float", "min": 0, "required": False},
    "vat_rate": {"type": "float", "min": 0, "max": 1, "required": False},
    "taxable_income": {"type": "float", "min": 0, "required": False},
    "corporate_tax_rate": {"type": "float", "min": 0, "max": 1, "required": False},
    "total_payroll": {"type": "float", "min": 0, "required": False},
    "special_deductions": {"type": "float", "min": 0, "required": False},
    "total_invoices": {"type": "int", "min": 0, "required": False},
    "input_invoice_count": {"type": "int", "min": 0, "required": False},
    "output_invoice_count": {"type": "int", "min": 0, "required": False},
}


def _cast(value, target_type: str):
    """Cast a value to the target type, return None on failure"""
    try:
        if target_type == "int":
            return int(value)
        elif target_type == "float":
            return float(value)
    except (ValueError, TypeError):
        return None
    return value


def validate(params: dict) -> dict:
    """
    Validate financial entry against DB schema rules.

    Returns:
        dict with keys: valid, errors, warnings, cleaned, calculations
    """
    errors = []
    warnings = []
    cleaned = {}
    calculations = {}

    # ---------------------------------------------------------------
    # 1. Field-level validation
    # ---------------------------------------------------------------
    for field, rules in VALIDATION_RULES.items():
        raw_value = params.get(field)

        # Check required
        if rules.get("required") and raw_value is None:
            errors.append(f"Missing required field: {field}")
            continue

        if raw_value is None:
            cleaned[field] = None
            continue

        # Cast to correct type
        typed = _cast(raw_value, rules["type"])
        if typed is None:
            errors.append(f"Field '{field}' must be {rules['type']}, got '{raw_value}'")
            continue

        # Range check
        min_val = rules.get("min")
        max_val = rules.get("max")
        if min_val is not None and typed < min_val:
            errors.append(f"Field '{field}' must be >= {min_val}, got {typed}")
            continue
        if max_val is not None and typed > max_val:
            errors.append(f"Field '{field}' must be <= {max_val}, got {typed}")
            continue

        # Enum check
        enum_vals = rules.get("values")
        if enum_vals is not None and typed not in enum_vals:
            errors.append(
                f"Field '{field}' must be one of {', '.join(enum_vals)}, got '{typed}'"
            )
            continue

        cleaned[field] = typed

    # ---------------------------------------------------------------
    # 2. Business rule validation (non-null fields only)
    # ---------------------------------------------------------------
    tr = cleaned.get("total_revenue")
    ts = cleaned.get("taxable_sales")
    tf = cleaned.get("tax_free_sales")
    te = cleaned.get("total_expenses")
    de = cleaned.get("deductible_expenses")
    nd = cleaned.get("non_deductible_expenses")

    # Revenue: total_revenue >= taxable_sales + tax_free_sales
    if tr is not None and ts is not None and tf is not None:
        if tr < ts + tf:
            errors.append(
                f"total_revenue ({tr:,.2f}) must be >= "
                f"taxable_sales ({ts:,.2f}) + tax_free_sales ({tf:,.2f}) = {ts + tf:,.2f}"
            )

    # Expenses: total_expenses >= deductible + non_deductible
    if te is not None and de is not None and nd is not None:
        if te < de + nd:
            errors.append(
                f"total_expenses ({te:,.2f}) must be >= "
                f"deductible_expenses ({de:,.2f}) + non_deductible_expenses ({nd:,.2f}) = {de + nd:,.2f}"
            )

    # ---------------------------------------------------------------
    # 3. Calculated fields
    # ---------------------------------------------------------------
    tr = cleaned.get("total_revenue") or 0
    te = cleaned.get("total_expenses") or 0
    ot = cleaned.get("output_tax") or 0
    it = cleaned.get("input_tax") or 0

    calculations = {
        "gross_profit": round(tr - te, 2),
        "estimated_vat": round(ot - it, 2),
        "profit_margin_pct": round(((tr - te) / tr * 100), 2) if tr > 0 else 0,
    }

    # ---------------------------------------------------------------
    # 4. Warnings
    # ---------------------------------------------------------------
    if calculations["gross_profit"] < 0:
        warnings.append("Gross profit is negative — expenses exceed revenue")

    if tr and tr > 10_000_000:
        warnings.append(f"Revenue is large ({tr:,.2f}). Please verify the figures.")

    # ---------------------------------------------------------------
    # 5. Result
    # ---------------------------------------------------------------
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "cleaned": {k: v for k, v in cleaned.items() if v is not None},
        "calculations": calculations,
        "summary": {
            "total_revenue": tr,
            "total_expenses": te,
            "gross_profit": calculations["gross_profit"],
            "profit_margin": calculations["profit_margin_pct"],
        },
    }


if __name__ == "__main__":
    param_file = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--params" and i + 1 < len(sys.argv[1:]):
            param_file = sys.argv[i + 2]
            break

    if not param_file:
        print(json.dumps({"valid": False, "errors": ["Missing --params argument"], "warnings": []}))
        sys.exit(1)

    try:
        with open(param_file, "r", encoding="utf-8") as f:
            params = json.load(f)
    except Exception as e:
        print(json.dumps({"valid": False, "errors": [f"Cannot read params: {e}"], "warnings": []}))
        sys.exit(1)

    result = validate(params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
