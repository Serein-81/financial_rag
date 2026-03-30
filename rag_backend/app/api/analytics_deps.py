"""分析功能权限控制依赖"""
from functools import wraps
from fastapi import Depends, HTTPException
from enum import Enum
from typing import Callable, List, Optional
import logging

from app.models.user import User
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    TENANT_ADMIN = "tenant_admin"
    TENANT_USER = "tenant_user"


class AnalyticsPermission(str, Enum):
    VIEW_ENTERPRISE_DASHBOARD = "view_enterprise_dashboard"
    VIEW_ENTERPRISE_TRENDS = "view_enterprise_trends"
    VIEW_USER_BEHAVIOR = "view_user_behavior"
    VIEW_KB_HEALTH = "view_kb_health"
    VIEW_KB_USAGE = "view_kb_usage"
    EXPORT_ENTERPRISE_DATA = "export_enterprise_data"
    MANAGE_SUBSCRIPTIONS = "manage_subscriptions"
    VIEW_PERSONAL_HISTORY = "view_personal_history"


ROLE_PERMISSIONS = {
    UserRole.TENANT_ADMIN: {
        AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD,
        AnalyticsPermission.VIEW_ENTERPRISE_TRENDS,
        AnalyticsPermission.VIEW_USER_BEHAVIOR,
        AnalyticsPermission.VIEW_KB_HEALTH,
        AnalyticsPermission.VIEW_KB_USAGE,
        AnalyticsPermission.EXPORT_ENTERPRISE_DATA,
        AnalyticsPermission.MANAGE_SUBSCRIPTIONS,
        AnalyticsPermission.VIEW_PERSONAL_HISTORY,
    },
    UserRole.TENANT_USER: {
        AnalyticsPermission.VIEW_PERSONAL_HISTORY,
    }
}


def get_user_role(user: User) -> UserRole:
    if hasattr(user, 'role') and user.role == 'admin':
        return UserRole.TENANT_ADMIN
    if hasattr(user, 'is_tenant_admin') and user.is_tenant_admin:
        return UserRole.TENANT_ADMIN
    if hasattr(user, 'tenant_role') and user.tenant_role == 'tenant_admin':
        return UserRole.TENANT_ADMIN
    
    return UserRole.TENANT_USER


def has_permission(user: User, permission: AnalyticsPermission) -> bool:
    role = get_user_role(user)
    user_permissions = ROLE_PERMISSIONS.get(role, set())
    return permission in user_permissions


def has_any_permission(user: User, permissions: List[AnalyticsPermission]) -> bool:
    return any(has_permission(user, p) for p in permissions)


def has_all_permissions(user: User, permissions: List[AnalyticsPermission]) -> bool:
    return all(has_permission(user, p) for p in permissions)


def require_analytics_permission(
    permission: AnalyticsPermission,
    error_message: Optional[str] = None
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                    break
            else:
                raise HTTPException(
                    status_code=500,
                    detail="用户信息未找到"
                )
            
            if not has_permission(current_user, permission):
                logger.warning(
                    f"User {current_user.id} denied access to {permission.value}. "
                    f"User role: {get_user_role(current_user)}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=error_message or f"您没有权限执行此操作: {permission.value}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(
    permissions: List[AnalyticsPermission],
    error_message: Optional[str] = None
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=500,
                    detail="用户信息未找到"
                )
            
            if not has_any_permission(current_user, permissions):
                logger.warning(
                    f"User {current_user.id} denied access. "
                    f"Required any of: {[p.value for p in permissions]}. "
                    f"User role: {get_user_role(current_user)}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=error_message or "您没有权限执行此操作"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_tenant_admin(
    error_message: Optional[str] = None
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=500,
                    detail="用户信息未找到"
                )
            
            role = get_user_role(current_user)
            if role != UserRole.TENANT_ADMIN:
                logger.warning(
                    f"User {current_user.id} (role: {role}) attempted to access admin resource"
                )
                raise HTTPException(
                    status_code=403,
                    detail=error_message or "此操作需要企业管理员权限"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_user_data_filter(
    current_user: User,
    user_id: Optional[str] = None
) -> dict:
    """
    获取用户数据过滤条件。
    普通用户只能查看自己的数据，管理员可以查看指定用户或全部数据。
    """
    role = get_user_role(current_user)
    
    if role == UserRole.TENANT_ADMIN:
        if user_id:
            return {"user_id": user_id}
        return {}
    else:
        return {"user_id": current_user.id}


def get_user_filter_condition(
    current_user: User,
    user_id_param: Optional[str] = None,
    param_name: str = "user_id"
) -> Optional[dict]:
    """
    生成 SQLAlchemy 查询过滤条件。
    """
    role = get_user_role(current_user)
    
    if role == UserRole.TENANT_ADMIN:
        if user_id_param:
            return {param_name: user_id_param}
        return None
    else:
        return {param_name: current_user.id}
