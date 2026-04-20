"""
税务报告 Repository

提供税务报告的数据库操作接口，自动处理租户隔离

使用方式：
    from app.repositories.tax_report import TaxReportRepository
    
    async def get_report(db: AsyncSession, report_id: str, tenant_id: str):
        repo = TaxReportRepository(db)
        return await repo.get_by_id(report_id, tenant_id=tenant_id)
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.tax_report import TaxReport
import logging

logger = logging.getLogger(__name__)


class TaxReportRepository(BaseRepository[TaxReport]):
    """
    税务报告 Repository
    
    提供税务报告的 CRUD 操作，自动处理租户隔离
    
    继承自 BaseRepository，提供：
    - get(): 根据 ID 获取报告
    - list(): 获取报告列表
    - create(): 创建报告
    - update(): 更新报告
    - delete(): 删除报告
    
    额外提供：
    - get_by_filename(): 根据文件名获取
    - find_duplicates(): 查找重复报告
    - get_by_status(): 根据状态获取
    """
    
    def __init__(self, session: AsyncSession):
        """初始化税务报告 Repository"""
        super().__init__(session, TaxReport)
    
    async def get_by_id(
        self,
        report_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[TaxReport]:
        """
        根据 ID 获取税务报告
        
        Args:
            report_id: 报告 ID
            tenant_id: 租户 ID
            
        Returns:
            TaxReport 或 None
        """
        return await self.get(report_id, tenant_id=tenant_id)
    
    async def get_by_filename(
        self,
        filename: str,
        tenant_id: Optional[str] = None
    ) -> Optional[TaxReport]:
        """
        根据文件名获取税务报告
        
        Args:
            filename: 文件名
            tenant_id: 租户 ID
            
        Returns:
            TaxReport 或 None
        """
        tid = tenant_id or self.tenant_id
        
        query = select(TaxReport).where(
            and_(
                TaxReport.tenant_id == tid,
                func.trim(TaxReport.original_filename) == func.trim(filename)
            )
        ).order_by(TaxReport.created_at.desc())
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def find_duplicates(
        self,
        tenant_id: str,
        filename: str,
        file_hash: Optional[str] = None
    ) -> Optional[TaxReport]:
        """
        查找重复的税务报告
        
        Args:
            tenant_id: 租户 ID
            filename: 原始文件名
            file_hash: 文件哈希（可选）
            
        Returns:
            重复的报告或 None
        """
        normalized_filename = filename.strip()
        
        query = select(TaxReport).where(
            and_(
                TaxReport.tenant_id == tenant_id,
                func.trim(TaxReport.original_filename) == func.trim(normalized_filename)
            )
        ).order_by(TaxReport.created_at.desc())
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_status(
        self,
        status: str,
        tenant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TaxReport]:
        """
        根据状态获取税务报告列表
        
        Args:
            status: 报告状态
            tenant_id: 租户 ID
            skip: 跳过记录数
            limit: 返回记录数限制
            
        Returns:
            TaxReport 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )
    
    async def get_by_user(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TaxReport]:
        """
        根据用户获取税务报告列表
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            skip: 跳过记录数
            limit: 返回记录数限制
            
        Returns:
            TaxReport 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )
    
    async def count_by_status(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        统计各状态的报告数量
        
        Args:
            tenant_id: 租户 ID
            
        Returns:
            状态计数字典
        """
        tid = tenant_id or self.tenant_id
        
        query = select(
            TaxReport.status,
            func.count(TaxReport.id)
        ).where(
            TaxReport.tenant_id == tid
        ).group_by(TaxReport.status)
        
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.fetchall()}
    
    async def create_report(
        self,
        user_id: str,
        tenant_id: str,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size: int,
        minio_path: str,
        **kwargs
    ) -> TaxReport:
        """
        创建税务报告
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            filename: 文件名
            original_filename: 原始文件名
            file_type: 文件类型
            file_size: 文件大小
            minio_path: MinIO 存储路径
            **kwargs: 其他字段
            
        Returns:
            创建的 TaxReport
        """
        data = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'filename': filename,
            'original_filename': original_filename,
            'file_type': file_type,
            'file_size': file_size,
            'minio_path': minio_path,
            'status': 'pending',
            **kwargs
        }
        
        return await self.create(**data)
    
    async def update_status(
        self,
        report_id: str,
        status: str,
        message: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[TaxReport]:
        """
        更新报告状态
        
        Args:
            report_id: 报告 ID
            status: 新状态
            message: 状态消息
            tenant_id: 租户 ID
            
        Returns:
            更新后的 TaxReport
        """
        data = {'status': status}
        
        if message:
            data['processing_message'] = message
        
        if status == 'completed':
            from datetime import datetime
            data['completed_at'] = datetime.now()
        
        return await self.update(report_id, tenant_id=tenant_id, **data)
    
    async def update_processing_result(
        self,
        report_id: str,
        processing_result: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Optional[TaxReport]:
        """
        更新处理结果
        
        Args:
            report_id: 报告 ID
            processing_result: 处理结果
            tenant_id: 租户 ID
            
        Returns:
            更新后的 TaxReport
        """
        return await self.update(
            report_id,
            tenant_id=tenant_id,
            processing_result=processing_result
        )
    
    async def update_risk_assessment(
        self,
        report_id: str,
        confidence_score: Optional[str] = None,
        risk_score: Optional[int] = None,
        risk_level: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[TaxReport]:
        """
        更新风险评估
        
        Args:
            report_id: 报告 ID
            confidence_score: 置信度
            risk_score: 风险评分
            risk_level: 风险等级
            tenant_id: 租户 ID
            
        Returns:
            更新后的 TaxReport
        """
        data = {}
        
        if confidence_score is not None:
            data['confidence_score'] = confidence_score
        if risk_score is not None:
            data['risk_score'] = risk_score
        if risk_level is not None:
            data['risk_level'] = risk_level
        
        if data:
            return await self.update(report_id, tenant_id=tenant_id, **data)
        
        return await self.get(report_id, tenant_id=tenant_id)
