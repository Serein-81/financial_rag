"""
提示词管理模块

统一管理所有智能体的提示词，便于维护和版本控制。

目录结构：
    prompts/
    ├── __init__.py           # 统一导出
    ├── base.py               # 提示词加载基类
    ├── output_agent/         # 输出智能体提示词
    ├── react_agent/          # ReAct 智能体提示词
    ├── report_agent/         # 报表智能体提示词
    ├── system/               # 系统智能体提示词
    │   ├── greeting_agent.txt
    │   └── ...
    └── templates/            # 通用模板
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent
SYSTEM_PROMPTS_DIR = PROMPTS_DIR / "system"


def load_prompt(prompt_name: str, subdir: Optional[str] = None) -> str:
    """
    加载提示词文件

    Args:
        prompt_name: 提示词文件名（不含扩展名）
        subdir: 子目录，默认为 system/

    Returns:
        提示词内容
    """
    if subdir:
        prompt_dir = PROMPTS_DIR / subdir
    else:
        prompt_dir = SYSTEM_PROMPTS_DIR

    prompt_file = prompt_dir / f"{prompt_name}.txt"

    try:
        content = prompt_file.read_text(encoding="utf-8")
        logger.debug(f"已加载提示词: {prompt_file.name}")
        return content
    except FileNotFoundError:
        logger.error(f"提示词文件不存在: {prompt_file}")
        return ""
    except Exception as e:
        logger.error(f"加载提示词失败: {e}")
        return ""


def load_greeting_prompt() -> str:
    """加载问候语智能体提示词"""
    return load_prompt("greeting_agent")


__all__ = ["PROMPTS_DIR", "load_prompt", "load_greeting_prompt"]
