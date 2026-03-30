"""
审核请求数据模型

用于存储需要人工审核的请求
"""

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class ReviewRequest(Base):
    """
    审核请求模型
    
    用于记录需要人工审核的请求，包括：
    - 税务报告异常检测
    - 置信度低于阈值
    - 发现高风险问题
    - 用户主动发起的审核请求
    """
    __tablename__ = "review_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="关联的任务ID")
    tenant_id = Column(String(50), nullable=False, index=True, comment="租户ID（隔离）")
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="发起人ID")
    
    # 审核类型和优先级
    review_type = Column(String(50), nullable=False, default="tax", comment="审核类型: tax/finance/legal/compliance")
    priority = Column(String(20), nullable=False, default="normal", comment="优先级: low/normal/high/urgent")
    
    # 触发原因
    trigger_reason = Column(String(100), nullable=False, comment="触发原因")
    trigger_details = Column(JSONB, nullable=True, comment="触发详情")
    
    # 审核内容
    title = Column(String(500), nullable=True, comment="审核标题")
    description = Column(Text, nullable=True, comment="审核描述")
    content = Column(JSONB, nullable=True, comment="审核内容（AI处理结果等）")
    
    # 关联文档
    document_ids = Column(JSONB, nullable=True, comment="关联的文档ID列表")
    
    # 审核状态
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/in_progress/completed/rejected")
    assigned_to = Column(UUID(as_uuid=True), nullable=True, index=True, comment="分配给谁")
    assigned_at = Column(DateTime(timezone=True), nullable=True, comment="分配时间")
    
    # 审核结果
    review_result = Column(JSONB, nullable=True, comment="审核结果")
    review_comments = Column(Text, nullable=True, comment="审核意见")
    reviewed_at = Column(DateTime(timezone=True), nullable=True, comment="审核时间")
    reviewed_by = Column(UUID(as_uuid=True), nullable=True, comment="审核人")
    
    # 处理时间统计
    processing_time_seconds = Column(Integer, nullable=True, comment="处理时长（秒）")
    sla_deadline = Column(DateTime(timezone=True), nullable=True, comment="SLA截止时间")
    
    # 元数据
    extra_metadata = Column(JSONB, nullable=True, comment="其他元数据")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 索引
    __table_args__ = (
        Index('ix_review_requests_tenant_status', 'tenant_id', 'status'),
        Index('ix_review_requests_tenant_priority', 'tenant_id', 'priority'),
        Index('ix_review_requests_assigned_status', 'assigned_to', 'status'),
        Index('ix_review_requests_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ReviewRequest(id={self.id}, task_id={self.task_id}, type={self.review_type}, status={self.status})>"
    
    @property
    def is_overdue(self) -> bool:
        """是否已超过SLA"""
        if not self.sla_deadline:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.sla_deadline
    
    @property
    def age_hours(self) -> int:
        """从创建到现在的小时数"""
        if not self.created_at:
            return 0
        from datetime import datetime, timezone
        delta = datetime.now(timezone.utc) - self.created_at
        return int(delta.total_seconds() / 3600)


class ReviewRequestComment(Base):
    """
    审核评论模型
    
    用于存储审核过程中的评论和讨论
    """
    __tablename__ = "review_request_comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_request_id = Column(UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    content = Column(Text, nullable=False, comment="评论内容")
    comment_type = Column(String(20), nullable=False, default="comment", comment="评论类型: comment/note/action")
    
    # 关联实体
    related_entity_type = Column(String(50), nullable=True, comment="关联实体类型")
    related_entity_id = Column(String(100), nullable=True, comment="关联实体ID")
    
    # 附件
    attachments = Column(JSONB, nullable=True, comment="附件列表")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 索引
    __table_args__ = (
        Index('ix_review_request_comments_request_created', 'review_request_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ReviewRequestComment(id={self.id}, request_id={self.review_request_id}, type={self.comment_type})>"


class ReviewRequestAction(Base):
    """
    审核操作记录模型
    
    用于记录审核过程中的所有操作
    """
    __tablename__ = "review_request_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_request_id = Column(UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    action = Column(String(50), nullable=False, comment="操作类型: create/assign/approve/reject/comment/escalate")
    action_details = Column(JSONB, nullable=True, comment="操作详情")
    
    old_value = Column(JSONB, nullable=True, comment="旧值")
    new_value = Column(JSONB, nullable=True, comment="新值")
    
    ip_address = Column(String(50), nullable=True, comment="IP地址")
    user_agent = Column(String(500), nullable=True, comment="User Agent")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 索引
    __table_args__ = (
        Index('ix_review_request_actions_request_created', 'review_request_id', 'created_at'),
        Index('ix_review_request_actions_user_created', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ReviewRequestAction(id={self.id}, request_id={self.review_request_id}, action={self.action})>"
