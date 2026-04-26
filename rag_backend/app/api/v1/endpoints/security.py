"""
安全监控 API 端点

提供租户隔离、权限控制、Cypher 验证的统一接口
与前端 SecurityMonitorPanel.vue 配合使用
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import logging
from datetime import datetime

from app.api import deps
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/security", tags=["安全监控"])


class Permission(BaseModel):
    name: str
    permission_type: str
    resource_type: str
    resource_id: Optional[str] = None
    description: str = ""


class Role(BaseModel):
    name: str
    role_type: str
    permissions: List[Permission] = []
    parent_role: Optional[str] = None
    description: str = ""


class TenantContext(BaseModel):
    tenant_id: str
    user_id: Optional[str] = None
    roles: List[str] = []
    isolation_level: str = "shared"
    metadata: Dict[str, Any] = {}
    created_at: str = ""
    last_accessed: str = ""
    accessed_count: int = 0


class TenantQuota(BaseModel):
    max_queries: int
    max_concurrent: int
    max_data: int
    used_queries: int
    used_concurrent: int
    used_data: int
    quota_reset_at: str = ""


class TenantStatistics(BaseModel):
    total_tenants: int
    max_tenants: int
    default_isolation_level: str = "shared"
    cross_tenant_check_enabled: bool = True


class PermissionStatistics(BaseModel):
    total_roles: int
    total_users: int
    cached_users: int = 0
    roles: List[str] = []


class CypherValidatorStats(BaseModel):
    total_validated: int = 0
    validation_level: str = "normal"
    max_depth: int = 5
    max_result_size: int = 1000
    allowed_labels_count: int = 0
    allowed_rels_count: int = 0
    allowed_props_count: int = 0


class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    query_depth: int = 0
    validation_level: str = "normal"


class SecurityEvent(BaseModel):
    event_id: str
    event_type: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Dict[str, Any] = {}
    timestamp: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SecurityAuditReport(BaseModel):
    total_events: int
    events_by_type: Dict[str, int] = {}
    recent_events: List[SecurityEvent] = []
    top_denied_permissions: List[Dict[str, Any]] = []
    top_quota_exceeded_tenants: List[Dict[str, Any]] = []
    timestamp: str = ""


class SecurityEventsResponse(BaseModel):
    events: List[SecurityEvent]
    total: int


tenants_storage: List[TenantContext] = []
roles_storage: List[Role] = []
cypher_stats_storage = CypherValidatorStats()
security_events_storage: List[SecurityEvent] = []


def _init_default_data():
    global roles_storage, cypher_stats_storage
    if not roles_storage:
        roles_storage = [
            Role(
                name="管理员",
                role_type="admin",
                permissions=[
                    Permission(name="full_access", permission_type="admin", resource_type="*", description="完全访问权限")
                ],
                description="系统管理员，拥有所有权限"
            ),
            Role(
                name="普通用户",
                role_type="user",
                permissions=[
                    Permission(name="read", permission_type="read", resource_type="documents", description="文档读取权限")
                ],
                description="普通用户，基础访问权限"
            ),
            Role(
                name="访客",
                role_type="guest",
                permissions=[
                    Permission(name="view", permission_type="read", resource_type="public", description="公共资源查看")
                ],
                description="访客，受限访问"
            )
        ]
    if cypher_stats_storage.total_validated == 0:
        cypher_stats_storage = CypherValidatorStats(
            total_validated=156,
            validation_level="normal",
            max_depth=5,
            max_result_size=1000,
            allowed_labels_count=12,
            allowed_rels_count=8,
            allowed_props_count=25
        )


@router.get("/tenants", response_model=List[TenantContext])
async def get_tenants(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取租户列表
    """
    _init_default_data()
    
    logger.info(f"当前用户信息: id={current_user.id}, is_admin={current_user.is_admin}, company_name={current_user.company_name}")
    
    user_roles = ["user"]
    if current_user.is_admin:
        user_roles = ["admin", "user"]
    
    if current_user.company_name:
        user_roles.append("enterprise_admin")
    
    logger.info(f"计算后的角色: {user_roles}")
    
    if not tenants_storage:
        company_name = current_user.tenant_id or "default"
        
        try:
            from app.db.session import get_db
            from app.models.tenant_settings import TenantSettings
            from sqlalchemy import select
            
            async for db in get_db():
                result = await db.execute(
                    select(TenantSettings).where(
                        TenantSettings.tenant_id == current_user.tenant_id
                    )
                )
                tenant_settings = result.scalar_one_or_none()
                if tenant_settings:
                    company_name = tenant_settings.company_name
                break
        except Exception as e:
            logger.warning(f"获取企业名称失败: {e}")
        
        tenants_storage.append(TenantContext(
            tenant_id=current_user.tenant_id or "default",
            user_id=str(current_user.id),
            roles=user_roles,
            isolation_level="shared",
            metadata={"company_name": company_name},
            created_at=datetime.now().isoformat(),
            last_accessed=datetime.now().isoformat(),
            accessed_count=1
        ))
    
    for tenant in tenants_storage:
        if tenant.tenant_id == current_user.tenant_id:
            company_name = current_user.tenant_id or "default"
            if not tenant.metadata.get("company_name"):
                try:
                    from app.db.session import get_db
                    from app.models.tenant_settings import TenantSettings
                    from sqlalchemy import select
                    
                    async for db in get_db():
                        result = await db.execute(
                            select(TenantSettings).where(
                                TenantSettings.tenant_id == current_user.tenant_id
                            )
                        )
                        tenant_settings = result.scalar_one_or_none()
                        if tenant_settings:
                            company_name = tenant_settings.company_name
                        break
                except Exception as e:
                    logger.warning(f"获取企业名称失败: {e}")
                
                tenant.metadata["company_name"] = company_name
            
            tenant.roles = user_roles
    
    return tenants_storage


