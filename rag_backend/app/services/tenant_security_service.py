"""
租户安全服务

负责租户隔离验证、审计日志记录等安全功能

PgBouncer Transaction 模式改造：
- 使用 Repository 层替代直接的 AsyncSessionLocal 调用
- 移除 SET LOCAL 依赖
- 租户隔离通过显式传递 tenant_id 实现
"""

from typing import Optional, Dict, Any
from app.repositories.tenant_audit_log import TenantAuditLogRepository
from app.middleware.tenant_middleware import get_current_tenant_id, get_current_user_id
from app.db.session import AsyncSessionLocal
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TenantSecurityService:
    """租户安全服务"""
    
    @staticmethod
    async def validate_tenant_access(
        target_tenant_id: str,
        operation: str = "read",
        resource_type: str = "data"
    ) -> bool:
        """
        验证租户访问权限
        
        Args:
            target_tenant_id: 目标租户ID
            operation: 操作类型 (read/write/delete)
            resource_type: 资源类型 (data/file/api)
        
        Returns:
            bool: 是否允许访问
        
        Raises:
            PermissionError: 跨租户访问被拒绝
        """
        current_tenant = get_current_tenant_id()
        current_user = get_current_user_id()
        
        if not current_tenant:
            await TenantSecurityService.log_security_event(
                event_type="missing_tenant_context",
                details={
                    "operation": operation,
                    "resource_type": resource_type,
                    "target_tenant": target_tenant_id,
                    "user_id": current_user
                },
                severity="high"
            )
            raise PermissionError("Missing tenant context")
        
        if current_tenant != target_tenant_id:
            await TenantSecurityService.log_security_event(
                event_type="cross_tenant_access_attempt",
                details={
                    "current_tenant": current_tenant,
                    "target_tenant": target_tenant_id,
                    "operation": operation,
                    "resource_type": resource_type,
                    "user_id": current_user
                },
                severity="critical"
            )
            raise PermissionError(f"Cross-tenant access denied: {current_tenant} -> {target_tenant_id}")
        
        logger.debug(f"租户访问验证通过: {current_tenant}, 操作: {operation}, 资源: {resource_type}")
        
        return True
    
    @staticmethod
    async def log_security_event(
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> None:
        """
        记录安全事件到审计日志
        
        Args:
            event_type: 事件类型
            details: 事件详情
            severity: 严重程度 (info/warning/high/critical)
            user_id: 用户ID（可选，默认从上下文获取）
            tenant_id: 租户ID（可选，默认从上下文获取）
        """
        try:
            _user_id = user_id or get_current_user_id()
            _tenant_id = tenant_id or get_current_tenant_id()
            
            if details is None:
                details = {}
            
            details["event_type"] = event_type
            details["severity"] = severity
            details["timestamp"] = datetime.now().isoformat()
            
            logger.info(
                f"安全事件: type={event_type}, severity={severity}, "
                f"tenant={_tenant_id}, user={_user_id}, details={details}"
            )
            
            try:
                async with AsyncSessionLocal() as session:
                    repository = TenantAuditLogRepository(session)
                    await repository.create(
                        tenant_id=_tenant_id or "system",
                        user_id=_user_id or "system",
                        action=event_type,
                        resource_type="security_event",
                        resource_id="",
                        details=details,
                        ip_address=details.get("ip_address"),
                        user_agent=details.get("user_agent")
                    )
            except Exception as repo_error:
                logger.warning(f"记录审计日志失败（不影响主流程）: {repo_error}")
                
        except (ValueError, KeyError) as e:
            logger.error(f"记录安全事件数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"记录安全事件IO错误: {e}")
        except Exception as e:
            logger.error(f"记录安全事件失败: {e}")
    
    @staticmethod
    async def check_data_access_permission(
        resource_owner_tenant_id: str,
        resource_type: str = "data"
    ) -> bool:
        """
        检查数据访问权限
        
        Args:
            resource_owner_tenant_id: 资源所属租户ID
            resource_type: 资源类型
        
        Returns:
            bool: 是否有权限
        """
        return await TenantSecurityService.validate_tenant_access(
            target_tenant_id=resource_owner_tenant_id,
            operation="read",
            resource_type=resource_type
        )
    
    @staticmethod
    async def check_data_write_permission(
        resource_owner_tenant_id: str,
        resource_type: str = "data"
    ) -> bool:
        """
        检查数据写入权限
        
        Args:
            resource_owner_tenant_id: 资源所属租户ID
            resource_type: 资源类型
        
        Returns:
            bool: 是否有权限
        """
        return await TenantSecurityService.validate_tenant_access(
            target_tenant_id=resource_owner_tenant_id,
            operation="write",
            resource_type=resource_type
        )


tenant_security = TenantSecurityService()