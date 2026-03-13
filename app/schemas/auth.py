# app/schemas/auth.py
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from uuid import UUID
import re

# 1. 登录请求模型 (前端 -> 后端)
class UserLogin(BaseModel):
    email: EmailStr  # 强制校验邮箱格式
    password: str

# 2. 普通用户注册请求模型
class UserRegister(BaseModel):
    email: EmailStr
    phone: str = Field(..., description="手机号，必填")
    password: str = Field(..., min_length=6, description="密码，至少6位")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 6:
            raise ValueError('密码至少需要6位')
        return v

# 3. 企业管理员注册请求模型
class AdminRegister(BaseModel):
    email: EmailStr
    phone: str = Field(..., description="手机号，必填")
    password: str = Field(..., min_length=6, description="密码，至少6位")
    full_name: str = Field(..., min_length=2, max_length=100, description="真实姓名，必填")
    company_name: str = Field(..., min_length=2, max_length=200, description="企业名称，必填")
    company_position: Optional[str] = Field(None, max_length=100, description="职位")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 6:
            raise ValueError('密码至少需要6位')
        return v

# 4. 用户信息更新请求模型
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100, description="真实姓名")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    company_name: Optional[str] = Field(None, max_length=200, description="企业名称")
    company_position: Optional[str] = Field(None, max_length=100, description="职位")

# 5. Token 响应模型 (后端 -> 前端)
class Token(BaseModel):
    access_token: str
    token_type: str
    user_name: str  # 方便前端显示 "你好, XXX"
    is_admin: bool  # 是否为管理员

# 6. Token 载荷模型 (内部使用)
class TokenPayload(BaseModel):
    sub: Optional[str] = None

# 7. 用户信息响应模型 (后端 -> 前端)
class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    phone: str
    full_name: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    company_name: Optional[str] = None
    company_position: Optional[str] = None
    is_active: bool
    is_admin: bool
    is_phone_verified: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True