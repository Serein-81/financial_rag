# app/models/policy_relation.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class RelationType(str, enum.Enum):
    """政策关系类型枚举"""
    REPLACES = "replaces"           # 替代
    SUPPLEMENTS = "supplements"     # 补充
    RELATED = "related"             # 相关
    CONFLICTS = "conflicts"         # 冲突
    INTERPRETS = "interprets"       # 解读


class PolicyRelation(Base):
    """
    政策关系表模型
    
    存储政策之间的关联关系
    用于建立政策间的替代/补充/相关关系
    """
    __tablename__ = "policy_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    source_policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    target_policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    relation_type = Column(
        SQLEnum(RelationType, name='relation_type', native_enum=False),
        default=RelationType.RELATED,
        nullable=False,
        index=True
    )
    
    description = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_policy_relations_source', 'source_policy_id'),
        Index('ix_policy_relations_target', 'target_policy_id'),
        Index('ix_policy_relations_source_target', 'source_policy_id', 'target_policy_id', unique=True),
    )
    
    def __repr__(self):
        return f"<PolicyRelation(source={self.source_policy_id}, target={self.target_policy_id}, type={self.relation_type})>"
