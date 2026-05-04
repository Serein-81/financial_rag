#!/usr/bin/env python3
"""
Legal Compliance Search Script (Fallback)

Searches for compliance regulations using Tavily web search API.
This is a fallback for when the MCP search_web tool is not available
or when the agent needs structured batch search results.

Primary workflow: The SKILL.md instructs the agent to use the MCP `search_web` tool directly.
This script serves as a supplementary structured search for specific compliance lookups.

Usage:
    python search_compliance.py --params <params.json>

Params:
    {
        "business_type": "llc",
        "industry": "technology",
        "location": "Beijing",
        "keywords": ["ICP license", "registration"],
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
import urllib.parse


TAVILY_API_URL = "https://api.tavily.com/search"


def build_search_queries(params: dict) -> list:
    """Build targeted search queries from business context."""
    industry = params.get("industry", "").lower()
    business_type = params.get("business_type", "").lower()
    location = params.get("location", "")
    keywords = params.get("keywords", [])

    queries = []

    # Registration search
    if business_type and location:
        queries.append(
            f"{business_type} company registration requirements {location} China 2025"
        )
    elif location:
        queries.append(f"company registration requirements {location} China 2025")
    else:
        queries.append("company registration requirements China 2025")

    # Industry-specific search
    if industry:
        queries.append(f"{industry} industry license permit China regulatory requirements")
        queries.append(f"{industry} compliance obligations China 2025")

    # Keyword-specific searches
    for kw in keywords:
        queries.append(f"{kw} {industry} China regulation requirement")

    return queries


def search_tavily(query: str, api_key: str) -> list:
    """Execute a single Tavily search query."""
    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": False,
        "max_results": 5,
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],
                    "score": r.get("score", 0),
                }
                for r in results
            ]
    except Exception as e:
        return [{"title": f"Search failed: {e}", "url": "", "content": "", "score": 0}]


def search(params: dict) -> dict:
    """Search for compliance regulations using Tavily web search."""
    api_key = params.get(
        "api_key",
        os.environ.get("TAVILY_API_KEY", ""),
    )

    if not api_key:
        return {
            "success": False,
            "error": "TAVILY_API_KEY not configured. "
                     "Set it in environment variables or pass api_key in params. "
                     "Falling back to reference documents.",
            "fallback": True,
            "results": [],
            "queries_tried": [],
        }

    business_type = params.get("business_type", "").lower()
    industry = params.get("industry", "").lower()
    location = params.get("location", "")

    queries = build_search_queries(params)

    # Execute searches (limit to 3 to avoid rate limiting)
    all_results = []
    seen_urls = set()

    for query in queries[:3]:
        results = search_tavily(query, api_key)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls and r.get("content"):
                seen_urls.add(url)
                all_results.append(r)

    # Deduplicate and sort by score
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Classify results into categories
    registration_results = [
        r for r in all_results
        if any(kw in (r.get("title", "") + r.get("content", "")).lower()
               for kw in ["registration", "license", "business license", "incorporation"])
    ]
    compliance_results = [
        r for r in all_results
        if any(kw in (r.get("title", "") + r.get("content", "")).lower()
               for kw in ["compliance", "regulation", "requirement", "obligation"])
    ]
    industry_results = [
        r for r in all_results
        if industry and industry in (r.get("title", "") + r.get("content", "")).lower()
    ]

    return {
        "success": True,
        "business_type": business_type,
        "industry": industry,
        "location": location,
        "total_results": len(all_results),
        "registration_results": registration_results[:5],
        "compliance_results": compliance_results[:5],
        "industry_results": industry_results[:5],
        "all_results": all_results[:10],
        "queries_executed": queries[:3],
        "disclaimer": (
            "This information is from web search results and may not reflect "
            "the most current regulations. Always verify with local authorities "
            "and consult a qualified legal professional for binding advice."
        ),
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

    result = search(params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
