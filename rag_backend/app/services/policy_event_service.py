"""
政策通知事件服务

提供政策匹配的实时推送功能

跨进程支持：
- 事件通过 Redis Pub/Sub 广播到所有 worker 进程
- 最近通知持久化到 Redis List（重启不丢失）
- Redis 不可用时自动降级为单进程内存模式（行为与旧版一致）
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Redis 键与频道
REDIS_CHANNEL = "policy_events"
REDIS_RECENT_KEY = "policy_notifications:recent:{enterprise_id}"
RECENT_MAX_LEN = 100              # 每个企业最多保留的最近通知数
RECENT_TTL_SECONDS = 7 * 24 * 3600  # 最近通知保留 7 天
MEMORY_RECENT_MAX_LEN = 200       # 内存降级模式下的上限


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyNotificationEvent":
        """从字典还原事件（用于 Redis 跨进程传输）"""
        event = cls(
            event_type=PolicyEventType(data["event_type"]),
            enterprise_id=data["enterprise_id"],
            policy_id=data.get("policy_id", ""),
            data=data.get("data") or {},
            policy_title=data.get("policy_title"),
            impact_level=data.get("impact_level"),
            match_score=data.get("match_score"),
        )
        event.event_id = data.get("event_id", event.event_id)
        event.timestamp = data.get("timestamp", event.timestamp)
        return event

    def to_sse_data(self) -> str:
        """
        转换为 SSE 格式数据

        包含 event: 命名事件行，前端可通过
        EventSource.addEventListener(event_type, ...) 监听对应事件
        """
        return (
            f"event: {self.event_type.value}\n"
            f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"
        )


class PolicyEventService:
    """
    政策事件服务

    独立管理政策通知事件，支持企业级别订阅。
    多 worker 部署时通过 Redis Pub/Sub 跨进程广播。
    """

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._notifications: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # 内存降级存储
        self._lock = asyncio.Lock()
        self._instance_id = str(uuid.uuid4())  # 进程标识，用于过滤 Redis 回环消息
        self._redis = None
        self._redis_failed = False
        self._listener_task: Optional[asyncio.Task] = None

        logger.info("✅ 政策事件服务初始化完成")

    # ------------------------------------------------------------------
    # Redis 接入（懒加载 + 自动降级）
    # ------------------------------------------------------------------

    async def _get_redis(self):
        """懒加载 Redis 客户端；连接失败则记忆失败状态并降级内存模式"""
        if self._redis is not None or self._redis_failed:
            return self._redis

        try:
            import redis.asyncio as aioredis
            from app.core.config import settings

            client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=10,
            )
            await client.ping()
            self._redis = client
            logger.info("✅ 政策事件服务已接入 Redis Pub/Sub")
        except Exception as e:
            self._redis_failed = True
            self._redis = None
            logger.warning(f"⚠️ Redis 不可用，政策事件降级为单进程内存模式: {e}")

        return self._redis

    async def _ensure_listener(self):
        """确保本进程存在一个 Redis 频道监听任务（接收其他进程发布的事件）"""
        if self._listener_task and not self._listener_task.done():
            return

        redis_client = await self._get_redis()
        if not redis_client:
            return

        self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        """监听 Redis 频道，将其他进程发布的事件分发给本进程的订阅者"""
        backoff = 1

        while True:
            try:
                redis_client = await self._get_redis()
                if not redis_client:
                    return

                pubsub = redis_client.pubsub()
                await pubsub.subscribe(REDIS_CHANNEL)
                logger.info(f"📡 已订阅 Redis 政策事件频道: {REDIS_CHANNEL}")
                backoff = 1

                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        payload = json.loads(message["data"])
                        if payload.pop("_origin", None) == self._instance_id:
                            continue  # 本进程发布的事件已直接分发，跳过回环
                        event = PolicyNotificationEvent.from_dict(payload)
                        await self._dispatch_local(event)
                    except Exception as e:
                        logger.error(f"❌ 解析 Redis 政策事件失败: {e}")

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"⚠️ Redis 监听中断，{backoff}s 后重连: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    # ------------------------------------------------------------------
    # 内部分发与存储
    # ------------------------------------------------------------------

    async def _dispatch_local(self, event: PolicyNotificationEvent):
        """分发事件给本进程内的订阅者"""
        async with self._lock:
            subscribers = self._subscribers.get(event.enterprise_id, set()).copy()

        for queue in subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(f"❌ 政策事件推送失败: {e}")

    async def _store_recent(self, event: PolicyNotificationEvent):
        """最近通知优先存 Redis（跨进程、重启可见），失败时降级内存"""
        event_dict = event.to_dict()

        redis_client = await self._get_redis()
        if redis_client:
            try:
                key = REDIS_RECENT_KEY.format(enterprise_id=event.enterprise_id)
                pipe = redis_client.pipeline()
                pipe.lpush(key, json.dumps(event_dict, ensure_ascii=False))
                pipe.ltrim(key, 0, RECENT_MAX_LEN - 1)
                pipe.expire(key, RECENT_TTL_SECONDS)
                await pipe.execute()
                return
            except Exception as e:
                logger.warning(f"⚠️ Redis 存储通知失败，降级内存: {e}")

        store = self._notifications[event.enterprise_id]
        store.append(event_dict)
        del store[:-MEMORY_RECENT_MAX_LEN]

    # ------------------------------------------------------------------
    # 对外接口（与旧版签名兼容）
    # ------------------------------------------------------------------

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
            count = len(self._subscribers[enterprise_id])

        await self._ensure_listener()
        logger.info(f"🔔 企业订阅政策通知: enterprise_id={enterprise_id}, 当前订阅数={count}")
        return queue

    async def unsubscribe(self, enterprise_id: str, queue: asyncio.Queue):
        """
        取消订阅

        Args:
            enterprise_id: 企业ID
            queue: 事件队列
        """
        async with self._lock:
            self._subscribers[enterprise_id].discard(queue)
            count = len(self._subscribers[enterprise_id])
        logger.info(f"🔕 取消企业订阅: enterprise_id={enterprise_id}, 当前订阅数={count}")

    async def publish(self, event: PolicyNotificationEvent):
        """
        发布政策通知事件

        1. 直接分发给本进程订阅者（Redis 故障不影响单进程可用性）
        2. 持久化到最近通知列表
        3. 通过 Redis 广播给其他 worker 进程

        Args:
            event: 政策通知事件
        """
        await self._dispatch_local(event)
        await self._store_recent(event)

        redis_client = await self._get_redis()
        if redis_client:
            try:
                payload = event.to_dict()
                payload["_origin"] = self._instance_id
                await redis_client.publish(
                    REDIS_CHANNEL,
                    json.dumps(payload, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"⚠️ Redis 广播政策事件失败（本进程推送不受影响）: {e}")

        logger.info(
            f"📤 发布政策事件: {event.event_type.value} - "
            f"enterprise_id={event.enterprise_id}, policy={event.policy_id}"
        )

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
        获取最近的通知（旧 → 新排序，与旧版一致）

        Args:
            enterprise_id: 企业ID
            limit: 返回数量

        Returns:
            List[Dict]: 最近的通知列表
        """
        redis_client = await self._get_redis()
        if redis_client:
            try:
                key = REDIS_RECENT_KEY.format(enterprise_id=enterprise_id)
                items = await redis_client.lrange(key, 0, limit - 1)
                return [json.loads(item) for item in items][::-1]
            except Exception as e:
                logger.warning(f"⚠️ Redis 读取通知失败，降级内存: {e}")

        return self._notifications.get(enterprise_id, [])[-limit:]

    async def get_notification_count(self, enterprise_id: str) -> int:
        """获取最近通知总数"""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                key = REDIS_RECENT_KEY.format(enterprise_id=enterprise_id)
                return int(await redis_client.llen(key))
            except Exception as e:
                logger.warning(f"⚠️ Redis 读取通知数失败，降级内存: {e}")

        return len(self._notifications.get(enterprise_id, []))

    def get_subscriber_count(self, enterprise_id: str) -> int:
        """
        获取订阅者数量（仅统计本进程）

        Args:
            enterprise_id: 企业ID

        Returns:
            int: 订阅者数量
        """
        return len(self._subscribers.get(enterprise_id, set()))


policy_event_service = PolicyEventService()
