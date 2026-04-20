"""
Repository 模式基类

提供标准化的数据库操作接口，自动处理租户隔离

核心功能：
1. 自动 tenant_id 过滤
2. 统一的 CRUD 接口
3. 类型安全的查询构建

使用方式：
    from app.repositories.base import BaseRepository
    from app.models import TaxReport
    
    class TaxReportRepository(BaseRepository[TaxReport]):
        def __init__(self, session: AsyncSession):
            super().__init__(session, TaxReport)
        
        async def get_by_filename(self, filename: str):
            return await self.list(filename=filename)
    
    # 使用
    async def get_report(db: AsyncSession, report_id: str, tenant_id: str):
        repo = TaxReportRepository(db)
        return await repo.get(report_id, tenant_id=tenant_id)
"""

from typing import TypeVar, Generic, List, Optional, Type, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.sql import Select
from app.db.base import Base
from app.middleware.tenant_middleware import get_current_tenant_id
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T]):
    """
    基础 Repository 类
    
    所有数据访问类应继承此类
    自动实现租户隔离
    
    使用示例：
        class DocumentRepository(BaseRepository[Document]):
            def __init__(self, session: AsyncSession):
                super().__init__(session, Document)
    """
    
    def __init__(self, session: AsyncSession, model: Type[T]):
        """
        初始化 Repository
        
        Args:
            session: AsyncSession 实例
            model: SQLAlchemy 模型类
        """
        self.session = session
        self.model = model
        self._tenant_column = self._get_tenant_column()
    
    def _get_tenant_column(self):
        """
        获取模型的 tenant_id 列
        
        Returns:
            Column 对象或 None（如果模型没有 tenant_id）
        """
        if not hasattr(self.model, 'tenant_id'):
            return None
        return getattr(self.model, 'tenant_id')
    
    @property
    def tenant_id(self) -> str:
        """
        从上下文获取当前租户ID
        
        Returns:
            租户ID字符串
            
        Raises:
            ValueError: 如果没有设置租户上下文
        """
        tid = get_current_tenant_id()
        if not tid:
            raise ValueError(
                "Missing tenant context - tenant_id is required. "
                "Please ensure the request has a valid tenant context set."
            )
        return tid
    
    def _apply_tenant_filter(self, query: Select, tenant_id: Optional[str] = None) -> Select:
        """
        应用租户过滤
        
        Args:
            query: Select 查询对象
            tenant_id: 租户ID（可选，默认从上下文获取）
            
        Returns:
            添加了租户过滤的 Select 查询
        """
        tid = tenant_id or self.tenant_id
        
        if self._tenant_column and tid:
            return query.where(self._tenant_column == tid)
        
        return query
    
    async def get(
        self,
        id: Any,
        tenant_id: Optional[str] = None,
        raise_if_not_found: bool = True
    ) -> Optional[T]:
        """
        根据ID获取记录
        
        Args:
            id: 记录ID
            tenant_id: 租户ID（可选，默认从上下文获取）
            raise_if_not_found: 是否在未找到时抛出异常
            
        Returns:
            记录对象或 None
            
        Raises:
            ValueError: 如果 raise_if_not_found=True 且记录不存在
        """
        tid = tenant_id or self.tenant_id
        
        query = select(self.model).where(self.model.id == id)
        query = self._apply_tenant_filter(query, tid)
        
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        
        if not record and raise_if_not_found:
            raise ValueError(
                f"{self.model.__name__} with id={id} not found "
                f"for tenant_id={tid}"
            )
        
        return record
    
    async def get_by(
        self,
        tenant_id: Optional[str] = None,
        raise_if_not_found: bool = True,
        **filters
    ) -> Optional[T]:
        """
        根据指定条件获取单条记录
        
        Args:
            tenant_id: 租户ID（可选）
            raise_if_not_found: 是否在未找到时抛出异常
            **filters: 查询条件，如 name="test"
            
        Returns:
            记录对象或 None
        """
        tid = tenant_id or self.tenant_id
        
        query = select(self.model)
        query = self._apply_tenant_filter(query, tid)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                query = query.where(column == value)
        
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        
        if not record and raise_if_not_found:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
            raise ValueError(
                f"{self.model.__name__} with {filter_str} not found "
                f"for tenant_id={tid}"
            )
        
        return record
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[str] = None,
        order_by: Optional[str] = None,
        order_desc: bool = True,
        **filters
    ) -> List[T]:
        """
        获取记录列表
        
        Args:
            skip: 跳过记录数（分页）
            limit: 返回记录数限制（分页）
            tenant_id: 租户ID（可选）
            order_by: 排序字段名
            order_desc: 是否降序排列
            **filters: 查询条件
            
        Returns:
            记录列表
        """
        tid = tenant_id or self.tenant_id
        
        query = select(self.model)
        query = self._apply_tenant_filter(query, tid)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                if isinstance(value, (list, tuple)):
                    query = query.where(column.in_(value))
                else:
                    query = query.where(column == value)
        
        if order_by and hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
        
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def count(
        self,
        tenant_id: Optional[str] = None,
        **filters
    ) -> int:
        """
        获取记录总数
        
        Args:
            tenant_id: 租户ID（可选）
            **filters: 查询条件
            
        Returns:
            记录数量
        """
        tid = tenant_id or self.tenant_id
        
        query = select(func.count(self.model.id))
        query = self._apply_tenant_filter(query, tid)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                if isinstance(value, (list, tuple)):
                    query = query.where(column.in_(value))
                else:
                    query = query.where(column == value)
        
        result = await self.session.execute(query)
        return result.scalar()
    
    async def create(self, **data) -> T:
        """
        创建新记录
        
        Args:
            **data: 记录数据
            
        Returns:
            创建的记录对象
            
        Note:
            如果模型有 tenant_id 字段且 data 中未提供，
            会自动从上下文获取并设置
        """
        if self._tenant_column and 'tenant_id' not in data:
            data['tenant_id'] = self.tenant_id
        
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        
        logger.info(
            f"Created {self.model.__name__} id={instance.id} "
            f"tenant_id={getattr(instance, 'tenant_id', 'N/A')}"
        )
        return instance
    
    async def update(
        self,
        id: Any,
        tenant_id: Optional[str] = None,
        **data
    ) -> Optional[T]:
        """
        更新记录
        
        Args:
            id: 记录ID
            tenant_id: 租户ID（可选）
            **data: 更新数据
            
        Returns:
            更新后的记录对象
        """
        tid = tenant_id or self.tenant_id
        
        conditions = [self.model.id == id]
        if self._tenant_column and tid:
            conditions.append(self._tenant_column == tid)
        
        query = (
            update(self.model)
            .where(and_(*conditions))
            .values(**data)
            .returning(self.model)
        )
        
        result = await self.session.execute(query)
        await self.session.commit()
        
        updated = result.scalar_one_or_none()
        if updated:
            logger.info(
                f"Updated {self.model.__name__} id={id} "
                f"tenant_id={tid}"
            )
        
        return updated
    
    async def delete(
        self,
        id: Any,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        删除记录
        
        Args:
            id: 记录ID
            tenant_id: 租户ID（可选）
            
        Returns:
            是否删除成功
        """
        tid = tenant_id or self.tenant_id
        
        conditions = [self.model.id == id]
        if self._tenant_column and tid:
            conditions.append(self._tenant_column == tid)
        
        query = delete(self.model).where(and_(*conditions))
        result = await self.session.execute(query)
        await self.session.commit()
        
        deleted = result.rowcount > 0
        if deleted:
            logger.info(
                f"Deleted {self.model.__name__} id={id} "
                f"tenant_id={tid}"
            )
        
        return deleted
    
    async def exists(
        self,
        id: Any,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        检查记录是否存在
        
        Args:
            id: 记录ID
            tenant_id: 租户ID（可选）
            
        Returns:
            记录是否存在
        """
        tid = tenant_id or self.tenant_id
        
        query = select(func.count(self.model.id)).where(self.model.id == id)
        query = self._apply_tenant_filter(query, tid)
        
        result = await self.session.execute(query)
        return result.scalar() > 0
    
    async def exists_by(
        self,
        tenant_id: Optional[str] = None,
        **filters
    ) -> bool:
        """
        根据条件检查记录是否存在
        
        Args:
            tenant_id: 租户ID（可选）
            **filters: 查询条件
            
        Returns:
            记录是否存在
        """
        tid = tenant_id or self.tenant_id
        
        query = select(func.count(self.model.id))
        query = self._apply_tenant_filter(query, tid)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                query = query.where(column == value)
        
        result = await self.session.execute(query)
        return result.scalar() > 0
    
    async def bulk_create(
        self,
        records: List[Dict[str, Any]]
    ) -> List[T]:
        """
        批量创建记录
        
        Args:
            records: 记录数据列表
            
        Returns:
            创建的记录列表
        """
        if self._tenant_column:
            for record in records:
                if 'tenant_id' not in record:
                    record['tenant_id'] = self.tenant_id
        
        instances = [self.model(**data) for data in records]
        self.session.add_all(instances)
        await self.session.commit()
        
        for instance in instances:
            await self.session.refresh(instance)
        
        logger.info(
            f"Bulk created {len(instances)} {self.model.__name__} records "
            f"for tenant_id={self.tenant_id}"
        )
        
        return instances
    
    async def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        tenant_id: Optional[str] = None,
        **filters
    ) -> Dict[str, Any]:
        """
        分页查询
        
        Args:
            page: 页码（从1开始）
            page_size: 每页记录数
            tenant_id: 租户ID（可选）
            **filters: 查询条件
            
        Returns:
            包含 items, total, page, page_size, total_pages 的字典
        """
        tid = tenant_id or self.tenant_id
        
        total = await self.count(tid, **filters)
        
        skip = (page - 1) * page_size
        items = await self.list(
            skip=skip,
            limit=page_size,
            tenant_id=tid,
            **filters
        )
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
