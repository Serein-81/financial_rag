# app/schemas/auth.py
from datetime import datetime

from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

# 1. 登录请求模型 (前端 -> 后端)
class UserLogin(BaseModel):
    email: EmailStr  # 强制校验邮箱格式
    password: str

# 2. 注册请求模型 (前端 -> 后端)
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

# 3. Token 响应模型 (后端 -> 前端)
# 登录成功后返回这个结构
class Token(BaseModel):
    access_token: str
    token_type: str
    user_name: str  # 方便前端显示 "你好, XXX"

# 4. Token 载荷模型 (内部使用)
# 用于解析 Token 里的数据
class TokenPayload(BaseModel):
    sub: Optional[str] = None

# 5. 用户信息响应模型 (后端 -> 前端)
# 注意：这里绝不能包含 password 字段！
class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    # created_at: Optional[str] = None # 或者 datetime
    created_at: Optional[datetime] = None
    class Config:
        # 允许从 ORM 对象 (数据库模型) 直接读取数据
        from_attributes = True