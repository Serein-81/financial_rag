"""
任务管理 API 端点
提供定时任务的 CRUD 操作和执行日志查询
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from pydantic import BaseModel, field_validator

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.models.scheduled_task import ScheduledTask, TaskExecutionLog
from app.services.task_scheduler import task_scheduler

logger = logging.getLogger(__name__)

router = APIRouter()


class TaskCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    task_type: str
    frequency: str
    next_run_time: datetime
    params: Optional[dict] = None
    enabled: bool = True


class TaskUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    next_run_time: Optional[datetime] = None
    params: Optional[dict] = None
    enabled: Optional[bool] = None


class TaskToggleRequest(BaseModel):
    enabled: bool


class TaskResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    task_type: str
    frequency: str
    next_run_time: Optional[datetime]
    last_run_time: Optional[datetime]
    enabled: bool
    status: str
    params: Optional[dict] = None
    result: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime]

    @field_validator('id', mode='before')
    @classmethod
    def convert_id_to_str(cls, v):
        if hasattr(v, '__str__'):
            return str(v)
        return v

    class Config:
        from_attributes = True


def task_to_response(task: ScheduledTask) -> TaskResponse:
    """将数据库任务模型转换为API响应模型"""
    return TaskResponse(
        id=str(task.id),
        name=task.name,
        description=task.description,
        task_type=task.task_type,
        frequency=task.frequency,
        next_run_time=task.next_run_time,
        last_run_time=task.last_run_time,
        enabled=task.enabled,
        status=task.status,
        params=task.task_params,
        result=None,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


async def get_task_by_id_or_task_id(
    db: AsyncSession,
    task_identifier: str,
    user_id: uuid.UUID
) -> Optional[ScheduledTask]:
    """通过 id (UUID) 或 task_id (字符串) 查询任务"""
    try:
        task_uuid = uuid.UUID(task_identifier)
        query = select(ScheduledTask).where(
            and_(
                ScheduledTask.id == task_uuid,
                ScheduledTask.user_id == user_id
            )
        )
    except ValueError:
        query = select(ScheduledTask).where(
            and_(
                ScheduledTask.task_id == task_identifier,
                ScheduledTask.user_id == user_id
            )
        )
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


class ExecutionLogResponse(BaseModel):
    id: str
    task_id: str
    scheduled_task_id: Optional[str] = None
    task_name: Optional[str] = None
    task_type: Optional[str] = None
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[int]
    result: Optional[dict]
    error: Optional[str]
    error_traceback: Optional[str] = None
    execution_type: Optional[str] = None
    triggered_manually: Optional[bool] = False
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionLogListResponse(BaseModel):
    logs: List[ExecutionLogResponse]
    total: int
    page: int
    page_size: int


class TaskStatisticsResponse(BaseModel):
    total_tasks: int
    active_tasks: int
    paused_tasks: int
    completed_today: int
    failed_today: int
    upcoming_tasks: List[TaskResponse]


class TaxReminderRequest(BaseModel):
    tax_type: str
    due_date: datetime


@router.get("/list", response_model=TaskListResponse)
async def list_tasks(
    task_type: Optional[str] = Query(None, description="任务类型"),
    status: Optional[str] = Query(None, description="任务状态"),
    enabled: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取任务列表
    """
    try:
        conditions = [
            ScheduledTask.user_id == current_user.id,
            ScheduledTask.tenant_id == str(current_user.tenant_id)
        ]

        if task_type:
            conditions.append(ScheduledTask.task_type == task_type)
        if status:
            conditions.append(ScheduledTask.status == status)
        if enabled is not None:
            conditions.append(ScheduledTask.enabled == enabled)

        count_query = select(func.count(ScheduledTask.id)).where(and_(*conditions))
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        offset = (page - 1) * page_size
        query = (
            select(ScheduledTask)
            .where(and_(*conditions))
            .order_by(desc(ScheduledTask.created_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(query)
        tasks = result.scalars().all()

        return TaskListResponse(
            tasks=[task_to_response(t) for t in tasks],
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.post("/create", response_model=TaskResponse)
async def create_task(
    request: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新任务
    """
    try:
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = ScheduledTask(
            task_id=task_id,
            user_id=current_user.id,
            tenant_id=str(current_user.tenant_id),
            task_type=request.task_type,
            name=request.name,
            description=request.description,
            frequency=request.frequency,
            next_run_time=request.next_run_time,
            task_params=request.params,
            enabled=request.enabled,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        if request.enabled:
            await task_scheduler.add_task(task)

        return task_to_response(task)
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ 创建任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("/task/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个任务详情
    """
    try:
        query = select(ScheduledTask).where(
            and_(
                ScheduledTask.task_id == task_id,
                ScheduledTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取任务详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {str(e)}")


@router.put("/task/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新任务
    """
    try:
        task = await get_task_by_id_or_task_id(db, task_id, current_user.id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        original_task_id = task.task_id

        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(task, field):
                setattr(task, field, value)

        task.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(task)

        await task_scheduler.remove_task(original_task_id)
        if task.enabled:
            await task_scheduler.add_task(task)

        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ 更新任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新任务失败: {str(e)}")


@router.delete("/task/{task_id}")
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除任务
    """
    try:
        task = await get_task_by_id_or_task_id(db, task_id, current_user.id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        await task_scheduler.remove_task(task.task_id)

        await db.delete(task)
        await db.commit()

        return {"message": "任务已删除"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ 删除任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


@router.post("/task/{task_id}/toggle")
async def toggle_task(
    task_id: str,
    request: TaskToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    启用/禁用任务
    """
    try:
        task = await get_task_by_id_or_task_id(db, task_id, current_user.id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        task.enabled = request.enabled
        task.updated_at = datetime.now(timezone.utc)

        await db.commit()

        if request.enabled:
            await task_scheduler.add_task(task)
        else:
            await task_scheduler.remove_task(task.task_id)

        return {"message": f"任务已{'启用' if request.enabled else '禁用'}"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ 切换任务状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"切换任务状态失败: {str(e)}")


@router.post("/task/{task_id}/run")
async def run_task_now(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    手动立即执行任务
    """
    try:
        task = await get_task_by_id_or_task_id(db, task_id, current_user.id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        execution_id = await task_scheduler.run_task_now(task)

        return {"execution_id": execution_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 手动执行任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"手动执行任务失败: {str(e)}")


@router.get("/logs", response_model=ExecutionLogListResponse)
async def get_execution_logs(
    task_id: Optional[str] = Query(None, description="任务ID"),
    status: Optional[str] = Query(None, description="执行状态"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取任务执行日志列表
    """
    try:
        conditions = [
            TaskExecutionLog.user_id == current_user.id,
            TaskExecutionLog.tenant_id == str(current_user.tenant_id)
        ]

        if task_id:
            conditions.append(TaskExecutionLog.task_id == task_id)
        if status:
            conditions.append(TaskExecutionLog.status == status)
        if start_date:
            conditions.append(TaskExecutionLog.start_time >= start_date)
        if end_date:
            conditions.append(TaskExecutionLog.start_time <= end_date)

        count_query = select(func.count(TaskExecutionLog.id)).where(and_(*conditions))
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        offset = (page - 1) * page_size
        query = (
            select(TaskExecutionLog)
            .where(and_(*conditions))
            .order_by(desc(TaskExecutionLog.start_time))
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(query)
        logs = result.scalars().all()

        task_query = select(ScheduledTask.task_id, ScheduledTask.name).where(
            ScheduledTask.user_id == current_user.id
        )
        task_result = await db.execute(task_query)
        task_names = {row[0]: row[1] for row in task_result.all()}

        return ExecutionLogListResponse(
            logs=[
                ExecutionLogResponse(
                    id=str(log.id),
                    task_id=log.task_id,
                    scheduled_task_id=str(log.scheduled_task_id) if log.scheduled_task_id else None,
                    task_name=task_names.get(log.task_id),
                    task_type=log.task_type,
                    status=log.status,
                    start_time=log.start_time,
                    end_time=log.end_time,
                    duration=log.duration_seconds,
                    result=log.result,
                    error=log.error_message,
                    error_traceback=log.error_traceback,
                    execution_type=log.execution_type,
                    triggered_manually=log.triggered_manually,
                    created_at=log.created_at
                )
                for log in logs
            ],
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"❌ 获取执行日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取执行日志失败: {str(e)}")


@router.get("/logs/{log_id}", response_model=ExecutionLogResponse)
async def get_log_detail(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取执行日志详情
    """
    try:
        query = select(TaskExecutionLog).where(
            and_(
                TaskExecutionLog.id == uuid.UUID(log_id),
                TaskExecutionLog.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        log = result.scalar_one_or_none()

        if not log:
            raise HTTPException(status_code=404, detail="日志不存在")

        return ExecutionLogResponse(
            id=str(log.id),
            task_id=log.task_id,
            scheduled_task_id=str(log.scheduled_task_id) if log.scheduled_task_id else None,
            task_type=log.task_type,
            status=log.status,
            start_time=log.start_time,
            end_time=log.end_time,
            duration=log.duration_seconds,
            result=log.result,
            error=log.error_message,
            error_traceback=log.error_traceback,
            execution_type=log.execution_type,
            triggered_manually=log.triggered_manually,
            created_at=log.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取日志详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取日志详情失败: {str(e)}")


@router.get("/statistics", response_model=TaskStatisticsResponse)
async def get_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取任务统计信息
    """
    try:
        base_conditions = [
            ScheduledTask.user_id == current_user.id,
            ScheduledTask.tenant_id == str(current_user.tenant_id)
        ]

        total_query = select(func.count(ScheduledTask.id)).where(and_(*base_conditions))
        total_result = await db.execute(total_query)
        total_tasks = total_result.scalar()

        active_query = select(func.count(ScheduledTask.id)).where(
            and_(*base_conditions, ScheduledTask.enabled == True)
        )
        active_result = await db.execute(active_query)
        active_tasks = active_result.scalar()

        paused_query = select(func.count(ScheduledTask.id)).where(
            and_(*base_conditions, ScheduledTask.enabled == False)
        )
        paused_result = await db.execute(paused_query)
        paused_tasks = paused_result.scalar()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        completed_today_query = select(func.count(TaskExecutionLog.id)).where(
            and_(
                TaskExecutionLog.user_id == current_user.id,
                TaskExecutionLog.tenant_id == str(current_user.tenant_id),
                TaskExecutionLog.start_time >= today_start,
                TaskExecutionLog.status == "completed"
            )
        )
        completed_result = await db.execute(completed_today_query)
        completed_today = completed_result.scalar()

        failed_today_query = select(func.count(TaskExecutionLog.id)).where(
            and_(
                TaskExecutionLog.user_id == current_user.id,
                TaskExecutionLog.tenant_id == str(current_user.tenant_id),
                TaskExecutionLog.start_time >= today_start,
                TaskExecutionLog.status == "failed"
            )
        )
        failed_result = await db.execute(failed_today_query)
        failed_today = failed_result.scalar()

        upcoming_query = (
            select(ScheduledTask)
            .where(and_(*base_conditions, ScheduledTask.enabled == True))
            .order_by(ScheduledTask.next_run_time)
            .limit(5)
        )
        upcoming_result = await db.execute(upcoming_query)
        upcoming_tasks = upcoming_result.scalars().all()

        return TaskStatisticsResponse(
            total_tasks=total_tasks or 0,
            active_tasks=active_tasks or 0,
            paused_tasks=paused_tasks or 0,
            completed_today=completed_today or 0,
            failed_today=failed_today or 0,
            upcoming_tasks=[task_to_response(t) for t in upcoming_tasks]
        )
    except Exception as e:
        logger.error(f"❌ 获取统计信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.post("/setup/tax-reminder", response_model=TaskResponse)
async def setup_tax_reminder(
    request: TaxReminderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    快速设置税务提醒任务
    """
    try:
        tax_type_names = {
            "vat": "增值税",
            "income": "企业所得税",
            "personal": "个人所得税",
            "other": "其他税种"
        }

        task_name = f"税务申报提醒 - {tax_type_names.get(request.tax_type, request.tax_type)}"

        task_id = f"tax_reminder_{uuid.uuid4().hex[:12]}"

        task = ScheduledTask(
            task_id=task_id,
            user_id=current_user.id,
            tenant_id=str(current_user.tenant_id),
            task_type="tax_reminder",
            name=task_name,
            description=f"在申报截止日前提醒您完成{tax_type_names.get(request.tax_type, '税务')}申报",
            frequency="once",
            next_run_time=request.due_date,
            task_params={"tax_type": request.tax_type, "due_date": request.due_date.isoformat()},
            enabled=True,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        await task_scheduler.add_task(task)

        return task_to_response(task)
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ 创建税务提醒失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建税务提醒失败: {str(e)}")
