"""
提示词管理模块

统一管理所有智能体的提示词，支持结构化和向后兼容。

目录结构：
    prompts/
    ├── __init__.py           # 统一导出
    ├── base.py               # 提示词加载基类
    ├── prompt_registry.py    # 结构化提示词注册表（新）
    ├── agents/               # 结构化智能体提示词（新）
    │   ├── react_agent/
    │   ├── plan_agent/
    │   ├── smart_router/
    │   └── ...
    ├── output_agent/         # 输出智能体提示词（保留）
    ├── system/               # 系统智能体提示词（废弃，保留）
    └── templates/            # 通用模板（向后兼容）
"""

import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent
SYSTEM_PROMPTS_DIR = PROMPTS_DIR / "system"
TEMPLATES_DIR = PROMPTS_DIR / "templates"
AGENTS_DIR = PROMPTS_DIR / "agents"


def load_prompt(prompt_name: str, subdir: Optional[str] = None) -> str:
    """
    加载提示词文件（向后兼容）

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
        logger.debug(f"提示词文件不存在: {prompt_file}")
        return ""
    except Exception as e:
        logger.error(f"加载提示词失败: {e}")
        return ""


def load_greeting_prompt() -> str:
    """加载问候语智能体提示词"""
    return load_prompt("greeting_agent")


def load_agent_prompt(agent_name: str) -> Optional[str]:
    """
    加载智能体提示词（优先使用新结构）

    Args:
        agent_name: 智能体名称

    Returns:
        提示词内容，如果不存在返回 None
    """
    from app.prompts.prompt_registry import get_prompt_registry
    
    registry = get_prompt_registry()
    return registry.load_system_prompt(agent_name)


def list_available_agents() -> List[str]:
    """
    列出所有可用的智能体

    Returns:
        智能体名称列表
    """
    from app.prompts.prompt_registry import get_prompt_registry
    
    registry = get_prompt_registry()
    return registry.list_agents()


def get_agent_config(agent_name: str) -> Optional[dict]:
    """
    获取智能体配置

    Args:
        agent_name: 智能体名称

    Returns:
        智能体配置字典
    """
    from app.prompts.prompt_registry import get_prompt_registry
    
    registry = get_prompt_registry()
    return registry.get_agent(agent_name)


def reload_prompt_registry():
    """重新加载提示词注册表"""
    from app.prompts.prompt_registry import get_prompt_registry
    
    registry = get_prompt_registry()
    registry.reload()


__all__ = [
    "PROMPTS_DIR",
    "SYSTEM_PROMPTS_DIR",
    "TEMPLATES_DIR",
    "AGENTS_DIR",
    "load_prompt",
    "load_greeting_prompt",
    "load_agent_prompt",
    "list_available_agents",
    "get_agent_config",
    "reload_prompt_registry",
]
