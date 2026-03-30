"""
Agent 协作记录模型
"""

import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class AgentCollaboration(Base):
    """Agent 协作记录"""
    __tablename__ = "agent_collaborations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联任务
    task_id = Column(UUID(as_uuid=True), ForeignKey("audit_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    
    # Agent 信息
    from_agent = Column(String(50))
    to_agent = Column(String(50))
    
    # 消息信息
    message_type = Column(String(20))  # request/response/notification
    message_content = Column(JSONB)
    
    # 时间戳
    timestamp = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    
    # 关系
    task = relationship("AuditTask", back_populates="collaborations")
    
    # 多租户复合索引
    __table_args__ = (
        Index('idx_agent_collab_tenant_time', 'tenant_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<AgentCollaboration(from={self.from_agent}, to={self.to_agent}, type={self.message_type})>"
