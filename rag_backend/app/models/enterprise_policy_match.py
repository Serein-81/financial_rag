# app/models/enterprise_policy_match.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class NotificationStatus(str, enum.Enum):
    """通知状态枚举"""
    PENDING = "pending"             # 待发送
    SENT = "sent"                   # 已发送
    ACKNOWLEDGED = "acknowledged"   # 已确认
    DISMISSED = "dismissed"         # 已忽略
    FAILED = "failed"               # 发送失败


class MatchStatus(str, enum.Enum):
    """匹配状态枚举"""
    ACTIVE = "active"               # 活跃匹配
    INACTIVE = "inactive"           # 已失效
    EXPIRED = "expired"             # 已过期


class EnterprisePolicyMatch(Base):
    """
    企业-政策匹配表模型
    
    存储企业与政策的匹配关系
    用于个性化政策推送
    """
    __tablename__ = "enterprise_policy_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    enterprise_id = Column(String(100), nullable=False, index=True)
    
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    match_score = Column(Float, default=0.0)
    
    match_reasons = Column(JSONB, default=[])
    
    notification_status = Column(
        SQLEnum(NotificationStatus, name='notification_status', native_enum=False),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True
    )
    
    match_status = Column(
        SQLEnum(MatchStatus, name='match_status', native_enum=False),
        default=MatchStatus.ACTIVE,
        nullable=False,
        index=True
    )
    
    notified_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    
    feedback = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_enterprise_policy_enterprise', 'enterprise_id'),
        Index('ix_enterprise_policy_policy', 'policy_id'),
        Index('ix_enterprise_policy_notification', 'notification_status'),
        Index('ix_enterprise_policy_unique', 'enterprise_id', 'policy_id', unique=True),
    )
    
    def __repr__(self):
        return f"<EnterprisePolicyMatch(enterprise={self.enterprise_id}, policy={self.policy_id}, score={self.match_score})>"
