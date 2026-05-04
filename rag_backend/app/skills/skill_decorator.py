"""
Skill Decorator - Python @skill 装饰器

允许将 Python 函数 / class 直接定义为技能,
适用于不需要独立 SKILL.md 的轻量级内联技能。

使用方式:
    @skill(
        name="validate-financial-data",
        description="This skill validates financial data format and completeness.",
        domain="finance"
    )
    async def validate_financial_data(data: dict) -> dict:
        # 技能逻辑
        ...
"""

import inspect
import logging
from functools import wraps
from typing import Callable, Dict, Any, Optional, List, Awaitable

from .skill_registry import SkillRegistry, SkillEntry, SkillMetadata

logger = logging.getLogger(__name__)


# 存储注册的内联技能
_inline_skills: Dict[str, Dict[str, Any]] = {}


def skill(
    name: str,
    description: str,
    domain: Optional[str] = None,
    when_to_use: str = "",
    allowed_tools: Optional[List[str]] = None,
):
    """
    装饰器: 将异步函数注册为技能

    Args:
        name: 技能名称 (小写字母/数字/连字符)
        description: 技能描述
        domain: 所属领域
        when_to_use: 何时触发
        allowed_tools: 预授权工具列表
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"@skill 装饰的函数必须是 async 函数: {func.__name__}")

        skill_info = {
            "name": name,
            "description": description,
            "domain": domain,
            "when_to_use": when_to_use,
            "allowed_tools": allowed_tools or [],
            "func": func,
            "module": func.__module__,
        }

        _inline_skills[name] = skill_info

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        logger.debug("内联技能注册: name=%s, domain=%s", name, domain)
        return wrapper

    return decorator


def get_inline_skill(name: str) -> Optional[Dict[str, Any]]:
    """获取内联技能信息"""
    return _inline_skills.get(name)


def list_inline_skills() -> List[Dict[str, Any]]:
    """列出所有内联技能"""
    return [
        {
            "name": info["name"],
            "description": info["description"],
            "domain": info["domain"],
            "when_to_use": info["when_to_use"],
            "module": info["module"],
        }
        for info in _inline_skills.values()
    ]


async def execute_inline_skill(name: str, **kwargs) -> Any:
    """
    执行内联技能

    Args:
        name: 技能名称
        **kwargs: 传递给技能函数的参数

    Returns:
        技能执行结果

    Raises:
        KeyError: 技能不存在
    """
    info = _inline_skills.get(name)
    if info is None:
        raise KeyError(f"内联技能不存在: {name}")
    return await info["func"](**kwargs)
