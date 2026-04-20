"""
文档 Repository

提供文档的数据库操作接口，自动处理租户隔离

使用方式：
    from app.repositories.document import DocumentRepository
    
    async def get_document(db: AsyncSession, doc_id: str, tenant_id: str):
        repo = DocumentRepository(db)
        return await repo.get_by_id(doc_id, tenant_id=tenant_id)
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.document import Document
import logging

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository[Document]):
    """
    文档 Repository
    
    提供文档的 CRUD 操作，自动处理租户隔离
    
    继承自 BaseRepository，提供：
    - get(): 根据 ID 获取文档
    - list(): 获取文档列表
    - create(): 创建文档
    - update(): 更新文档
    - delete(): 删除文档
    
    额外提供：
    - get_by_filename(): 根据文件名获取
    - get_by_kb_id(): 根据知识库 ID 获取
    - get_by_user(): 根据用户获取
    - get_public_docs(): 获取公开文档
    """
    
    def __init__(self, session: AsyncSession):
        """初始化文档 Repository"""
        super().__init__(session, Document)
    
    async def get_by_id(
        self,
        doc_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Document]:
        """
        根据 ID 获取文档
        
        Args:
            doc_id: 文档 ID
            tenant_id: 租户 ID
            
        Returns:
            Document 或 None
        """
        return await self.get(doc_id, tenant_id=tenant_id)
    
    async def get_by_filename(
        self,
        filename: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Document]:
        """
        根据文件名获取文档
        
        Args:
            filename: 文件名
            tenant_id: 租户 ID
            
        Returns:
            Document 或 None
        """
        return await self.get_by(
            tenant_id=tenant_id,
            filename=filename,
            raise_if_not_found=False
        )
    
    async def get_by_kb_id(
        self,
        kb_id: str,
        tenant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        visibility: Optional[str] = None
    ) -> List[Document]:
        """
        根据知识库 ID 获取文档列表
        
        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            skip: 跳过记录数
            limit: 返回记录数限制
            visibility: 可见性过滤（可选）
            
        Returns:
            Document 列表
        """
        filters = {'kb_id': kb_id}
        
        if visibility:
            filters['visibility'] = visibility
        
        return await self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            order_by='created_at',
            order_desc=True,
            **filters
        )
    
    async def get_by_user(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """
        根据用户获取文档列表
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            skip: 跳过记录数
            limit: 返回记录数限制
            
        Returns:
            Document 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )
    
    async def get_public_docs(
        self,
        tenant_id: Optional[str] = None,
        kb_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """
        获取公开文档
        
        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID（可选）
            skip: 跳过记录数
            limit: 返回记录数限制
            
        Returns:
            Document 列表
        """
        query = select(Document)
        
        tid = tenant_id or self.tenant_id
        query = query.where(
            and_(
                Document.tenant_id == tid,
                Document.visibility == 'public'
            )
        )
        
        if kb_id:
            query = query.where(Document.kb_id == kb_id)
        
        query = query.offset(skip).limit(limit).order_by(Document.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_private_docs(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """
        获取用户的私有文档
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            skip: 跳过记录数
            limit: 返回记录数限制
            
        Returns:
            Document 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            user_id=user_id,
            visibility='private',
            skip=skip,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )
    
    async def count_by_status(
        self,
        tenant_id: Optional[str] = None,
        kb_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        统计各状态的文档数量
        
        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID（可选）
            
        Returns:
            状态计数字典
        """
        tid = tenant_id or self.tenant_id
        
        query = select(
            Document.status,
            func.count(Document.id)
        ).where(Document.tenant_id == tid)
        
        if kb_id:
            query = query.where(Document.kb_id == kb_id)
        
        query = query.group_by(Document.status)
        
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.fetchall()}
    
    async def create_document(
        self,
        tenant_id: str,
        kb_id: str,
        user_id: str,
        filename: str,
        file_path: str,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
        visibility: str = 'private',
        **kwargs
    ) -> Document:
        """
        创建文档
        
        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID
            user_id: 用户 ID
            filename: 文件名
            file_path: 文件路径
            file_type: 文件类型
            file_size: 文件大小
            visibility: 可见性
            **kwargs: 其他字段
            
        Returns:
            创建的 Document
        """
        data = {
            'tenant_id': tenant_id,
            'kb_id': kb_id,
            'user_id': user_id,
            'filename': filename,
            'file_path': file_path,
            'file_type': file_type,
            'file_size': file_size,
            'visibility': visibility,
            'status': 'pending',
            **kwargs
        }
        
        return await self.create(**data)
    
    async def update_status(
        self,
        doc_id: str,
        status: str,
        error_msg: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[Document]:
        """
        更新文档状态
        
        Args:
            doc_id: 文档 ID
            status: 新状态
            error_msg: 错误消息
            tenant_id: 租户 ID
            
        Returns:
            更新后的 Document
        """
        data = {'status': status}
        
        if error_msg:
            data['error_msg'] = error_msg
        
        return await self.update(doc_id, tenant_id=tenant_id, **data)
    
    async def update_processing(
        self,
        doc_id: str,
        status: str = 'processing',
        meta_info: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[Document]:
        """
        更新文档处理信息
        
        Args:
            doc_id: 文档 ID
            status: 处理状态
            meta_info: 元信息
            tenant_id: 租户 ID
            
        Returns:
            更新后的 Document
        """
        data = {'status': status}
        
        if meta_info:
            data['meta_info'] = meta_info
        
        return await self.update(doc_id, tenant_id=tenant_id, **data)
    
    async def mark_completed(
        self,
        doc_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Document]:
        """
        标记文档为已完成
        
        Args:
            doc_id: 文档 ID
            tenant_id: 租户 ID
            
        Returns:
            更新后的 Document
        """
        return await self.update(
            doc_id,
            tenant_id=tenant_id,
            status='completed'
        )
