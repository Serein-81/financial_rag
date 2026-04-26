"""
Transport Strategy Interface

策略模式接口定义
将传输层从具体实现中解耦，支持运行时切换传输模式
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, AsyncGenerator, List, Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class TransportMode(str, Enum):
    """传输模式枚举"""
    GRAPH_STATE = "graph_state"    # LangGraph 状态黑板模式（当前 MVP）
    HTTP = "http"                  # HTTP 远程调用（未来微服务）
    LOCAL = "local"                # 本地进程通信


class TransportStrategy(ABC):
    """
    传输策略抽象接口
    
    定义传输层的标准行为，支持：
    1. 发送消息（同步/异步）
    2. 订阅事件
    3. 健康检查
    
    设计理念：
    - 不依赖具体传输实现
    - 支持状态黑板模式和 HTTP 模式
    - 提供统一的接口契约
    """

    def __init__(self, mode: TransportMode):
        self._mode = mode
        self._connected: bool = False
        logger.info(f"📡 TransportStrategy 初始化: {mode.value}")

    @property
    def mode(self) -> TransportMode:
        """获取传输模式"""
        return self._mode

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def send_message(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        state_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送消息

        Args:
            to_agent: 目标 Agent 名称
            message: 消息内容（A2A Payload）
            tenant_id: 租户 ID
            state_context: 状态上下文（用于 GRAPH_STATE 模式）

        Returns:
            响应消息
        """
        pass

    @abstractmethod
    async def send_notification(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        state_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        发送通知（单向消息）

        Args:
            to_agent: 目标 Agent 名称
            message: 消息内容
            tenant_id: 租户 ID
            state_context: 状态上下文
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        agent: str,
        event_types: List[str],
        callback: Callable,
        tenant_id: Optional[str] = None
    ) -> str:
        """
        订阅事件

        Args:
            agent: Agent 名称
            event_types: 事件类型列表
            callback: 回调函数
            tenant_id: 租户 ID

        Returns:
            订阅 ID
        """
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        pass

    @abstractmethod
    async def stream_events(
        self,
        task_id: str,
        tenant_id: Optional[str] = None,
        state_context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式接收事件

        Args:
            task_id: 任务 ID
            tenant_id: 租户 ID
            state_context: 状态上下文

        Yields:
            事件数据
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """获取传输元数据"""
        return {
            "mode": self._mode.value,
            "connected": self._connected,
        }


@dataclass
class TransportEnvelope:
    """
    A2A 消息信封

    将 A2A Payload 封装为标准信封格式
    用于跨传输模式传递
    """
    task_id: str
    from_agent: str
    to_agent: str
    message: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    tenant_id: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message": self.message,
            "metadata": self.metadata,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransportEnvelope":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", ""),
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", ""),
            message=data.get("message", {}),
            metadata=data.get("metadata", {}),
            tenant_id=data.get("tenant_id"),
            timestamp=data.get("timestamp"),
        )