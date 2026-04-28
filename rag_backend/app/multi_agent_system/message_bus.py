"""
消息总线 (Message Bus)
用于 Agent 间的通信和协作
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"


@dataclass
class AgentMessage:
    """Agent 消息"""
    id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime
    task_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "tenant_id": self.tenant_id
        }


class MessageBus:
    """
    消息总线
    
    功能：
    1. 发布/订阅模式
    2. 消息路由
    3. 消息持久化
    4. 消息队列管理
    """
    
    def __init__(self):
        """初始化消息总线"""
        # 订阅者字典: {agent_name: [callback_functions]}
        self.subscribers: Dict[str, List[Callable]] = {}
        
        # 消息队列: {agent_name: [messages]}
        self.message_queues: Dict[str, List[AgentMessage]] = {}
        
        # 消息历史（用于调试和审计）
        self.message_history: List[AgentMessage] = []
        
        # 异步锁
        self.lock = asyncio.Lock()
        
        logger.debug("Message bus initialized")
    
    async def publish(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        content: Dict[str, Any],
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """
        发布消息
        
        Args:
            from_agent: 发送方 Agent
            to_agent: 接收方 Agent（"*" 表示广播）
            message_type: 消息类型
            content: 消息内容
            task_id: 任务 ID
            tenant_id: 租户 ID
            
        Returns:
            消息 ID
        """
        message = AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            timestamp=datetime.utcnow(),
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        async with self.lock:
            # 添加到历史记录
            self.message_history.append(message)
            
            # 路由消息
            if to_agent == "*":
                # 广播消息
                await self._broadcast_message(message)
            else:
                # 单播消息
                await self._unicast_message(message)
        
        print(f"📤 [消息总线] {from_agent} → {to_agent}: {message_type.value}")
        return message.id
    
    async def _broadcast_message(self, message: AgentMessage):
        """广播消息"""
        for agent_name in self.subscribers.keys():
            if agent_name != message.from_agent:  # 不发送给自己
                await self._deliver_message(agent_name, message)
    
    async def _unicast_message(self, message: AgentMessage):
        """单播消息"""
        await self._deliver_message(message.to_agent, message)
    
    async def _deliver_message(self, agent_name: str, message: AgentMessage):
        """投递消息"""
        # 添加到消息队列
        if agent_name not in self.message_queues:
            self.message_queues[agent_name] = []
        self.message_queues[agent_name].append(message)
        
        # 通知订阅者
        if agent_name in self.subscribers:
            for callback in self.subscribers[agent_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    print(f"❌ [消息总线] 回调执行失败: {e}")
    
    def subscribe(self, agent_name: str, callback: Callable):
        """
        订阅消息
        
        Args:
            agent_name: Agent 名称
            callback: 回调函数
        """
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = []
        
        self.subscribers[agent_name].append(callback)
        print(f"📥 [消息总线] {agent_name} 订阅成功")
    
    def unsubscribe(self, agent_name: str, callback: Callable = None):
        """
        取消订阅
        
        Args:
            agent_name: Agent 名称
            callback: 回调函数（None 表示取消所有订阅）
        """
        if agent_name not in self.subscribers:
            return
        
        if callback is None:
            # 取消所有订阅
            del self.subscribers[agent_name]
        else:
            # 取消特定回调
            if callback in self.subscribers[agent_name]:
                self.subscribers[agent_name].remove(callback)
        
        print(f"📤 [消息总线] {agent_name} 取消订阅")
    
    async def get_messages(
        self,
        agent_name: str,
        limit: int = 10,
        clear_queue: bool = True
    ) -> List[AgentMessage]:
        """
        获取消息
        
        Args:
            agent_name: Agent 名称
            limit: 消息数量限制
            clear_queue: 是否清空队列
            
        Returns:
            消息列表
        """
        async with self.lock:
            if agent_name not in self.message_queues:
                return []
            
            messages = self.message_queues[agent_name][-limit:]
            
            if clear_queue:
                self.message_queues[agent_name] = []
            
            return messages
    
    async def send_request(
        self,
        from_agent: str,
        to_agent: str,
        request_content: Dict[str, Any],
        timeout: float = 30.0,
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[AgentMessage]:
        """
        发送请求并等待响应
        
        Args:
            from_agent: 发送方
            to_agent: 接收方
            request_content: 请求内容
            timeout: 超时时间
            task_id: 任务 ID
            tenant_id: 租户 ID
            
        Returns:
            响应消息
        """
        # 生成请求 ID
        request_id = str(uuid.uuid4())
        request_content["request_id"] = request_id
        
        # 发送请求
        await self.publish(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            content=request_content,
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        # 等待响应
        start_time = asyncio.get_event_loop().time()
        while True:
            # 检查超时
            if asyncio.get_event_loop().time() - start_time > timeout:
                print(f"⏰ [消息总线] 请求超时: {from_agent} → {to_agent}")
                return None
            
            # 检查响应
            messages = await self.get_messages(from_agent, clear_queue=False)
            for message in messages:
                if (message.message_type == MessageType.RESPONSE and
                    message.from_agent == to_agent and
                    message.content.get("request_id") == request_id):
                    
                    # 从队列中移除这条消息
                    async with self.lock:
                        if from_agent in self.message_queues:
                            self.message_queues[from_agent].remove(message)
                    
                    return message
            
            # 短暂等待
            await asyncio.sleep(0.1)
    
    async def send_response(
        self,
        from_agent: str,
        to_agent: str,
        request_id: str,
        response_content: Dict[str, Any],
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ):
        """
        发送响应
        
        Args:
            from_agent: 发送方
            to_agent: 接收方
            request_id: 请求 ID
            response_content: 响应内容
            task_id: 任务 ID
            tenant_id: 租户 ID
        """
        response_content["request_id"] = request_id
        
        await self.publish(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.RESPONSE,
            content=response_content,
            task_id=task_id,
            tenant_id=tenant_id
        )
    
    async def persist_messages(self, db_session):
        """
        持久化消息到数据库
        
        Args:
            db_session: 数据库会话
        """
        try:
            from app.models.agent_collaboration import AgentCollaboration
            
            async with self.lock:
                # 获取未持久化的消息
                messages_to_persist = [
                    msg for msg in self.message_history
                    if msg.task_id  # 只持久化有任务 ID 的消息
                ]
                
                # 批量插入数据库
                for message in messages_to_persist:
                    collaboration = AgentCollaboration(
                        task_id=message.task_id,
                        tenant_id=message.tenant_id,
                        from_agent=message.from_agent,
                        to_agent=message.to_agent,
                        message_type=message.message_type.value,
                        message_content=message.content,
                        timestamp=message.timestamp
                    )
                    db_session.add(collaboration)
                
                await db_session.commit()
                print(f"💾 [消息总线] 持久化 {len(messages_to_persist)} 条消息")
                
        except Exception as e:
            print(f"❌ [消息总线] 消息持久化失败: {e}")
            await db_session.rollback()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_messages": len(self.message_history),
            "active_subscribers": len(self.subscribers),
            "queued_messages": sum(len(queue) for queue in self.message_queues.values()),
            "message_types": {
                msg_type.value: sum(1 for msg in self.message_history if msg.message_type == msg_type)
                for msg_type in MessageType
            }
        }
    
    def clear_history(self, keep_recent: int = 100):
        """
        清理历史消息
        
        Args:
            keep_recent: 保留最近的消息数量
        """
        if len(self.message_history) > keep_recent:
            self.message_history = self.message_history[-keep_recent:]
            print(f"🧹 [消息总线] 清理历史消息，保留最近 {keep_recent} 条")
