# app/models/workflow_trace.py

"""
工作流追踪数据模型

用于记录LangGraph工作流的执行过程，与AgentTracer形成双层追踪架构：
- WorkflowInstance: 工作流级别的追踪
- WorkflowNodeExecution: 节点级别的追踪
"""

from sqlalchemy import Column, String, Text, Integer, Float, JSON, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from enum import Enum as PyEnum

from app.db.base import Base


class WorkflowStatus(str, PyEnum):
    """工作流执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN_REVIEW = "waiting_human_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowNodeExecution(Base):
    """
    工作流节点执行记录
    
    记录每个节点的执行明细，与WorkflowInstance通过workflow_trace_id关联
    """
    __tablename__ = "workflow_node_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    workflow_trace_id = Column(UUID, ForeignKey("workflow_traces.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_trace_id = Column(UUID, ForeignKey("agent_traces.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的Agent追踪ID")
    
    node_name = Column(String(100), nullable=False, comment="节点名称")
    node_type = Column(String(50), nullable=True, comment="节点类型: normal/human_review/conditional")
    
    execution_order = Column(Integer, nullable=False, default=0, comment="执行顺序")
    
    input_data = Column(JSON, nullable=True, comment="节点输入（摘要）")
    output_data = Column(JSON, nullable=True, comment="节点输出（摘要）")
    
    status = Column(String(20), nullable=False, default="running", comment="状态: running/completed/failed/skipped")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    execution_time_ms = Column(Float, nullable=True, comment="执行时长（毫秒）")
    token_usage = Column(JSON, nullable=True, comment="Token使用量")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    
    workflow_trace = relationship("WorkflowTrace", back_populates="node_executions")
    
    __table_args__ = (
        Index('ix_workflow_node_executions_trace_order', 'workflow_trace_id', 'execution_order'),
        Index('ix_workflow_node_executions_node_name', 'node_name'),
    )
    
    def __repr__(self):
        return f"<WorkflowNodeExecution(id={self.id}, node={self.node_name}, status={self.status})>"


class WorkflowTrace(Base):
    """
    工作流追踪记录
    
    记录工作流实例的完整执行过程，是工作流级别追踪的核心
    """
    __tablename__ = "workflow_traces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    workflow_type = Column(String(100), nullable=False, index=True, comment="工作流类型: tax_submission/policy_notification/contract_review等")
    workflow_version = Column(String(50), nullable=True, comment="工作流版本")
    
    session_id = Column(UUID, ForeignKey("chat_sessions.id"), nullable=True, index=True, comment="关联的会话ID")
    tenant_id = Column(String(50), nullable=True, index=True, comment="租户ID")
    user_id = Column(UUID, nullable=True, index=True, comment="用户ID")
    
    input_data = Column(JSON, nullable=True, comment="工作流输入参数")
    output_data = Column(JSON, nullable=True, comment="工作流输出结果")
    
    status = Column(String(30), nullable=False, default="pending", index=True, comment="状态")
    
    current_node = Column(String(100), nullable=True, comment="当前执行节点")
    total_nodes = Column(Integer, nullable=False, default=0, comment="总节点数")
    completed_nodes = Column(Integer, nullable=False, default=0, comment="已完成节点数")
    
    execution_time_ms = Column(Float, nullable=True, comment="总执行时长（毫秒）")
    
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    checkpointer_type = Column(String(20), nullable=True, comment="检查点存储类型: redis/postgres")
    checkpoint_id = Column(String(100), nullable=True, comment="检查点ID")
    
    workflow_metadata = Column(JSON, nullable=True, comment="额外元数据")
    
    human_review_id = Column(UUID, ForeignKey("review_requests.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的人工审核请求ID")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    
    node_executions = relationship("WorkflowNodeExecution", back_populates="workflow_trace", cascade="all, delete-orphan", order_by="WorkflowNodeExecution.execution_order")
    
    __table_args__ = (
        Index('ix_workflow_traces_tenant_status', 'tenant_id', 'status'),
        Index('ix_workflow_traces_user_created', 'user_id', 'created_at'),
        Index('ix_workflow_traces_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<WorkflowTrace(id={self.id}, type={self.workflow_type}, status={self.status})>"
    
    @property
    def execution_duration_seconds(self) -> float:
        """获取执行时长（秒）"""
        if not self.execution_time_ms:
            return 0.0
        return self.execution_time_ms / 1000.0
    
    @property
    def progress_percentage(self) -> float:
        """获取完成进度百分比"""
        if self.total_nodes == 0:
            return 0.0
        return (self.completed_nodes / self.total_nodes) * 100
    
    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status in [WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value, WorkflowStatus.CANCELLED.value]
