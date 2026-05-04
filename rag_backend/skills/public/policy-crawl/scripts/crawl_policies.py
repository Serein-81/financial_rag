#!/usr/bin/env python3
"""
Policy Crawl Script

Crawls policy data from government sources and saves to the local database.
Calls the backend API or service to execute the full pipeline.

Usage:
    python crawl_policies.py --params <params.json>

Params:
    {
        "method": "full",           # "full" or "crawl_only"
        "max_per_source": 20,
        "notify_enterprises": true,
        "keywords": ["增值税", "企业所得税"],
        "api_base_url": "http://localhost:8000"
    }

Output:
    JSON with crawl results
"""

import json
import sys
import os
import urllib.request
import urllib.error
from datetime import datetime


def crawl_via_api(params: dict) -> dict:
    """Call the policy collect API endpoint."""
    api_base_url = params.get("api_base_url", "http://localhost:8000")
    keywords = params.get("keywords", [])

    url = f"{api_base_url.rstrip('/')}/api/v1/policy/collect"
    body = json.dumps({"keywords": keywords, "max_per_source": params.get("max_per_source", 20)}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {
                "success": True,
                "method": "api",
                "result": result,
                "crawl_time": datetime.now().isoformat(),
            }
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        return {"success": False, "method": "api", "error": str(e), "error_detail": error_body}
    except urllib.error.URLError as e:
        return {"success": False, "method": "api", "error": f"Cannot reach server: {e.reason}"}
    except Exception as e:
        return {"success": False, "method": "api", "error": f"Unexpected error: {str(e)}"}


def check_scheduler_status(params: dict) -> dict:
    """Check the policy scheduler status."""
    api_base_url = params.get("api_base_url", "http://localhost:8000")
    url = f"{api_base_url.rstrip('/')}/api/v1/policy/scheduler/status"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "scheduler_status": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    param_file = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--params" and i + 1 < len(sys.argv[1:]):
            param_file = sys.argv[i + 2]
            break

    if not param_file:
        # Default: check status first, then crawl
        default_params = {
            "method": "status",
            "api_base_url": "http://localhost:8000",
        }
        result = check_scheduler_status(default_params)
    else:
        with open(param_file, "r", encoding="utf-8") as f:
            params = json.load(f)

        method = params.get("method", "full")

        if method == "status":
            result = check_scheduler_status(params)
        else:
            result = crawl_via_api(params)

    print(json.dumps(result, ensure_ascii=False, indent=2))
