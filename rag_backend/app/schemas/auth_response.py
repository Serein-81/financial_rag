# app/schemas/auth_response.py
"""认证响应相关的Schema模型"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from uuid import UUID

class Token(BaseModel):
    """Token响应模型"""
    access_token: str
    refresh_token: Optional[str] = None  # 用于续期的刷新令牌（7天有效）
    token_type: str
    user_name: str  # 方便前端显示 "你好, XXX"
    is_admin: bool  # 是否为管理员
    user_id: Optional[str] = None  # 用户ID，用于日志记录

class TokenPayload(BaseModel):
    """Token载荷模型（内部使用）"""
    sub: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str

class UserProfile(BaseModel):
    """用户信息响应模型"""
    id: UUID
    email: EmailStr
    phone: Optional[str] = None
    full_name: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    company_name: Optional[str] = None
    company_position: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: bool
    is_admin: bool
    is_phone_verified: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        from_attributes=True
    )