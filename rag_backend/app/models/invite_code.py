"""
邀请码模型
用于企业管理员邀请普通用户加入企业租户
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class InviteCode(Base):
    """邀请码模型"""
    __tablename__ = "invite_codes"
    
    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(32), unique=True, nullable=False, index=True)
    
    # 租户和创建者信息
    tenant_id = Column(String(50), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 邀请配置
    max_uses = Column(Integer, default=1, nullable=False)  # 最大使用次数
    used_count = Column(Integer, default=0, nullable=False)  # 已使用次数
    expires_at = Column(DateTime(timezone=True), nullable=True)  # 过期时间
    
    # 邀请信息
    description = Column(String(200), nullable=True)  # 邀请描述
    role = Column(String(20), default="member", nullable=False)  # 被邀请用户的角色
    
    # 状态字段
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<InviteCode(code={self.code}, tenant_id={self.tenant_id})>"
    
    @property
    def is_expired(self) -> bool:
        """检查邀请码是否已过期"""
        if not self.expires_at:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_exhausted(self) -> bool:
        """检查邀请码是否已用完"""
        return self.used_count >= self.max_uses
    
    @property
    def is_valid(self) -> bool:
        """检查邀请码是否有效"""
        return (
            self.is_active and 
            not self.is_expired and 
            not self.is_exhausted
        )
    
    @property
    def remaining_uses(self) -> int:
        """剩余使用次数"""
        return max(0, self.max_uses - self.used_count)


class InviteCodeUsage(Base):
    """邀请码使用记录"""
    __tablename__ = "invite_code_usages"
    
    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联字段
    invite_code_id = Column(UUID(as_uuid=True), ForeignKey("invite_codes.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 使用信息
    used_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)  # 支持IPv6
    user_agent = Column(String(500), nullable=True)
    
    # 关系
    invite_code = relationship("InviteCode")
    user = relationship("User")
    
    def __repr__(self):
        return f"<InviteCodeUsage(code_id={self.invite_code_id}, user_id={self.user_id})>"