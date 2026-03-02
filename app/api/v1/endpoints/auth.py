# app/api/v1/endpoints/auth.py
from datetime import timedelta
from sqlalchemy.future import select
from app.core import security
from app.core.config import settings
from app.schemas.auth import UserRegister, UserLogin, Token, UserOut
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException,status
from app.db import AsyncSessionLocal
from app.api import deps
from app.models.user import User
from app.services.minio_service import minio_service

router = APIRouter()


@router.post("/avatar")
async def upload_avatar(
        file: UploadFile = File(...),  # 接收前端传来的 FormData 文件
        current_user: User = Depends(deps.get_current_user)
):
    # 1. 验证文件类型（防止有人上传病毒代码伪装成图片）
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片文件！")

    # 2. 读取文件字节并上传到 MinIO
    file_bytes = await file.read()
    try:
        avatar_url = minio_service.upload_avatar(
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片上传 MinIO 失败: {str(e)}")

    # 3. 将生成的 URL 存入 PostgreSQL 的 users 表
    async with AsyncSessionLocal() as db:
        db_user = await db.get(User, current_user.id)
        db_user.avatar_url = avatar_url
        await db.commit()

    return {
        "status": "success",
        "message": "头像上传成功",
        "avatar_url": avatar_url
    }

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


@router.post("/avatar")
async def upload_user_avatar(
        file: UploadFile = File(...),
        current_user: User = Depends(deps.get_current_user)  # 👈 需要 Token 鉴权
):
    """用户上传/更新头像"""
    # 1. 安全拦截：只允许上传图片
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片文件！")

    # 2. 读取文件字节并上传到 MinIO
    file_bytes = await file.read()
    try:
        avatar_url = minio_service.upload_avatar(
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type
        )
    except Exception as e:
        print(f"MinIO 上传报错: {e}")
        raise HTTPException(status_code=500, detail="图片上传存储服务器失败")

    # 3. 将生成的图片 URL 更新到数据库的用户表里
    async with AsyncSessionLocal() as db:
        # 重新从数据库查出这个用户实例以便修改
        db_user = await db.get(User, current_user.id)
        if db_user:
            db_user.avatar_url = avatar_url
            await db.commit()

    return {
        "status": "success",
        "message": "头像上传成功",
        "avatar_url": avatar_url
    }