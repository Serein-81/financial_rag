# app/models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)  # 手机号（必填）
    hashed_password = Column(String, nullable=False)
    
    # 多租户字段
    tenant_id = Column(String(50), nullable=False, index=True)  # 租户ID，用于多租户隔离
    
    # 用户信息
    full_name = Column(String(100), nullable=True)  # 真实姓名（可后续补充）
    nickname = Column(String(50), nullable=True)  # 昵称
    username = Column(String(50), nullable=True)  # 用户名（为了向后兼容）
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)  # 个人简介
    
    # 企业信息（仅企业管理员需要）
    company_name = Column(String(200), nullable=True)  # 企业名称
    company_position = Column(String(100), nullable=True)  # 职位
    
    # 状态字段
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # 企业管理员标识
    is_phone_verified = Column(Boolean, default=False)  # 手机号是否已验证
    
    # 时间字段
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 🌟 [升级] 加上 cascade="all, delete-orphan"，实现真正的“人走茶凉”（清理关联数据）
    knowledge_bases = relationship("KnowledgeBase", back_populates="owner", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    semantic_memories = relationship("SemanticMemory", back_populates="user", cascade="all, delete-orphan")
    
    @property
    def is_enterprise_admin(self) -> bool:
        """检查是否为企业管理员"""
        return self.is_admin