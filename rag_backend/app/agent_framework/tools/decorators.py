"""
工具自动注册装饰器

提供 @auto_register_tool 装饰器，自动发现和注册工具。
"""

from typing import Callable, Optional, Dict, Any, List
import inspect
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# 全局工具注册表
_AUTO_REGISTER_TOOLS: List[Dict[str, Any]] = []


def auto_register_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    tags: Optional[List[str]] = None,
    enabled: bool = True,
    timeout: int = 30
):
    """
    自动注册工具装饰器

    使用方式:
    ```python
    @auto_register_tool(
        name="calculate_tax",
        description="计算企业所得税",
        category="tax",
        tags=["税务", "计算"]
    )
    async def calculate_tax(income: float, rate: float = 0.25) -> float:
        return income * rate
    ```

    Args:
        name: 工具名称，默认使用函数名
        description: 工具描述，默认使用函数 docstring
        category: 工具分类
        tags: 工具标签列表
        enabled: 是否启用
        timeout: 超时时间（秒）

    Returns:
        装饰后的函数
    """

    def decorator(func: Callable):
        # 自动提取信息
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip().split('\n')[0]

        # 提取参数信息
        sig = inspect.signature(func)
        parameters = {}

        for param_name, param in sig.parameters.items():
            param_info = {
                "type": "string",  # 默认类型
                "required": param.default == inspect.Parameter.empty,
                "description": f"{param_name} 参数"
            }

            # 从类型注解推断类型
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation

                # 处理基本类型
                if annotation is str or annotation == "str":
                    param_info["type"] = "string"
                elif annotation is int or annotation == "int":
                    param_info["type"] = "integer"
                elif annotation is float or annotation == "float":
                    param_info["type"] = "number"
                elif annotation is bool or annotation == "bool":
                    param_info["type"] = "boolean"
                elif hasattr(annotation, "__origin__"):
                    # 处理泛型类型 (如 List[str])
                    param_info["type"] = "array"
                else:
                    param_info["type"] = "string"

            # 添加默认值
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
                param_info["required"] = False

            parameters[param_name] = param_info

        # 收集元数据
        metadata = {
            "name": tool_name,
            "description": tool_desc,
            "parameters": parameters,
            "category": category,
            "tags": tags or [],
            "enabled": enabled,
            "timeout": timeout,
            "func": func,
            "source_file": inspect.getfile(func) if hasattr(func, "__code__") else "unknown",
            "is_async": inspect.iscoroutinefunction(func)
        }

        # 注册到全局列表
        _AUTO_REGISTER_TOOLS.append(metadata)

        # 标记函数，方便后续识别
        func._auto_register_metadata = metadata

        # 保留原函数行为
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # 根据原函数是否异步选择包装器
        if inspect.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        # 复制元数据到包装器
        wrapper._auto_register_metadata = metadata

        return wrapper

    return decorator


def get_auto_registered_tools() -> List[Dict[str, Any]]:
    """
    获取所有自动注册的工具

    Returns:
        工具元数据列表
    """
    return _AUTO_REGISTER_TOOLS.copy()


def clear_auto_registered_tools():
    """清空已注册工具列表（主要用于测试）"""
    global _AUTO_REGISTER_TOOLS
    _AUTO_REGISTER_TOOLS.clear()


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    根据名称获取工具元数据

    Args:
        name: 工具名称

    Returns:
        工具元数据，如果不存在返回 None
    """
    for tool in _AUTO_REGISTER_TOOLS:
        if tool["name"] == name:
            return tool
    return None
