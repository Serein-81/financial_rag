"""
定时任务调度器
提供税务申报提醒、定期报告生成、政策更新推送等功能

包含两个主要组件：
1. TaskScheduler: 调度器核心，管理定时任务的创建、调度和执行
2. TaskManager: 业务层面的任务配置封装，提供便捷的任务创建方法
"""

import asyncio
import logging
import traceback
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta, timezone
from enum import Enum

logger = logging.getLogger(__name__)

from app.services.tax_intelligence_service import TaxIntelligenceService
from app.services.financial_health_service import FinancialHealthService
from app.services.policy_tracking_service import PolicyTrackingService
from app.services.admin_notification_service import AdminNotificationService


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
    db_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None

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
            "retry_count": self.retry_count,
            "db_id": self.db_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id
        }


from dataclasses import dataclass


async def tax_reminder_task(params: Dict[str, Any]):
    """税务申报提醒任务"""
    try:
        tenant_id = params.get("tenant_id")
        tax_type = params.get("tax_type", "vat")
        user_id = params.get("user_id")

        logger.info(f"📋 执行税务申报提醒任务: {tenant_id}, {tax_type}")

        notification_service = AdminNotificationService()
        await notification_service.send_notification(
            user_id=user_id,
            title="税务申报提醒",
            message=f"您的{tax_type}申报即将到期，请及时处理。",
            notification_type="tax_reminder",
            priority="high"
        )

        logger.info(f"✅ 税务申报提醒已发送: {tenant_id}")

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 税务申报提醒任务数据错误: {e}", exc_info=True)
    except (OSError, IOError) as e:
        logger.error(f"❌ 税务申报提醒任务IO错误: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ 税务申报提醒任务失败: {e}", exc_info=True)


async def financial_health_report_task(params: Dict[str, Any]):
    """定期财务健康报告生成任务"""
    try:
        tenant_id = params.get("tenant_id")
        user_id = params.get("user_id")
        period_days = params.get("period_days", 30)

        logger.info(f"📋 执行定期财务健康报告任务: {tenant_id}, 周期: {period_days}天")

        service = FinancialHealthService()

        request = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "period_start": datetime.now().date() - timedelta(days=period_days),
            "period_end": datetime.now().date(),
            "include_anomaly_detection": True,
            "include_trend_analysis": True
        }

        result = await service.monitor_financial_health(request)

        logger.info(f"✅ 定期财务健康报告生成完成: {tenant_id}")

        return result

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 定期财务健康报告任务数据错误: {e}", exc_info=True)
    except (OSError, IOError) as e:
        logger.error(f"❌ 定期财务健康报告任务IO错误: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ 定期财务健康报告任务失败: {e}", exc_info=True)


async def policy_update_push_task(params: Dict[str, Any]):
    """政策更新推送任务"""
    try:
        tenant_id = params.get("tenant_id")
        subscription_id = params.get("subscription_id")

        logger.info(f"📋 执行政策更新推送任务: {tenant_id}")

        service = PolicyTrackingService()
        updates = await service.fetch_policy_updates(
            tenant_id=tenant_id,
            subscription_id=subscription_id
        )

        if updates and updates.get("updates"):
            notification_service = AdminNotificationService()
            await notification_service.send_notification(
                user_id=params.get("user_id"),
                title="政策更新通知",
                message=f"发现{len(updates['updates'])}条新政策更新",
                notification_type="policy_update",
                priority="medium"
            )

        logger.info(f"✅ 政策更新推送任务完成: {tenant_id}")

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 政策更新推送任务数据错误: {e}", exc_info=True)
    except (OSError, IOError) as e:
        logger.error(f"❌ 政策更新推送任务IO错误: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ 政策更新推送任务失败: {e}", exc_info=True)


