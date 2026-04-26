"""
LangGraph State Transport

LangGraph 状态黑板模式的传输实现

特点：
1. 不发网络请求，不调内存指针
2. 将 A2A Payload 打包成标准信封
3. 追加到 LangGraph 的 State 黑板里

设计理念：
- 纯函数式状态操作
- 与 LangGraph 的状态管理无缝集成
- 支持 A2A Task 模型作为状态载体
"""

import logging
from typing import Optional, Dict, Any, AsyncGenerator, List, Callable, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

from .strategy import TransportStrategy, TransportMode, TransportEnvelope
from ..models import Task, TaskStatus, Message

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class StateBlackboard:
    """
    状态黑板

    用于存储和管理 A2A 任务队列
    作为 LangGraph State 的核心载体
    """

    def __init__(self):
        self._task_queue: List[Task] = []
        self._pending_tasks: Dict[str, Task] = {}
        self._completed_tasks: Dict[str, Task] = {}
        self._subscriptions: Dict[str, List[Callable]] = {}
        logger.info("📋 StateBlackboard 初始化")

    def enqueue_task(self, task: Task) -> str:
        """
        将任务加入队列

        Args:
            task: A2A Task 对象

        Returns:
            任务 ID
        """
        task.id = task.id or str(uuid4())
        self._task_queue.append(task)
        self._pending_tasks[task.id] = task
        logger.info(f"📥 任务入队: {task.id}")
        self._notify_subscribers(task.id, "enqueued")
        return task.id

    def dequeue_task(self) -> Optional[Task]:
        """
        从队列取出任务（FIFO）

        Returns:
            任务对象或 None
        """
        if self._task_queue:
            task = self._task_queue.pop(0)
            logger.info(f"📤 任务出队: {task.id}")
            self._notify_subscribers(task.id, "dequeued")
            return task
        return None

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._pending_tasks.get(task_id) or self._completed_tasks.get(task_id)

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """
        标记任务完成

        Args:
            task_id: 任务 ID
            result: 执行结果

        Returns:
            是否成功
        """
        task = self._pending_tasks.pop(task_id, None)
        if task:
            task.status = TaskStatus.COMPLETED
            task.updatedAt = datetime.now()
            if result:
                task.metadata["result"] = result
            self._completed_tasks[task_id] = task
            logger.info(f"✅ 任务完成: {task_id}")
            self._notify_subscribers(task_id, "completed")
            return True
        return False

    def fail_task(self, task_id: str, error: str) -> bool:
        """
        标记任务失败

        Args:
            task_id: 任务 ID
            error: 错误信息

        Returns:
            是否成功
        """
        task = self._pending_tasks.pop(task_id, None)
        if task:
            task.status = TaskStatus.FAILED
            task.updatedAt = datetime.now()
            task.metadata["error"] = error
            self._completed_tasks[task_id] = task
            logger.warning(f"❌ 任务失败: {task_id} - {error}")
            self._notify_subscribers(task_id, "failed")
            return True
        return False

    def subscribe(self, task_id: str, callback: Callable) -> None:
        """订阅任务状态变更"""
        if task_id not in self._subscriptions:
            self._subscriptions[task_id] = []
        self._subscriptions[task_id].append(callback)

    def unsubscribe(self, task_id: str, callback: Callable) -> None:
        """取消订阅"""
        if task_id in self._subscriptions:
            self._subscriptions[task_id] = [
                cb for cb in self._subscriptions[task_id] if cb != callback
            ]

    def _notify_subscribers(self, task_id: str, event: str) -> None:
        """通知订阅者"""
        if task_id in self._subscriptions:
            for callback in self._subscriptions[task_id]:
                try:
                    callback(task_id, event)
                except Exception as e:
                    logger.error(f"❌ 订阅回调失败: {e}")

    def get_pending_count(self) -> int:
        """获取待处理任务数"""
        return len(self._pending_tasks)

    def get_completed_count(self) -> int:
        """获取已完成任务数"""
        return len(self._completed_tasks)


