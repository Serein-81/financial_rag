"""
文档检索工具 - 按需检索模式

提供Agent按需读取文档内容的工具,支持:
1. 按切块ID读取内容
2. 语义搜索文档章节
3. 租户隔离过滤
4. 数量限制控制
"""

from typing import List, Dict, Any, Optional
from app.services.chunk_service import ChunkService
from app.services.unified_retriever import UnifiedRetriever


class DocumentChunkRetrievalTool:
    """文档切块检索工具"""
    
    def __init__(self):
        self.chunk_service = ChunkService()
        self.unified_retriever = UnifiedRetriever()
    
    async def read_document_chunks(
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
            # 限制数量
            limited_ids = chunk_ids[:max_chunks]
            
            # 读取切块(带租户隔离)
            chunks = await self.chunk_service.get_chunks_by_ids(
                chunk_ids=limited_ids,
                tenant_id=tenant_id  # 🔒 租户隔离
            )
            
            # 格式化返回
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
            return {
                'error': str(e),
                'chunks': [],
                'total': 0,
                'truncated': False
            }
    
    async def search_document_sections(
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
            # 构建过滤条件
            filters = {'tenant_id': tenant_id}  # 🔒 租户隔离
            
            if doc_ids:
                filters['doc_id'] = {'$in': doc_ids}
            
            # 语义搜索
            results = await self.unified_retriever.retrieve(
                query=query,
                filters=filters,
                top_k=max_chunks
            )
            
            # 格式化返回
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
            return {
                'error': str(e),
                'chunks': [],
                'total': 0
            }
    
    async def get_document_summary(
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
            # 获取文档的第一个切块(通常包含摘要)
            chunks = await self.chunk_service.get_chunks_by_doc_id(
                doc_id=doc_id,
                tenant_id=tenant_id,  # 🔒 租户隔离
                limit=1
            )
            
            if chunks:
                first_chunk = chunks[0]
                return {
                    'doc_id': doc_id,
                    'summary': first_chunk.content[:500],  # 前500字作为摘要
                    'total_chunks': await self.chunk_service.count_chunks_by_doc_id(
                        doc_id=doc_id,
                        tenant_id=tenant_id
                    ),
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
            return {
                'error': str(e),
                'doc_id': doc_id,
                'summary': '',
                'total_chunks': 0,
                'metadata': {}
            }
