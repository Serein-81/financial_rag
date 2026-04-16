"""
权限控制系统

提供细粒度的权限管理和访问控制

功能：
1. 权限定义和枚举
2. 角色管理
3. 基于角色的访问控制 (RBAC)
4. 权限验证
5. 权限继承
"""

from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)


class PermissionType(Enum):
    """权限类型"""
    READ = "read"                 # 读取权限
    WRITE = "write"               # 写入权限
    DELETE = "delete"             # 删除权限
    EXECUTE = "execute"           # 执行权限
    ADMIN = "admin"               # 管理权限
    SUPER_ADMIN = "super_admin"   # 超级管理员


class RoleType(Enum):
    """角色类型"""
    GUEST = "guest"               # 访客
    USER = "user"                 # 普通用户
    PREMIUM_USER = "premium_user" # 高级用户
    OPERATOR = "operator"         # 运营人员
    ADMIN = "admin"               # 管理员
    SUPER_ADMIN = "super_admin"   # 超级管理员


@dataclass
class Permission:
    """
    权限定义
    
    Attributes:
        name: 权限名称
        permission_type: 权限类型
        resource_type: 资源类型
        resource_id: 资源 ID（可选）
        description: 权限描述
        conditions: 额外条件
    """
    name: str
    permission_type: PermissionType
    resource_type: str
    resource_id: Optional[str] = None
    description: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        """使 Permission 可哈希"""
        return hash((self.name, self.permission_type, self.resource_type, self.resource_id))
    
    def __eq__(self, other):
        """比较两个 Permission 是否相等"""
        if not isinstance(other, Permission):
            return False
        return (
            self.name == other.name and
            self.permission_type == other.permission_type and
            self.resource_type == other.resource_type and
            self.resource_id == other.resource_id
        )
    
    def matches(
        self,
        permission_type: PermissionType,
        resource_type: str,
        resource_id: Optional[str] = None,
    ) -> bool:
        """
        检查权限是否匹配
        
        Args:
            permission_type: 权限类型
            resource_type: 资源类型
            resource_id: 资源 ID
            
        Returns:
            bool: 是否匹配
        """
        if self.permission_type != permission_type:
            return False
        
        if self.resource_type != resource_type:
            return False
        
        if self.resource_id is not None and resource_id is not None:
            return self.resource_id == resource_id
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "permission_type": self.permission_type.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "conditions": self.conditions,
        }


@dataclass
class Role:
    """
    角色定义
    
    Attributes:
        name: 角色名称
        role_type: 角色类型
        permissions: 权限列表
        parent_role: 父角色（权限继承）
        description: 角色描述
    """
    name: str
    role_type: RoleType
    permissions: List[Permission] = field(default_factory=list)
    parent_role: Optional["Role"] = None
    description: str = ""
    
    def has_permission(
        self,
        permission_type: PermissionType,
        resource_type: str,
        resource_id: Optional[str] = None,
    ) -> bool:
        """
        检查角色是否具有指定权限
        
        Args:
            permission_type: 权限类型
            resource_type: 资源类型
            resource_id: 资源 ID
            
        Returns:
            bool: 是否具有权限
        """
        for permission in self.permissions:
            if permission.matches(permission_type, resource_type, resource_id):
                return True
        
        if self.parent_role:
            return self.parent_role.has_permission(
                permission_type, resource_type, resource_id
            )
        
        return False
    
    def add_permission(self, permission: Permission) -> None:
        """添加权限"""
        if permission not in self.permissions:
            self.permissions.append(permission)
    
    def remove_permission(self, permission_name: str) -> bool:
        """移除权限"""
        for i, perm in enumerate(self.permissions):
            if perm.name == permission_name:
                del self.permissions[i]
                return True
        return False
    
    def get_all_permissions(self) -> Set[Permission]:
        """获取所有权限（包括继承的）"""
        permissions = set(self.permissions)
        if self.parent_role:
            permissions.update(self.parent_role.get_all_permissions())
        return permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "role_type": self.role_type.value,
            "permissions": [p.to_dict() for p in self.permissions],
            "parent_role": self.parent_role.name if self.parent_role else None,
            "description": self.description,
        }


