"""
企业用户管理API端点
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.api import deps
from app.models.user import User
from app.schemas.auth_response import UserProfile
from app.db.session import get_db

router = APIRouter()


# =======================
# 权限检查辅助函数
# =======================

def require_admin_user(current_user: User = Depends(deps.get_current_user)) -> User:
    """要求当前用户是管理员"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# =======================
# 企业用户管理
# =======================

@router.get("/users", response_model=List[UserProfile])
async def list_enterprise_users(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    search: Optional[str] = Query(None, description="搜索关键词（邮箱、昵称、姓名）"),
    is_active: Optional[bool] = Query(None, description="用户状态过滤"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业用户列表
    - 只显示同一租户下的用户
    - 支持搜索和过滤
    """
    query = db.query(User).filter(User.tenant_id == admin_user.tenant_id)
    
    # 搜索过滤
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_pattern),
                User.nickname.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    # 状态过滤
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # 排序和分页
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    
    return users


@router.get("/users/stats")
async def get_enterprise_user_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业用户统计信息
    """
    tenant_id = admin_user.tenant_id
    
    # 基础统计
    total_users = db.query(User).filter(User.tenant_id == tenant_id).count()
    active_users = db.query(User).filter(
        and_(User.tenant_id == tenant_id, User.is_active == True)
    ).count()
    inactive_users = total_users - active_users
    
    # 管理员统计
    admin_users = db.query(User).filter(
        and_(User.tenant_id == tenant_id, User.is_admin == True)
    ).count()
    regular_users = total_users - admin_users
    
    # 最近注册用户
    from datetime import datetime, timedelta
    recent_threshold = datetime.utcnow() - timedelta(days=30)
    recent_users = db.query(User).filter(
        and_(
            User.tenant_id == tenant_id,
            User.created_at >= recent_threshold
        )
    ).count()
    
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
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业用户详情
    - 只能查看同一租户下的用户
    """
    user = db.query(User).filter(
        and_(
            User.id == user_id,
            User.tenant_id == admin_user.tenant_id
        )
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新用户状态（启用/禁用）
    - 管理员不能禁用自己
    """
    # 检查是否是自己
    if str(admin_user.id) == user_id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")
    
    # 查找用户
    user = db.query(User).filter(
        and_(
            User.id == user_id,
            User.tenant_id == admin_user.tenant_id
        )
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新状态
    user.is_active = is_active
    db.commit()
    
    status_text = "启用" if is_active else "禁用"
    return {"message": f"用户已{status_text}"}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    is_admin: bool,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新用户角色（管理员/普通用户）
    - 管理员不能取消自己的管理员权限
    """
    # 检查是否是自己
    if str(admin_user.id) == user_id and not is_admin:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
    
    # 查找用户
    user = db.query(User).filter(
        and_(
            User.id == user_id,
            User.tenant_id == admin_user.tenant_id
        )
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新角色
    user.is_admin = is_admin
    db.commit()
    
    role_text = "管理员" if is_admin else "普通用户"
    return {"message": f"用户角色已更新为{role_text}"}


@router.delete("/users/{user_id}")
async def remove_user_from_enterprise(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    将用户从企业中移除
    - 用户将被转移到个人租户
    - 管理员不能移除自己
    """
    # 检查是否是自己
    if str(admin_user.id) == user_id:
        raise HTTPException(status_code=400, detail="不能移除自己")
    
    # 查找用户
    user = db.query(User).filter(
        and_(
            User.id == user_id,
            User.tenant_id == admin_user.tenant_id
        )
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 生成新的个人租户ID
    from app.api.v1.endpoints.auth import generate_tenant_id
    new_tenant_id = generate_tenant_id("user")
    
    # 更新用户租户
    user.tenant_id = new_tenant_id
    user.is_admin = False  # 移除管理员权限
    db.commit()
    
    return {"message": "用户已从企业中移除，转移到个人租户"}


# =======================
# 企业信息管理
# =======================

@router.get("/info")
async def get_enterprise_info(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业信息
    """
    # 获取企业基本信息（从管理员用户获取）
    company_info = {
        "tenant_id": admin_user.tenant_id,
        "company_name": admin_user.company_name,
        "admin_name": admin_user.full_name or admin_user.nickname,
        "admin_email": admin_user.email,
        "admin_phone": admin_user.phone,
        "created_at": admin_user.created_at
    }
    
    # 获取用户统计
    total_users = db.query(User).filter(User.tenant_id == admin_user.tenant_id).count()
    active_users = db.query(User).filter(
        and_(User.tenant_id == admin_user.tenant_id, User.is_active == True)
    ).count()
    
    company_info.update({
        "total_users": total_users,
        "active_users": active_users
    })
    
    return company_info


@router.put("/info")
async def update_enterprise_info(
    company_name: Optional[str] = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新企业信息
    """
    if company_name:
        admin_user.company_name = company_name
        db.commit()
    
    return {"message": "企业信息更新成功"}


# =======================
# 企业活动日志
# =======================

@router.get("/activity-log")
async def get_enterprise_activity_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业活动日志
    - 用户注册、状态变更等活动记录
    """
    # 这里可以扩展为完整的审计日志系统
    # 目前返回基础的用户活动信息
    
    users = db.query(User).filter(
        User.tenant_id == admin_user.tenant_id
    ).order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    
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