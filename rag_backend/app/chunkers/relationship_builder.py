"""
节点关系构建器 (Relationship Builder)

在 chunking 全部完成后，根据 domain 建立节点间关系：
- Financial: 文本段落 PARENT → 表格 CHILD
- Tax: PREVIOUS / NEXT 条款指针
- Legal: LEAF → PARENT + PARENT → CHILDREN 反向引用
- General: LEAF → PARENT Auto-Merging 关系
"""

import logging
from typing import List
from app.chunkers.base_chunker import ChunkResult

logger = logging.getLogger(__name__)


class RelationshipBuilder:
    """
    节点关系构建器。

    所有 domain 共享一轮遍历即可完成，避免多遍扫描。
    注意：此时 chunk_index 是临时占位符，
    后续由存储层替换为真实数据库 UUID。
    """

    PARENT_RELATION = "PARENT"
    CHILDREN_RELATION = "CHILDREN"
    PREVIOUS_RELATION = "PREVIOUS"
    NEXT_RELATION = "NEXT"
    SOURCE_RELATION = "SOURCE"

    def build(
        self,
        chunks: List[ChunkResult],
        domain: str,
    ) -> List[ChunkResult]:
        """
        根据 domain 建立关系。

        Args:
            chunks: 已切分的所有 chunk 列表
            domain: 文档领域

        Returns:
            已建立关系的 chunks
        """
        if domain == "finance":
            return self._build_finance_relations(chunks)
        elif domain == "tax":
            return self._build_tax_relations(chunks)
        elif domain == "legal":
            return self._build_legal_relations(chunks)
        else:
            return self._build_general_relations(chunks)

    def _build_finance_relations(
        self,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        财务关系构建。

        扫描 chunk 序列，检测 pattern [text_chunk, table_chunk]：
        文本段落作为 PARENT，表格作为 CHILD。
        """
        # 按 chunk_index 排序
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)

        for i, chunk in enumerate(sorted_chunks):
            if chunk.block_type == "table" and i > 0:
                prev_chunk = sorted_chunks[i - 1]
                # 前一个 chunk 是文本段落 → 建立 PARENT 关系
                if prev_chunk.block_type in ("paragraph", None):
                    chunk.relationships[self.PARENT_RELATION] = (
                        prev_chunk.chunk_index
                    )
                    # 在 PARENT 上建立反向引用
                    children = prev_chunk.relationships.get(
                        self.CHILDREN_RELATION, []
                    )
                    children.append(chunk.chunk_index)
                    prev_chunk.relationships[self.CHILDREN_RELATION] = children

        logger.debug(
            f"[RelationshipBuilder] Finance: 为 {len(chunks)} 个 chunk "
            f"建立表格-正文关系"
        )
        return chunks

    def _build_tax_relations(
        self,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        税务关系构建。

        按 clause 序号建立 PREVIOUS / NEXT 指针。
        所有节点按 chunk_index 排序后依次链接。
        """
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)

        for i, chunk in enumerate(sorted_chunks):
            if i > 0:
                chunk.relationships[self.PREVIOUS_RELATION] = (
                    sorted_chunks[i - 1].chunk_index
                )
            if i < len(sorted_chunks) - 1:
                chunk.relationships[self.NEXT_RELATION] = (
                    sorted_chunks[i + 1].chunk_index
                )

        logger.debug(
            f"[RelationshipBuilder] Tax: 为 {len(chunks)} 个 clause "
            f"建立 PREVIOUS/NEXT 链"
        )
        return chunks

    def _build_legal_relations(
        self,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        法务关系构建。

        - leaf → PARENT 关系（已在 LegalChunker 中建立占位）
        - PARENT → CHILDREN 反向引用
        """
        parent_to_children = {}

        for chunk in chunks:
            if self.PARENT_RELATION in (chunk.relationships or {}):
                parent_idx = chunk.relationships[self.PARENT_RELATION]
                parent_to_children.setdefault(parent_idx, []).append(
                    chunk.chunk_index
                )

        for chunk in chunks:
            if chunk.chunk_index in parent_to_children:
                chunk.relationships[self.CHILDREN_RELATION] = (
                    parent_to_children[chunk.chunk_index]
                )

        logger.debug(
            f"[RelationshipBuilder] Legal: 为 {len(chunks)} 个 clause "
            f"建立 PARENT/CHILDREN 关系"
        )
        return chunks

    def _build_general_relations(
        self,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        通用关系构建。

        leaf → PARENT 关系已在 GeneralChunker 中建立。
        这里补充 PARENT → CHILDREN 反向引用。
        """
        parent_to_children = {}

        for chunk in chunks:
            if self.PARENT_RELATION in (chunk.relationships or {}):
                parent_idx = chunk.relationships[self.PARENT_RELATION]
                parent_to_children.setdefault(parent_idx, []).append(
                    chunk.chunk_index
                )

        for chunk in chunks:
            if chunk.chunk_index in parent_to_children:
                chunk.relationships[self.CHILDREN_RELATION] = (
                    parent_to_children[chunk.chunk_index]
                )

        logger.debug(
            f"[RelationshipBuilder] General: 为 {len(chunks)} 个 chunk "
            f"建立 Auto-Merging 关系"
        )
        return chunks


# 全局单例
relationship_builder = RelationshipBuilder()
