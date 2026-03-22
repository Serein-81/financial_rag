"""
租户安全服务
负责租户隔离验证、审计日志记录等安全功能
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from app.db.session import AsyncSessionLocal
from app.models.tenant_audit_log import TenantAuditLog
from app.middleware.tenant_middleware import get_current_tenant_id, get_current_user_id, set_tenant_context_for_db
import logging
import json
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
        
        # 检查是否设置了租户上下文
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
        
        # 检查租户匹配
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
        
        # 记录正常访问（调试级别）
        logger.debug(f"租户访问验证通过: {current_tenant}, 操作: {operation}, 资源: {resource_type}")
        
        return True
    
    @staticmethod
    async def log_security_event(
        event_type: str,
        details: Dict[str, Any],
        severity: str = "info",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        记录安全事件到审计日志
        
        Args:
            event_type: 事件类型
            details: 事件详情
            severity: 严重程度 (info/warning/high/critical)
            tenant_id: 租户ID（可选，默认从上下文获取）
            user_id: 用户ID（可选，默认从上下文获取）
        """
        try:
            # 获取上下文信息
            if not tenant_id:
                tenant_id = get_current_tenant_id() or "UNKNOWN"
            if not user_id:
                user_id = get_current_user_id()
            
            # 创建审计日志
            async with AsyncSessionLocal() as session:
                # 设置租户上下文（使用系统权限）
                # 🔥 修复：SET LOCAL 不支持参数化查询，使用字符串格式化
                safe_tenant_id = tenant_id.replace("'", "''")  # 防止 SQL 注入
                await session.execute(
                    text(f"SET LOCAL app.current_tenant_id = '{safe_tenant_id}'")
                )
                
                audit_log = TenantAuditLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=event_type,
                    resource_type="security_audit",  # 🔥 修复：使用 resource_type 而不是 table_name
                    access_result="logged",  # 🔥 添加必需字段
                    details={
                        "event_type": event_type,
                        "severity": severity,
                        "timestamp": datetime.utcnow().isoformat(),
                        **details
                    }
                )
                
                session.add(audit_log)
                await session.commit()
                
                # 根据严重程度记录日志
                if severity == "critical":
                    logger.critical(f"安全事件: {event_type}, 详情: {details}")
                elif severity == "high":
                    logger.error(f"安全事件: {event_type}, 详情: {details}")
                elif severity == "warning":
                    logger.warning(f"安全事件: {event_type}, 详情: {details}")
                else:
                    logger.info(f"安全事件: {event_type}, 详情: {details}")
                
        except Exception as e:
            logger.error(f"记录安全事件失败: {e}")
    
    @staticmethod
    async def get_tenant_security_stats(
        tenant_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        获取租户安全统计信息
        
        Args:
            tenant_id: 租户ID
            days: 统计天数
        
        Returns:
            Dict: 安全统计信息
        """
        try:
            async with AsyncSessionLocal() as session:
                # 设置租户上下文
                await set_tenant_context_for_db(session, tenant_id)
                
                # 查询安全事件统计
                query = text("""
                    SELECT 
                        action,
                        COUNT(*) as count,
                        MAX(created_at) as last_occurrence
                    FROM tenant_audit_logs 
                    WHERE tenant_id = :tenant_id 
                        AND created_at >= NOW() - INTERVAL ':days days'
                        AND resource_type = 'security_audit'
                    GROUP BY action
                    ORDER BY count DESC
                """)
                
                result = await session.execute(query, {
                    "tenant_id": tenant_id,
                    "days": days
                })
                
                events = []
                for row in result:
                    events.append({
                        "event_type": row.action,
                        "count": row.count,
                        "last_occurrence": row.last_occurrence.isoformat() if row.last_occurrence else None
                    })
                
                # 查询总体统计
                total_query = text("""
                    SELECT COUNT(*) as total_events
                    FROM tenant_audit_logs 
                    WHERE tenant_id = :tenant_id 
                        AND created_at >= NOW() - INTERVAL ':days days'
                        AND resource_type = 'security_audit'
                """)
                
                total_result = await session.execute(total_query, {
                    "tenant_id": tenant_id,
                    "days": days
                })
                
                total_events = total_result.scalar() or 0
                
                return {
                    "tenant_id": tenant_id,
                    "period_days": days,
                    "total_events": total_events,
                    "events_by_type": events,
                    "generated_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"获取租户安全统计失败: {e}")
            return {
                "tenant_id": tenant_id,
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def check_tenant_isolation_health() -> Dict[str, Any]:
        """
        检查租户隔离机制健康状态
        
        Returns:
            Dict: 健康检查结果
        """
        health_status = {
            "overall_status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            async with AsyncSessionLocal() as session:
                
                # 1. 检查 RLS 是否启用
                rls_check = text("""
                    SELECT 
                        schemaname,
                        tablename,
                        rowsecurity
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                        AND tablename IN ('users', 'knowledge_bases', 'documents', 'document_chunks')
                """)
                
                result = await session.execute(rls_check)
                rls_tables = []
                for row in result:
                    rls_tables.append({
                        "table": row.tablename,
                        "rls_enabled": row.rowsecurity
                    })
                
                health_status["checks"]["rls_status"] = {
                    "status": "pass" if all(t["rls_enabled"] for t in rls_tables) else "fail",
                    "tables": rls_tables
                }
                
                # 2. 检查租户隔离策略
                policy_check = text("""
                    SELECT 
                        schemaname,
                        tablename,
                        policyname,
                        cmd
                    FROM pg_policies 
                    WHERE schemaname = 'public'
                        AND policyname LIKE 'tenant_isolation_%'
                """)
                
                result = await session.execute(policy_check)
                policies = []
                for row in result:
                    policies.append({
                        "table": row.tablename,
                        "policy": row.policyname,
                        "command": row.cmd
                    })
                
                health_status["checks"]["isolation_policies"] = {
                    "status": "pass" if len(policies) > 0 else "fail",
                    "policies": policies
                }
                
                # 3. 检查审计触发器
                trigger_check = text("""
                    SELECT 
                        event_object_table,
                        trigger_name,
                        action_timing,
                        event_manipulation
                    FROM information_schema.triggers 
                    WHERE trigger_schema = 'public'
                        AND trigger_name LIKE 'audit_tenant_access_%'
                """)
                
                result = await session.execute(trigger_check)
                triggers = []
                for row in result:
                    triggers.append({
                        "table": row.event_object_table,
                        "trigger": row.trigger_name,
                        "timing": row.action_timing,
                        "events": row.event_manipulation
                    })
                
                health_status["checks"]["audit_triggers"] = {
                    "status": "pass" if len(triggers) > 0 else "fail",
                    "triggers": triggers
                }
                
                # 4. 检查最近的安全事件
                recent_events_check = text("""
                    SELECT 
                        action,
                        COUNT(*) as count
                    FROM tenant_audit_logs 
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                        AND details->>'severity' IN ('high', 'critical')
                    GROUP BY action
                """)
                
                result = await session.execute(recent_events_check)
                recent_events = []
                for row in result:
                    recent_events.append({
                        "event_type": row.action,
                        "count": row.count
                    })
                
                health_status["checks"]["recent_security_events"] = {
                    "status": "warning" if len(recent_events) > 0 else "pass",
                    "events": recent_events
                }
                
                # 确定总体状态
                check_statuses = [check["status"] for check in health_status["checks"].values()]
                if "fail" in check_statuses:
                    health_status["overall_status"] = "unhealthy"
                elif "warning" in check_statuses:
                    health_status["overall_status"] = "warning"
                
        except Exception as e:
            logger.error(f"租户隔离健康检查失败: {e}")
            health_status["overall_status"] = "error"
            health_status["error"] = str(e)
        
        return health_status


# 创建全局实例
tenant_security = TenantSecurityService()