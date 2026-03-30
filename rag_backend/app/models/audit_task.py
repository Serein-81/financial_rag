"""
审查任务模型
"""

import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class AuditTask(Base):
    """审查任务"""
    __tablename__ = "audit_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 用户和租户
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    
    # 审查类型
    audit_type = Column(String(50))  # finance/tax/legal/comprehensive
    
    # 状态
    status = Column(String(20), default="pending", index=True)  # pending/processing/completed/failed
    
    # 文档列表
    documents = Column(JSONB)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    results = relationship("AuditResult", back_populates="task", cascade="all, delete-orphan")
    collaborations = relationship("AgentCollaboration", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AuditTask(id={self.id}, type={self.audit_type}, status={self.status})>"
