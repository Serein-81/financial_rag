"""
定时任务调度器
提供税务申报提醒、定期报告生成、政策更新推送等功能
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型"""
    TAX_REMINDER = "tax_reminder"  # 税务申报提醒
    FINANCIAL_REPORT = "financial_report"  # 定期财务报告
    POLICY_UPDATE = "policy_update"  # 政策更新推送
    ANOMALY_CHECK = "anomaly_check"  # 财务异常检查
    CUSTOM = "custom"  # 自定义任务


class TaskFrequency(str, Enum):
    """执行频率"""
    ONCE = "once"  # 一次性
    DAILY = "daily"  # 每日
    WEEKLY = "weekly"  # 每周
    MONTHLY = "monthly"  # 每月
    QUARTERLY = "quarterly"  # 每季度
    YEARLY = "yearly"  # 每年


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    task_type: TaskType
    name: str
    description: str
    frequency: TaskFrequency
    next_run_time: datetime
    last_run_time: Optional[datetime] = None
    callback: Optional[Callable] = None
    params: Dict[str, Any] = None
    status: TaskStatus = TaskStatus.PENDING
    enabled: bool = True
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "name": self.name,
            "description": self.description,
            "frequency": self.frequency.value,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "status": self.status.value,
            "enabled": self.enabled,
            "retry_count": self.retry_count
        }


from dataclasses import dataclass


