#!/usr/bin/env python3
"""
Financial Data Entry Submitter

Submits validated financial data to the backend API.
Calls POST /api/v1/financial-data to create a single record.

Usage:
    python submit_entry.py --params <params.json>

Params JSON:
    {
        "fiscal_year": 2025,
        "period_type": "yearly",
        "total_revenue": 500000,
        "total_expenses": 300000,
        ... (all validated financial fields)

        "tenant_id": "tenant_001",
        "user_id": "user_abc123",
        "api_base_url": "http://localhost:8000"
    }

Output:
    JSON with submission result
"""

import json
import sys
import os
import urllib.request
import urllib.error
import urllib.parse
from datetime import date


def calculate_period_dates(fiscal_year: int, period_type: str) -> tuple:
    """Calculate period_start and period_end from fiscal_year and period_type."""
    if period_type == "yearly":
        return f"{fiscal_year}-01-01", f"{fiscal_year}-12-31"
    elif period_type == "quarterly":
        # Default to Q1 if not specified
        return f"{fiscal_year}-01-01", f"{fiscal_year}-03-31"
    elif period_type == "monthly":
        return f"{fiscal_year}-01-01", f"{fiscal_year}-01-31"
    return f"{fiscal_year}-01-01", f"{fiscal_year}-12-31"


def submit(params: dict) -> dict:
    """Submit financial data to the backend API."""
    tenant_id = params.pop("tenant_id", os.environ.get("TENANT_ID", "default"))
    user_id = params.pop("user_id", os.environ.get("USER_ID", "default"))
    api_base_url = params.pop("api_base_url", os.environ.get("API_BASE_URL", "http://localhost:8000"))

    fiscal_year = params.get("fiscal_year")
    period_type = params.get("period_type", "yearly")

    # Calculate period dates if not provided
    period_start = params.pop("period_start", None) or calculate_period_dates(fiscal_year, period_type)[0]
    period_end = params.pop("period_end", None) or calculate_period_dates(fiscal_year, period_type)[1]

    # Build the request body matching the FinancialDataCreate schema
    body = {
        "fiscal_year": fiscal_year,
        "period_type": period_type,
        "period_start": period_start,
        "period_end": period_end,
        "total_revenue": params.get("total_revenue", 0),
        "total_expenses": params.get("total_expenses", 0),
        "taxable_sales": params.get("taxable_sales", 0),
        "tax_free_sales": params.get("tax_free_sales", 0),
        "deductible_expenses": params.get("deductible_expenses", 0),
        "non_deductible_expenses": params.get("non_deductible_expenses", 0),
        "input_tax": params.get("input_tax", 0),
        "output_tax": params.get("output_tax", 0),
        "vat_rate": params.get("vat_rate", 0.13),
        "taxable_income": params.get("taxable_income", 0),
        "corporate_tax_rate": params.get("corporate_tax_rate", 0.25),
        "total_payroll": params.get("total_payroll", 0),
        "special_deductions": params.get("special_deductions", 0),
        "total_invoices": params.get("total_invoices", 0),
        "input_invoice_count": params.get("input_invoice_count", 0),
        "output_invoice_count": params.get("output_invoice_count", 0),
        "data_source": "manual",
        "notes": params.get("notes", ""),
    }

    # Remove None values, default to 0
    body = {k: (v if v is not None else 0) for k, v in body.items()}

    url = f"{api_base_url.rstrip('/')}/api/v1/financial-data"

    # Build auth header using user_id and tenant_id
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": str(user_id),
        "X-Tenant-ID": str(tenant_id),
    }

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode("utf-8")
            response_json = json.loads(response_body)
            return {
                "success": True,
                "status_code": resp.status,
                "record_id": response_json.get("id", response_json.get("record_id", "unknown")),
                "response": response_json,
            }
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        return {
            "success": False,
            "status_code": e.code,
            "error": str(e),
            "error_detail": error_body,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "status_code": 0,
            "error": f"Cannot reach server: {e.reason}",
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "error": f"Unexpected error: {str(e)}",
        }


if __name__ == "__main__":
    param_file = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--params" and i + 1 < len(sys.argv[1:]):
            param_file = sys.argv[i + 2]
            break

    if not param_file:
        print(json.dumps({"success": False, "error": "Missing --params argument"}))
        sys.exit(1)

    try:
        with open(param_file, "r", encoding="utf-8") as f:
            params = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Cannot read params: {e}"}))
        sys.exit(1)

    result = submit(params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
