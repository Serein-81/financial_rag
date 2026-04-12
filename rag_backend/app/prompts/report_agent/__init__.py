"""
报表智能体提示词

包含：
- report_prompt.txt: 报表生成提示词
"""

from ..base import PromptLoader
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
_loader = PromptLoader(PROMPTS_DIR)


def get_report_prompt(report_type: str = "general") -> str:
    """获取报表生成提示词"""
    return _loader.load_template("report_prompt.txt", report_type=report_type)


def get_sales_report_prompt(context: str = "") -> str:
    """获取销售报表提示词"""
    return _loader.load_template("sales_report.txt", context=context)


def get_financial_report_prompt(context: str = "") -> str:
    """获取财务报表提示词"""
    return _loader.load_template("financial_report.txt", context=context)


def get_operation_report_prompt(context: str = "") -> str:
    """获取运营报表提示词"""
    return _loader.load_template("operation_report.txt", context=context)


def get_inventory_report_prompt(context: str = "") -> str:
    """获取库存报表提示词"""
    return _loader.load_template("inventory_report.txt", context=context)


__all__ = [
    "get_report_prompt",
    "get_sales_report_prompt",
    "get_financial_report_prompt",
    "get_operation_report_prompt",
    "get_inventory_report_prompt",
    "PROMPTS_DIR",
]
