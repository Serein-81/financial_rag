"""
文档检索工具集

提供企业文档检索能力，支持按切块ID读取、语义搜索和文档摘要获取
继承 ToolBase 基类，集成到统一工具管理系统
"""

import logging
from typing import List, Dict, Any, Optional
from .base import ToolBase

logger = logging.getLogger(__name__)


class DocumentChunkRetrievalTool(ToolBase):
    """
    文档切块检索工具
    
    提供 Agent 按需读取文档内容的工具，支持：
    1. 按切块ID读取内容
    2. 语义搜索文档章节
    3. 获取文档摘要信息
    4. 租户隔离过滤
    5. 数量限制控制
    """
    
    def __init__(self):
        super().__init__(
            name="document_chunk_retrieval",
            description="文档检索工具，支持按切块ID读取、语义搜索和文档摘要获取",
            timeout=30,
            tags=["文档", "检索", "知识库"]
        )
        self.chunk_service = None
        self.unified_retriever = None
    
    def _ensure_services(self):
        """延迟初始化服务，避免循环导入"""
        if self.chunk_service is None:
            from app.services.chunk_service import ChunkService
            self.chunk_service = ChunkService()
        if self.unified_retriever is None:
            from app.services.unified_retriever import UnifiedRetriever
            self.unified_retriever = UnifiedRetriever()
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行文档检索
        
        根据 action 参数执行不同的检索操作：
        - read_chunks: 按切块ID读取
        - search: 语义搜索
        - summary: 获取文档摘要
        """
        self._ensure_services()
        
        action = kwargs.get("action", "search")
        
        try:
            if action == "read_chunks":
                return await self._read_document_chunks(
                    kwargs.get("chunk_ids", []),
                    kwargs.get("tenant_id"),
                    kwargs.get("max_chunks", 10)
                )
            elif action == "search":
                return await self._search_document_sections(
                    kwargs.get("query"),
                    kwargs.get("tenant_id"),
                    kwargs.get("doc_ids"),
                    kwargs.get("max_chunks", 10)
                )
            elif action == "summary":
                return await self._get_document_summary(
                    kwargs.get("doc_id"),
                    kwargs.get("tenant_id")
                )
            else:
                return {
                    "error": f"不支持的操作类型: {action}",
                    "supported_actions": ["read_chunks", "search", "summary"]
                }
        except Exception as e:
            logger.error(f"文档检索失败: {str(e)}", exc_info=True)
            return {
                "error": f"文档检索失败: {str(e)}",
                "action": action
            }
    
    async def _read_document_chunks(
        self,
        chunk_ids: List[str],
        tenant_id: str,
        max_chunks: int = 10
    ) -> Dict[str, Any]:
        """
        按切块ID读取文档内容
        
        Args:
            chunk_ids: 切块ID列表
            tenant_id: 租户ID(用于隔离)
            max_chunks: 最大返回数量(默认10)
            
        Returns:
            {
                'chunks': [{'id': str, 'content': str, 'metadata': dict}],
                'total': int,
                'truncated': bool
            }
        """
        try:
            limited_ids = chunk_ids[:max_chunks]
            
            chunks = await self.chunk_service.get_chunks_by_ids(
                chunk_ids=limited_ids,
                tenant_id=tenant_id
            )
            
            result = {
                'chunks': [
                    {
                        'id': chunk.id,
                        'content': chunk.content,
                        'metadata': chunk.metadata
                    }
                    for chunk in chunks
                ],
                'total': len(chunks),
                'truncated': len(chunk_ids) > max_chunks
            }
            
            return result
            
        except Exception as e:
            logger.error(f"读取文档切块失败: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'chunks': [],
                'total': 0,
                'truncated': False
            }
    
    async def _search_document_sections(
        self,
        query: str,
        tenant_id: str,
        doc_ids: Optional[List[str]] = None,
        max_chunks: int = 10
    ) -> Dict[str, Any]:
        """
        语义搜索文档章节
        
        Args:
            query: 搜索查询
            tenant_id: 租户ID
            doc_ids: 限定文档ID列表(可选)
            max_chunks: 最大返回数量
            
        Returns:
            {
                'chunks': [{'id': str, 'content': str, 'score': float, 'metadata': dict}],
                'total': int
            }
        """
        try:
            filters = {'tenant_id': tenant_id}
            
            if doc_ids:
                filters['doc_id'] = {'$in': doc_ids}
            
            results = await self.unified_retriever.retrieve(
                query=query,
                filters=filters,
                top_k=max_chunks
            )
            
            return {
                'chunks': [
                    {
                        'id': r.get('id'),
                        'content': r.get('content'),
                        'score': r.get('score', 0.0),
                        'metadata': r.get('metadata', {})
                    }
                    for r in results
                ],
                'total': len(results)
            }
            
        except Exception as e:
            logger.error(f"语义搜索失败: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'chunks': [],
                'total': 0
            }
    
    async def _get_document_summary(
        self,
        doc_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        获取文档摘要信息
        
        Args:
            doc_id: 文档ID
            tenant_id: 租户ID
            
        Returns:
            {
                'doc_id': str,
                'summary': str,
                'total_chunks': int,
                'metadata': dict
            }
        """
        try:
            chunks = await self.chunk_service.get_chunks_by_doc_id(
                doc_id=doc_id,
                tenant_id=tenant_id,
                limit=1
            )
            
            if chunks:
                first_chunk = chunks[0]
                total_chunks = await self.chunk_service.count_chunks_by_doc_id(
                    doc_id=doc_id,
                    tenant_id=tenant_id
                )
                
                return {
                    'doc_id': doc_id,
                    'summary': first_chunk.content[:500],
                    'total_chunks': total_chunks,
                    'metadata': first_chunk.metadata
                }
            else:
                return {
                    'doc_id': doc_id,
                    'summary': '',
                    'total_chunks': 0,
                    'metadata': {}
                }
                
        except Exception as e:
            logger.error(f"获取文档摘要失败: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'doc_id': doc_id,
                'summary': '',
                'total_chunks': 0,
                'metadata': {}
            }
