#!/usr/bin/env python3
"""
Enterprise Policy Matching Script

Matches an enterprise profile against tax policies to identify applicable
benefits, compliance obligations, and risks.

Usage:
    python match_policies.py --params <params.json>

Params:
    {
        "method": "api",            # "api" or "builtin"
        "enterprise_profile": {
            "industry": "信息技术",
            "region": "广东深圳",
            "scale": "中型",
            "tax_types": ["增值税", "企业所得税"],
            "keywords": ["高新技术", "研发"],
            "special_qualifications": ["高新技术企业"]
        },
        "api_base_url": "http://localhost:8000"
    }

Output:
    JSON with matched policies and analysis
"""

import json
import sys
import os
import urllib.request
import urllib.error
from datetime import datetime


# Built-in policy rules for fallback matching
POLICY_RULES = [
    {
        "id": "HI-TECH-15",
        "name": "高新技术企业企业所得税优惠",
        "description": "经认定的高新技术企业，减按15%税率征收企业所得税（标准税率25%）",
        "authority": "《企业所得税法》第二十八条",
        "conditions": {
            "industry": ["信息技术", "生物医药", "新材料", "先进制造", "航空航天", "集成电路", "软件", "新能源"],
            "qualifications": ["高新技术企业"],
        },
        "benefit": "税率从25%降至15%，降幅10个百分点",
        "deadline": "每年5月31日前汇算清缴",
        "risk_level": "medium",
    },
    {
        "id": "RND-DEDUCTION-100",
        "name": "研发费用加计扣除",
        "description": "企业开展研发活动中实际发生的研发费用，未形成无形资产计入当期损益的，按实际发生额的100%在税前加计扣除",
        "authority": "《财政部 税务总局 科技部公告》",
        "conditions": {
            "keywords": ["研发", "技术开发", "创新"],
        },
        "benefit": "研发费用100%加计扣除",
        "deadline": "每年汇算清缴时申报",
        "risk_level": "low",
    },
    {
        "id": "SMALL-MICRO-TAX",
        "name": "小型微利企业企业所得税优惠",
        "description": "小型微利企业年应纳税所得额不超过100万元的部分，减按25%计入应纳税所得额，按20%税率缴纳企业所得税",
        "authority": "《企业所得税法》及实施条例",
        "conditions": {
            "scale": ["小型", "微型"],
        },
        "benefit": "实际税负率5%（100万以内部分）",
        "deadline": "每年汇算清缴时自动适用",
        "risk_level": "low",
    },
    {
        "id": "VAT-SMALL-REDUCTION",
        "name": "增值税小规模纳税人减免",
        "description": "增值税小规模纳税人适用3%征收率的应税销售收入，减按1%征收率征收增值税",
        "authority": "《财政部 税务总局公告》",
        "conditions": {
            "scale": ["小型", "微型"],
            "tax_types": ["增值税"],
        },
        "benefit": "征收率从3%降至1%",
        "deadline": "每月/每季申报时适用",
        "risk_level": "low",
    },
    {
        "id": "SOFTWARE-TAX",
        "name": "软件企业企业所得税优惠",
        "description": "我国境内新办的集成电路设计企业和符合条件的软件企业，经认定后，自获利年度起，享受\"两免三减半\"",
        "authority": "《财政部 税务总局 发展改革委 工业和信息化部公告》",
        "conditions": {
            "industry": ["软件", "信息技术"],
            "qualifications": ["软件企业"],
        },
        "benefit": "两免三减半（前两年免征，后三年减半）",
        "deadline": "获利年度起适用",
        "risk_level": "medium",
    },
    {
        "id": "HAINAN-FTZ-15",
        "name": "海南自由贸易港企业所得税优惠",
        "description": "对注册在海南自由贸易港并实质性运营的鼓励类产业企业，减按15%税率征收企业所得税",
        "authority": "《海南自由贸易港建设总体方案》",
        "conditions": {
            "region": ["海南"],
        },
        "benefit": "税率15%",
        "deadline": "每年汇算清缴",
        "risk_level": "medium",
    },
    {
        "id": "WEST-DEVELOP-15",
        "name": "西部大开发企业所得税优惠",
        "description": "对设在西部地区的鼓励类产业企业，减按15%的税率征收企业所得税",
        "authority": "《财政部 税务总局 国家发展改革委公告》",
        "conditions": {
            "region": ["重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "广西"],
        },
        "benefit": "税率15%",
        "deadline": "每年汇算清缴",
        "risk_level": "low",
    },
    {
        "id": "IC-DEDUCTION",
        "name": "集成电路企业企业所得税优惠",
        "description": "集成电路线宽小于28纳米的经营期15年以上的集成电路生产企业或项目，自获利年度起，享受\"十年免征\"",
        "authority": "《国务院关于印发新时期促进集成电路产业和软件产业高质量发展若干政策的通知》",
        "conditions": {
            "industry": ["集成电路", "半导体"],
        },
        "benefit": "十年免征企业所得税",
        "deadline": "获利年度起适用",
        "risk_level": "high",
    },
]


def match_builtin(profile: dict) -> dict:
    """Match enterprise profile against built-in policy rules."""
    industry = (profile.get("industry") or "").lower()
    region = (profile.get("region") or "").lower()
    scale = (profile.get("scale") or "").lower()
    tax_types = [t.lower() for t in profile.get("tax_types", [])]
    keywords = [k.lower() for k in profile.get("keywords", [])]
    qualifications = [q.lower() for q in profile.get("special_qualifications", [])]

    matched = []
    for rule in POLICY_RULES:
        conditions = rule.get("conditions", {})
        score = 0
        match_reasons = []

        # Industry match
        cond_industries = [c.lower() for c in conditions.get("industry", [])]
        if cond_industries:
            if any(ind in industry for ind in cond_industries) or any(ind in industry for ind in cond_industries):
                score += 3
                match_reasons.append(f"行业匹配: {industry}")

        # Region match
        cond_regions = [r.lower() for r in conditions.get("region", [])]
        if cond_regions:
            if any(r in region for r in cond_regions):
                score += 3
                match_reasons.append(f"地区匹配: {region}")

        # Scale match
        cond_scales = [s.lower() for s in conditions.get("scale", [])]
        if cond_scales:
            if scale in cond_scales:
                score += 2
                match_reasons.append(f"规模匹配: {scale}")

        # Tax type match
        cond_tax_types = [t.lower() for t in conditions.get("tax_types", [])]
        if cond_tax_types:
            if any(t in tax_types for t in cond_tax_types):
                score += 2
                match_reasons.append("税种匹配")

        # Keyword match
        cond_keywords = [k.lower() for k in conditions.get("keywords", [])]
        if cond_keywords:
            if any(kw in keywords for kw in cond_keywords):
                score += 3
                match_reasons.append("关键词匹配")

        # Qualification match
        cond_quals = [q.lower() for q in conditions.get("qualifications", [])]
        if cond_quals:
            if any(q in qualifications for q in cond_quals):
                score += 4
                match_reasons.append(f"资质匹配: {qualifications}")

        if score >= 2:
            status = "✅ 符合条件" if score >= 4 else "⚠️ 可能符合"
            matched.append({
                "policy_id": rule["id"],
                "policy_name": rule["name"],
                "description": rule["description"],
                "match_score": min(score / 5.0, 1.0),
                "match_status": status,
                "benefit": rule["benefit"],
                "deadline": rule["deadline"],
                "authority": rule["authority"],
                "risk_level": rule["risk_level"],
                "reasons": match_reasons,
            })

    matched.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "success": True,
        "method": "builtin",
        "profile": profile,
        "total_matched": len(matched),
        "high_confidence": [m for m in matched if m["match_score"] >= 0.8],
        "medium_confidence": [m for m in matched if 0.4 <= m["match_score"] < 0.8],
        "low_confidence": [m for m in matched if m["match_score"] < 0.4],
        "results": matched,
        "disclaimer": "This matching is for reference only. Always verify with a qualified tax professional.",
    }


def match_via_api(profile: dict, api_base_url: str) -> dict:
    """Match via the policy matching API."""
    url = f"{api_base_url.rstrip('/')}/api/v1/policy/match"
    body = json.dumps({"enterprise_profile": profile}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "method": "api", "result": result}
    except Exception as e:
        return {"success": False, "method": "api", "error": str(e)}


if __name__ == "__main__":
    param_file = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--params" and i + 1 < len(sys.argv[1:]):
            param_file = sys.argv[i + 2]
            break

    if not param_file:
        # Default demo profile
        params = {
            "method": "builtin",
            "enterprise_profile": {
                "industry": "信息技术",
                "region": "广东深圳",
                "scale": "中型",
                "tax_types": ["增值税", "企业所得税"],
                "keywords": ["研发", "技术开发"],
                "special_qualifications": ["高新技术企业"],
            },
        }
    else:
        with open(param_file, "r", encoding="utf-8") as f:
            params = json.load(f)

    profile = params.get("enterprise_profile", {})
    method = params.get("method", "builtin")

    if method == "api":
        result = match_via_api(profile, params.get("api_base_url", "http://localhost:8000"))
    else:
        result = match_builtin(profile)

    print(json.dumps(result, ensure_ascii=False, indent=2))
