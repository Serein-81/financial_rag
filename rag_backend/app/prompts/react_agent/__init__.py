"""
ReAct 智能体提示词

包含：
- react_prompt.txt: ReAct 推理提示词
"""

from ..base import PromptLoader
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
_loader = PromptLoader(PROMPTS_DIR)


def get_react_prompt(
    tools_description: str = "",
    context: str = ""
) -> str:
    """获取 ReAct 推理提示词"""
    template = _loader.load("react_prompt.txt")
    return template.format(
        tools_description=tools_description,
        context=context
    )


def get_react_format_instruction() -> str:
    """获取格式说明"""
    return _loader.load("format_instruction.txt")


__all__ = [
    "get_react_prompt",
    "get_react_format_instruction",
    "PROMPTS_DIR",
]
