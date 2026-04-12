"""
工具基类模块

定义所有工具的基类，提供统一的工具接口
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    tags: list = field(default_factory=list)


class ToolBase(ABC):
    """工具基类

    所有工具都应该继承此类并实现 execute 方法
    """

    def __init__(
        self,
        name: str,
        description: str,
        timeout: int = 30,
        tags: Optional[list] = None
    ):
        """
        初始化工具基类

        Args:
            name: 工具名称
            description: 工具描述
            timeout: 超时时间（秒）
            tags: 工具标签
        """
        self.name = name
        self.description = description
        self.timeout = timeout
        self.tags = tags or []

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具的核心逻辑

        Args:
            **kwargs: 工具执行参数

        Returns:
            工具执行结果
        """
        pass

    def get_metadata(self) -> ToolMetadata:
        """获取工具元数据"""
        return ToolMetadata(
            name=self.name,
            description=self.description,
            timeout=self.timeout,
            tags=self.tags
        )

    async def validate_params(self, **kwargs) -> bool:
        """
        验证工具参数

        Args:
            **kwargs: 待验证的参数

        Returns:
            参数是否有效
        """
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"


class registry:
    """工具注册表

    用于注册和查找工具
    """
    _tools: Dict[str, ToolBase] = {}

    @classmethod
    def register(cls, tool: ToolBase):
        """注册工具"""
        cls._tools[tool.name] = tool
        logger.info(f"注册工具: {tool.name}")

    @classmethod
    def get(cls, name: str) -> Optional[ToolBase]:
        """获取工具"""
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list:
        """列出所有工具"""
        return list(cls._tools.keys())

    @classmethod
    def clear(cls):
        """清空注册表"""
        cls._tools.clear()
