"""
工具基类 - 提供统一的工具注册、超时、错误处理机制
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """工具执行错误"""
    pass


class ToolTimeoutError(ToolExecutionError):
    """工具执行超时"""
    pass


class ToolBase(ABC):
    """工具基类"""

    def __init__(self, name: str, description: str, timeout: int = 60):
        self.name = name
        self.description = description
        self.timeout = timeout
        self._call_count = 0
        self._error_count = 0
        self._total_time = 0.0

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具的核心逻辑，子类必须实现"""
        pass

    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        运行工具，包含超时、错误处理、统计
        """
        self._call_count += 1
        start_time = asyncio.get_event_loop().time()

        try:
            result = await asyncio.wait_for(
                self.execute(**kwargs),
                timeout=self.timeout
            )
            elapsed = asyncio.get_event_loop().time() - start_time
            self._total_time += elapsed

            logger.info(f"✅ 工具 {self.name} 执行成功 ({elapsed:.2f}s)")

            return {
                "success": True,
                "result": result,
                "tool_name": self.name,
                "elapsed_time": round(elapsed, 3),
                "timestamp": datetime.now().isoformat()
            }

        except asyncio.TimeoutError:
            self._error_count += 1
            elapsed = asyncio.get_event_loop().time() - start_time
            self._total_time += elapsed

            logger.error(f"⏰ 工具 {self.name} 执行超时 ({self.timeout}s)")

            return {
                "success": False,
                "error": f"工具执行超时 ({self.timeout}s)",
                "error_type": "timeout",
                "tool_name": self.name,
                "elapsed_time": round(elapsed, 3),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self._error_count += 1
            elapsed = asyncio.get_event_loop().time() - start_time
            self._total_time += elapsed

            logger.error(f"❌ 工具 {self.name} 执行失败: {str(e)}")

            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "tool_name": self.name,
                "elapsed_time": round(elapsed, 3),
                "timestamp": datetime.now().isoformat()
            }

    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        avg_time = self._total_time / self._call_count if self._call_count > 0 else 0
        error_rate = self._error_count / self._call_count if self._call_count > 0 else 0

        return {
            "name": self.name,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "error_rate": round(error_rate * 100, 2),
            "total_time": round(self._total_time, 2),
            "avg_time": round(avg_time, 3)
        }

    def reset_stats(self):
        """重置统计"""
        self._call_count = 0
        self._error_count = 0
        self._total_time = 0.0


class ToolRegistry:
    """工具注册表 - 管理所有可用工具"""

    def __init__(self):
        self._tools: Dict[str, ToolBase] = {}

    def register(self, tool: ToolBase):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"📝 工具已注册: {tool.name}")

    def get(self, name: str) -> Optional[ToolBase]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list:
        """列出所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "timeout": tool.timeout
            }
            for tool in self._tools.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取所有工具统计"""
        return {
            "total_tools": len(self._tools),
            "tools": [tool.get_stats() for tool in self._tools.values()]
        }


registry = ToolRegistry()
