"""
MCP 工具装饰器

提供自定义装饰器来标记工具类型：
- @local_tool: 标记为本地 STDIO MCP 工具
- @cloud_tool: 标记为云端 MCP HTTP 工具

使用示例：
    @local_tool(description="查询数据库")
    async def query_database(...):
        ...
    
    @cloud_tool(description="计算税务")
    async def calculate_tax(...):
        ...
"""

import logging
from typing import Callable, Optional, Any, Dict, List, TypeVar
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


class ToolSource(Enum):
    """工具来源"""
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    source: ToolSource
    tags: List[str] = field(default_factory=list)
    timeout: int = 30


TOOL_REGISTRY: Dict[str, ToolMetadata] = {}


def local_tool(
    description: str = "",
    name: str = None,
    tags: List[str] = None,
    timeout: int = 30
):
    """
    装饰器：标记为本地 STDIO MCP 工具
    
    适用于需要访问本地数据库的工具
    
    Args:
        description: 工具描述
        name: 工具名称，默认使用函数名
        tags: 工具标签
        timeout: 超时时间（秒）
    
    Returns:
        装饰器函数
    """
    def decorator(func: F) -> F:
        tool_name = name or func.__name__
        
        metadata = ToolMetadata(
            name=tool_name,
            description=description or func.__doc__ or "",
            source=ToolSource.LOCAL,
            tags=tags or [],
            timeout=timeout
        )
        
        TOOL_REGISTRY[tool_name] = metadata
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._tool_metadata = metadata
        wrapper._tool_source = ToolSource.LOCAL
        wrapper.name = tool_name
        wrapper.description = metadata.description
        
        logger.debug(f"注册本地工具: {tool_name}")
        
        return wrapper
    
    return decorator


def cloud_tool(
    description: str = "",
    name: str = None,
    tags: List[str] = None,
    timeout: int = 30
):
    """
    装饰器：标记为云端 MCP HTTP 工具
    
    适用于需要访问外部 API 或纯计算的工具
    
    Args:
        description: 工具描述
        name: 工具名称，默认使用函数名
        tags: 工具标签
        timeout: 超时时间（秒）
    
    Returns:
        装饰器函数
    """
    def decorator(func: F) -> F:
        tool_name = name or func.__name__
        
        metadata = ToolMetadata(
            name=tool_name,
            description=description or func.__doc__ or "",
            source=ToolSource.CLOUD,
            tags=tags or [],
            timeout=timeout
        )
        
        TOOL_REGISTRY[tool_name] = metadata
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._tool_metadata = metadata
        wrapper._tool_source = ToolSource.CLOUD
        wrapper.name = tool_name
        wrapper.description = metadata.description
        
        logger.debug(f"注册云端工具: {tool_name}")
        
        return wrapper
    
    return decorator


def get_tool_metadata(func: Callable) -> Optional[ToolMetadata]:
    """获取工具元数据"""
    return getattr(func, '_tool_metadata', None)


def get_tool_source(func: Callable) -> Optional[ToolSource]:
    """获取工具来源"""
    return getattr(func, '_tool_source', None)


def get_registry() -> Dict[str, ToolMetadata]:
    """获取工具注册表"""
    return TOOL_REGISTRY.copy()


def clear_registry():
    """清空工具注册表"""
    global TOOL_REGISTRY
    TOOL_REGISTRY = {}
