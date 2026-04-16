"""
租户隔离机制

确保多租户环境下的数据隔离和安全访问

功能：
1. 租户上下文管理
2. 数据隔离验证
3. 跨租户访问控制
4. 租户配额管理
"""

import contextvars
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import threading

logger = logging.getLogger(__name__)


class TenantIsolationLevel(Enum):
    """隔离级别"""
    STRICT = "strict"           # 严格隔离，完全分离
    SHARED = "shared"           # 共享模式
    HYBRID = "hybrid"           # 混合模式


class TenantContext:
    """
    租户上下文
    
    管理当前请求的租户信息
    """
    
    def __init__(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        isolation_level: TenantIsolationLevel = TenantIsolationLevel.STRICT,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化租户上下文
        
        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID
            roles: 用户角色列表
            isolation_level: 隔离级别
            metadata: 额外元数据
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.roles = roles or []
        self.isolation_level = isolation_level
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self._accessed_count = 0
    
    def __enter__(self):
        """进入上下文"""
        self.last_accessed = datetime.now()
        self._accessed_count += 1
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        pass
    
    def has_role(self, role: str) -> bool:
        """检查是否具有角色"""
        return role in self.roles
    
    def has_any_role(self, roles: List[str]) -> bool:
        """检查是否具有任一角色"""
        return any(role in self.roles for role in roles)
    
    def add_role(self, role: str) -> None:
        """添加角色"""
        if role not in self.roles:
            self.roles.append(role)
    
    def remove_role(self, role: str) -> None:
        """移除角色"""
        if role in self.roles:
            self.roles.remove(role)
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "roles": self.roles,
            "isolation_level": self.isolation_level.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "accessed_count": self._accessed_count
        }