class LangGraphTransport(TransportStrategy):
    """
    LangGraph 状态传输

    核心职责：
    1. 将 A2A Payload 打包成 TransportEnvelope
    2. 将信封追加到 State 黑板
    3. 从黑板读取任务结果

    不做任何网络调用或内存指针操作
    """

    def __init__(self, state_blackboard: Optional[StateBlackboard] = None):
        super().__init__(TransportMode.GRAPH_STATE)
        self._blackboard = state_blackboard or StateBlackboard()
        self._local_agents: Dict[str, Callable] = {}
        logger.info("🧬 LangGraphTransport 初始化（状态黑板模式）")

    def register_agent(self, agent_name: str, handler: Callable) -> None:
        """
        注册本地 Agent 处理函数

        Args:
            agent_name: Agent 名称
            handler: 处理函数（异步）
        """
        self._local_agents[agent_name] = handler
        logger.info(f"✅ 注册 Agent 处理函数: {agent_name}")

    async def connect(self) -> None:
        """建立连接（状态黑板模式无需网络连接）"""
        self._connected = True
        logger.info("🧬 LangGraphTransport 连接成功（虚拟连接）")

    async def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        logger.info("🧬 LangGraphTransport 连接断开")

    def _build_envelope(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        from_agent: str = "system"
    ) -> TransportEnvelope:
        """
        构建传输信封

        Args:
            to_agent: 目标 Agent
            message: 消息内容
            tenant_id: 租户 ID
            from_agent: 来源 Agent

        Returns:
            标准化的信封对象
        """
        task_id = message.get("task_id") or str(uuid4())
        envelope = TransportEnvelope(
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message=message,
            metadata=message.get("metadata", {}),
            tenant_id=tenant_id,
            timestamp=datetime.utcnow().isoformat()
        )
        return envelope

    def _build_task_from_envelope(self, envelope: TransportEnvelope) -> Task:
        """
        从信封构建 A2A Task

        Args:
            envelope: 传输信封

        Returns:
            A2A Task 对象
        """
        user_message = Message(
            role="user",
            parts=envelope.message.get("parts", []),
            metadata=envelope.metadata
        )
        task = Task(
            id=envelope.task_id,
            sessionId=envelope.message.get("session_id"),
            metadata={
                "from_agent": envelope.from_agent,
                "to_agent": envelope.to_agent,
                "tenant_id": envelope.tenant_id,
                "original_message": envelope.message
            }
        )
        task.messages.append(user_message)
        task.status = TaskStatus.SUBMITTED
        return task

    async def send_message(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        state_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送消息（追加到状态黑板）

        在 GRAPH_STATE 模式下：
        1. 构建 TransportEnvelope
        2. 转换为 A2A Task
        3. 加入状态黑板队列

        Args:
            to_agent: 目标 Agent 名称
            message: A2A Payload
            tenant_id: 租户 ID
            state_context: 状态上下文（包含 result_callback 等）

        Returns:
            包含 task_id 的响应
        """
        if not self._connected:
            await self.connect()

        envelope = self._build_envelope(to_agent, message, tenant_id)
        task = self._build_task_from_envelope(envelope)

        task_id = self._blackboard.enqueue_task(task)
        logger.info(f"📬 消息已追加到黑板: {to_agent}, task_id={task_id}")

        if to_agent in self._local_agents and state_context:
            result_callback = state_context.get("result_callback")
            if result_callback:
                try:
                    result = await self._local_agents[to_agent](task, state_context)
                    self._blackboard.complete_task(task_id, result)
                    if result_callback:
                        await result_callback(task_id, result)
                except Exception as e:
                    logger.error(f"❌ Agent 处理失败: {e}")
                    self._blackboard.fail_task(task_id, str(e))
                    raise

        return {
            "task_id": task_id,
            "status": "queued",
            "to_agent": to_agent,
            "envelope": envelope.to_dict()
        }

    async def send_notification(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None,
        state_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        发送通知（追加到黑板，不等待响应）

        Args:
            to_agent: 目标 Agent 名称
            message: 通知内容
            tenant_id: 租户 ID
            state_context: 状态上下文
        """
        if not self._connected:
            await self.connect()

        envelope = self._build_envelope(
            to_agent=to_agent,
            message=message,
            tenant_id=tenant_id,
            from_agent=message.get("from_agent", "system")
        )
        task = self._build_task_from_envelope(envelope)
        task.metadata["notification"] = True

        task_id = self._blackboard.enqueue_task(task)
        logger.info(f"🔔 通知已追加到黑板: {to_agent}, task_id={task_id}")

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
        subscription_id = f"{agent}_{uuid4().hex[:8]}"

        async def task_callback(task_id: str, event: str):
            task = self._blackboard.get_task(task_id)
            if task:
                await callback({
                    "task_id": task_id,
                    "event": event,
                    "task": task.model_dump() if hasattr(task, 'model_dump') else {},
                    "agent": agent
                })

        self._blackboard.subscribe(subscription_id, task_callback)
        logger.info(f"📡 订阅已创建: {subscription_id}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        for task_id in list(self._blackboard._subscriptions.keys()):
            callbacks = self._blackboard._subscriptions[task_id]
            self._blackboard._subscriptions[task_id] = []

        if subscription_id in self._blackboard._subscriptions:
            del self._blackboard._subscriptions[subscription_id]
        logger.info(f"📡 订阅已取消: {subscription_id}")

    async def stream_events(
        self,
        task_id: str,
        tenant_id: Optional[str] = None,
        state_context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式接收事件（从黑板读取）

        Args:
            task_id: 任务 ID
            tenant_id: 租户 ID
            state_context: 状态上下文

        Yields:
            状态更新事件
        """
        task = self._blackboard.get_task(task_id)
        if not task:
            return

        yield {
            "task_id": task_id,
            "status": task.status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": task.metadata
        }

        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED]:
            return

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            状态黑板是否正常
        """
        return self._connected

    def get_blackboard(self) -> StateBlackboard:
        """获取状态黑板实例"""
        return self._blackboard

    def get_queue_depth(self) -> int:
        """获取队列深度"""
        return self._blackboard.get_pending_count()

    def clear_completed_tasks(self) -> int:
        """清理已完成任务"""
        count = len(self._blackboard._completed_tasks)
        self._blackboard._completed_tasks.clear()
        return count