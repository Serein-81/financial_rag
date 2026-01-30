# app/schemas/user.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

# 注册/登录请求体
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Token 响应体
class Token(BaseModel):
    access_token: str
    token_type: str

# 用户信息响应体
class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    is_active: bool

    class Config:
        from_attributes = True