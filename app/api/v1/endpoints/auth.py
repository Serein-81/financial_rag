# app/api/v1/endpoints/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.future import select
from app.core import security
from app.db import AsyncSessionLocal
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate):
    async with AsyncSessionLocal() as db:
        # 1. 检查邮箱是否已存在
        result = await db.execute(select(User).where(User.email == user_in.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        # 2. 创建新用户
        new_user = User(
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password)
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user


@router.post("/login", response_model=Token)
async def login_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    兼容 OAuth2 标准的登录接口 (Swagger UI 会自动用这个)
    username 字段对应 email
    """
    async with AsyncSessionLocal() as db:
        # 1. 查用户
        result = await db.execute(select(User).where(User.email == form_data.username))
        user = result.scalar_one_or_none()

        # 2. 校验密码
        if not user or not security.verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. 签发 Token
        access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}