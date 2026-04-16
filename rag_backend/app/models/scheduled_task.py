"""
定时任务数据库模型
存储定时任务的配置和执行历史
"""

import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
import enum


class TaskType(str, enum.Enum):
    """任务类型"""
    TAX_REMINDER = "tax_reminder"  # 税务申报提醒
    FINANCIAL_REPORT = "financial_report"  # 定期财务报告
    POLICY_UPDATE = "policy_update"  # 政策更新推送
    ANOMALY_CHECK = "anomaly_check"  # 财务异常检查
    CUSTOM = "custom"  # 自定义任务


class TaskFrequency(str, enum.Enum):
    """执行频率"""
    ONCE = "once"  # 一次性
    DAILY = "daily"  # 每日
    WEEKLY = "weekly"  # 每周
    MONTHLY = "monthly"  # 每月
    QUARTERLY = "quarterly"  # 每季度
    YEARLY = "yearly"  # 每年


class TaskStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class ScheduledTask(Base):
    """
    定时任务模型
    
    存储定时任务的配置信息
    """
    __tablename__ = "scheduled_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(String(100), unique=True, nullable=False, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    task_type = Column(String(50), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    frequency = Column(String(20), nullable=False)

    next_run_time = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_time = Column(DateTime(timezone=True), nullable=True)

    task_params = Column(JSONB, nullable=True)

    status = Column(String(20), default="pending", index=True)

    enabled = Column(Boolean, default=True)

    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    notification_enabled = Column(Boolean, default=True)
    notification_channels = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ScheduledTask(id={self.id}, name={self.name}, status={self.status})>"


class TaskExecutionLog(Base):
    """
    任务执行日志模型
    
    存储定时任务的执行记录
    """
    __tablename__ = "task_execution_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(String(100), nullable=False, index=True)
    scheduled_task_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    task_type = Column(String(50), nullable=False)

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)

    duration_seconds = Column(Integer, nullable=True)

    status = Column(String(20), nullable=False, index=True)

    result = Column(JSONB, nullable=True)

    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    execution_type = Column(String(20), default="scheduled")
    triggered_manually = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<TaskExecutionLog(id={self.id}, task_id={self.task_id}, status={self.status})>"


class TaskNotification(Base):
    """
    任务通知记录模型
    
    存储任务相关通知的发送记录
    """
    __tablename__ = "task_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=True)
    execution_log_id = Column(UUID(as_uuid=True), ForeignKey("task_execution_logs.id", ondelete="CASCADE"), nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    notification_type = Column(String(50), nullable=False)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    channels = Column(JSONB, nullable=True)

    status = Column(String(20), default="pending", index=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<TaskNotification(id={self.id}, type={self.notification_type}, status={self.status})>"
