# app/api/v1/endpoints/auth.py
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db import AsyncSessionLocal
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, Token, UserOut

router = APIRouter()


# =======================
# 📝 1. 用户注册接口
# =======================
@router.post("/register", response_model=UserOut)
async def register(user_in: UserRegister):
    """
    注册新用户 (接收 JSON)
    """
    async with AsyncSessionLocal() as db:
        # 1. 检查邮箱是否已存在
        result = await db.execute(select(User).where(User.email == user_in.email))
        existing_user = result.scalars().first()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="该邮箱已被注册"
            )

        # 2. 创建新用户
        new_user = User(
            email=user_in.email,
            # 🔐 必须使用 security.py 里的加密函数
            hashed_password=security.get_password_hash(user_in.password),
            full_name=user_in.full_name,
            is_active=True
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return new_user


# =======================
# 🔑 2. 用户登录接口
# =======================
# 👇👇👇 重点看这里，这里必须是 UserLogin (JSON)，不能是 Depends() 👇👇👇
@router.post("/login", response_model=Token)
async def login(user_in: UserLogin):
    """
    用户登录 (接收 JSON: {"email": "...", "password": "..."})
    """
    async with AsyncSessionLocal() as db:
        # 1. 查找用户
        result = await db.execute(select(User).where(User.email == user_in.email))
        user = result.scalars().first()

        # 2. 验证账号是否存在 + 密码是否正确
        if not user or not security.verify_password(user_in.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. 检查账号状态
        if not user.is_active:
            raise HTTPException(status_code=400, detail="账号已停用")

        # 4. 签发 Token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        access_token = security.create_access_token(
            subject=user.id,
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_name": user.full_name or user.email
        }