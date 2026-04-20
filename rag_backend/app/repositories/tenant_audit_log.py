"""
租户审计日志 Repository

提供租户审计日志的数据库操作接口，自动处理租户隔离

使用方式：
    from app.repositories.tenant_audit_log import TenantAuditLogRepository
    
    async def create_audit_log(db: AsyncSession):
        repo = TenantAuditLogRepository(db)
        await repo.create_audit_log(
            tenant_id="tenant_123",
            user_id="user_456",
            action="document_view",
            resource_type="document",
            details={"doc_id": "123"}
        )
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.tenant_audit_log import TenantAuditLog
import logging

logger = logging.getLogger(__name__)


class TenantAuditLogRepository(BaseRepository[TenantAuditLog]):
    """
    租户审计日志 Repository
    
    提供租户审计日志的 CRUD 操作，自动处理租户隔离
    
    继承自 BaseRepository，提供：
    - get(): 根据 ID 获取日志
    - list(): 获取日志列表
    - create(): 创建日志
    
    额外提供：
    - create_audit_log(): 创建审计日志
    - get_by_event_type(): 根据事件类型获取
    - get_recent_logs(): 获取最近日志
    """
    
    def __init__(self, session: AsyncSession):
        """初始化租户审计日志 Repository"""
        super().__init__(session, TenantAuditLog)
    
    async def create_audit_log(
        self,
        tenant_id: str,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        details: Optional[Dict[str, Any]] = None,
        access_result: str = "success",
        severity: str = "info"
    ) -> TenantAuditLog:
        """
        创建审计日志
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID
            action: 操作类型
            resource_type: 资源类型
            details: 详细信息
            access_result: 访问结果
            severity: 严重程度
            
        Returns:
            创建的审计日志
        """
        data = {
            'tenant_id': tenant_id,
            'user_id': user_id,
            'action': action,
            'resource_type': resource_type,
            'details': details or {},
        }
        
        return await self.create(**data)
    
    async def get_by_event_type(
        self,
        action: str,
        tenant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TenantAuditLog]:
        """
        根据事件类型获取日志
        
        Args:
            action: 事件类型
            tenant_id: 租户ID
            skip: 跳过记录数
            limit: 返回记录数限制
            
        Returns:
            TenantAuditLog 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            action=action,
            skip=skip,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )
    
    async def get_recent_logs(
        self,
        tenant_id: Optional[str] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[TenantAuditLog]:
        """
        获取最近的日志
        
        Args:
            tenant_id: 租户ID
            hours: 最近几小时
            limit: 返回记录数限制
            
        Returns:
            TenantAuditLog 列表
        """
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(TenantAuditLog)
        
        tid = tenant_id or self.tenant_id
        
        if tid and hasattr(TenantAuditLog, 'tenant_id'):
            query = query.where(TenantAuditLog.tenant_id == tid)
        
        query = query.where(TenantAuditLog.created_at >= cutoff_time)
        query = query.order_by(TenantAuditLog.created_at.desc())
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def count_by_severity(
        self,
        tenant_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, int]:
        """
        统计各严重程度的日志数量
        
        Args:
            tenant_id: 租户ID
            days: 统计天数
            
        Returns:
            严重程度计数字典
        """
        from datetime import datetime, timedelta
        
        tid = tenant_id or self.tenant_id
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            TenantAuditLog.severity,
            func.count(TenantAuditLog.id)
        ).where(TenantAuditLog.created_at >= cutoff_time)
        
        if tid and hasattr(TenantAuditLog, 'tenant_id'):
            query = query.where(TenantAuditLog.tenant_id == tid)
        
        query = query.group_by(TenantAuditLog.severity)
        
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.fetchall()}
