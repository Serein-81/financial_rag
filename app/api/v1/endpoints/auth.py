# app/api/v1/endpoints/auth.py
from datetime import timedelta
from sqlalchemy.future import select
from app.core import security
from app.core.config import settings
from app.schemas.auth_request import UserRegister, AdminRegister, UserLogin
from app.schemas.auth_response import Token, UserProfile
from app.schemas.user import UserProfileUpdate
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from app.db import AsyncSessionLocal
from app.api import deps
from app.models.user import User
from app.services.minio_service import minio_service
from app.services.sms_service import sms_service
from pydantic import BaseModel
import uuid

router = APIRouter()


# =======================
# 🏢 租户ID生成工具函数
# =======================
def generate_tenant_id(user_type: str, company_name: str = None) -> str:
    """
    生成租户ID
    
    Args:
        user_type: 用户类型 ("user" 或 "admin")
        company_name: 企业名称（仅管理员需要）
    
    Returns:
        str: 生成的租户ID
    """
    if user_type == "admin" and company_name:
        # 企业租户：基于公司名生成
        company_slug = company_name.lower().replace(" ", "_").replace("-", "_")[:20]
        # 移除特殊字符，只保留字母数字和下划线
        company_slug = ''.join(c for c in company_slug if c.isalnum() or c == '_')
        return f"company_{company_slug}_{uuid.uuid4().hex[:8]}"
    else:
        # 个人租户：基于用户ID生成
        return f"user_{uuid.uuid4().hex[:12]}"


# =======================
# 📱 短信验证码相关模型
# =======================
class SendSMSRequest(BaseModel):
    phone: str


class VerifySMSRequest(BaseModel):
    phone: str
    code: str


# =======================
# 📱 1. 发送短信验证码
# =======================
@router.post("/sms/send")
async def send_sms_code(request: SendSMSRequest):
    """
    发送短信验证码
    - 1小时内只能发送1次
    - 每日最多发送3次
    """
    try:
        result = await sms_service.send_verification_code(request.phone)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "expire_seconds": result.get("expire_seconds"),
            "debug_code": result.get("debug_code")  # 仅开发模式
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"短信服务异常: {str(e)}"
        )


# =======================
# 📱 2. 验证短信验证码
# =======================
@router.post("/sms/verify")
async def verify_sms_code(request: VerifySMSRequest):
    """验证短信验证码"""
    try:
        result = sms_service.verify_code(request.phone, request.code)
        
        if not result["valid"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"验证码验证异常: {str(e)}"
        )


