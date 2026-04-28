"""
企业用户管理API端点
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func, select

from app.api import deps
from app.models.user import User
from app.models.tenant_settings import TenantSettings
from app.schemas.auth_response import UserProfile
from app.db.session import get_db

router = APIRouter()


def require_admin_user(current_user: User = Depends(deps.get_current_user)) -> User:
    """要求当前用户是管理员"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


async def _get_company_name(
    db: AsyncSession,
    tenant_id: str,
    fallback: Optional[str] = None
) -> str:
    result = await db.execute(
        select(TenantSettings.company_name).where(TenantSettings.tenant_id == tenant_id)
    )
    settings_company_name = result.scalar_one_or_none()
    return settings_company_name or fallback or "未命名企业"


async def _sync_company_name(
    db: AsyncSession,
    tenant_id: str,
    company_name: str,
    admin_user: User
) -> None:
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    tenant_settings = result.scalar_one_or_none()
    if tenant_settings:
        tenant_settings.company_name = company_name
    else:
        tenant_settings = TenantSettings(
            tenant_id=tenant_id,
            company_name=company_name,
            admin_email=admin_user.email,
            admin_name=admin_user.full_name or admin_user.nickname,
            admin_phone=admin_user.phone
        )
        db.add(tenant_settings)

    users_result = await db.execute(select(User).where(User.tenant_id == tenant_id))
    for user in users_result.scalars().all():
        user.company_name = company_name


@router.get("/users", response_model=List[UserProfile])
async def list_enterprise_users(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    search: Optional[str] = Query(None, description="搜索关键词（邮箱、昵称、姓名）"),
    is_active: Optional[bool] = Query(None, description="用户状态过滤"),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业用户列表（管理员专用）
    - 只显示同一租户下的用户
    - 支持搜索和过滤
    """
    query = select(User).where(User.tenant_id == admin_user.tenant_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_pattern),
                User.nickname.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    query = query.order_by(desc(User.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users


@router.get("/users/list", response_model=List[UserProfile])
async def list_tenant_users(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=200, description="限制数量"),
    search: Optional[str] = Query(None, description="搜索关键词（邮箱、昵称、姓名）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取租户用户列表（所有已认证用户可用）
    - 用于群聊邀请等功能
    - 只显示同一租户下的用户
    """
    query = select(User).where(User.tenant_id == current_user.tenant_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_pattern),
                User.nickname.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    query = query.order_by(desc(User.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users


@router.get("/users/stats")
async def get_enterprise_user_stats(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业用户统计信息
    """
    tenant_id = admin_user.tenant_id
    
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    )
    total_users = total_users_result.scalar()
    
    active_users_result = await db.execute(
        select(func.count(User.id)).where(
            and_(User.tenant_id == tenant_id, User.is_active.is_(True))
        )
    )
    active_users = active_users_result.scalar()
    inactive_users = total_users - active_users
    
    admin_users_result = await db.execute(
        select(func.count(User.id)).where(
            and_(User.tenant_id == tenant_id, User.is_admin.is_(True))
        )
    )
    admin_users = admin_users_result.scalar()
    regular_users = total_users - admin_users
    
    from datetime import datetime, timedelta
    recent_threshold = datetime.utcnow() - timedelta(days=30)
    recent_users_result = await db.execute(
        select(func.count(User.id)).where(
            and_(
                User.tenant_id == tenant_id,
                User.created_at >= recent_threshold
            )
        )
    )
    recent_users = recent_users_result.scalar()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "admin_users": admin_users,
        "regular_users": regular_users,
        "recent_users": recent_users
    }


@router.get("/users/{user_id}", response_model=UserProfile)
async def get_enterprise_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业用户详情
    - 只能查看同一租户下的用户
    """
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新用户状态（启用/禁用）
    - 管理员不能禁用自己
    """
    if str(admin_user.id) == user_id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")
    
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_active = is_active
    await db.commit()
    
    status_text = "启用" if is_active else "禁用"
    return {"message": f"用户已{status_text}"}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    is_admin: bool,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新用户角色（管理员/普通用户）
    - 管理员不能取消自己的管理员权限
    """
    if str(admin_user.id) == user_id and not is_admin:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
    
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_admin = is_admin
    await db.commit()
    
    role_text = "管理员" if is_admin else "普通用户"
    return {"message": f"用户角色已更新为{role_text}"}


@router.delete("/users/{user_id}")
async def remove_user_from_enterprise(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    将用户从企业中移除
    - 用户将被转移到个人租户
    - 管理员不能移除自己
    """
    if str(admin_user.id) == user_id:
        raise HTTPException(status_code=400, detail="不能移除自己")
    
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    from app.api.v1.endpoints.auth import generate_tenant_id
    new_tenant_id = generate_tenant_id("user")
    
    user.tenant_id = new_tenant_id
    user.is_admin = False
    await db.commit()
    
    return {"message": "用户已从企业中移除，转移到个人租户"}


@router.get("/info", response_model=dict)
async def get_enterprise_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取企业信息（所有用户可用）
    """
    company_name = await _get_company_name(
        db,
        current_user.tenant_id,
        current_user.company_name
    )
    company_info = {
        "id": current_user.tenant_id,
        "name": company_name,
        "tenant_id": current_user.tenant_id,
        "admin_name": current_user.full_name or current_user.nickname,
        "admin_email": current_user.email,
        "admin_phone": current_user.phone,
        "created_at": current_user.created_at
    }
    
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == current_user.tenant_id)
    )
    total_users = total_users_result.scalar()
    
    active_users_result = await db.execute(
        select(func.count(User.id)).where(
            and_(User.tenant_id == current_user.tenant_id, User.is_active.is_(True))
        )
    )
    active_users = active_users_result.scalar()
    
    company_info.update({
        "member_count": total_users,
        "total_users": total_users,
        "active_users": active_users
    })
    
    return company_info


@router.put("/info")
async def update_enterprise_info(
    company_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新企业信息
    """
    if company_name:
        await _sync_company_name(db, admin_user.tenant_id, company_name, admin_user)
        await db.commit()
    
    return {"message": "企业信息更新成功"}


@router.get("/activity-log")
async def get_enterprise_activity_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业活动日志
    - 用户注册、状态变更等活动记录
    """
    result = await db.execute(
        select(User)
        .where(User.tenant_id == admin_user.tenant_id)
        .order_by(desc(User.created_at))
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    
    activities = []
    for user in users:
        activities.append({
            "type": "user_registered",
            "user_id": str(user.id),
            "user_email": user.email,
            "user_name": user.nickname or user.full_name,
            "timestamp": user.created_at,
            "description": f"用户 {user.email} 加入企业"
        })
    
    return activities
