"""
Agent 任务状态数据库模型

用于跟踪 LangGraph 任务执行状态，支持跨会话恢复
"""

import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class TaskStatus(str, enum.Enum):
    """任务状态枚举 - 值必须与数据库枚举类型完全匹配（小写）"""
    PENDING = "pending"           # 等待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"        # 已完成
    FAILED = "failed"             # 执行失败
    CANCELLED = "cancelled"       # 已取消
    INTERRUPTED = "interrupted"   # 被中断（前端断开）


class TaskPriority(str, enum.Enum):
    """任务优先级 - 值必须与数据库枚举类型完全匹配（小写）"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AgentTaskStatus(Base):
    """Agent 任务状态表"""
    __tablename__ = "agent_task_status"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    task_id = Column(String(100), unique=True, nullable=False, index=True)
    thread_id = Column(String(255), nullable=False, index=True)
    
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    request_id = Column(String(100), nullable=True, index=True)
    
    task_type = Column(String(50), nullable=False)
    task_name = Column(String(255), nullable=True)
    
    status = Column(
        SQLEnum(
            TaskStatus,
            name="task_status_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True
    )
    priority = Column(
        SQLEnum(
            TaskPriority,
            name="task_priority_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=TaskPriority.NORMAL,
        nullable=False
    )
    
    user_query = Column(Text, nullable=True)
    final_response = Column(Text, nullable=True)
    
    current_node = Column(String(100), nullable=True)
    progress_percent = Column(Integer, default=0)
    progress_message = Column(String(500), nullable=True)
    
    specialist_progress = Column(JSONB, nullable=True)
    
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    execution_time_ms = Column(Float, default=0.0)
    
    arq_job_id = Column(String(100), nullable=True, index=True)
    
    checkpoint_id = Column(String(255), nullable=True)
    
    extra_metadata = Column(JSONB, nullable=True)
    
    needs_clarification = Column(Boolean, default=False, nullable=False)
    clarification_request = Column(JSONB, nullable=True)
    intent_analysis = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_task_status_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_task_status_user', 'user_id', 'status'),
        Index('idx_task_status_thread', 'thread_id', 'status'),
    )
    
    def __repr__(self):
        return f"<AgentTaskStatus(id={self.task_id}, status={self.status})>"
    
    @property
    def is_finished(self) -> bool:
        """是否已结束（完成、失败、取消）"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.status in [TaskStatus.RUNNING, TaskStatus.PENDING]
    
    def to_summary(self) -> dict:
        """转换为摘要字典"""
        return {
            "task_id": self.task_id,
            "thread_id": self.thread_id,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "task_type": self.task_type,
            "current_node": self.current_node,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "specialist_progress": self.specialist_progress,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message
        }


class AgentTaskEvent(Base):
    """Agent 任务事件日志表"""
    __tablename__ = "agent_task_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    task_id = Column(String(100), ForeignKey("agent_task_status.task_id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, nullable=True)
    
    node_name = Column(String(100), nullable=True)
    event_message = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_task_event_task', 'task_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AgentTaskEvent(task_id={self.task_id}, type={self.event_type})>"


class AgentTaskCheckpoint(Base):
    """Agent 任务检查点表（用于恢复）"""
    __tablename__ = "agent_task_checkpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    task_id = Column(String(100), ForeignKey("agent_task_status.task_id", ondelete="CASCADE"), nullable=False, index=True)
    
    checkpoint_id = Column(String(255), nullable=False)
    parent_checkpoint_id = Column(String(255), nullable=True)
    
    node_name = Column(String(100), nullable=True)
    
    state_data = Column(JSONB, nullable=False)
    extra_metadata = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_task_checkpoint_task', 'task_id', 'created_at'),
        Index('idx_task_checkpoint_parent', 'parent_checkpoint_id'),
    )
    
    def __repr__(self):
        return f"<AgentTaskCheckpoint(task_id={self.task_id}, node={self.node_name})>"