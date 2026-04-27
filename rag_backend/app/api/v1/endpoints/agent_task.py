"""
Agent 任务状态 API 端点

用于前端状态水合 (Hydration) - 实现"切回页面继续"功能

主要功能：
1. 提交任务 -> 立即返回 200 OK，任务后台执行
2. 查询状态 -> 返回任务进度和当前节点
3. 水合恢复 -> 前端切回时获取完整状态并恢复
4. 断点续跑 -> 从上次死掉的节点复活继续执行
"""

import uuid
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.agent_task import (
    TaskStatusResponse,
    TaskSubmitRequest,
    TaskSubmitResponse,
    ThreadHydrationResponse,
    CheckpointInfo,
    TaskEventResponse
)
from app.langgraph.postgres_saver import get_postgres_saver
from app.langgraph.workflow_tasks import get_langgraph_task_manager
from app.db.session import get_db, AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent-task", tags=["agent-task"])


def get_db_session_factory():
    """获取数据库会话工厂函数（用于非依赖注入场景）"""
    return AsyncSessionLocal


async def get_task_manager():
    """获取任务管理器"""
    from app.core.config import settings
    
    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    return get_langgraph_task_manager(redis_url)


@router.post("/submit", response_model=TaskSubmitResponse)
async def submit_agent_task(
    request: TaskSubmitRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    提交 Agent 任务
    
    前端调用此接口后：
    1. 立即返回 200 OK 和 task_id/thread_id
    2. 任务在后台通过 ARQ Worker 执行
    3. 前端通过 GET /status/{thread_id} 查询进度
    
    关键设计：
    - 使用固定的 thread_id 关联用户会话
    - 即使前端断开，任务仍继续在后台执行
    - 用户切回时可通过水合接口恢复状态
    """
    task_manager = await get_task_manager()
    
    thread_id = request.thread_id or f"thread_{uuid.uuid4().hex[:16]}"
    task_id = f"lgwf_{uuid.uuid4().hex[:16]}"
    
    try:
        from app.models.agent_task import AgentTaskStatus, TaskStatus, TaskPriority
        from app.db.base import Base
        from sqlalchemy import select
        
        task_record = AgentTaskStatus(
            task_id=task_id,
            thread_id=thread_id,
            tenant_id=tenant_context["tenant_id"],
            user_id=current_user.id,
            task_type="langgraph_workflow",
            task_name="多智能体工作流",
            status=TaskStatus.PENDING,
            priority=TaskPriority(request.priority),
            user_query=request.user_query,
            metadata={
                "enable_reflection": request.enable_reflection,
                "max_specialists": request.max_specialists,
                "context": request.context or {}
            }
        )
        
        db.add(task_record)
        await db.commit()
        
        logger.info(
            f"[AgentTask] 提交任务: task_id={task_id}, "
            f"thread_id={thread_id[:8]}..., user={current_user.id}"
        )
        
        return TaskSubmitResponse(
            task_id=task_id,
            thread_id=thread_id,
            status="submitted",
            message="任务已提交到后台队列，请使用 GET /status/{thread_id} 查询进度",
            estimated_completion_seconds=60
        )
        
    except Exception as e:
        logger.error(f"[AgentTask] 提交任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"任务提交失败: {str(e)}")


@router.get("/status/{thread_id}", response_model=TaskStatusResponse)
async def get_task_status_by_thread(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    查询任务状态（通过 thread_id）
    
    前端轮询此接口获取任务进度：
    - 如果任务完成，返回 final_response
    - 如果任务进行中，返回 current_node 和 progress
    - 如果任务失败，返回 error_message
    
    用于：
    1. SSE 进度条的定期检查
    2. 页面刷新后恢复状态
    """
    try:
        from app.models.agent_task import AgentTaskStatus
        from sqlalchemy import select, desc
        
        result = await db.execute(
            select(AgentTaskStatus)
            .where(
                AgentTaskStatus.thread_id == thread_id,
                AgentTaskStatus.tenant_id == tenant_context["tenant_id"]
            )
            .order_by(desc(AgentTaskStatus.created_at))
            .limit(1)
        )
        
        task_record = result.scalar_one_or_none()
        
        if not task_record:
            raise HTTPException(status_code=404, detail="未找到任务记录")
        
        postgres_saver = get_postgres_saver(get_db_session_factory())
        checkpoints = await postgres_saver.list_checkpoints(thread_id, limit=10)
        
        latest_checkpoint_id = await postgres_saver.get_latest_checkpoint_id(thread_id)
        
        can_resume = (
            task_record.status.value in ["running", "pending", "interrupted"]
            and latest_checkpoint_id is not None
        )
        
        return TaskStatusResponse(
            task_id=task_record.task_id,
            thread_id=task_record.thread_id,
            status=task_record.status.value if hasattr(task_record.status, 'value') else str(task_record.status),
            task_type=task_record.task_type,
            task_name=task_record.task_name,
            current_node=task_record.current_node,
            progress_percent=task_record.progress_percent or 0,
            progress_message=task_record.progress_message,
            specialist_progress=task_record.specialist_progress,
            user_query=task_record.user_query,
            final_response=task_record.final_response,
            checkpoints=[
                CheckpointInfo(
                    checkpoint_id=cp.get("checkpoint_id", ""),
                    parent_checkpoint_id=cp.get("parent_checkpoint_id"),
                    metadata=cp.get("metadata"),
                    created_at=cp.get("created_at"),
                    updated_at=cp.get("updated_at")
                )
                for cp in checkpoints
            ],
            latest_checkpoint_id=latest_checkpoint_id,
            created_at=task_record.created_at.isoformat() if task_record.created_at else None,
            started_at=task_record.started_at.isoformat() if task_record.started_at else None,
            completed_at=task_record.completed_at.isoformat() if task_record.completed_at else None,
            execution_time_ms=task_record.execution_time_ms,
            error_message=task_record.error_message,
            retry_count=task_record.retry_count or 0,
            can_resume=can_resume,
            needs_hydration=task_record.status.value in ["running", "pending"],
            needs_clarification=getattr(task_record, 'needs_clarification', False) if task_record else False,
            clarification_request=getattr(task_record, 'clarification_request', None) if task_record else None,
            intent_analysis=getattr(task_record, 'intent_analysis', None) if task_record else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AgentTask] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/status/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_by_id(
    task_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """通过 task_id 查询任务状态"""
    try:
        from app.models.agent_task import AgentTaskStatus
        from sqlalchemy import select
        
        result = await db.execute(
            select(AgentTaskStatus).where(AgentTaskStatus.task_id == task_id)
        )
        
        task_record = result.scalar_one_or_none()
        
        if not task_record:
            raise HTTPException(status_code=404, detail="未找到任务记录")
        
        if task_record.tenant_id != tenant_context["tenant_id"]:
            raise HTTPException(status_code=403, detail="无权访问此任务")
        
        postgres_saver = get_postgres_saver(get_db_session_factory())
        checkpoints = await postgres_saver.list_checkpoints(task_record.thread_id, limit=10)
        latest_checkpoint_id = await postgres_saver.get_latest_checkpoint_id(task_record.thread_id)
        
        can_resume = (
            task_record.status.value in ["running", "pending", "interrupted"]
            and latest_checkpoint_id is not None
        )
        
        return TaskStatusResponse(
            task_id=task_record.task_id,
            thread_id=task_record.thread_id,
            status=task_record.status.value if hasattr(task_record.status, 'value') else str(task_record.status),
            task_type=task_record.task_type,
            task_name=task_record.task_name,
            current_node=task_record.current_node,
            progress_percent=task_record.progress_percent or 0,
            progress_message=task_record.progress_message,
            specialist_progress=task_record.specialist_progress,
            user_query=task_record.user_query,
            final_response=task_record.final_response,
            checkpoints=[
                CheckpointInfo(
                    checkpoint_id=cp.get("checkpoint_id", ""),
                    parent_checkpoint_id=cp.get("parent_checkpoint_id"),
                    metadata=cp.get("metadata"),
                    created_at=cp.get("created_at"),
                    updated_at=cp.get("updated_at")
                )
                for cp in checkpoints
            ],
            latest_checkpoint_id=latest_checkpoint_id,
            created_at=task_record.created_at.isoformat() if task_record.created_at else None,
            started_at=task_record.started_at.isoformat() if task_record.started_at else None,
            completed_at=task_record.completed_at.isoformat() if task_record.completed_at else None,
            execution_time_ms=task_record.execution_time_ms,
            error_message=task_record.error_message,
            retry_count=task_record.retry_count or 0,
            can_resume=can_resume,
            needs_hydration=task_record.status.value in ["running", "pending"],
            needs_clarification=getattr(task_record, 'needs_clarification', False) if task_record else False,
            clarification_request=getattr(task_record, 'clarification_request', None) if task_record else None,
            intent_analysis=getattr(task_record, 'intent_analysis', None) if task_record else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AgentTask] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/hydrate/{thread_id}", response_model=ThreadHydrationResponse)
async def hydrate_thread_state(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    前端状态水合接口
    
    场景：用户从其他页面切回多智能体页面
    
    前端应做的第一件事：
    1. 静默调用此接口（不显示加载状态）
    2. 检查 needs_hydration 和状态
    3. 根据返回结果决定：
       - 如果 completed: 直接渲染 final_response
       - 如果 running: 重新连接 SSE 进度条
       - 如果 failed: 显示错误信息，提供重试选项
    
    关键设计：
    - 前端不需要重新发起提问
    - 后端返回完整的恢复状态
    - 支持从任意断点继续
    """
    try:
        from app.models.agent_task import AgentTaskStatus
        from sqlalchemy import select, desc
        
        result = await db.execute(
            select(AgentTaskStatus)
            .where(
                AgentTaskStatus.thread_id == thread_id,
                AgentTaskStatus.tenant_id == tenant_context["tenant_id"]
            )
            .order_by(desc(AgentTaskStatus.created_at))
            .limit(1)
        )
        
        task_record = result.scalar_one_or_none()
        
        if not task_record:
            return ThreadHydrationResponse(
                thread_id=thread_id,
                needs_hydration=False,
                recommendations=["未找到历史任务，可以开始新任务"]
            )
        
        postgres_saver = get_postgres_saver(get_db_session_factory())
        checkpoints = await postgres_saver.list_checkpoints(thread_id, limit=20)
        latest_checkpoint = await postgres_saver.get_latest_checkpoint_id(thread_id)
        
        last_checkpoint_info = None
        if latest_checkpoint:
            latest_cp_data = await postgres_saver.get_checkpoint(thread_id, latest_checkpoint)
            if latest_cp_data:
                last_checkpoint_info = CheckpointInfo(
                    checkpoint_id=latest_checkpoint,
                    metadata=latest_cp_data.get("metadata"),
                    created_at=latest_cp_data.get("updated_at") if 'updated_at' in latest_cp_data else None
                )
        
        checkpoint_history = [
            CheckpointInfo(
                checkpoint_id=cp.get("checkpoint_id", ""),
                parent_checkpoint_id=cp.get("parent_checkpoint_id"),
                metadata=cp.get("metadata"),
                created_at=cp.get("created_at"),
                updated_at=cp.get("updated_at")
            )
            for cp in checkpoints
        ]
        
        status = task_record.status.value if hasattr(task_record.status, 'value') else str(task_record.status)
        
        recovered_state = None
        if status == "running" and last_checkpoint_info:
            recovered_state = {
                "current_node": task_record.current_node,
                "progress_percent": task_record.progress_percent,
                "specialist_progress": task_record.specialist_progress,
                "checkpoint_id": latest_checkpoint
            }
        
        recommendations = []
        if status == "completed":
            recommendations = ["任务已完成，可以查看结果"]
        elif status == "running":
            recommendations = ["任务正在后台执行", "当前节点: " + (task_record.current_node or "未知")]
        elif status == "failed":
            recommendations = ["任务执行失败", "错误: " + (task_record.error_message or "未知错误"), "可以点击重试按钮重新执行"]
        elif status == "interrupted":
            recommendations = ["任务被中断", "可以尝试恢复执行"]
        
        task_info = TaskStatusResponse(
            task_id=task_record.task_id,
            thread_id=task_record.thread_id,
            status=status,
            task_type=task_record.task_type,
            task_name=task_record.task_name,
            current_node=task_record.current_node,
            progress_percent=task_record.progress_percent or 0,
            progress_message=task_record.progress_message,
            specialist_progress=task_record.specialist_progress,
            user_query=task_record.user_query,
            final_response=task_record.final_response,
            created_at=task_record.created_at.isoformat() if task_record.created_at else None,
            started_at=task_record.started_at.isoformat() if task_record.started_at else None,
            completed_at=task_record.completed_at.isoformat() if task_record.completed_at else None,
            execution_time_ms=task_record.execution_time_ms,
            error_message=task_record.error_message,
            can_resume=status in ["running", "pending", "interrupted"] and latest_checkpoint is not None,
            needs_hydration=status in ["running", "pending"]
        )
        
        return ThreadHydrationResponse(
            thread_id=thread_id,
            needs_hydration=status in ["running", "pending"],
            task_info=task_info,
            last_checkpoint=last_checkpoint_info,
            checkpoint_history=checkpoint_history,
            recovered_state=recovered_state,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"[AgentTask] 水合失败: {e}")
        raise HTTPException(status_code=500, detail=f"水合失败: {str(e)}")


@router.get("/events/{task_id}", response_model=TaskEventResponse)
async def get_task_events(
    task_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """获取任务事件日志"""
    try:
        from app.models.agent_task import AgentTaskEvent, AgentTaskStatus
        from sqlalchemy import select, desc
        
        task_result = await db.execute(
            select(AgentTaskStatus).where(AgentTaskStatus.task_id == task_id)
        )
        task_record = task_result.scalar_one_or_none()
        
        if not task_record:
            raise HTTPException(status_code=404, detail="未找到任务记录")
        
        if task_record.tenant_id != tenant_context["tenant_id"]:
            raise HTTPException(status_code=403, detail="无权访问此任务")
        
        events_result = await db.execute(
            select(AgentTaskEvent)
            .where(AgentTaskEvent.task_id == task_id)
            .order_by(desc(AgentTaskEvent.created_at))
            .limit(limit)
        )
        
        events = [
            {
                "event_type": event.event_type,
                "node_name": event.node_name,
                "message": event.event_message,
                "event_data": event.event_data,
                "created_at": event.created_at.isoformat() if event.created_at else None
            }
            for event in events_result.scalars().all()
        ]
        
        return TaskEventResponse(
            task_id=task_id,
            events=events,
            total_count=len(events)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AgentTask] 获取事件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取事件失败: {str(e)}")


@router.post("/resume/{thread_id}")
async def resume_task(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    恢复中断的任务
    
    场景：
    - 用户切回页面发现任务中断
    - 前端调用此接口重新激活任务
    - 后端从最新检查点继续执行
    """
    try:
        from app.models.agent_task import AgentTaskStatus, TaskStatus
        from sqlalchemy import select, update
        
        result = await db.execute(
            select(AgentTaskStatus)
            .where(
                AgentTaskStatus.thread_id == thread_id,
                AgentTaskStatus.tenant_id == tenant_context["tenant_id"]
            )
        )
        
        task_record = result.scalar_one_or_none()
        
        if not task_record:
            raise HTTPException(status_code=404, detail="未找到任务记录")
        
        postgres_saver = get_postgres_saver(get_db_session_factory())
        checkpoint_id = await postgres_saver.get_latest_checkpoint_id(thread_id)
        
        if not checkpoint_id:
            raise HTTPException(status_code=400, detail="没有可用的检查点，无法恢复")
        
        await db.execute(
            update(AgentTaskStatus)
            .where(AgentTaskStatus.task_id == task_record.task_id)
            .values(status=TaskStatus.PENDING, error_message=None)
        )
        await db.commit()
        
        logger.info(f"[AgentTask] 恢复任务: thread_id={thread_id[:8]}...")
        
        return {
            "status": "resumed",
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "message": "任务已恢复，将从断点继续执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AgentTask] 恢复任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


@router.post("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """取消任务"""
    try:
        from app.models.agent_task import AgentTaskStatus, TaskStatus
        from sqlalchemy import update
        
        result = await db.execute(
            select(AgentTaskStatus).where(AgentTaskStatus.task_id == task_id)
        )
        
        task_record = result.scalar_one_or_none()
        
        if not task_record:
            raise HTTPException(status_code=404, detail="未找到任务记录")
        
        if task_record.tenant_id != tenant_context["tenant_id"]:
            raise HTTPException(status_code=403, detail="无权访问此任务")
        
        if task_record.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"任务已结束，无法取消 (status={task_record.status})")
        
        await db.execute(
            update(AgentTaskStatus)
            .where(AgentTaskStatus.task_id == task_id)
            .values(status=TaskStatus.CANCELLED, completed_at=datetime.now())
        )
        await db.commit()
        
        logger.info(f"[AgentTask] 取消任务: task_id={task_id}")
        
        return {
            "status": "cancelled",
            "task_id": task_id,
            "message": "任务已取消"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AgentTask] 取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")


@router.delete("/clear/{thread_id}")
async def clear_thread(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """清理线程的所有数据和检查点"""
    try:
        from app.models.agent_task import AgentTaskStatus
        from sqlalchemy import delete
        
        await db.execute(
            delete(AgentTaskStatus)
            .where(
                AgentTaskStatus.thread_id == thread_id,
                AgentTaskStatus.tenant_id == tenant_context["tenant_id"]
            )
        )
        await db.commit()
        
        postgres_saver = get_postgres_saver(get_db_session_factory())
        await postgres_saver.delete_checkpoint(thread_id)
        
        logger.info(f"[AgentTask] 清理线程: thread_id={thread_id[:8]}...")
        
        return {
            "status": "cleared",
            "thread_id": thread_id,
            "message": "线程数据已清理"
        }
        
    except Exception as e:
        logger.error(f"[AgentTask] 清理线程失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")
