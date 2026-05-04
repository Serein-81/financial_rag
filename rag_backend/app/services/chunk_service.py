# app/services/chunk_service.py
"""
文本切块服务 (v2 Unified)

统一的切块服务门面，同时支持：
- 旧 API: split_text(), split_text_simple(), get_supported_types() (向后兼容)
- 新 API: create_chunks() (多智能体数据摄入)
- DB 查询: get_chunks_by_ids(), get_chunks_by_doc_id(), count_chunks_by_doc_id() (文档检索工具)

内部统一使用 DomainChunkerFactory 进行领域感知切块。
"""
import logging
import uuid
from types import SimpleNamespace
from typing import List, Union, Optional, Dict, Any
from sqlalchemy import select, func
from app.db import AsyncSessionLocal
from app.chunkers import ChunkResult
from app.chunkers.domain_chunker_factory import domain_chunker_factory
from app.chunkers.markdown_chunker import MarkdownChunkStrategy
from app.chunkers.plain_text_chunker import PlainTextChunkStrategy
from app.chunkers.structured_document_chunker import StructuredDocumentChunker

logger = logging.getLogger(__name__)


class ChunkService:
    """
    文本切块服务 (v2 Unified)

    职责:
    1. 旧 API: 根据文档类型选择合适的切块策略 (向后兼容)
    2. 新 API: 领域感知切块 + 数据库存储
    3. DB 查询: 按 ID/文档查询切块
    """

    def __init__(self):
        # 保留旧策略用于纯文本切分（旧 API 调用）
        self._text_strategies = {
            "text": PlainTextChunkStrategy(),
            "plain": PlainTextChunkStrategy(),
            "default": PlainTextChunkStrategy(),
            "markdown": MarkdownChunkStrategy(),
            "md": MarkdownChunkStrategy(),
            "structured": StructuredDocumentChunker(),
        }

    # ============================================================
    # 旧 API：向后兼容 (给 test_chunk_integration 等使用)
    # ============================================================

    def split_text(
        self,
        text: str,
        doc_type: str = "text",
        chunk_tokens: int = 500,
        overlap_tokens: int = 50,
        return_metadata: bool = False,
    ) -> Union[List[str], List[ChunkResult]]:
        """
        切分文本 (旧 API, 向后兼容)

        Args:
            text: 待切分的文本
            doc_type: 文档类型 ("markdown", "text", "structured" 等)
            chunk_tokens: 每个切片的目标 Token 数量
            overlap_tokens: 切片之间的重叠 Token 数量
            return_metadata: 是否返回元数据

        Returns:
            List[str] 或 List[ChunkResult]
        """
        if not text:
            return []

        # 选择合适的策略
        normalized_type = doc_type.lower().strip()
        strategy = self._text_strategies.get(normalized_type)

        if not strategy:
            # 模糊匹配
            for key, s in self._text_strategies.items():
                if key in normalized_type or normalized_type in key:
                    strategy = s
                    break

        if not strategy:
            strategy = self._text_strategies["default"]

        # 执行切块
        chunk_results = strategy.chunk(text, chunk_tokens, overlap_tokens)

        if return_metadata:
            return chunk_results
        return [chunk.content for chunk in chunk_results]

    def split_text_simple(self, text: str) -> List[str]:
        """
        简化版切块方法 (向后兼容)
        """
        return self.split_text(text=text, doc_type="text")

    def get_supported_types(self) -> List[str]:
        """
        获取所有支持的文档类型
        """
        return list(self._text_strategies.keys())

    # ============================================================
    # 新 API：领域感知切块 + 数据库存储
    # ============================================================

    async def create_chunks(
        self,
        text: str,
        doc_id: str,
        tenant_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """
        创建切块并存储到数据库 (指针模式)

        供 data_ingestion.py 等多智能体管道使用。
        使用领域感知切块器，将切块持久化到数据库。

        Args:
            text: 文档文本内容
            doc_id: 文档 ID
            tenant_id: 租户 ID
            metadata: 额外元数据 (doc_name, doc_type, user_id 等)

        Returns:
            已存储的 DocumentChunk 对象列表 (含数据库 ID)
        """
        from app.models.chunk import DocumentChunk

        if not text:
            return []

        metadata = metadata or {}

        # 使用默认 GeneralChunker 进行切块
        chunker = domain_chunker_factory.get_chunker("general")
        from app.models.structured_document import (
            StructuredDocument, DocumentBlock, BlockType, DocumentMetadata, DocumentType,
        )

        # 将纯文本包装为结构化文档
        struct_doc = StructuredDocument(
            title=metadata.get("doc_name", "untitled"),
            doc_type=DocumentType.TEXT,
            metadata=DocumentMetadata(
                source_format=metadata.get("doc_type", "text"),
                extraction_method="plain_text",
            ),
        )
        struct_doc.add_raw_block(DocumentBlock(
            type=BlockType.PARAGRAPH,
            content=text,
        ))

        # 执行切块
        chunk_results = chunker.chunk(struct_doc)
        if not chunk_results:
            return []

        # 存储到数据库
        chunks_to_insert = []
        for idx, cr in enumerate(chunk_results):
            chunk = DocumentChunk(
                document_id=uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id,
                content=cr.content,
                chunk_index=idx,
                token_count=cr.tokens,
                tenant_id=tenant_id,
                domain=cr.domain or "general",
                node_type=cr.node_type or "leaf",
                relationships=cr.relationships or {},
                meta_info={
                    "doc_name": metadata.get("doc_name", ""),
                    "user_id": metadata.get("user_id", ""),
                    **(cr.metadata or {}),
                },
            )
            chunks_to_insert.append(chunk)

        async with AsyncSessionLocal() as db:
            db.add_all(chunks_to_insert)
            await db.commit()
            for chunk in chunks_to_insert:
                await db.refresh(chunk)

        logger.info(
            f"[ChunkService] create_chunks: {len(chunks_to_insert)} 个切块 "
            f"已存储 (doc_id={doc_id})"
        )
        return chunks_to_insert

    # ============================================================
    # DB 查询 API：供 document_retrieval_tools.py 使用
    # ============================================================

    async def get_chunks_by_ids(
        self,
        chunk_ids: List[str],
        tenant_id: Optional[str] = None,
    ) -> List[Any]:
        """
        按切块 ID 列表批量读取切块内容

        Args:
            chunk_ids: 切块 ID 列表
            tenant_id: 租户 ID (可选过滤)

        Returns:
            dict 列表，每项含 id/content/metadata (兼容 document_retrieval_tools.py)
        """
        if not chunk_ids:
            return []

        from app.models.chunk import DocumentChunk

        async with AsyncSessionLocal() as db:
            query = select(DocumentChunk).where(
                DocumentChunk.id.in_([
                    uuid.UUID(cid) if isinstance(cid, str) else cid
                    for cid in chunk_ids
                ])
            )
            if tenant_id:
                query = query.where(DocumentChunk.tenant_id == tenant_id)

            result = await db.execute(query)
            rows = result.scalars().all()

        # 将 ORM 对象转为 dict，适配 caller 期望的 .metadata 属性
        return [
            SimpleNamespace(
                id=str(row.id),
                content=row.content,
                metadata=row.meta_info or {},
            )
            for row in rows
        ]

    async def get_chunks_by_doc_id(
        self,
        doc_id: str,
        tenant_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Any]:
        """
        按文档 ID 查询切块

        Args:
            doc_id: 文档 ID
            tenant_id: 租户 ID (可选过滤)
            limit: 最大返回数量

        Returns:
            dict 列表，每项含 id/content/metadata
        """
        from app.models.chunk import DocumentChunk
        from app.models.document import Document

        async with AsyncSessionLocal() as db:
            query = (
                select(DocumentChunk)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(DocumentChunk.document_id == (
                    uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id
                ))
            )
            if tenant_id:
                query = query.where(Document.tenant_id == tenant_id)

            query = query.limit(limit)
            result = await db.execute(query)
            rows = result.scalars().all()

        return [
            SimpleNamespace(
                id=str(row.id),
                content=row.content,
                metadata=row.meta_info or {},
            )
            for row in rows
        ]

    async def count_chunks_by_doc_id(
        self,
        doc_id: str,
        tenant_id: Optional[str] = None,
    ) -> int:
        """
        统计文档的切块总数

        Args:
            doc_id: 文档 ID
            tenant_id: 租户 ID (可选过滤)

        Returns:
            切块数量
        """
        from app.models.chunk import DocumentChunk
        from app.models.document import Document

        async with AsyncSessionLocal() as db:
            query = (
                select(func.count(DocumentChunk.id))
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(DocumentChunk.document_id == (
                    uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id
                ))
            )
            if tenant_id:
                query = query.where(Document.tenant_id == tenant_id)

            result = await db.execute(query)
            count = result.scalar()

        return count or 0


# 实例化单例
chunk_service = ChunkService()
