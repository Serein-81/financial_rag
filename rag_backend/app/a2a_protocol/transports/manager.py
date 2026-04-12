"""
Transport Manager

传输管理器
自动选择最优传输方式，简化 Agent 通信
"""

import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from enum import Enum

from .base import TransportConfig, TransportType, AgentTransport, TransportError
from .local_transport import LocalAgentTransport
from .http_transport import HttpAgentTransport

logger = logging.getLogger(__name__)


class AgentLocation(str, Enum):
    """Agent 位置"""
    LOCAL = "local"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class TransportManager:
    """
    传输管理器
    
    功能：
    1. 自动选择传输方式（本地 vs HTTP）
    2. 维护传输实例池
    3. 支持 Agent 注册发现
    4. 负载均衡（TODO）
    
    使用示例：
    ```python
    manager = TransportManager()
    
    # 自动选择传输
    result = await manager.send_message(
        to_agent="assistant",
        message={"content": "Hello"},
        tenant_id="tenant_123"
    )
    ```
    """
    
    def __init__(self):
        self._local_transport: Optional[LocalAgentTransport] = None
        self._http_transports: Dict[str, HttpAgentTransport] = {}
        self._agent_registry: Dict[str, AgentLocation] = {}
        self._default_timeout = 30.0
        
        logger.info("🚀 Transport Manager 初始化")
    
    async def initialize(self, message_bus=None) -> None:
        """
        初始化传输管理器
        
        Args:
            message_bus: 可选的消息总线实例
        """
        local_config = TransportConfig(
            transport_type=TransportType.LOCAL,
            timeout=self._default_timeout
        )
        self._local_transport = LocalAgentTransport(local_config, message_bus)
        await self._local_transport.connect()
        
        logger.info("✅ Transport Manager 初始化完成")
    
    def register_local_agent(self, agent_name: str, agent_instance: Any) -> None:
        """
        注册本地 Agent
        
        Args:
            agent_name: Agent 名称
            agent_instance: Agent 实例
        """
        if self._local_transport is None:
            raise TransportError("Transport Manager 未初始化", code=500)
        
        self._local_transport.register_local_agent(agent_name, agent_instance)
        self._agent_registry[agent_name] = AgentLocation.LOCAL
    
    def register_remote_agent(self, agent_name: str, url: str, headers: Dict[str, str] = None) -> None:
        """
        注册远程 Agent
        
        Args:
            agent_name: Agent 名称
            url: Agent 服务地址
            headers: 可选的请求头
        """
        config = TransportConfig(
            transport_type=TransportType.HTTP,
            url=url,
            timeout=self._default_timeout,
            headers=headers or {}
        )
        
        self._http_transports[agent_name] = HttpAgentTransport(config)
        self._agent_registry[agent_name] = AgentLocation.REMOTE
        
        logger.info(f"✅ 注册远程 Agent: {agent_name} -> {url}")
    
    def get_agent_location(self, agent_name: str) -> AgentLocation:
        """
        获取 Agent 位置
        
        Args:
            agent_name: Agent 名称
            
        Returns:
            Agent 位置
        """
        return self._agent_registry.get(agent_name, AgentLocation.UNKNOWN)
    
    def _get_transport(self, agent_name: str) -> AgentTransport:
        """
        获取对应的传输实例
        
        Args:
            agent_name: Agent 名称
            
        Returns:
            传输实例
        """
        location = self.get_agent_location(agent_name)
        
        if location == AgentLocation.LOCAL:
            if self._local_transport is None:
                raise TransportError("本地传输未初始化", code=500)
            return self._local_transport
        
        elif location == AgentLocation.REMOTE:
            if agent_name not in self._http_transports:
                raise TransportError(f"未注册远程 Agent: {agent_name}", code=404)
            return self._http_transports[agent_name]
        
        else:
            raise TransportError(f"未知的 Agent 位置: {agent_name}", code=404)
    
    async def send_message(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        wait_for_response: bool = True
    ) -> Dict[str, Any]:
        """
        发送消息
        
        自动选择最优传输方式：
        1. 本地 Agent -> LocalAgentTransport
        2. 远程 Agent -> HttpAgentTransport
        
        Args:
            to_agent: 目标 Agent
            message: 消息内容
            tenant_id: 租户 ID（用于安全穿透）
            wait_for_response: 是否等待响应
            
        Returns:
            响应消息
        """
        transport = self._get_transport(to_agent)
        
        try:
            if wait_for_response:
                return await transport.send_message(to_agent, message, tenant_id)
            else:
                await transport.send_notification(to_agent, message, tenant_id)
                return {"status": "sent", "agent": to_agent}
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 发送消息数据失败: {e}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"❌ 发送消息IO失败: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 发送消息失败: {e}")
            raise
    
    async def broadcast(
        self,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        exclude_agents: List[str] = None
    ) -> Dict[str, Any]:
        """
        广播消息
        
        发送给所有本地注册的 Agent
        
        Args:
            message: 消息内容
            tenant_id: 租户 ID
            exclude_agents: 排除的 Agent 列表
            
        Returns:
            广播结果
        """
        if self._local_transport is None:
            raise TransportError("本地传输未初始化", code=500)
        
        exclude_agents = exclude_agents or []
        results = {}
        
        for agent_name in self._agent_registry:
            if agent_name in exclude_agents:
                continue
            
            if self._agent_registry[agent_name] == AgentLocation.LOCAL:
                try:
                    result = await self.send_message(agent_name, message, tenant_id)
                    results[agent_name] = result
                except (ValueError, KeyError) as e:
                    results[agent_name] = {"error": f"数据错误: {str(e)}"}
                except (OSError, IOError) as e:
                    results[agent_name] = {"error": f"IO错误: {str(e)}"}
                except Exception as e:
                    results[agent_name] = {"error": str(e)}
        
        return {
            "total": len(results),
            "results": results
        }
    
    async def stream_task_events(
        self,
        to_agent: str,
        task_id: str,
        tenant_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式接收任务事件
        
        Args:
            to_agent: 目标 Agent
            task_id: 任务 ID
            tenant_id: 租户 ID
            
        Yields:
            事件数据
        """
        transport = self._get_transport(to_agent)
        
        async for event in transport.stream_events(task_id, tenant_id):
            yield event
    
    async def subscribe_events(
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
        transport = self._get_transport(agent)
        return await transport.subscribe(agent, event_types, callback, tenant_id)
    
    async def health_check_all(self) -> Dict[str, Any]:
        """
        健康检查所有传输
        
        Returns:
            健康状态
        """
        status = {
            "manager": True,
            "local": False,
            "remote": {}
        }
        
        if self._local_transport:
            status["local"] = await self._local_transport.health_check()
        
        for name, transport in self._http_transports.items():
            status["remote"][name] = await transport.health_check()
        
        return status
    
    async def shutdown(self) -> None:
        """关闭传输管理器"""
        if self._local_transport:
            await self._local_transport.disconnect()
        
        for transport in self._http_transports.values():
            await transport.disconnect()
        
        self._http_transports.clear()
        logger.info("🔌 Transport Manager 已关闭")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "local_agents": sum(1 for loc in self._agent_registry.values() if loc == AgentLocation.LOCAL),
            "remote_agents": sum(1 for loc in self._agent_registry.values() if loc == AgentLocation.REMOTE),
            "http_transports": len(self._http_transports),
            "registry": {name: loc.value for name, loc in self._agent_registry.items()}
        }


_transport_manager_instance: Optional[TransportManager] = None


async def get_transport_manager() -> TransportManager:
    """
    获取传输管理器单例
    
    Returns:
        TransportManager 实例
    """
    global _transport_manager_instance
    
    if _transport_manager_instance is None:
        _transport_manager_instance = TransportManager()
        await _transport_manager_instance.initialize()
    
    return _transport_manager_instance


async def shutdown_transport_manager() -> None:
    """关闭传输管理器"""
    global _transport_manager_instance
    
    if _transport_manager_instance:
        await _transport_manager_instance.shutdown()
        _transport_manager_instance = None