# =======================
# 📝 3. 普通用户注册接口（无需验证码）
# =======================
@router.post("/register", response_model=UserProfile)
async def register_user(
    user_in: UserRegister,
    invite_code: str = Query(None, description="企业邀请码（可选）")
):
    """
    普通用户注册
    - 需要提供：邮箱、密码
    - 可选提供：手机号、昵称、企业邀请码
    - 如果有邀请码，用户将加入对应的企业租户
    - 如果没有邀请码，创建个人租户
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
        
        # 2. 检查手机号是否已存在（如果提供了手机号）
        if user_in.phone:
            result = await db.execute(select(User).where(User.phone == user_in.phone))
            existing_phone = result.scalars().first()
            if existing_phone:
                raise HTTPException(
                    status_code=400,
                    detail="该手机号已被注册"
                )

        # 3. 处理租户分配
        tenant_id = None
        if invite_code:
            # 验证邀请码并获取企业租户ID
            from app.services.invite_code_service import InviteCodeService
            validation_result = InviteCodeService.validate_invite_code(db, invite_code)
            if not validation_result.valid:
                raise HTTPException(status_code=400, detail=validation_result.message)
            tenant_id = validation_result.tenant_id
        else:
            # 创建个人租户
            tenant_id = generate_tenant_id("user")

        # 4. 创建普通用户
        new_user = User(
            email=user_in.email,
            phone=user_in.phone,  # 可能为None
            hashed_password=security.get_password_hash(user_in.password),
            nickname=user_in.nickname,
            tenant_id=tenant_id,  # 🔥 关键修复：分配租户ID（个人或企业）
            is_active=True,
            is_admin=False,  # 普通用户
            is_phone_verified=bool(user_in.phone)  # 如果提供了手机号就标记为已验证
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # 5. 如果使用了邀请码，记录使用情况
        if invite_code:
            from app.services.invite_code_service import InviteCodeService
            InviteCodeService.use_invite_code(
                db=db,
                code=invite_code,
                user_id=str(new_user.id)
            )

        return new_user


# =======================
# 📝 4. 企业管理员注册接口（无需验证码）
# =======================
@router.post("/register/admin", response_model=UserProfile)
async def register_admin(
    admin_in: AdminRegister
):
    """
    企业管理员注册
    - 需要提供：邮箱、密码、真实姓名、企业名称
    - 可选提供：手机号、职位、昵称
    - 注册后自动设置为管理员权限
    """
    async with AsyncSessionLocal() as db:
        # 1. 检查邮箱是否已存在
        result = await db.execute(select(User).where(User.email == admin_in.email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="该邮箱已被注册"
            )
        
        # 2. 检查手机号是否已存在（如果提供了手机号）
        if admin_in.phone:
            result = await db.execute(select(User).where(User.phone == admin_in.phone))
            existing_phone = result.scalars().first()
            if existing_phone:
                raise HTTPException(
                    status_code=400,
                    detail="该手机号已被注册"
                )

        # 3. 创建企业管理员用户
        new_admin = User(
            email=admin_in.email,
            phone=admin_in.phone,  # 可能为None
            hashed_password=security.get_password_hash(admin_in.password),
            full_name=admin_in.full_name,
            nickname=admin_in.nickname,
            company_name=admin_in.company_name,
            company_position=admin_in.company_position,
            tenant_id=generate_tenant_id("admin", admin_in.company_name),  # 🔥 关键修复：分配企业租户ID
            is_active=True,
            is_admin=True,  # 企业管理员
            is_phone_verified=bool(admin_in.phone)  # 如果提供了手机号就标记为已验证
        )

        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        return new_admin


# =======================
# 🔑 5. 用户登录接口
# =======================
@router.post("/login", response_model=Token)
async def login(user_in: UserLogin):
    """
    用户登录 (接收 JSON: {"email": "...", "password": "..."})
    支持普通用户和企业管理员登录
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
            "user_name": user.nickname or user.full_name or user.email,
            "is_admin": user.is_admin
        }


# =======================
# 👤 6. 获取当前用户信息
# =======================
@router.get("/me", response_model=UserProfile)
async def get_current_user_info(
    current_user: User = Depends(deps.get_current_user)
):
    """获取当前登录用户的详细信息"""
    return current_user


# =======================
# ✏️ 7. 更新用户信息
# =======================
@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    更新用户个人信息
    - 可以补充真实姓名、昵称、个人简介等
    - 企业管理员可以更新企业信息
    """
    async with AsyncSessionLocal() as db:
        # 重新从数据库获取用户实例
        db_user = await db.get(User, current_user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 更新字段（只更新提供的字段）
        update_data = profile_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        await db.commit()
        await db.refresh(db_user)
        
        return db_user


# =======================
# 📷 8. 上传头像
# =======================
@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user)
):
    """用户上传/更新头像"""
    # 1. 验证文件类型
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
        raise HTTPException(status_code=500, detail=f"图片上传失败: {str(e)}")

    # 3. 更新数据库
    async with AsyncSessionLocal() as db:
        db_user = await db.get(User, current_user.id)
        if db_user:
            db_user.avatar_url = avatar_url
            await db.commit()

    return {
        "status": "success",
        "message": "头像上传成功",
        "avatar_url": avatar_url
    }