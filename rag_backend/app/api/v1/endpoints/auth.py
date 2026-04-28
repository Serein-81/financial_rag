# app/api/v1/endpoints/auth.py
from datetime import timedelta
from sqlalchemy.future import select
from app.core import security
from app.core.config import settings
from app.schemas.auth_request import UserRegister, AdminRegister, UserLogin, ChangePasswordRequest, UpdatePhoneRequest, ChangeInviteCodeRequest
from app.schemas.auth_response import Token, UserProfile
from app.schemas.user import UserProfileUpdate
from app.schemas.invite_code import InviteCodeCreate, InviteCodeValidationResult
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query, Request
from app.db import AsyncSessionLocal
from app.api import deps
from app.models.user import User
from app.models.tenant_settings import TenantSettings
from app.services.minio_service import minio_service
from app.services.sms_service import sms_service
from app.services.invite_code_service import InviteCodeService
from app.utils.log_decorators import log_user_action
from pydantic import BaseModel, Field
import uuid

router = APIRouter()


# =======================
# 邀请码相关请求模型
# =======================
class ApplyInviteCodeRequest(BaseModel):
    """使用邀请码加入企业请求"""
    invite_code: str = Field(..., min_length=8, max_length=32, description="企业邀请码")


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
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
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
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
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
@log_user_action(
    action_type="AUTH",
    action_name="user_register",
    resource_type="user",
    description="User registration"
)
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
            validation_result = await InviteCodeService.validate_invite_code(db, invite_code)
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
            await InviteCodeService.use_invite_code(
                db=db,
                code=invite_code,
                user_id=str(new_user.id)
            )

        return new_user


# =======================
# 📝 4. 企业管理员注册接口（无需验证码）
# =======================
@router.post("/register/admin", response_model=UserProfile)
@log_user_action(
    action_type="AUTH",
    action_name="admin_register",
    resource_type="user",
    description="Admin user registration"
)
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
        db.add(TenantSettings(
            tenant_id=new_admin.tenant_id,
            company_name=admin_in.company_name,
            admin_name=admin_in.full_name or admin_in.nickname,
            admin_email=admin_in.email,
            admin_phone=admin_in.phone,
            is_trial=True
        ))
        await db.commit()
        await db.refresh(new_admin)

        return new_admin


# =======================
# 🔑 5. 用户登录接口
# =======================
@router.post("/login", response_model=Token)
@log_user_action(
    action_type="AUTH",
    action_name="user_login",
    resource_type="user",
    description="User login attempt"
)
async def login(request: Request, user_in: UserLogin):
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
            expires_delta=access_token_expires,
            tenant_id=user.tenant_id  # 包含租户ID到Token中
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_name": user.nickname or user.full_name or user.email,
            "is_admin": user.is_admin,
            "user_id": str(user.id)  # 返回用户ID用于日志记录
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
@log_user_action(
    action_type="PROFILE",
    action_name="update_profile",
    resource_type="user",
    description="User updated their profile"
)
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
        update_data = profile_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        await db.commit()
        await db.refresh(db_user)
        
        return db_user


# =======================
# 📷 8. 上传头像
# =======================
@router.post("/avatar")
@log_user_action(
    action_type="PROFILE",
    action_name="upload_avatar",
    resource_type="avatar",
    description="User uploaded avatar"
)
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
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
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


# =======================
# 🏢 9. 使用邀请码加入企业
# =======================
@router.post("/apply-invite-code", response_model=dict)
@log_user_action(
    action_type="INVITE",
    action_name="apply_invite_code",
    resource_type="tenant",
    description="User applied invite code to join enterprise"
)
async def apply_invite_code(
    request: Request,
    apply_data: ApplyInviteCodeRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    使用邀请码加入企业
    - 验证邀请码的有效性
    - 将用户添加到对应的企业租户
    - 记录邀请码使用情况
    - 如果用户已经是某个企业的成员，需要先退出原企业
    """
    # 检查用户是否已经是企业管理员
    if current_user.is_admin:
        raise HTTPException(
            status_code=400,
            detail="管理员账户无法使用邀请码，请使用企业管理员账号"
        )
    
    # 获取客户端信息
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    async with AsyncSessionLocal() as db:
        # 验证邀请码
        validation_result = await InviteCodeService.validate_invite_code(
            db=db,
            code=apply_data.invite_code
        )
        
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=validation_result.message
            )
        
        # 检查用户是否已经是该企业的成员
        if current_user.tenant_id == validation_result.tenant_id:
            raise HTTPException(
                status_code=400,
                detail="您已经是该企业的成员"
            )
        
        # 检查用户是否已经使用过邀请码
        existing_user = await db.get(User, current_user.id)
        if existing_user.tenant_id.startswith("company_"):
            raise HTTPException(
                status_code=400,
                detail="您已经是某个企业的成员，请先退出原企业后再试"
            )
        
        # 使用邀请码
        success, message, tenant_id = await InviteCodeService.use_invite_code(
            db=db,
            code=apply_data.invite_code,
            user_id=str(current_user.id),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # 更新用户的租户ID
        existing_user.tenant_id = tenant_id
        await db.commit()
        
        return {
            "success": True,
            "message": message,
            "tenant_id": tenant_id,
            "company_name": validation_result.company_name
        }


# =======================
# 🔑 10. 创建邀请码（管理员专用）
# =======================
@router.post("/invite-codes", response_model=dict)
@log_user_action(
    action_type="INVITE",
    action_name="create_invite_code",
    resource_type="invite_code",
    description="Admin created an invite code"
)
async def create_invite_code_for_user(
    invite_data: InviteCodeCreate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    创建企业邀请码（管理员专用）
    - 只有企业管理员可以创建邀请码
    - 邀请码用于邀请普通用户加入企业租户
    - 支持自定义邀请码的有效期、使用次数和描述
    """
    # 权限检查：必须是管理员
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="只有企业管理员可以创建邀请码"
        )
    
    async with AsyncSessionLocal() as db:
        # 创建邀请码
        invite_code = await InviteCodeService.create_invite_code(
            db=db,
            creator_id=str(current_user.id),
            tenant_id=current_user.tenant_id,
            invite_data=invite_data
        )
        
        return {
            "success": True,
            "message": "邀请码创建成功",
            "invite_code": {
                "id": str(invite_code.id),
                "code": invite_code.code,
                "max_uses": invite_code.max_uses,
                "remaining_uses": invite_code.remaining_uses,
                "expires_at": invite_code.expires_at.isoformat() if invite_code.expires_at else None,
                "description": invite_code.description,
                "created_at": invite_code.created_at.isoformat()
            }
        }


