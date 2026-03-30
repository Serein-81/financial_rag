"""
租户审计日志模型
记录所有租户相关的访问和操作
"""

import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class TenantAuditLog(Base):
    """租户审计日志"""
    __tablename__ = "tenant_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 用户信息
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tenant_id = Column(String(50), index=True)
    
    # 操作信息
    action = Column(String(100))  # 操作类型：read/write/delete/update
    resource_type = Column(String(50))  # 资源类型：document/chunk/session
    resource_id = Column(String(100))  # 资源ID
    
    # 访问结果
    access_result = Column(String(20), index=True)  # success/denied/error
    
    # 请求信息
    ip_address = Column(String(50))
    user_agent = Column(Text)
    
    # 详细信息
    details = Column(JSONB, default={})
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    
    def __repr__(self):
        return f"<TenantAuditLog(tenant={self.tenant_id}, action={self.action}, result={self.access_result})>"