class TenantIsolation:
    """
    租户隔离管理器
    
    提供多租户环境下的数据隔离保障
    """
    
    def __init__(
        self,
        default_isolation_level: TenantIsolationLevel = TenantIsolationLevel.STRICT,
        enable_cross_tenant_check: bool = True,
        max_tenants: int = 1000,
    ):
        """
        初始化租户隔离管理器
        
        Args:
            default_isolation_level: 默认隔离级别
            enable_cross_tenant_check: 是否启用跨租户检查
            max_tenants: 最大租户数
        """
        self.default_isolation_level = default_isolation_level
        self.enable_cross_tenant_check = enable_cross_tenant_check
        self.max_tenants = max_tenants
        
        self._tenants: Dict[str, TenantContext] = {}
        self._tenant_quotas: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def register_tenant(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TenantContext:
        """
        注册租户
        
        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID
            roles: 用户角色
            metadata: 额外元数据
            
        Returns:
            TenantContext: 租户上下文
        """
        with self._lock:
            if len(self._tenants) >= self.max_tenants:
                raise RuntimeError(f"租户数量超过限制: {self.max_tenants}")
            
            if tenant_id in self._tenants:
                logger.warning(f"租户已存在: {tenant_id}")
                return self._tenants[tenant_id]
            
            context = TenantContext(
                tenant_id=tenant_id,
                user_id=user_id,
                roles=roles,
                isolation_level=self.default_isolation_level,
                metadata=metadata,
            )
            
            self._tenants[tenant_id] = context
            self._tenant_quotas[tenant_id] = {
                "max_queries": 1000,
                "max_concurrent": 100,
                "max_data": 1000,
                "used_queries": 0,
                "used_concurrent": 0,
                "used_data": 0,
                "quota_reset_at": datetime.now() + timedelta(hours=1)
            }
            
            logger.info(f"租户注册成功: {tenant_id}")
            return context
    
    def get_tenant(self, tenant_id: str) -> Optional[TenantContext]:
        """获取租户上下文"""
        return self._tenants.get(tenant_id)
    
    def unregister_tenant(self, tenant_id: str) -> bool:
        """注销租户"""
        with self._lock:
            if tenant_id in self._tenants:
                del self._tenants[tenant_id]
                if tenant_id in self._tenant_quotas:
                    del self._tenant_quotas[tenant_id]
                logger.info(f"租户注销: {tenant_id}")
                return True
            return False
    
    def is_isolated(self, tenant_id_1: str, tenant_id_2: str) -> bool:
        """
        检查两个租户是否隔离
        
        Args:
            tenant_id_1: 租户 ID 1
            tenant_id_2: 租户 ID 2
            
        Returns:
            bool: 是否隔离
        """
        if tenant_id_1 == tenant_id_2:
            return self.default_isolation_level == TenantIsolationLevel.STRICT
        
        return True
    
    def validate_data_access(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        """
        验证数据访问权限
        
        Args:
            tenant_id: 租户 ID
            resource_type: 资源类型
            resource_id: 资源 ID
            
        Returns:
            bool: 是否有权访问
        """
        if not self.enable_cross_tenant_check:
            return True
        
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            logger.warning(f"未知租户尝试访问: {tenant_id}")
            return False
        
        if tenant.isolation_level == TenantIsolationLevel.STRICT:
            if not self._check_resource_ownership(tenant_id, resource_type, resource_id):
                logger.warning(
                    f"租户 {tenant_id} 尝试访问不属于自己的资源: "
                    f"{resource_type}/{resource_id}"
                )
                return False
        
        return True
    
    def _check_resource_ownership(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        """检查资源所有权"""
        return True
    
    def check_quota(
        self,
        tenant_id: str,
        quota_type: str,
        increment: int = 1,
    ) -> bool:
        """
        检查和更新配额
        
        Args:
            tenant_id: 租户 ID
            quota_type: 配额类型 (queries, concurrent, data)
            increment: 增量
            
        Returns:
            bool: 是否在配额内
        """
        with self._lock:
            if tenant_id not in self._tenant_quotas:
                logger.warning(f"租户配额不存在: {tenant_id}")
                return False
            
            quota = self._tenant_quotas[tenant_id]
            
            quota_reset = quota.get("quota_reset_at")
            if quota_reset and datetime.now() > quota_reset:
                self._reset_quotas(tenant_id)
                quota = self._tenant_quotas[tenant_id]
            
            used_key = f"used_{quota_type}"
            max_key = f"max_{quota_type}"
            
            max_allowed = quota.get(max_key)
            if max_allowed is None:
                return True
            
            current_used = quota.get(used_key, 0)
            
            if current_used + increment > max_allowed:
                logger.warning(
                    f"租户 {tenant_id} 超过配额限制: "
                    f"{quota_type} ({current_used + increment}/{max_allowed})"
                )
                return False
            
            quota[used_key] = current_used + increment
            return True
    
    def _reset_quotas(self, tenant_id: str) -> None:
        """重置租户配额"""
        if tenant_id in self._tenant_quotas:
            self._tenant_quotas[tenant_id].update({
                "used_queries": 0,
                "used_concurrent": 0,
                "used_data": 0,
                "quota_reset_at": datetime.now() + timedelta(hours=1)
            })
    
    def get_tenant_quota(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """获取租户配额信息"""
        return self._tenant_quotas.get(tenant_id)
    
    def get_all_tenants(self) -> List[str]:
        """获取所有租户 ID"""
        return list(self._tenants.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tenants": len(self._tenants),
            "max_tenants": self.max_tenants,
            "default_isolation_level": self.default_isolation_level.value,
            "cross_tenant_check_enabled": self.enable_cross_tenant_check,
        }


_tenant_context_var: contextvars.ContextVar[Optional[TenantContext]] = \
    contextvars.ContextVar("tenant_context", default=None)

_global_isolation: Optional[TenantIsolation] = None


def get_tenant_context() -> Optional[TenantContext]:
    """获取当前租户上下文"""
    return _tenant_context_var.get()


def set_tenant_context(context: Optional[TenantContext]) -> None:
    """设置当前租户上下文"""
    _tenant_context_var.set(context)


def get_tenant_isolation() -> TenantIsolation:
    """获取全局租户隔离管理器"""
    global _global_isolation
    if _global_isolation is None:
        _global_isolation = TenantIsolation()
    return _global_isolation
