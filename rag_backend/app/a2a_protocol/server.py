"""
A2A Server

A2A 协议的服务端实现
处理来自其他 Agent 的请求
"""

import asyncio
import logging
from typing import Dict, Optional, Any, Callable, AsyncGenerator
from uuid import uuid4
from datetime import datetime

from .models import (
    Task, TaskStatus, Message, TaskSubmitParams,
    TaskStatusUpdateEvent
)
from .agent_card import AgentCard

logger = logging.getLogger(__name__)


class A2AServer:
    """
    A2A 协议服务端
    
    功能：
    1. 任务提交和处理
    2. 任务状态查询
    3. SSE 流式推送
    4. 任务取消
    """
    
    def __init__(self, agent_card: AgentCard):
        self.agent_card = agent_card
        self._tasks: Dict[str, Task] = {}
        self._task_queues: Dict[str, asyncio.Queue] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
        logger.info(f"🖥️ A2A Server 初始化: {agent_card.name}")
    
    def set_task_handler(self, handler: Callable) -> None:
        """
        设置任务处理器
        
        Args:
            handler: 异步函数，签名: async def handler(task: Task) -> Task
        """
        self._task_handlers["default"] = handler
    
    def set_named_handler(self, name: str, handler: Callable) -> None:
        """设置命名任务处理器"""
        self._task_handlers[name] = handler
    
    async def submit_task(self, params: TaskSubmitParams) -> Task:
        """
        提交新任务
        
        Args:
            params: 任务提交参数
            
        Returns:
            创建的任务
        """
        async with self._lock:
            task = Task(
                id=str(uuid4()),
                sessionId=params.sessionId
            )
            task.add_message(
                role="user",
                content=self._extract_text_from_message(params.message)
            )
            task.status = TaskStatus.SUBMITTED
            
            self._tasks[task.id] = task
            self._task_queues[task.id] = asyncio.Queue()
            
            logger.info(f"📝 任务提交: {task.id}")
            
            asyncio.create_task(self._process_task(task))
            
            return task
    
    async def _process_task(self, task: Task) -> None:
        """处理任务"""
        try:
            task.status = TaskStatus.WORKING
            await self._notify_status_update(task)
            
            handler = self._task_handlers.get("default")
            if handler:
                result = await handler(task)
                if isinstance(result, Task):
                    task = result
            
            task.status = TaskStatus.COMPLETED
            task.updatedAt = datetime.now()
            await self._notify_status_update(task)
            
            logger.info(f"✅ 任务完成: {task.id}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 任务数据失败: {task.id} - {e}")
            task.status = TaskStatus.FAILED
        except (OSError, IOError) as e:
            logger.error(f"❌ 任务IO失败: {task.id} - {e}")
            task.status = TaskStatus.FAILED
        except Exception as e:
            logger.error(f"❌ 任务失败: {task.id} - {e}")
            task.status = TaskStatus.FAILED
            task.metadata["error"] = str(e)
            await self._notify_status_update(task)
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    async def get_task_stream(
        self, 
        task_id: str
    ) -> AsyncGenerator[TaskStatusUpdateEvent, None]:
        """
        获取任务状态流
        
        Args:
            task_id: 任务 ID
            
        Yields:
            任务状态更新事件
        """
        queue = self._task_queues.get(task_id)
        if not queue:
            return
        
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield event
                if event.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED]:
                    break
            except asyncio.TimeoutError:
                yield TaskStatusUpdateEvent(
                    taskId=task_id,
                    status=self._tasks[task_id].status,
                    metadata={"timeout": True}
                )
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task or task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            return False
        
        task.status = TaskStatus.CANCELED
        await self._notify_status_update(task)
        return True
    
    async def send_task_update(
        self,
        task_id: str,
        event: TaskStatusUpdateEvent
    ) -> None:
        """发送任务状态更新"""
        queue = self._task_queues.get(task_id)
        if queue:
            await queue.put(event)
    
    async def send_task_artifact(
        self,
        task_id: str,
        artifact: Dict[str, Any]
    ) -> None:
        """发送任务产物"""
        task = self._tasks.get(task_id)
        if task:
            task.add_artifact(artifact)
    
    async def _notify_status_update(self, task: Task) -> None:
        """通知状态更新"""
        event = TaskStatusUpdateEvent(
            taskId=task.id,
            status=task.status,
            metadata=task.metadata
        )
        await self.send_task_update(task.id, event)
    
    def _extract_text_from_message(self, message: Message) -> str:
        """从消息中提取文本"""
        parts_text = []
        for part in message.parts:
            if hasattr(part, 'text'):
                parts_text.append(part.text)
            elif hasattr(part, 'data'):
                parts_text.append(str(part.data))
        return "\n".join(parts_text) if parts_text else ""
    
    def get_agent_card(self) -> AgentCard:
        """获取 Agent Card"""
        return self.agent_card
    
    def list_tasks(self, status: TaskStatus = None) -> list[Task]:
        """列出任务"""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())
