import json
import re
from typing import Any


def _parse_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    parts = re.split(r"[\n,，;；]+", text)
    return [part.strip(" -\t") for part in parts if part.strip(" -\t")]


def analyze_evidence_gaps(required_items: str, provided_items: str) -> str:
    """对比所需证据和已提供材料，输出缺口分析。"""
    required = _parse_items(required_items)
    provided = _parse_items(provided_items)
    provided_text = "\n".join(provided).lower()

    covered = []
    missing = []
    for item in required:
        item_text = item.lower()
        if item_text in provided_text or any(item_text in candidate.lower() for candidate in provided):
            covered.append(item)
        else:
            missing.append(item)

    coverage = round(len(covered) / len(required), 4) if required else 0
    if not required:
        risk_level = "证据要求不明确"
    elif coverage >= 0.8:
        risk_level = "低"
    elif coverage >= 0.5:
        risk_level = "中"
    else:
        risk_level = "高"

    result = {
        "所需证据数量": len(required),
        "已覆盖数量": len(covered),
        "覆盖率": coverage,
        "风险等级": risk_level,
        "已覆盖证据": covered,
        "缺失证据": missing,
        "建议": "优先补充缺失证据后再输出最终结论。" if missing else "当前证据覆盖较完整，可进入下一步分析。",
    }
    return json.dumps(result, ensure_ascii=False)


SKILL_TOOLS = [
    {
        "name": "analyze_evidence_gaps",
        "description": "对比所需证据清单和已提供材料清单，输出缺失证据、覆盖率、风险等级和补充建议。",
        "func": analyze_evidence_gaps,
        "parameters": {
            "required_items": {
                "type": "string",
                "description": "所需证据清单，支持 JSON 数组、换行、逗号或分号分隔。",
                "required": True,
            },
            "provided_items": {
                "type": "string",
                "description": "已提供材料清单，支持 JSON 数组、换行、逗号或分号分隔。",
                "required": True,
            },
        },
    }
]
