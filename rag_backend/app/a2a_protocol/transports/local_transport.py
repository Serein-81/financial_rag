"""
Local Agent Transport

本地传输实现
复用 message_bus 实现同进程 Agent 间的通信
"""

import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator, List

from .base import TransportConfig, AgentTransport, TransportError
from ..models import TaskSubmitParams

logger = logging.getLogger(__name__)


class LocalAgentTransport(AgentTransport):
    """
    本地传输
    
    特点：
    1. 零网络开销 - 直接内存通信
    2. 低延迟 - 微秒级响应
    3. 高吞吐 - 无序列化/反序列化
    4. 自动复用 message_bus
    
    适用场景：
    - 同进程内的 Agent 通信
    - 微服务架构的同节点部署
    - 开发/测试环境
    """
    
    def __init__(self, config: TransportConfig, message_bus=None):
        super().__init__(config)
        self.message_bus = message_bus
        self._local_agents: Dict[str, Any] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._subscriptions: Dict[str, str] = {}
    
    def register_local_agent(self, agent_name: str, agent_instance: Any) -> None:
        """
        注册本地 Agent
        
        Args:
            agent_name: Agent 名称
            agent_instance: Agent 实例
        """
        self._local_agents[agent_name] = agent_instance
        logger.info(f"✅ 注册本地 Agent: {agent_name}")
    
    def unregister_local_agent(self, agent_name: str) -> None:
        """
        注销本地 Agent
        
        Args:
            agent_name: Agent 名称
        """
        if agent_name in self._local_agents:
            del self._local_agents[agent_name]
            logger.info(f"🗑️ 注销本地 Agent: {agent_name}")
    
    async def connect(self) -> None:
        """建立连接"""
        if self._connected:
            return
        
        if self.message_bus is None:
            from app.multi_agent_system.message_bus import MessageBus
            self.message_bus = MessageBus()
        
        self._connected = True
        logger.info("🔗 Local Transport 连接成功")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if not self._connected:
            return
        
        self._connected = False
        logger.info("🔌 Local Transport 连接断开")
    
    async def send_message(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息（同步请求-响应模式）
        
        使用 message_bus 的 send_request 机制
        """
        if not self._connected:
            await self.connect()
        
        if to_agent in self._local_agents:
            return await self._handle_local_message(to_agent, message, tenant_id)
        
        return await self._send_via_message_bus(to_agent, message, tenant_id)
    
    async def _handle_local_message(
        self,
        agent_name: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理本地消息（直接调用）
        
        绕过 message_bus，直接调用本地 Agent
        """
        try:
            agent = self._local_agents[agent_name]
            
            if hasattr(agent, "process_message"):
                result = await agent.process_message(message)
                return result
            elif hasattr(agent, "handle_task"):
                params = TaskSubmitParams(**message.get("params", {}))
                result = await agent.handle_task(params)
                return result.model_dump()
            else:
                raise TransportError(
                    f"Agent {agent_name} 没有可调用的方法",
                    code=500
                )
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 本地消息处理数据失败: {e}")
            raise TransportError(f"本地消息处理数据失败: {str(e)}", code=500)
        except (OSError, IOError) as e:
            logger.error(f"❌ 本地消息处理IO失败: {e}")
            raise TransportError(f"本地消息处理IO失败: {str(e)}", code=500)
        except Exception as e:
            logger.error(f"❌ 本地消息处理失败: {e}")
            raise TransportError(f"本地消息处理失败: {str(e)}", code=500)
    
    async def _send_via_message_bus(
        self,
        agent_name: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        通过 message_bus 发送消息
        
        用于同进程但非直接注册的 Agent
        """
        try:
            response = await self.message_bus.send_request(
                from_agent=message.get("from_agent", "unknown"),
                to_agent=agent_name,
                request_content=message,
                timeout=self.config.timeout,
                tenant_id=tenant_id
            )
            
            if response is None:
                raise TransportError(f"请求超时: {agent_name}", code=504)
            
            return response.content
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Message Bus 发送数据失败: {e}")
            raise TransportError(f"消息发送数据失败: {str(e)}", code=500)
        except (OSError, IOError) as e:
            logger.error(f"❌ Message Bus 发送IO失败: {e}")
            raise TransportError(f"消息发送IO失败: {str(e)}", code=500)
        except Exception as e:
            logger.error(f"❌ Message Bus 发送失败: {e}")
            raise TransportError(f"消息发送失败: {str(e)}", code=500)
    
    async def send_notification(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> None:
        """
        发送通知（单向消息）
        
        使用 message_bus 的 publish 机制
        """
        if not self._connected:
            await self.connect()
        
        from rag_backend.app.multi_agent_system.message_bus import MessageType
        
        await self.message_bus.publish(
            from_agent=message.get("from_agent", "unknown"),
            to_agent=to_agent,
            message_type=MessageType.NOTIFICATION,
            content=message,
            tenant_id=tenant_id
        )
    
    async def subscribe(
        self,
        agent: str,
        event_types: List[str],
        callback,
        tenant_id: Optional[str] = None
    ) -> str:
        """
        订阅事件
        
        在 message_bus 上注册订阅
        """
        if not self._connected:
            await self.connect()
        
        subscription_id = f"{agent}:{':'.join(event_types)}"
        
        self.message_bus.subscribe(agent, callback)
        self._subscriptions[subscription_id] = agent
        
        logger.info(f"📥 订阅事件: {subscription_id}")
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        if subscription_id in self._subscriptions:
            agent = self._subscriptions[subscription_id]
            self.message_bus.unsubscribe(agent)
            del self._subscriptions[subscription_id]
            logger.info(f"📤 取消订阅: {subscription_id}")
    
    async def stream_events(
        self,
        task_id: str,
        tenant_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式接收事件
        
        本地传输使用队列轮询模拟 SSE
        """
        if not self._connected:
            await self.connect()
        
        last_index = 0
        
        while self._connected:
            messages = await self.message_bus.get_messages(
                agent_name=f"task:{task_id}",
                limit=10,
                clear_queue=False
            )
            
            for msg in messages[last_index:]:
                yield msg.content
                last_index += 1
            
            await asyncio.sleep(0.1)
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self._connected and self.message_bus is not None
    
    def get_local_agents(self) -> List[str]:
        """
        获取所有本地注册的 Agent
        
        Returns:
            Agent 名称列表
        """
        return list(self._local_agents.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取传输统计信息
        
        Returns:
            统计信息
        """
        return {
            "type": "local",
            "connected": self._connected,
            "local_agents": len(self._local_agents),
            "subscriptions": len(self._subscriptions),
            "pending_requests": len(self._pending_requests),
        }