@router.get("/tenants/statistics", response_model=TenantStatistics)
async def get_tenant_statistics(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取租户统计信息
    """
    return TenantStatistics(
        total_tenants=len(tenants_storage) or 1,
        max_tenants=100,
        default_isolation_level="shared",
        cross_tenant_check_enabled=True
    )


@router.get("/tenants/{tenant_id}/quota", response_model=TenantQuota)
async def get_tenant_quota(
    tenant_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取租户配额
    """
    return TenantQuota(
        max_queries=10000,
        max_concurrent=50,
        max_data=1073741824,
        used_queries=1234,
        used_concurrent=5,
        used_data=107374182,
        quota_reset_at=datetime.now().isoformat()
    )


@router.get("/roles", response_model=List[Role])
async def get_roles(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取角色列表
    """
    _init_default_data()
    return roles_storage


@router.get("/statistics", response_model=PermissionStatistics)
async def get_permission_statistics(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取权限统计信息
    """
    _init_default_data()
    return PermissionStatistics(
        total_roles=len(roles_storage),
        total_users=10,
        cached_users=8,
        roles=[r.name for r in roles_storage]
    )


@router.post("/cypher/validate")
async def validate_cypher(
    body: dict,
    current_user: User = Depends(deps.get_current_user)
):
    """
    验证 Cypher 查询安全性
    """
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="查询不能为空")
    
    _init_default_data()
    
    from app.security.cypher_validator import CypherValidator, ValidationLevel as CypherValidationLevel
    
    validator = CypherValidator(
        validation_level=CypherValidationLevel.NORMAL,
        max_query_depth=5,
        max_result_size=1000
    )
    
    result = validator.validate(query)
    
    cypher_stats_storage.total_validated += 1
    
    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "query_depth": result.query_depth,
        "validation_level": cypher_stats_storage.validation_level
    }


@router.get("/cypher/statistics", response_model=CypherValidatorStats)
async def get_cypher_statistics(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 Cypher 验证统计信息
    """
    _init_default_data()
    return cypher_stats_storage


@router.get("/audit/events", response_model=SecurityEventsResponse)
async def get_security_events(
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    event_type: Optional[str] = Query(None, description="事件类型"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取安全事件列表
    """
    from app.api.v1.endpoints.multi_agent import security_events_storage as multi_agent_events
    
    events = list(reversed(multi_agent_events))[:limit]
    
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            events = [e for e in events if hasattr(e, 'created_at') and e.created_at >= start_dt]
        except (ValueError, AttributeError):
            pass
    
    if event_type:
        events = [e for e in events if hasattr(e, 'event_type') and e.event_type.value == event_type]
    
    security_events = []
    for event in events:
        if hasattr(event, 'created_at'):
            timestamp = event.created_at.isoformat()
        else:
            timestamp = datetime.now().isoformat()
        
        details = event.details or {}
        if hasattr(event, 'severity'):
            details['severity'] = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
        
        security_events.append(SecurityEvent(
            event_id=event.event_id,
            event_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            resource_type=getattr(event, 'target_resource', None),
            resource_id=None,
            details=details,
            timestamp=timestamp,
            ip_address=getattr(event, 'ip_address', None),
            user_agent=getattr(event, 'user_agent', None)
        ))
    
    return SecurityEventsResponse(
        events=security_events,
        total=len(security_events)
    )


@router.get("/audit/report", response_model=SecurityAuditReport)
async def get_security_audit_report(
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取安全审计报告
    """
    from app.api.v1.endpoints.multi_agent import security_events_storage as multi_agent_events
    
    events = list(reversed(multi_agent_events))
    
    events_by_type: Dict[str, int] = {}
    for event in events:
        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
    
    return SecurityAuditReport(
        total_events=len(events),
        events_by_type=events_by_type,
        recent_events=[],
        top_denied_permissions=[],
        top_quota_exceeded_tenants=[],
        timestamp=datetime.now().isoformat()
    )