class PermissionChecker:
    """
    权限检查器
    
    提供运行时权限验证功能
    """
    
    def __init__(self):
        """初始化权限检查器"""
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, List[str]] = {}
        self._user_permissions_cache: Dict[str, Set[Permission]] = {}
        self._lock = threading.RLock()
        
        self._initialize_default_roles()
    
    def _initialize_default_roles(self) -> None:
        """初始化默认角色"""
        guest_role = Role(
            name="guest",
            role_type=RoleType.GUEST,
            description="访客角色",
            permissions=[
                Permission(
                    name="read_public",
                    permission_type=PermissionType.READ,
                    resource_type="public_data",
                    description="读取公共数据"
                ),
            ]
        )
        
        user_role = Role(
            name="user",
            role_type=RoleType.USER,
            description="普通用户角色",
            parent_role=guest_role,
            permissions=[
                Permission(
                    name="read_own_data",
                    permission_type=PermissionType.READ,
                    resource_type="user_data",
                    description="读取自己的数据"
                ),
                Permission(
                    name="write_own_data",
                    permission_type=PermissionType.WRITE,
                    resource_type="user_data",
                    description="写入自己的数据"
                ),
            ]
        )
        
        premium_user_role = Role(
            name="premium_user",
            role_type=RoleType.PREMIUM_USER,
            description="高级用户角色",
            parent_role=user_role,
            permissions=[
                Permission(
                    name="read_analytics",
                    permission_type=PermissionType.READ,
                    resource_type="analytics",
                    description="读取分析数据"
                ),
            ]
        )
        
        operator_role = Role(
            name="operator",
            role_type=RoleType.OPERATOR,
            description="运营人员角色",
            parent_role=premium_user_role,
            permissions=[
                Permission(
                    name="manage_users",
                    permission_type=PermissionType.ADMIN,
                    resource_type="users",
                    description="管理用户"
                ),
                Permission(
                    name="read_logs",
                    permission_type=PermissionType.READ,
                    resource_type="system_logs",
                    description="读取系统日志"
                ),
            ]
        )
        
        admin_role = Role(
            name="admin",
            role_type=RoleType.ADMIN,
            description="管理员角色",
            parent_role=operator_role,
            permissions=[
                Permission(
                    name="manage_tenant",
                    permission_type=PermissionType.ADMIN,
                    resource_type="tenant",
                    description="管理租户"
                ),
                Permission(
                    name="manage_settings",
                    permission_type=PermissionType.READ,
                    resource_type="system_settings",
                    description="管理系统设置"
                ),
            ]
        )
        
        super_admin_role = Role(
            name="super_admin",
            role_type=RoleType.SUPER_ADMIN,
            description="超级管理员角色",
            parent_role=admin_role,
            permissions=[
                Permission(
                    name="super_admin_all",
                    permission_type=PermissionType.SUPER_ADMIN,
                    resource_type="*",
                    description="所有权限"
                ),
            ]
        )
        
        self._roles = {
            "guest": guest_role,
            "user": user_role,
            "premium_user": premium_user_role,
            "operator": operator_role,
            "admin": admin_role,
            "super_admin": super_admin_role,
        }
    
    def register_role(self, role: Role) -> None:
        """
        注册角色
        
        Args:
            role: 角色对象
        """
        with self._lock:
            self._roles[role.name] = role
            self._user_permissions_cache.clear()
            logger.info(f"角色注册成功: {role.name}")
    
    def get_role(self, role_name: str) -> Optional[Role]:
        """获取角色"""
        return self._roles.get(role_name)
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """
        为用户分配角色
        
        Args:
            user_id: 用户 ID
            role_name: 角色名称
            
        Returns:
            bool: 是否分配成功
        """
        with self._lock:
            if role_name not in self._roles:
                logger.warning(f"角色不存在: {role_name}")
                return False
            
            if user_id not in self._user_roles:
                self._user_roles[user_id] = []
            
            if role_name not in self._user_roles[user_id]:
                self._user_roles[user_id].append(role_name)
                self._user_permissions_cache.pop(user_id, None)
                logger.info(f"用户 {user_id} 分配角色 {role_name}")
            
            return True
    
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """
        撤销用户角色
        
        Args:
            user_id: 用户 ID
            role_name: 角色名称
            
        Returns:
            bool: 是否撤销成功
        """
        with self._lock:
            if user_id in self._user_roles:
                if role_name in self._user_roles[user_id]:
                    self._user_roles[user_id].remove(role_name)
                    self._user_permissions_cache.pop(user_id, None)
                    logger.info(f"用户 {user_id} 撤销角色 {role_name}")
                    return True
            return False
    
    def get_user_roles(self, user_id: str) -> List[str]:
        """获取用户角色列表"""
        return self._user_roles.get(user_id, [])
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        获取用户所有权限
        
        Args:
            user_id: 用户 ID
            
        Returns:
            Set[Permission]: 权限集合
        """
        if user_id in self._user_permissions_cache:
            return self._user_permissions_cache[user_id]
        
        permissions: Set[Permission] = set()
        user_roles = self._user_roles.get(user_id, [])
        
        for role_name in user_roles:
            role = self._roles.get(role_name)
            if role:
                permissions.update(role.get_all_permissions())
        
        self._user_permissions_cache[user_id] = permissions
        return permissions
    
    def check_permission(
        self,
        user_id: str,
        permission_type: PermissionType,
        resource_type: str,
        resource_id: Optional[str] = None,
    ) -> bool:
        """
        检查用户权限
        
        Args:
            user_id: 用户 ID
            permission_type: 权限类型
            resource_type: 资源类型
            resource_id: 资源 ID
            
        Returns:
            bool: 是否有权限
        """
        user_permissions = self.get_user_permissions(user_id)
        
        for permission in user_permissions:
            if permission.permission_type == PermissionType.SUPER_ADMIN:
                return True
            
            if permission.matches(permission_type, resource_type, resource_id):
                return True
        
        return False
    
    def require_permission(
        self,
        user_id: str,
        permission_type: PermissionType,
        resource_type: str,
        resource_id: Optional[str] = None,
    ) -> None:
        """
        要求用户具有指定权限
        
        Args:
            user_id: 用户 ID
            permission_type: 权限类型
            resource_type: 资源类型
            resource_id: 资源 ID
            
        Raises:
            PermissionDenied: 权限不足
        """
        if not self.check_permission(user_id, permission_type, resource_type, resource_id):
            raise PermissionDenied(
                f"用户 {user_id} 缺少权限: "
                f"{permission_type.value} {resource_type}"
            )
    
    def get_accessible_resources(
        self,
        user_id: str,
        permission_type: PermissionType,
        resource_type: str,
    ) -> List[str]:
        """
        获取用户可访问的资源列表
        
        Args:
            user_id: 用户 ID
            permission_type: 权限类型
            resource_type: 资源类型
            
        Returns:
            List[str]: 资源 ID 列表
        """
        user_permissions = self.get_user_permissions(user_id)
        resource_ids: List[str] = []
        
        for permission in user_permissions:
            if permission.matches(permission_type, resource_type):
                if permission.resource_id:
                    resource_ids.append(permission.resource_id)
                elif permission.resource_id == "*":
                    return ["*"]
        
        return list(set(resource_ids))
    
    def clear_cache(self) -> None:
        """清除权限缓存"""
        with self._lock:
            self._user_permissions_cache.clear()
            logger.info("权限缓存已清除")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_roles": len(self._roles),
            "total_users": len(self._user_roles),
            "cached_users": len(self._user_permissions_cache),
            "roles": list(self._roles.keys()),
        }


class PermissionDenied(Exception):
    """权限拒绝异常"""
    pass


_global_permission_checker: Optional[PermissionChecker] = None


def get_permission_checker() -> PermissionChecker:
    """获取全局权限检查器"""
    global _global_permission_checker
    if _global_permission_checker is None:
        _global_permission_checker = PermissionChecker()
    return _global_permission_checker
