"""
输出智能体提示词

包含：
- system_prompt.txt: 系统提示词（输出整合师角色）
- synthesis_prompt.txt: 整合提示词（用于整合专家结果）
- quick_review_prompt.txt: 快速审查提示词
- deep_review_prompt.txt: 深度审查提示词
- regeneration_hint_prompt.txt: 改进提示词
- final_output_prompt.txt: 最终输出提示词（轻量级，直接生成答案）
"""

from ..base import PromptLoader
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
_loader = PromptLoader(PROMPTS_DIR)


def get_system_prompt() -> str:
    """获取系统提示词"""
    return _loader.load("system_prompt.txt")


def get_synthesis_prompt(user_query: str, specialist_results: str) -> str:
    """获取整合提示词（用于整合专家结果）"""
    return _loader.load_template(
        "synthesis_prompt.txt",
        user_query=user_query,
        specialist_results=specialist_results
    )


def get_quick_review_prompt(user_query: str, output: str) -> str:
    """获取快速审查提示词"""
    return _loader.load_template("quick_review_prompt.txt", user_query=user_query, output=output)


def get_deep_review_prompt(user_query: str, output: str) -> str:
    """获取深度审查提示词"""
    return _loader.load_template("deep_review_prompt.txt", user_query=user_query, output=output)


def get_regeneration_hint_prompt(
    user_query: str,
    original_output: str,
    feedback: str
) -> str:
    """获取改进提示词"""
    return _loader.load_template(
        "regeneration_hint_prompt.txt",
        user_query=user_query,
        original_output=original_output,
        feedback=feedback
    )


def get_final_output_prompt(user_query: str, tool_result: str) -> str:
    """获取最终输出提示词（轻量级，直接基于工具结果生成答案）"""
    return _loader.load_template(
        "final_output_prompt.txt",
        user_query=user_query,
        tool_result=tool_result
    )


__all__ = [
    "get_system_prompt",
    "get_synthesis_prompt",
    "get_quick_review_prompt",
    "get_deep_review_prompt",
    "get_regeneration_hint_prompt",
    "get_final_output_prompt",
    "PROMPTS_DIR",
]
