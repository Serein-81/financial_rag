"""
A2A Client

A2A 协议的客户端实现
用于向其他 Agent 发送请求
"""

import asyncio
import httpx
import logging
from typing import Optional, Dict, Any, AsyncGenerator, List
from datetime import datetime

from .models import (
    Task, TaskStatus, Message, TextPart, TaskSubmitParams,
    TaskStatusUpdateEvent
)
from .agent_card import AgentCard

logger = logging.getLogger(__name__)


class A2AClient:
    """
    A2A 协议客户端
    
    用于与其他 Agent 通信
    支持：
    1. 任务提交
    2. 任务查询
    3. SSE 流式接收
    4. 推送通知配置
    """
    
    def __init__(self, agent_card: AgentCard):
        self.agent_card = agent_card
        self._session_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"🔗 A2A Client 初始化: {agent_card.name}")
    
    async def __aenter__(self) -> "A2AClient":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
    
    def set_session_id(self, session_id: str) -> None:
        """设置会话 ID"""
        self._session_id = session_id
    
    async def send_message(
        self,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        发送消息并获取响应
        
        Args:
            content: 消息内容
            metadata: 元数据
            
        Returns:
            响应数据
        """
        message = Message(
            role="user",
            parts=[TextPart(text=content)],
            metadata=metadata
        )
        
        params = TaskSubmitParams(
            sessionId=self._session_id,
            message=message,
            acceptedOutputModes=["text"]
        )
        
        return await self.submit_task(params)
    
    async def submit_task(self, params: TaskSubmitParams) -> Dict[str, Any]:
        """
        提交任务到远程 Agent
        
        Args:
            params: 任务参数
            
        Returns:
            任务响应
        """
        url = f"{self.agent_card.url}/a2a/v1/tasks/send"
        
        try:
            response = await self._client.post(
                url,
                json=params.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"❌ A2A 请求失败: {e}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务对象
        """
        url = f"{self.agent_card.url}/a2a/v1/tasks/{task_id}"
        
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()
            return Task(**data)
        except httpx.HTTPError as e:
            logger.warning(f"⚠️ 获取任务失败: {task_id} - {e}")
            return None
    
    async def stream_task_status(
        self,
        task_id: str
    ) -> AsyncGenerator[TaskStatusUpdateEvent, None]:
        """
        订阅任务状态流
        
        Args:
            task_id: 任务 ID
            
        Yields:
            状态更新事件
        """
        url = f"{self.agent_card.url}/a2a/v1/tasks/{task_id}/subscribe"
        
        try:
            async with self._client.stream("GET", url) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        yield TaskStatusUpdateEvent.model_validate_json(data)
        except httpx.HTTPError as e:
            logger.error(f"❌ 流订阅失败: {task_id} - {e}")
    
    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: float = 1.0,
        timeout: float = 60.0
    ) -> Optional[Task]:
        """
        等待任务完成
        
        Args:
            task_id: 任务 ID
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）
            
        Returns:
            完成的任务
        """
        start_time = datetime.now()
        
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.warning(f"⏰ 任务等待超时: {task_id}")
                return None
            
            task = await self.get_task(task_id)
            if not task:
                return None
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED]:
                return task
            
            await asyncio.sleep(poll_interval)
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功
        """
        url = f"{self.agent_card.url}/a2a/v1/tasks/{task_id}/cancel"
        
        try:
            response = await self._client.post(url)
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"❌ 取消任务失败: {task_id} - {e}")
            return False
    
    async def list_tasks(
        self,
        status: TaskStatus = None
    ) -> List[Task]:
        """
        列出任务
        
        Args:
            status: 过滤状态
            
        Returns:
            任务列表
        """
        url = f"{self.agent_card.url}/a2a/v1/tasks"
        params = {}
        if status:
            params["status"] = status.value
        
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return [Task(**t) for t in data.get("tasks", [])]
        except httpx.HTTPError as e:
            logger.error(f"❌ 列出任务失败: {e}")
            return []