async def anomaly_check_task(params: Dict[str, Any]):
    """财务异常检查任务"""
    try:
        tenant_id = params.get("tenant_id")
        user_id = params.get("user_id")

        logger.info(f"📋 执行财务异常检查任务: {tenant_id}")

        service = FinancialHealthService()

        request = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "period_start": datetime.now().date() - timedelta(days=7),
            "period_end": datetime.now().date(),
            "include_anomaly_detection": True,
            "include_trend_analysis": False
        }

        result = await service.monitor_financial_health(request)

        anomalies = result.get("anomalies_detected", [])
        if anomalies:
            notification_service = AdminNotificationService()
            await notification_service.send_notification(
                user_id=user_id,
                title="财务异常预警",
                message=f"检测到{len(anomalies)}个财务异常，请及时处理。",
                notification_type="anomaly_alert",
                priority="high"
            )

        logger.info(f"✅ 财务异常检查任务完成: {tenant_id}, 检测到{len(anomalies)}个异常")

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 财务异常检查任务数据错误: {e}", exc_info=True)
    except (OSError, IOError) as e:
        logger.error(f"❌ 财务异常检查任务IO错误: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ 财务异常检查任务失败: {e}", exc_info=True)


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
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
        task.status = TaskStatus.PENDING
        await self._task_queue.put(task)

    async def _execute_task(self, task: ScheduledTask, is_manual: bool = False):
        """执行任务"""
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
        start_time = datetime.now()
        
        execution_record = {
            "task_id": task.task_id,
            "task_name": task.name,
            "start_time": start_time.isoformat(),
            "status": "running"
        }

        try:
            callback_result = None
            if hasattr(task, 'callback') and task.callback:
                if asyncio.iscoroutinefunction(task.callback):
                    callback_result = await task.callback(task.params or {})
                else:
                    callback_result = task.callback(task.params or {})
            
            task.last_run_time = start_time
            task.status = TaskStatus.COMPLETED
            task.retry_count = 0

            execution_record["status"] = "completed"
            execution_record["end_time"] = datetime.now().isoformat()
            execution_record["duration"] = (datetime.now() - start_time).total_seconds()

            self._update_next_run_time(task)

            logger.info(f"✅ 任务执行成功: {task.name} ({task.task_id})")
            
            await self._sync_task_to_db(task)
            
            end_time = datetime.now()
            result_message = f"任务执行成功"
            callback_data = None
            if callback_result is not None:
                result_message = f"任务执行成功"
                callback_data = callback_result
            
            await self._save_execution_log_to_db(
                task=task,
                status="completed",
                start_time=start_time,
                end_time=end_time,
                result_data={
                    "success": True,
                    "message": result_message,
                    "data": {
                        "task_name": task.name,
                        "callback_result": callback_data
                    }
                },
                is_manual=is_manual
            )

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 任务执行数据错误: {task.name} ({task.task_id}): {e}", exc_info=True)
            end_time = datetime.now()
            await self._save_execution_log_to_db(
                task=task,
                status="failed",
                start_time=start_time,
                end_time=end_time,
                error=str(e),
                error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                is_manual=is_manual
            )
        except (OSError, IOError) as e:
            logger.error(f"❌ 任务执行IO错误: {task.name} ({task.task_id}): {e}", exc_info=True)
            end_time = datetime.now()
            await self._save_execution_log_to_db(
                task=task,
                status="failed",
                start_time=start_time,
                end_time=end_time,
                error=str(e),
                error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                is_manual=is_manual
            )
        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task.name} ({task.task_id}): {e}", exc_info=True)

            task.retry_count += 1
            end_time = datetime.now()

            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                logger.info(f"🔄 任务将重试 ({task.retry_count}/{task.max_retries}): {task.name}")
                await asyncio.sleep(60 * (2 ** task.retry_count))
                await self._queue_task(task)
                
                await self._save_execution_log_to_db(
                    task=task,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    error=str(e),
                    error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                    is_manual=is_manual
                )
            else:
                task.status = TaskStatus.FAILED
                execution_record["status"] = "failed"
                execution_record["error"] = str(e)

                await self._notify_task_failure(task, e)
                
                await self._save_execution_log_to_db(
                    task=task,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    error=str(e),
                    error_traceback=traceback.format_exc() if hasattr(traceback, 'format_exc') else None,
                    is_manual=is_manual
                )

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
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
        self._tasks[task.task_id] = task
        logger.info(f"📋 添加定时任务: {task.name} ({task.task_id}), 下次执行: {task.next_run_time}")
    
    def _convert_to_dataclass(self, db_task) -> ScheduledTask:
        """将数据库模型转换为调度器数据类"""
        
        task_type = TaskType(db_task.task_type) if isinstance(db_task.task_type, str) else db_task.task_type
        frequency = TaskFrequency(db_task.frequency) if isinstance(db_task.frequency, str) else db_task.frequency
        status = TaskStatus(db_task.status) if isinstance(db_task.status, str) else db_task.status
        
        return ScheduledTask(
            task_id=db_task.task_id,
            task_type=task_type,
            name=db_task.name,
            description=db_task.description or "",
            frequency=frequency,
            next_run_time=db_task.next_run_time,
            last_run_time=db_task.last_run_time,
            params=db_task.task_params or {},
            status=status,
            enabled=db_task.enabled,
            retry_count=db_task.retry_count,
            max_retries=db_task.max_retries,
            db_id=str(db_task.id),
            user_id=str(db_task.user_id),
            tenant_id=str(db_task.tenant_id)
        )

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
        if not isinstance(task, ScheduledTask):
            task = self._convert_to_dataclass(task)
        
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

    async def _save_execution_log_to_db(
        self,
        task: ScheduledTask,
        status: str,
        start_time: datetime,
        end_time: datetime,
        error: Optional[str] = None,
        error_traceback: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None,
        is_manual: bool = False
    ):
        """保存任务执行日志到数据库"""
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.scheduled_task import TaskExecutionLog
            
            async with AsyncSessionLocal() as db:
                duration_seconds = int((end_time - start_time).total_seconds())
                
                execution_log = TaskExecutionLog(
                    task_id=task.task_id,
                    scheduled_task_id=task.db_id,
                    user_id=task.user_id,
                    tenant_id=task.tenant_id,
                    task_type=task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type),
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration_seconds,
                    status=status,
                    result=result_data,
                    error_message=error,
                    error_traceback=error_traceback,
                    execution_type="manual" if is_manual else "scheduled",
                    triggered_manually=is_manual,
                    created_at=datetime.now(timezone.utc)
                )
                
                db.add(execution_log)
                await db.commit()
                
                log_status = "成功" if status == "completed" else "失败"
                logger.info(f"📝 已保存执行日志到数据库: {task.name} - {log_status} (耗时: {duration_seconds}s)")
                
        except Exception as e:
            logger.error(f"❌ 保存执行日志失败: {e}", exc_info=True)

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


