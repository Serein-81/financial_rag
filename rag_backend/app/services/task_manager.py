"""
定时任务实现
具体的税务申报提醒、定期报告、政策推送等任务实现
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.services.task_scheduler import task_scheduler, TaskType, TaskFrequency
from app.services.tax_intelligence_service import TaxIntelligenceService
from app.services.financial_health_service import FinancialHealthService
from app.services.policy_tracking_service import PolicyTrackingService
from app.services.admin_notification_service import AdminNotificationService

logger = logging.getLogger(__name__)


async def tax_reminder_task(params: Dict[str, Any]):
    """
    税务申报提醒任务
    
    参数:
        tenant_id: 租户ID
        tax_type: 税种类型
        due_date: 申报截止日期
        user_id: 用户ID
    """
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
    """
    定期财务健康报告生成任务
    
    参数:
        tenant_id: 租户ID
        user_id: 用户ID
        period_days: 报告周期（天数）
    """
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
    """
    政策更新推送任务
    
    参数:
        tenant_id: 租户ID
        subscription_id: 订阅ID
    """
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
    """
    财务异常检查任务
    
    参数:
        tenant_id: 租户ID
        user_id: 用户ID
    """
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


class TaskManager:
    """任务管理器"""

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
            next_run = self._add_months(next_run, 1)

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

    def _add_months(self, date: datetime, months: int) -> datetime:
        """增加月份"""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date.replace(year=year, month=month, day=day)

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
