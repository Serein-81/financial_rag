"""
A2A Transport Base

传输层抽象基类
定义统一的传输接口，支持多种传输方式
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, AsyncGenerator, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TransportType(str, Enum):
    """传输类型枚举"""
    LOCAL = "local"
    HTTP = "http"
    SSE = "sse"
    GRAPHQL = "graphql"


@dataclass
class TransportConfig:
    """传输配置"""
    transport_type: TransportType
    url: Optional[str] = None
    timeout: float = 30.0
    retry_times: int = 3
    retry_delay: float = 1.0
    max_connections: int = 100
    headers: Dict[str, str] = field(default_factory=dict)
    ssl_verify: bool = True
    compression: bool = True


class TransportError(Exception):
    """传输错误"""
    
    def __init__(self, message: str, code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class AgentTransport(ABC):
    """
    Agent 传输基类
    
    定义统一的传输接口
    所有传输实现必须继承此类
    """
    
    def __init__(self, config: TransportConfig):
        self.config = config
        self._connected: bool = False
        logger.info(f"🚀 Transport 初始化: {self.__class__.__name__}")
    
    @property
    def transport_type(self) -> TransportType:
        """获取传输类型"""
        return self.config.transport_type
    
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
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息（同步请求-响应模式）
        
        Args:
            to_agent: 目标 Agent 名称
            message: 消息内容
            tenant_id: 租户 ID（用于多租户穿透）
            
        Returns:
            响应消息
        """
        pass
    
    @abstractmethod
    async def send_notification(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> None:
        """
        发送通知（单向消息，不需要响应）
        
        Args:
            to_agent: 目标 Agent 名称
            message: 消息内容
            tenant_id: 租户 ID
        """
        pass
    
    @abstractmethod
    async def subscribe(
        self,
        agent: str,
        event_types: List[str],
        callback,
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
        """
        取消订阅
        
        Args:
            subscription_id: 订阅 ID
        """
        pass
    
    @abstractmethod
    async def stream_events(
        self,
        task_id: str,
        tenant_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式接收事件（SSE 模式）
        
        Args:
            task_id: 任务 ID
            tenant_id: 租户 ID
            
        Yields:
            事件数据
        """
        pass
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            是否健康
        """
        try:
            return self._connected
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 健康检查数据失败: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 健康检查IO失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 健康检查失败: {e}")
            return False
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取传输元数据
        
        Returns:
            元数据字典
        """
        return {
            "type": self.transport_type.value,
            "connected": self._connected,
            "url": self.config.url,
            "timeout": self.config.timeout,
        }