# =======================
# 📋 11. 获取用户的邀请码列表（管理员专用）
# =======================
@router.get("/invite-codes", response_model=dict)
@log_user_action(
    action_type="INVITE",
    action_name="list_invite_codes",
    resource_type="invite_code",
    description="Admin viewed invite code list"
)
async def get_my_invite_codes(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    include_inactive: bool = Query(False, description="是否包含非活跃的邀请码"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取当前企业的邀请码列表（管理员专用）
    - 显示当前企业租户下的所有邀请码
    - 支持分页和过滤
    """
    # 权限检查：必须是管理员
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="只有企业管理员可以查看邀请码列表"
        )
    
    async with AsyncSessionLocal() as db:
        # 获取邀请码列表
        invite_codes = await InviteCodeService.get_tenant_invite_codes(
            db=db,
            tenant_id=current_user.tenant_id,
            skip=skip,
            limit=limit,
            include_inactive=include_inactive
        )
        
        # 转换为响应格式
        codes_list = [
            {
                "id": str(code.id),
                "code": code.code,
                "max_uses": code.max_uses,
                "used_count": code.used_count,
                "remaining_uses": code.remaining_uses,
                "is_valid": code.is_valid,
                "expires_at": code.expires_at.isoformat() if code.expires_at else None,
                "description": code.description,
                "is_active": code.is_active,
                "created_at": code.created_at.isoformat()
            }
            for code in invite_codes
        ]
        
        return {
            "success": True,
            "total": len(codes_list),
            "invite_codes": codes_list
        }


# =======================
# 🔍 12. 验证邀请码（所有用户可用）
# =======================
@router.post("/validate-invite-code", response_model=InviteCodeValidationResult)
async def validate_invite_code_for_user(
    apply_data: ApplyInviteCodeRequest
):
    """
    验证邀请码有效性（所有用户可用）
    - 验证邀请码是否存在且有效
    - 返回邀请码的基本信息（企业名称、过期时间等）
    - 用于在用户填写邀请码前进行预验证
    """
    async with AsyncSessionLocal() as db:
        result = await InviteCodeService.validate_invite_code(     
            db=db,
            code=apply_data.invite_code
        )
        
        return result


# =======================
# 🔐 13. 修改密码
# =======================
@router.post("/change-password", response_model=dict)
@log_user_action(
    action_type="PROFILE",
    action_name="change_password",
    resource_type="user",
    description="User changed password"
)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    修改密码
    - 需要提供旧密码和新密码
    - 新密码至少6位
    - 验证旧密码正确后才能修改
    """
    async with AsyncSessionLocal() as db:
        db_user = await db.get(User, current_user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 验证旧密码
        if not security.verify_password(password_data.old_password, db_user.hashed_password):
            raise HTTPException(status_code=400, detail="旧密码错误")
        
        # 检查新旧密码是否相同
        if password_data.old_password == password_data.new_password:
            raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
        
        # 更新密码
        db_user.hashed_password = security.get_password_hash(password_data.new_password)
        await db.commit()
        
        return {
            "success": True,
            "message": "密码修改成功"
        }


# =======================
# 📱 14. 更新手机号
# =======================
@router.post("/update-phone", response_model=dict)
@log_user_action(
    action_type="PROFILE",
    action_name="update_phone",
    resource_type="user",
    description="User updated phone number"
)
async def update_phone(
    phone_data: UpdatePhoneRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    更新手机号
    - 需要提供新的手机号
    - 手机号格式必须为中国大陆手机号
    - 如果手机号已被其他用户使用，返回错误
    """
    async with AsyncSessionLocal() as db:
        # 检查手机号是否已被使用
        result = await db.execute(select(User).where(User.phone == phone_data.phone))
        existing_user = result.scalars().first()
        
        if existing_user and str(existing_user.id) != str(current_user.id):
            raise HTTPException(status_code=400, detail="该手机号已被其他用户使用")
        
        # 更新手机号
        db_user = await db.get(User, current_user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        db_user.phone = phone_data.phone
        db_user.is_phone_verified = True
        await db.commit()
        
        return {
            "success": True,
            "message": "手机号更新成功",
            "phone": phone_data.phone
        }


# =======================
# 🏢 15. 更换企业（修改企业邀请码）
# =======================
@router.post("/change-invite-code", response_model=dict)
@log_user_action(
    action_type="INVITE",
    action_name="change_invite_code",
    resource_type="tenant",
    description="User changed enterprise invite code"
)
async def change_invite_code(
    request: Request,
    change_data: ChangeInviteCodeRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    更换企业（修改企业邀请码）
    - 用于用户更换企业的场景
    - 需要先退出原企业，再加入新企业
    - 需要提供确认标志 confirm_leave=true
    - 如果用户是企业管理员，无法使用此功能
    """
    # 检查用户是否是企业管理员
    if current_user.is_admin:
        raise HTTPException(
            status_code=400,
            detail="管理员账户无法使用此功能，请使用企业管理员账号"
        )
    
    # 检查是否提供了确认标志
    if not change_data.confirm_leave:
        raise HTTPException(
            status_code=400,
            detail="请确认要离开当前企业（confirm_leave=true）"
        )
    
    # 获取客户端信息
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    async with AsyncSessionLocal() as db:
        db_user = await db.get(User, current_user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 验证新的邀请码
        validation_result = await InviteCodeService.validate_invite_code(
            db=db,
            code=change_data.new_invite_code
        )
        
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=validation_result.message
            )
        
        # 检查是否已经是该企业的成员
        if db_user.tenant_id == validation_result.tenant_id:
            raise HTTPException(
                status_code=400,
                detail="您已经是该企业的成员"
            )
        
        # 记录原租户信息
        old_tenant_id = db_user.tenant_id
        
        # 使用新的邀请码
        success, message, new_tenant_id = await InviteCodeService.use_invite_code(
            db=db,
            code=change_data.new_invite_code,
            user_id=str(current_user.id),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # 更新用户的租户ID
        db_user.tenant_id = new_tenant_id
        await db.commit()
        
        return {
            "success": True,
            "message": "成功离开原企业并加入新企业",
            "old_tenant_id": old_tenant_id,
            "new_tenant_id": new_tenant_id,
            "company_name": validation_result.company_name
        }


# =======================
# 🚪 16. 退出企业
# =======================
@router.post("/leave-enterprise", response_model=dict)
@log_user_action(
    action_type="INVITE",
    action_name="leave_enterprise",
    resource_type="tenant",
    description="User left enterprise"
)
async def leave_enterprise(
    confirm: bool = Query(False, description="确认退出企业"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    退出企业
    - 用于用户离开当前企业的场景
    - 退出后将创建个人租户
    - 需要提供确认标志 confirm=true
    - 如果用户是企业管理员，无法使用此功能
    """
    # 检查用户是否是企业管理员
    if current_user.is_admin:
        raise HTTPException(
            status_code=400,
            detail="管理员账户无法使用此功能"
        )
    
    # 检查是否提供了确认标志
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="请确认要退出企业（confirm=true）"
        )
    
    async with AsyncSessionLocal() as db:
        db_user = await db.get(User, current_user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 记录原租户信息
        old_tenant_id = db_user.tenant_id
        
        # 检查是否已经是个人租户
        if old_tenant_id.startswith("user_"):
            raise HTTPException(
                status_code=400,
                detail="您已经在个人租户中，无需退出"
            )
        
        # 创建新的个人租户ID
        new_tenant_id = generate_tenant_id("user")
        
        # 更新用户的租户ID
        db_user.tenant_id = new_tenant_id
        await db.commit()
        
        return {
            "success": True,
            "message": "成功退出企业，已切换到个人租户",
            "old_tenant_id": old_tenant_id,
            "new_tenant_id": new_tenant_id
        }


# =======================
# 📊 17. 获取用户企业信息
# =======================
@router.get("/enterprise-info", response_model=dict)
async def get_enterprise_info(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取用户当前的企业信息
    - 返回用户当前所属企业的信息
    - 如果用户在个人租户中，返回相应的提示
    """
    async with AsyncSessionLocal() as db:
        db_user = await db.get(User, current_user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        is_personal = db_user.tenant_id.startswith("user_")
        settings_result = await db.execute(
            select(TenantSettings.company_name).where(
                TenantSettings.tenant_id == db_user.tenant_id
            )
        )
        company_name = settings_result.scalar_one_or_none() or db_user.company_name
        
        return {
            "tenant_id": db_user.tenant_id,
            "company_name": company_name,
            "is_personal": is_personal,
            "is_admin": db_user.is_admin,
            "is_enterprise_member": not is_personal
        }
