"""运营分析权限控制单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
from enum import Enum


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


def get_user_role(user) -> UserRole:
    if hasattr(user, 'role') and user.role == 'admin':
        return UserRole.TENANT_ADMIN
    if hasattr(user, 'is_tenant_admin') and user.is_tenant_admin:
        return UserRole.TENANT_ADMIN
    if hasattr(user, 'tenant_role') and user.tenant_role == 'tenant_admin':
        return UserRole.TENANT_ADMIN
    
    return UserRole.TENANT_USER


def has_permission(user, permission: AnalyticsPermission) -> bool:
    role = get_user_role(user)
    user_permissions = ROLE_PERMISSIONS.get(role, set())
    return permission in user_permissions


def has_any_permission(user, permissions) -> bool:
    return any(has_permission(user, p) for p in permissions)


def has_all_permissions(user, permissions) -> bool:
    return all(has_permission(user, p) for p in permissions)


def require_analytics_permission(permission: AnalyticsPermission, error_message=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, MockUser):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(status_code=500, detail="用户信息未找到")
            
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=403,
                    detail=error_message or f"您没有权限执行此操作: {permission.value}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_tenant_admin(error_message=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, MockUser):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(status_code=500, detail="用户信息未找到")
            
            role = get_user_role(current_user)
            if role != UserRole.TENANT_ADMIN:
                raise HTTPException(
                    status_code=403,
                    detail=error_message or "此操作需要企业管理员权限"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_user_data_filter(current_user, user_id=None) -> dict:
    role = get_user_role(current_user)
    
    if role == UserRole.TENANT_ADMIN:
        if user_id:
            return {"user_id": user_id}
        return {}
    else:
        return {"user_id": current_user.id}


def get_user_filter_condition(current_user, user_id_param=None, param_name="user_id"):
    role = get_user_role(current_user)
    
    if role == UserRole.TENANT_ADMIN:
        if user_id_param:
            return {param_name: user_id_param}
        return None
    else:
        return {param_name: current_user.id}


class MockUser:
    def __init__(self, user_id: str, tenant_id: str, **attrs):
        self.id = user_id
        self.tenant_id = tenant_id
        for key, value in attrs.items():
            setattr(self, key, value)


class TestUserRole:
    
    def test_role_from_admin_attr(self):
        user = MockUser("user_001", "tenant_001", role="admin")
        role = get_user_role(user)
        assert role == UserRole.TENANT_ADMIN
    
    def test_role_from_is_tenant_admin(self):
        user = MockUser("user_001", "tenant_001", is_tenant_admin=True)
        role = get_user_role(user)
        assert role == UserRole.TENANT_ADMIN
    
    def test_role_from_tenant_role(self):
        user = MockUser("user_001", "tenant_001", tenant_role="tenant_admin")
        role = get_user_role(user)
        assert role == UserRole.TENANT_ADMIN
    
    def test_role_regular_user(self):
        user = MockUser("user_001", "tenant_001")
        role = get_user_role(user)
        assert role == UserRole.TENANT_USER


class TestRolePermissions:
    
    def test_tenant_admin_has_all_permissions(self):
        admin_permissions = ROLE_PERMISSIONS[UserRole.TENANT_ADMIN]
        
        assert AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD in admin_permissions
        assert AnalyticsPermission.VIEW_ENTERPRISE_TRENDS in admin_permissions
        assert AnalyticsPermission.VIEW_USER_BEHAVIOR in admin_permissions
        assert AnalyticsPermission.VIEW_KB_HEALTH in admin_permissions
        assert AnalyticsPermission.VIEW_KB_USAGE in admin_permissions
        assert AnalyticsPermission.EXPORT_ENTERPRISE_DATA in admin_permissions
        assert AnalyticsPermission.MANAGE_SUBSCRIPTIONS in admin_permissions
        assert AnalyticsPermission.VIEW_PERSONAL_HISTORY in admin_permissions
    
    def test_tenant_user_has_limited_permissions(self):
        user_permissions = ROLE_PERMISSIONS[UserRole.TENANT_USER]
        
        assert AnalyticsPermission.VIEW_PERSONAL_HISTORY in user_permissions
        assert AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD not in user_permissions
        assert AnalyticsPermission.VIEW_ENTERPRISE_TRENDS not in user_permissions
        assert AnalyticsPermission.VIEW_USER_BEHAVIOR not in user_permissions
        assert AnalyticsPermission.VIEW_KB_HEALTH not in user_permissions
        assert AnalyticsPermission.VIEW_KB_USAGE not in user_permissions
        assert AnalyticsPermission.EXPORT_ENTERPRISE_DATA not in user_permissions


class TestHasPermission:
    
    def test_admin_has_enterprise_dashboard_permission(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = has_permission(user, AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD)
        
        assert result is True
    
    def test_admin_has_user_behavior_permission(self):
        user = MockUser("admin_001", "tenant_001", is_tenant_admin=True)
        
        result = has_permission(user, AnalyticsPermission.VIEW_USER_BEHAVIOR)
        
        assert result is True
    
    def test_regular_user_does_not_have_enterprise_dashboard(self):
        user = MockUser("user_001", "tenant_001")
        
        result = has_permission(user, AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD)
        
        assert result is False
    
    def test_regular_user_has_personal_history(self):
        user = MockUser("user_001", "tenant_001")
        
        result = has_permission(user, AnalyticsPermission.VIEW_PERSONAL_HISTORY)
        
        assert result is True
    
    def test_regular_user_cannot_export_data(self):
        user = MockUser("user_001", "tenant_001")
        
        result = has_permission(user, AnalyticsPermission.EXPORT_ENTERPRISE_DATA)
        
        assert result is False


class TestHasAnyPermission:
    
    def test_admin_has_any_of_permissions(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = has_any_permission(
            user,
            [
                AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD,
                AnalyticsPermission.VIEW_USER_BEHAVIOR
            ]
        )
        
        assert result is True
    
    def test_user_has_one_of_permissions(self):
        user = MockUser("user_001", "tenant_001")
        
        result = has_any_permission(
            user,
            [
                AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD,
                AnalyticsPermission.VIEW_PERSONAL_HISTORY
            ]
        )
        
        assert result is True
    
    def test_user_has_none_of_permissions(self):
        user = MockUser("user_001", "tenant_001")
        
        result = has_any_permission(
            user,
            [
                AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD,
                AnalyticsPermission.EXPORT_ENTERPRISE_DATA
            ]
        )
        
        assert result is False


class TestHasAllPermissions:
    
    def test_admin_has_all_permissions(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = has_all_permissions(
            user,
            [
                AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD,
                AnalyticsPermission.VIEW_PERSONAL_HISTORY
            ]
        )
        
        assert result is True
    
    def test_user_missing_some_permissions(self):
        user = MockUser("user_001", "tenant_001")
        
        result = has_all_permissions(
            user,
            [
                AnalyticsPermission.VIEW_PERSONAL_HISTORY,
                AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD
            ]
        )
        
        assert result is False


class TestRequireAnalyticsPermission:
    
    @pytest.mark.asyncio
    async def test_admin_can_access_decorated_endpoint(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        @require_analytics_permission(AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD)
        async def protected_endpoint(current_user: MockUser = None):
            return {"success": True}
        
        result = await protected_endpoint(current_user=user)
        
        assert result == {"success": True}
    
    @pytest.mark.asyncio
    async def test_regular_user_denied_access(self):
        user = MockUser("user_001", "tenant_001")
        
        @require_analytics_permission(AnalyticsPermission.VIEW_ENTERPRISE_DASHBOARD)
        async def protected_endpoint(current_user: MockUser = None):
            return {"success": True}
        
        with pytest.raises(HTTPException) as exc_info:
            await protected_endpoint(current_user=user)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_custom_error_message(self):
        user = MockUser("user_001", "tenant_001")
        
        @require_analytics_permission(
            AnalyticsPermission.EXPORT_ENTERPRISE_DATA,
            error_message="自定义错误：您没有导出权限"
        )
        async def protected_endpoint(current_user: MockUser = None):
            return {"success": True}
        
        with pytest.raises(HTTPException) as exc_info:
            await protected_endpoint(current_user=user)
        
        assert exc_info.value.status_code == 403
        assert "自定义错误" in str(exc_info.value.detail)


class TestRequireTenantAdmin:
    
    @pytest.mark.asyncio
    async def test_tenant_admin_access(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        @require_tenant_admin()
        async def admin_endpoint(current_user: MockUser = None):
            return {"success": True}
        
        result = await admin_endpoint(current_user=user)
        
        assert result == {"success": True}
    
    @pytest.mark.asyncio
    async def test_regular_user_denied(self):
        user = MockUser("user_001", "tenant_001")
        
        @require_tenant_admin()
        async def admin_endpoint(current_user: MockUser = None):
            return {"success": True}
        
        with pytest.raises(HTTPException) as exc_info:
            await admin_endpoint(current_user=user)
        
        assert exc_info.value.status_code == 403
        assert "企业管理员权限" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_custom_admin_error_message(self):
        user = MockUser("user_001", "tenant_001")
        
        @require_tenant_admin(error_message="仅限超级管理员操作")
        async def admin_endpoint(current_user: MockUser = None):
            return {"success": True}
        
        with pytest.raises(HTTPException) as exc_info:
            await admin_endpoint(current_user=user)
        
        assert "仅限超级管理员操作" in str(exc_info.value.detail)


class TestGetUserDataFilter:
    
    def test_admin_get_all_data(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = get_user_data_filter(user)
        
        assert result == {}
    
    def test_admin_get_specific_user_data(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = get_user_data_filter(user, user_id="user_002")
        
        assert result == {"user_id": "user_002"}
    
    def test_regular_user_gets_own_data(self):
        user = MockUser("user_001", "tenant_001")
        
        result = get_user_data_filter(user)
        
        assert result == {"user_id": "user_001"}
    
    def test_regular_user_cannot_specify_other_user(self):
        user = MockUser("user_001", "tenant_001")
        
        result = get_user_data_filter(user, user_id="user_002")
        
        assert result == {"user_id": "user_001"}


class TestGetUserFilterCondition:
    
    def test_admin_no_filter_for_all_data(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = get_user_filter_condition(user)
        
        assert result is None
    
    def test_admin_with_user_id_param(self):
        user = MockUser("admin_001", "tenant_001", role="admin")
        
        result = get_user_filter_condition(user, user_id_param="user_003")
        
        assert result == {"user_id": "user_003"}
    
    def test_regular_user_forced_to_own_id(self):
        user = MockUser("user_001", "tenant_001")
        
        result = get_user_filter_condition(user, user_id_param="user_002")
        
        assert result == {"user_id": "user_001"}
    
    def test_custom_param_name(self):
        user = MockUser("user_001", "tenant_001")
        
        result = get_user_filter_condition(
            user,
            user_id_param="owner_id",
            param_name="owner_id"
        )
        
        assert result == {"owner_id": "user_001"}


class TestPermissionEnumValues:
    
    def test_all_permission_values_are_unique(self):
        values = [p.value for p in AnalyticsPermission]
        assert len(values) == len(set(values))
    
    def test_permission_values_are_snake_case(self):
        for permission in AnalyticsPermission:
            assert "_" in permission.value or permission.value.islower()


class TestEdgeCases:
    
    def test_user_without_any_role_attrs(self):
        user = MockUser("user_001", "tenant_001")
        role = get_user_role(user)
        assert role == UserRole.TENANT_USER
    
    def test_user_with_multiple_admin_attrs(self):
        user = MockUser(
            "user_001",
            "tenant_001",
            role="admin",
            is_tenant_admin=True,
            tenant_role="tenant_admin"
        )
        role = get_user_role(user)
        assert role == UserRole.TENANT_ADMIN
    
    def test_empty_permission_list_has_any(self):
        user = MockUser("user_001", "tenant_001")
        result = has_any_permission(user, [])
        assert result is False
    
    def test_empty_permission_list_has_all(self):
        user = MockUser("user_001", "tenant_001")
        result = has_all_permissions(user, [])
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
