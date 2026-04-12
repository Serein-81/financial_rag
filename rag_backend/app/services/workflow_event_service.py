"""
工作流事件服务

提供工作流状态的 SSE 实时推送功能
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


class WorkflowEventType(str, Enum):
    """工作流事件类型"""
    STARTED = "workflow_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_WARNING = "step_warning"
    STATUS_CHANGED = "status_changed"
    DATA_UPDATED = "data_updated"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    HUMAN_REVIEW_COMPLETED = "human_review_completed"
    COMPLETED = "workflow_completed"
    FAILED = "workflow_failed"
    HEARTBEAT = "heartbeat"


class WorkflowEvent:
    """工作流事件"""
    
    def __init__(
        self,
        event_type: WorkflowEventType,
        workflow_id: str,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
        step_name: Optional[str] = None,
        step_number: Optional[int] = None,
        error: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.workflow_id = workflow_id
        self.session_id = session_id
        self.timestamp = datetime.now().isoformat()
        self.step_name = step_name
        self.step_number = step_number
        self.data = data or {}
        self.error = error
        self.error_details = error_details
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "step_name": self.step_name,
            "step_number": self.step_number,
            "data": self.data,
            "error": self.error,
            "error_details": self.error_details
        }
    
    def to_sse_data(self) -> str:
        """转换为 SSE 格式数据"""
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class WorkflowEventService:
    """
    工作流事件服务
    
    管理工作流事件的发布和订阅，支持 SSE 推送
    """
    
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._workflow_states: Dict[str, Dict[str, Any]] = {}
        self._workflow_histories: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
        
        logger.info("✅ 工作流事件服务初始化完成")
    
    async def subscribe(self, workflow_id: str) -> asyncio.Queue:
        """
        订阅工作流事件
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            asyncio.Queue: 事件队列
        """
        queue = asyncio.Queue()
        async with self._lock:
            self._subscribers[workflow_id].add(queue)
            logger.info(f"📡 新的订阅: workflow_id={workflow_id}, 当前订阅数={len(self._subscribers[workflow_id])}")
        
        return queue
    
    async def unsubscribe(self, workflow_id: str, queue: asyncio.Queue):
        """
        取消订阅
        
        Args:
            workflow_id: 工作流ID
            queue: 事件队列
        """
        async with self._lock:
            if queue in self._subscribers[workflow_id]:
                self._subscribers[workflow_id].discard(queue)
                logger.info(f"📡 取消订阅: workflow_id={workflow_id}, 当前订阅数={len(self._subscribers[workflow_id])}")
    
    async def publish(self, event: WorkflowEvent):
        """
        发布工作流事件
        
        Args:
            event: 工作流事件
        """
        async with self._lock:
            subscribers = self._subscribers.get(event.workflow_id, set()).copy()
        
        if not subscribers:
            logger.debug(f"📭 没有订阅者: workflow_id={event.workflow_id}")
            return
        
        logger.info(f"📤 发布事件: {event.event_type.value} - workflow_id={event.workflow_id}, step={event.step_name}")
        
        for queue in subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(f"❌ 事件推送失败: {e}")
        
        if event.event_type in [
            WorkflowEventType.STEP_COMPLETED,
            WorkflowEventType.STEP_FAILED,
            WorkflowEventType.STATUS_CHANGED,
            WorkflowEventType.HUMAN_REVIEW_REQUIRED
        ]:
            self._workflow_histories[event.workflow_id].append(event.to_dict())
        
        if event.event_type in [
            WorkflowEventType.STEP_STARTED,
            WorkflowEventType.STEP_COMPLETED,
            WorkflowEventType.STEP_FAILED,
            WorkflowEventType.STATUS_CHANGED,
            WorkflowEventType.DATA_UPDATED
        ]:
            self._workflow_states[event.workflow_id] = event.to_dict()
    
    async def get_current_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取当前工作流状态
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            Optional[Dict[str, Any]]: 当前状态
        """
        return self._workflow_states.get(workflow_id)
    
    async def get_history(self, workflow_id: str) -> list:
        """
        获取工作流历史
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            list: 历史事件列表
        """
        return self._workflow_histories.get(workflow_id, [])
    
    async def emit_workflow_started(
        self,
        workflow_id: str,
        session_id: str,
        initial_data: Dict[str, Any]
    ):
        """发射工作流开始事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.STARTED,
            workflow_id=workflow_id,
            session_id=session_id,
            data=initial_data
        )
        await self.publish(event)
    
    async def emit_step_started(
        self,
        workflow_id: str,
        session_id: str,
        step_name: str,
        step_number: int,
        step_data: Optional[Dict[str, Any]] = None
    ):
        """发射步骤开始事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.STEP_STARTED,
            workflow_id=workflow_id,
            session_id=session_id,
            step_name=step_name,
            step_number=step_number,
            data=step_data or {}
        )
        await self.publish(event)
    
    async def emit_step_completed(
        self,
        workflow_id: str,
        session_id: str,
        step_name: str,
        step_number: int,
        result_data: Optional[Dict[str, Any]] = None
    ):
        """发射步骤完成事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.STEP_COMPLETED,
            workflow_id=workflow_id,
            session_id=session_id,
            step_name=step_name,
            step_number=step_number,
            data=result_data or {}
        )
        await self.publish(event)
    
    async def emit_step_failed(
        self,
        workflow_id: str,
        session_id: str,
        step_name: str,
        step_number: int,
        error: str,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """发射步骤失败事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.STEP_FAILED,
            workflow_id=workflow_id,
            session_id=session_id,
            step_name=step_name,
            step_number=step_number,
            error=error,
            error_details=error_details
        )
        await self.publish(event)
    
    async def emit_step_warning(
        self,
        workflow_id: str,
        session_id: str,
        step_name: str,
        step_number: int,
        warning: str,
        warning_data: Optional[Dict[str, Any]] = None
    ):
        """发射步骤警告事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.STEP_WARNING,
            workflow_id=workflow_id,
            session_id=session_id,
            step_name=step_name,
            step_number=step_number,
            data=warning_data or {},
            error=warning
        )
        await self.publish(event)
    
    async def emit_status_changed(
        self,
        workflow_id: str,
        session_id: str,
        new_status: str,
        status_data: Optional[Dict[str, Any]] = None
    ):
        """发射状态变更事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.STATUS_CHANGED,
            workflow_id=workflow_id,
            session_id=session_id,
            data=status_data or {},
            error=new_status
        )
        await self.publish(event)
    
    async def emit_data_updated(
        self,
        workflow_id: str,
        session_id: str,
        updated_fields: Dict[str, Any]
    ):
        """发射数据更新事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.DATA_UPDATED,
            workflow_id=workflow_id,
            session_id=session_id,
            data=updated_fields
        )
        await self.publish(event)
    
    async def emit_human_review_required(
        self,
        workflow_id: str,
        session_id: str,
        review_id: str,
        reason: str,
        review_data: Dict[str, Any]
    ):
        """发射人工审核请求事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.HUMAN_REVIEW_REQUIRED,
            workflow_id=workflow_id,
            session_id=session_id,
            data={
                "review_id": review_id,
                "reason": reason,
                **review_data
            }
        )
        await self.publish(event)
    
    async def emit_human_review_completed(
        self,
        workflow_id: str,
        session_id: str,
        review_id: str,
        approved: bool,
        comments: Optional[str] = None
    ):
        """发射人工审核完成事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.HUMAN_REVIEW_COMPLETED,
            workflow_id=workflow_id,
            session_id=session_id,
            data={
                "review_id": review_id,
                "approved": approved,
                "comments": comments
            }
        )
        await self.publish(event)
    
    async def emit_workflow_completed(
        self,
        workflow_id: str,
        session_id: str,
        final_data: Dict[str, Any]
    ):
        """发射工作流完成事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.COMPLETED,
            workflow_id=workflow_id,
            session_id=session_id,
            data=final_data
        )
        await self.publish(event)
    
    async def emit_workflow_failed(
        self,
        workflow_id: str,
        session_id: str,
        error: str,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """发射工作流失败事件"""
        event = WorkflowEvent(
            event_type=WorkflowEventType.FAILED,
            workflow_id=workflow_id,
            session_id=session_id,
            error=error,
            error_details=error_details
        )
        await self.publish(event)
    
    async def cleanup_old_workflows(self, max_age_hours: int = 24):
        """
        清理旧的工作流数据
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        now = datetime.now()
        workflows_to_remove = []
        
        for workflow_id, state in self._workflow_states.items():
            timestamp_str = state.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    age_hours = (now - timestamp).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        workflows_to_remove.append(workflow_id)
                except Exception:
                    pass
        
        async with self._lock:
            for workflow_id in workflows_to_remove:
                self._workflow_states.pop(workflow_id, None)
                self._workflow_histories.pop(workflow_id, None)
                subscribers = self._subscribers.pop(workflow_id, set())
                for queue in subscribers:
                    await queue.put(None)
        
        if workflows_to_remove:
            logger.info(f"🧹 清理了 {len(workflows_to_remove)} 个旧工作流")


workflow_event_service = WorkflowEventService()
