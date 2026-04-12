# app/models/policy.py
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Enum as SQLEnum, Index, LargeBinary, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class PolicyStatus(str, enum.Enum):
    """政策状态枚举"""
    ACTIVE = "active"          # 有效政策
    ARCHIVED = "archived"       # 已归档政策
    DRAFT = "draft"             # 草稿
    EXPIRED = "expired"         # 已过期


class PolicyPriority(str, enum.Enum):
    """政策优先级枚举"""
    CRITICAL = "critical"       # 紧急重要（需立即处理）
    HIGH = "high"               # 高优先级
    MEDIUM = "medium"           # 中优先级
    LOW = "low"                 # 低优先级


class Policy(Base):
    """
    政策主表模型
    
    存储从官方来源采集的税务政策信息
    注意：此表为独立表，不与用户知识库共享
    """
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    policy_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    
    source_url = Column(String(500), nullable=True)
    source_name = Column(String(100), nullable=False)
    
    published_date = Column(DateTime(timezone=True), nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    
    industries = Column(ARRAY(String), default=[])
    regions = Column(ARRAY(String), default=[])
    scales = Column(ARRAY(String), default=[])
    tax_types = Column(ARRAY(String), default=[])
    
    embedding = Column(LargeBinary, nullable=True)
    
    tags = Column(ARRAY(String), default=[])
    
    status = Column(
        SQLEnum(PolicyStatus, name='policy_status', native_enum=False),
        default=PolicyStatus.ACTIVE,
        nullable=False,
        index=True
    )
    
    priority = Column(
        SQLEnum(PolicyPriority, name='policy_priority', native_enum=False),
        default=PolicyPriority.MEDIUM,
        nullable=False,
        index=True
    )
    
    version = Column(String(50), default="1.0")
    
    view_count = Column(Integer, default=0)
    
    meta_info = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_policies_published_date', 'published_date'),
        Index('ix_policies_effective_date', 'effective_date'),
        Index('ix_policies_status_priority', 'status', 'priority'),
    )
    
    def __repr__(self):
        return f"<Policy(id={self.id}, title={self.title[:50]}...)>"