class TaskScheduler:
    """
    定时任务调度器
    
    功能：
    1. 管理定时任务（创建、更新、删除、暂停、恢复）
    2. 按计划执行任务
    3. 任务重试机制
    4. 任务执行日志
    """
    
    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._execution_history: List[Dict[str, Any]] = []
        logger.info("✅ 定时任务调度器初始化完成")

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("⚠️ 调度器已在运行中")
            return

        self._running = True
        logger.info("🚀 定时任务调度器已启动")

        asyncio.create_task(self._scheduler_loop())
        asyncio.create_task(self._execution_loop())

    async def stop(self):
        """停止调度器"""
        self._running = False
        logger.info("⏹️ 定时任务调度器已停止")

    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                current_time = datetime.now(timezone.utc)

                for task_id, task in self._tasks.items():
                    if not task.enabled:
                        continue

                    if task.status == TaskStatus.RUNNING:
                        continue

                    if task.next_run_time:
                        next_run = task.next_run_time
                        if next_run.tzinfo is None:
                            next_run = next_run.replace(tzinfo=timezone.utc)
                        if next_run <= current_time:
                            logger.info(f"📋 触发定时任务: {task.name} ({task_id})")
                            await self._queue_task(task)

                await asyncio.sleep(60)

            except (ValueError, KeyError) as e:
                logger.error(f"❌ 调度循环数据错误: {e}", exc_info=True)
                await asyncio.sleep(60)
            except (OSError, IOError) as e:
                logger.error(f"❌ 调度循环IO错误: {e}", exc_info=True)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"❌ 调度循环异常: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _execution_loop(self):
        """任务执行循环"""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )

                asyncio.create_task(self._execute_task(task))

            except asyncio.TimeoutError:
                continue
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 任务执行循环数据错误: {e}", exc_info=True)
                await asyncio.sleep(1)
            except (OSError, IOError) as e:
                logger.error(f"❌ 任务执行循环IO错误: {e}", exc_info=True)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ 任务执行循环异常: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _queue_task(self, task: ScheduledTask):
        """将任务加入执行队列"""
        task.status = TaskStatus.PENDING
        await self._task_queue.put(task)

    async def _execute_task(self, task: ScheduledTask, is_manual: bool = False):
        """执行任务"""
        start_time = datetime.now()
        
        execution_record = {
            "task_id": task.task_id,
            "task_name": task.name,
            "start_time": start_time.isoformat(),
            "status": "running"
        }

        try:
            if hasattr(task, 'callback') and task.callback:
                if asyncio.iscoroutinefunction(task.callback):
                    await task.callback(task.params or {})
                else:
                    task.callback(task.params or {})
            
            task.last_run_time = start_time
            task.status = TaskStatus.COMPLETED
            task.retry_count = 0

            execution_record["status"] = "completed"
            execution_record["end_time"] = datetime.now().isoformat()
            execution_record["duration"] = (datetime.now() - start_time).total_seconds()

            self._update_next_run_time(task)

            logger.info(f"✅ 任务执行成功: {task.name} ({task.task_id})")
            
            await self._sync_task_to_db(task)

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 任务执行数据错误: {task.name} ({task.task_id}): {e}", exc_info=True)
        except (OSError, IOError) as e:
            logger.error(f"❌ 任务执行IO错误: {task.name} ({task.task_id}): {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task.name} ({task.task_id}): {e}", exc_info=True)

            task.retry_count += 1

            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                logger.info(f"🔄 任务将重试 ({task.retry_count}/{task.max_retries}): {task.name}")
                await asyncio.sleep(60 * (2 ** task.retry_count))
                await self._queue_task(task)
            else:
                task.status = TaskStatus.FAILED
                execution_record["status"] = "failed"
                execution_record["error"] = str(e)

                await self._notify_task_failure(task, e)

            await self._sync_task_to_db(task)

            execution_record["end_time"] = datetime.now().isoformat()
            execution_record["duration"] = (datetime.now() - start_time).total_seconds()

        self._execution_history.append(execution_record)

        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-1000:]

    def _update_next_run_time(self, task: ScheduledTask):
        """更新下次执行时间"""
        if task.frequency == TaskFrequency.ONCE:
            task.next_run_time = None
            task.enabled = False
        elif task.frequency == TaskFrequency.DAILY:
            task.next_run_time = task.next_run_time + timedelta(days=1)
        elif task.frequency == TaskFrequency.WEEKLY:
            task.next_run_time = task.next_run_time + timedelta(weeks=1)
        elif task.frequency == TaskFrequency.MONTHLY:
            task.next_run_time = self._add_months(task.next_run_time, 1)
        elif task.frequency == TaskFrequency.QUARTERLY:
            task.next_run_time = self._add_months(task.next_run_time, 3)
        elif task.frequency == TaskFrequency.YEARLY:
            task.next_run_time = self._add_months(task.next_run_time, 12)

    def _add_months(self, date: datetime, months: int) -> datetime:
        """增加月份"""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date.replace(year=year, month=month, day=day)

    async def _notify_task_failure(self, task: ScheduledTask, error: Exception):
        """通知任务失败"""
        logger.error(f"🚨 任务失败超过最大重试次数: {task.name} ({task.task_id})")

    def create_task(
        self,
        task_id: str,
        task_type: TaskType,
        name: str,
        description: str,
        frequency: TaskFrequency,
        next_run_time: datetime,
        callback: Optional[Callable] = None,
        params: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ) -> ScheduledTask:
        """创建定时任务"""
        task = ScheduledTask(
            task_id=task_id,
            task_type=task_type,
            name=name,
            description=description,
            frequency=frequency,
            next_run_time=next_run_time,
            callback=callback,
            params=params or {},
            enabled=enabled
        )

        self._tasks[task_id] = task
        logger.info(f"📋 创建定时任务: {name} ({task_id}), 下次执行: {next_run_time}")

        return task

    async def add_task(self, task: ScheduledTask) -> None:
        """添加预创建的定时任务"""
        self._tasks[task.task_id] = task
        logger.info(f"📋 添加定时任务: {task.name} ({task.task_id}), 下次执行: {task.next_run_time}")

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    async def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            logger.info(f"🗑️ 移除定时任务: {task.name} ({task_id})")
            del self._tasks[task_id]
            return True
        return False

    async def run_task_now(self, task: ScheduledTask) -> str:
        """手动立即执行任务"""
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        logger.info(f"▶️ 手动执行任务: {task.name} ({task.task_id}), execution_id: {execution_id}")
        
        asyncio.create_task(self._execute_task(task, is_manual=True))
        
        return execution_id

    async def _sync_task_to_db(self, task: ScheduledTask):
        """同步任务状态到数据库"""
        try:
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal
            from app.models.scheduled_task import ScheduledTask as DBTaskModel
            
            async with AsyncSessionLocal() as db:
                query = select(DBTaskModel).where(DBTaskModel.task_id == task.task_id)
                result = await db.execute(query)
                db_task = result.scalar_one_or_none()
                
                if db_task:
                    db_task.last_run_time = task.last_run_time
                    db_task.next_run_time = task.next_run_time
                    db_task.status = task.status.value
                    db_task.enabled = task.enabled
                    db_task.updated_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.info(f"💾 已同步任务状态到数据库: {task.name}")
        except Exception as e:
            logger.error(f"❌ 同步任务状态失败: {e}", exc_info=True)

    def list_tasks(
        self,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        enabled: Optional[bool] = None
    ) -> List[ScheduledTask]:
        """列出任务"""
        tasks = list(self._tasks.values())

        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]

        if status:
            tasks = [t for t in tasks if t.status == status]

        if enabled is not None:
            tasks = [t for t in tasks if t.enabled == enabled]

        return tasks

    def update_task(
        self,
        task_id: str,
        enabled: Optional[bool] = None,
        next_run_time: Optional[datetime] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if enabled is not None:
            task.enabled = enabled

        if next_run_time:
            task.next_run_time = next_run_time

        if params:
            task.params.update(params)

        logger.info(f"✏️ 更新定时任务: {task.name} ({task_id})")
        return True

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            task = self._tasks.pop(task_id)
            logger.info(f"🗑️ 删除定时任务: {task.name} ({task_id})")
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        return self.update_task(task_id, enabled=False)

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        return self.update_task(task_id, enabled=True)

    def get_execution_history(
        self,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取执行历史"""
        if task_id:
            history = [h for h in self._execution_history if h["task_id"] == task_id]
        else:
            history = self._execution_history

        return history[-limit:]

    async def execute_task_now(self, task_id: str) -> bool:
        """立即执行任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        await self._queue_task(task)
        logger.info(f"🚀 立即执行任务: {task.name} ({task_id})")
        return True


task_scheduler = TaskScheduler()
