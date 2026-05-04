#!/usr/bin/env python3
"""
Tax Law Web Search Script (Fallback)

Searches for tax law information using Tavily web search API.
This is a fallback for when the MCP search_web tool is not available.

Primary workflow: The SKILL.md instructs the agent to use the MCP `search_web` tool directly.
This script serves as a supplementary structured lookup.

Usage:
    python search_tax_law.py --params <params.json>

Params:
    {
        "query": "企业所得税 税率 2025",
        "max_results": 5,
        "api_key": "tavily-xxx"  (optional, falls back to env TAVILY_API_KEY)
    }

Output:
    JSON with search results
"""

import json
import sys
import os
import urllib.request
import urllib.error


TAVILY_API_URL = "https://api.tavily.com/search"


def search_tavily(query: str, api_key: str, max_results: int = 5) -> dict:
    """Execute a Tavily search."""
    if not api_key:
        return {
            "success": False,
            "error": "TAVILY_API_KEY not configured. "
                     "Set it in environment variables or pass api_key in params.",
            "results": [],
        }

    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": max_results,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            TAVILY_API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            return {
                "success": True,
                "query": query,
                "answer": data.get("answer", ""),
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", "")[:800],
                        "score": r.get("score", 0),
                    }
                    for r in results[:max_results]
                ],
            }
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}", "results": []}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Network error: {e.reason}", "results": []}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {str(e)}", "results": []}


if __name__ == "__main__":
    param_file = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--params" and i + 1 < len(sys.argv[1:]):
            param_file = sys.argv[i + 2]
            break

    if not param_file:
        params = {"query": "企业所得税 最新政策 2025", "max_results": 5}
    else:
        with open(param_file, "r", encoding="utf-8") as f:
            params = json.load(f)

    query = params.get("query", "企业所得税 最新政策 2025")
    max_results = params.get("max_results", 5)
    api_key = params.get("api_key", os.environ.get("TAVILY_API_KEY", ""))

    result = search_tavily(query, api_key, max_results)
    print(json.dumps(result, ensure_ascii=False, indent=2))
