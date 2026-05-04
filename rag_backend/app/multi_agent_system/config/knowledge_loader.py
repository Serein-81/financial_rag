"""
知识库/风险规则加载器

从 JSON 配置文件加载专业知识库和风险评估规则。
运营人员可直接编辑 JSON 文件更新规则，无需修改代码。

配置文件路径（相对于本模块）：
    - knowledge_base.json: 专业知识库规则
    - risk_rules.json: 风险评估规则
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 配置文件目录
_CONFIG_DIR = Path(__file__).parent


def _load_json_file(filename: str) -> Dict[str, Any]:
    """加载 JSON 配置文件，返回字典；若失败返回空字典。"""
    filepath = _CONFIG_DIR / filename
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("成功加载配置: %s (keys=%s)", filename, [k for k in data if not k.startswith("_")])
        return data
    except FileNotFoundError:
        logger.warning("配置文件不存在: %s", filepath)
    except json.JSONDecodeError as e:
        logger.error("配置文件 JSON 解析失败: %s, error=%s", filepath, e)
    except Exception as e:
        logger.error("加载配置文件失败: %s, error=%s", filepath, e)
    return {}


def _get_fallback_knowledge(specialty: str) -> List[Dict[str, Any]]:
    """当配置文件不可用时，返回内置的兜底知识规则。"""
    fallbacks = {
        "finance": [
            {"rule_id": "FIN_001", "category": "资产负债", "description": "资产负债表必须平衡", "risk_level": "high"},
            {"rule_id": "FIN_002", "category": "现金流", "description": "现金流量表与银行对账单应一致", "risk_level": "medium"},
        ],
        "tax": [
            {"rule_id": "TAX_001", "category": "增值税", "description": "增值税进项税额不得超过销项税额", "risk_level": "high"},
            {"rule_id": "TAX_002", "category": "企业所得税", "description": "企业所得税率应符合税法规定", "risk_level": "medium"},
        ],
        "legal": [
            {"rule_id": "LEG_001", "category": "合同条款", "description": "合同条款不得违反法律法规", "risk_level": "high"},
            {"rule_id": "LEG_002", "category": "知识产权", "description": "使用他人知识产权需获得授权", "risk_level": "medium"},
        ],
    }
    return fallbacks.get(specialty, [])


def _get_fallback_risk_rules(specialty: str) -> List[Dict[str, Any]]:
    """当配置文件不可用时，返回内置的兜底风险规则。"""
    fallbacks = {
        "finance": [
            {"pattern": "资产负债不平衡", "risk_score": 0.9, "risk_level": "critical"},
            {"pattern": "现金流异常", "risk_score": 0.7, "risk_level": "high"},
        ],
        "tax": [
            {"pattern": "税率计算错误", "risk_score": 0.8, "risk_level": "high"},
            {"pattern": "虚开发票", "risk_score": 1.0, "risk_level": "critical"},
        ],
        "legal": [
            {"pattern": "合同条款模糊", "risk_score": 0.6, "risk_level": "medium"},
            {"pattern": "违反法律", "risk_score": 1.0, "risk_level": "critical"},
        ],
    }
    return fallbacks.get(specialty, [])


def load_knowledge_base(specialty: str) -> List[Dict[str, Any]]:
    """加载指定专业领域的知识库规则。

    优先从 knowledge_base.json 读取，失败时回退到内置兜底规则。
    """
    data = _load_json_file("knowledge_base.json")
    rules = data.get(specialty)
    if rules:
        logger.debug("从配置文件加载 %s 知识库: %d 条规则", specialty, len(rules))
        return rules

    logger.warning("配置文件未找到 %s 知识库，使用内置兜底规则", specialty)
    return _get_fallback_knowledge(specialty)


def load_risk_rules(specialty: str) -> List[Dict[str, Any]]:
    """加载指定专业领域的风险评估规则。

    优先从 risk_rules.json 读取，失败时回退到内置兜底规则。
    """
    data = _load_json_file("risk_rules.json")
    rules = data.get(specialty)
    if rules:
        logger.debug("从配置文件加载 %s 风险规则: %d 条规则", specialty, len(rules))
        return rules

    logger.warning("配置文件未找到 %s 风险规则，使用内置兜底规则", specialty)
    return _get_fallback_risk_rules(specialty)