class TaskManager:
    """任务管理器 - 业务层面的任务配置封装"""

    def __init__(self):
        self.tax_service = TaxIntelligenceService()
        self.financial_service = FinancialHealthService()
        self.policy_service = PolicyTrackingService()
        logger.info("✅ 任务管理器初始化完成")

    def setup_tax_reminder(
        self,
        tenant_id: str,
        user_id: str,
        tax_type: str,
        due_date: datetime
    ) -> str:
        """设置税务申报提醒"""
        task_id = f"tax_reminder_{tenant_id}_{tax_type}_{due_date.strftime('%Y%m%d')}"

        task_scheduler.create_task(
            task_id=task_id,
            task_type=TaskType.TAX_REMINDER,
            name=f"税务申报提醒 - {tax_type}",
            description=f"提醒租户{tenant_id}申报{tax_type}",
            frequency=TaskFrequency.ONCE,
            next_run_time=due_date - timedelta(days=3),
            callback=tax_reminder_task,
            params={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "tax_type": tax_type,
                "due_date": due_date.isoformat()
            },
            enabled=True
        )

        logger.info(f"✅ 已设置税务申报提醒: {task_id}")
        return task_id

    def setup_periodic_financial_report(
        self,
        tenant_id: str,
        user_id: str,
        frequency: TaskFrequency = TaskFrequency.WEEKLY
    ) -> str:
        """设置定期财务报告生成"""
        task_id = f"financial_report_{tenant_id}_{frequency.value}"

        next_run = datetime.now()
        if frequency == TaskFrequency.DAILY:
            next_run = next_run + timedelta(days=1)
        elif frequency == TaskFrequency.WEEKLY:
            next_run = next_run + timedelta(weeks=1)
        elif frequency == TaskFrequency.MONTHLY:
            next_run = task_scheduler._add_months(next_run, 1)

        task_scheduler.create_task(
            task_id=task_id,
            task_type=TaskType.FINANCIAL_REPORT,
            name=f"定期财务报告 - {frequency.value}",
            description=f"定期生成租户{tenant_id}的财务报告",
            frequency=frequency,
            next_run_time=next_run,
            callback=financial_health_report_task,
            params={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "period_days": 7 if frequency == TaskFrequency.WEEKLY else 30
            },
            enabled=True
        )

        logger.info(f"✅ 已设置定期财务报告: {task_id}")
        return task_id

    def setup_policy_update_subscription(
        self,
        tenant_id: str,
        user_id: str,
        subscription_id: str,
        frequency: TaskFrequency = TaskFrequency.DAILY
    ) -> str:
        """设置政策更新订阅"""
        task_id = f"policy_update_{tenant_id}_{subscription_id}"

        next_run = datetime.now() + timedelta(days=1)

        task_scheduler.create_task(
            task_id=task_id,
            task_type=TaskType.POLICY_UPDATE,
            name="政策更新推送",
            description=f"推送租户{tenant_id}订阅的政策更新",
            frequency=frequency,
            next_run_time=next_run,
            callback=policy_update_push_task,
            params={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "subscription_id": subscription_id
            },
            enabled=True
        )

        logger.info(f"✅ 已设置政策更新订阅: {task_id}")
        return task_id

    def setup_anomaly_check(
        self,
        tenant_id: str,
        user_id: str,
        frequency: TaskFrequency = TaskFrequency.DAILY
    ) -> str:
        """设置财务异常检查"""
        task_id = f"anomaly_check_{tenant_id}"

        next_run = datetime.now() + timedelta(days=1)

        task_scheduler.create_task(
            task_id=task_id,
            task_type=TaskType.ANOMALY_CHECK,
            name="财务异常检查",
            description=f"定期检查租户{tenant_id}的财务异常",
            frequency=frequency,
            next_run_time=next_run,
            callback=anomaly_check_task,
            params={
                "tenant_id": tenant_id,
                "user_id": user_id
            },
            enabled=True
        )

        logger.info(f"✅ 已设置财务异常检查: {task_id}")
        return task_id

    def list_tenant_tasks(self, tenant_id: str):
        """列出租户的所有任务"""
        all_tasks = task_scheduler.list_tasks()

        tenant_tasks = [
            task for task in all_tasks
            if task.params and task.params.get("tenant_id") == tenant_id
        ]

        return {
            "tenant_id": tenant_id,
            "tasks": [task.to_dict() for task in tenant_tasks],
            "total_count": len(tenant_tasks)
        }

    def cancel_tenant_tasks(self, tenant_id: str):
        """取消租户的所有任务"""
        all_tasks = task_scheduler.list_tasks()

        cancelled = []
        for task in all_tasks:
            if task.params and task.params.get("tenant_id") == tenant_id:
                task_scheduler.delete_task(task.task_id)
                cancelled.append(task.task_id)

        logger.info(f"✅ 已取消{len(cancelled)}个租户任务: {tenant_id}")
        return cancelled


task_manager = TaskManager()
