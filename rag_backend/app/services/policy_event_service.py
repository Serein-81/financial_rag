"""
政策通知事件服务

提供政策匹配的实时推送功能
基于 WorkflowEventService 扩展企业级别订阅
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Set, List
from datetime import datetime
from enum import Enum
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


class PolicyEventType(str, Enum):
    """政策事件类型"""
    POLICY_MATCHED = "policy_matched"
    POLICY_NOTIFICATION_SENT = "policy_notification_sent"
    POLICY_NOTIFICATION_ACKNOWLEDGED = "policy_notification_acknowledged"
    POLICY_HIGH_PRIORITY = "policy_high_priority"
    POLICY_DEADLINE_REMINDER = "policy_deadline_reminder"


class PolicyNotificationEvent:
    """政策通知事件"""
    
    def __init__(
        self,
        event_type: PolicyEventType,
        enterprise_id: str,
        policy_id: str,
        data: Optional[Dict[str, Any]] = None,
        policy_title: Optional[str] = None,
        impact_level: Optional[str] = None,
        match_score: Optional[float] = None
    ):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.enterprise_id = enterprise_id
        self.policy_id = policy_id
        self.timestamp = datetime.now().isoformat()
        self.data = data or {}
        self.policy_title = policy_title
        self.impact_level = impact_level
        self.match_score = match_score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "enterprise_id": self.enterprise_id,
            "policy_id": self.policy_id,
            "timestamp": self.timestamp,
            "policy_title": self.policy_title,
            "impact_level": self.impact_level,
            "match_score": self.match_score,
            "data": self.data
        }
    
    def to_sse_data(self) -> str:
        """转换为 SSE 格式数据"""
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class PolicyEventService:
    """
    政策事件服务
    
    独立管理政策通知事件，支持企业级别订阅
    """
    
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._notifications: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()
        
        logger.info("✅ 政策事件服务初始化完成")
    
    async def subscribe(self, enterprise_id: str) -> asyncio.Queue:
        """
        订阅企业政策通知
        
        Args:
            enterprise_id: 企业ID
            
        Returns:
            asyncio.Queue: 事件队列
        """
        queue = asyncio.Queue()
        async with self._lock:
            self._subscribers[enterprise_id].add(queue)
            logger.info(f"🔔 企业订阅政策通知: enterprise_id={enterprise_id}, 当前订阅数={len(self._subscribers[enterprise_id])}")
        
        return queue
    
    async def unsubscribe(self, enterprise_id: str, queue: asyncio.Queue):
        """
        取消订阅
        
        Args:
            enterprise_id: 企业ID
            queue: 事件队列
        """
        async with self._lock:
            if queue in self._subscribers[enterprise_id]:
                self._subscribers[enterprise_id].discard(queue)
                logger.info(f"🔕 取消企业订阅: enterprise_id={enterprise_id}, 当前订阅数={len(self._subscribers[enterprise_id])}")
    
    async def publish(self, event: PolicyNotificationEvent):
        """
        发布政策通知事件
        
        Args:
            event: 政策通知事件
        """
        async with self._lock:
            subscribers = self._subscribers.get(event.enterprise_id, set()).copy()
        
        if not subscribers:
            logger.debug(f"📭 没有订阅者: enterprise_id={event.enterprise_id}")
            self._notifications[event.enterprise_id].append(event.to_dict())
            return
        
        logger.info(f"📤 发布政策事件: {event.event_type.value} - enterprise_id={event.enterprise_id}, policy={event.policy_id}")
        
        for queue in subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(f"❌ 政策事件推送失败: {e}")
        
        self._notifications[event.enterprise_id].append(event.to_dict())
    
    async def emit_policy_matched(
        self,
        enterprise_id: str,
        policy_id: str,
        policy_title: str,
        match_score: float,
        impact_level: str,
        match_details: Optional[Dict[str, Any]] = None
    ):
        """
        发射政策匹配事件
        
        Args:
            enterprise_id: 企业ID
            policy_id: 政策ID
            policy_title: 政策标题
            match_score: 匹配分数
            impact_level: 影响级别
            match_details: 匹配详情
        """
        event = PolicyNotificationEvent(
            event_type=PolicyEventType.POLICY_MATCHED,
            enterprise_id=enterprise_id,
            policy_id=policy_id,
            policy_title=policy_title,
            match_score=match_score,
            impact_level=impact_level,
            data=match_details or {}
        )
        
        await self.publish(event)
    
    async def emit_notification_sent(
        self,
        enterprise_id: str,
        policy_id: str,
        policy_title: str,
        notification_id: str
    ):
        """
        发射通知已发送事件
        
        Args:
            enterprise_id: 企业ID
            policy_id: 政策ID
            policy_title: 政策标题
            notification_id: 通知ID
        """
        event = PolicyNotificationEvent(
            event_type=PolicyEventType.POLICY_NOTIFICATION_SENT,
            enterprise_id=enterprise_id,
            policy_id=policy_id,
            policy_title=policy_title,
            data={"notification_id": notification_id}
        )
        
        await self.publish(event)
    
    async def get_recent_notifications(
        self,
        enterprise_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取最近的通知
        
        Args:
            enterprise_id: 企业ID
            limit: 返回数量
            
        Returns:
            List[Dict]: 最近的通知列表
        """
        notifications = self._notifications.get(enterprise_id, [])
        return notifications[-limit:]
    
    def get_subscriber_count(self, enterprise_id: str) -> int:
        """
        获取订阅者数量
        
        Args:
            enterprise_id: 企业ID
            
        Returns:
            int: 订阅者数量
        """
        return len(self._subscribers.get(enterprise_id, set()))


policy_event_service = PolicyEventService()
