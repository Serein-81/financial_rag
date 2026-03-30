# app/schemas/auth_request.py
"""认证请求相关的Schema模型"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re

class UserLogin(BaseModel):
    """用户登录请求模型"""
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    """普通用户注册请求模型"""
    email: EmailStr
    phone: Optional[str] = Field(None, description="手机号，选填")
    password: str = Field(..., min_length=6, description="密码，至少6位")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if v and not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 6:
            raise ValueError('密码至少需要6位')
        return v

class AdminRegister(BaseModel):
    """企业管理员注册请求模型"""
    email: EmailStr
    phone: Optional[str] = Field(None, description="手机号，选填")
    password: str = Field(..., min_length=6, description="密码，至少6位")
    full_name: str = Field(..., min_length=2, max_length=100, description="真实姓名，必填")
    company_name: str = Field(..., min_length=2, max_length=200, description="企业名称，必填")
    company_position: Optional[str] = Field(None, max_length=100, description="职位")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if v and not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 6:
            raise ValueError('密码至少需要6位')
        return v


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码，至少6位")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """验证新密码强度"""
        if len(v) < 6:
            raise ValueError('新密码至少需要6位')
        return v


class UpdatePhoneRequest(BaseModel):
    """更新手机号请求模型"""
    phone: str = Field(..., description="新手机号")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v


class ChangeInviteCodeRequest(BaseModel):
    """更换企业邀请码请求模型"""
    new_invite_code: str = Field(..., min_length=8, max_length=32, description="新的企业邀请码")
    confirm_leave: bool = Field(False, description="确认离开当前企业")