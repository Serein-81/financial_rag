"""
法务领域切块策略 (Legal Chunker)

核心设计：
1. AST 层级树状切分：利用现有 build_hierarchy() 的标题层级
2. PARENT/LEAF 双层节点：章节为 PARENT，条款为 LEAF
3. 父节点预留 summary 字段（由 SummaryGenerator 填充）
"""

import logging
from typing import List
from app.chunkers.base_chunker import ChunkResult, ChunkStrategy
from app.models.structured_document import (
    StructuredDocument, DocumentSection, BlockType,
)

logger = logging.getLogger(__name__)


class LegalChunker:
    """
    法务文档切块器。

    基于 DocumentSection 层级树生成双层节点：
    - PARENT Node: 每个章节一个，包含该章节下所有内容的全文
    - LEAF Node: 每个独立条款一个，作为检索的基本单元
    """

    def chunk(
        self,
        structured_doc: StructuredDocument,
        chunk_tokens: int = 1024,
        overlap_tokens: int = 50,
    ) -> List[ChunkResult]:
        """
        对法务文档执行 AST 层级切分。

        Args:
            structured_doc: 结构化文档

        Returns:
            双层节点列表（PARENT + LEAF）
        """
        if not structured_doc.sections and not structured_doc.raw_blocks:
            return []

        chunks: List[ChunkResult] = []
        chunk_counter = [0]  # 用 list 实现闭包内的可变计数器

        if structured_doc.sections:
            self._traverse_sections(
                sections=structured_doc.sections,
                parent_path=[],
                chunks=chunks,
                counter=chunk_counter,
            )
        else:
            # 无层级时，按原始块切分
            for block in structured_doc.raw_blocks:
                if block.content and block.content.strip():
                    chunks.append(
                        ChunkResult(
                            content=block.content.strip(),
                            start=0,
                            end=len(block.content),
                            tokens=ChunkStrategy.approx_token_len(
                                block.content
                            ),
                            domain="legal",
                            node_type="leaf",
                            chunk_index=chunk_counter[0],
                            block_type=block.type.value,
                        )
                    )
                    chunk_counter[0] += 1

        logger.info(
            f"[LegalChunker] 切块完成: "
            f"{sum(1 for c in chunks if c.node_type == 'parent')} 个 PARENT, "
            f"{sum(1 for c in chunks if c.node_type == 'leaf')} 个 LEAF"
        )
        return chunks

    def _traverse_sections(
        self,
        sections: List[DocumentSection],
        parent_path: List[str],
        chunks: List[ChunkResult],
        counter: List[int],
    ):
        """DFS 遍历并生成双层节点"""
        for section in sections:
            current_path = parent_path + [section.heading]
            heading_path = " > ".join(current_path)
            full_content = section.get_full_content()

            if not full_content.strip():
                continue

            # 创建 PARENT Node（章节）
            parent_idx = counter[0]
            parent_chunk = ChunkResult(
                content=full_content,
                start=0,
                end=len(full_content),
                tokens=ChunkStrategy.approx_token_len(full_content),
                heading_path=heading_path,
                domain="legal",
                node_type="parent",
                chunk_index=parent_idx,
                metadata={
                    "section_title": section.heading,
                    "section_level": section.level,
                },
            )
            chunks.append(parent_chunk)
            counter[0] += 1

            # 创建 LEAF Node（每个独立条款）
            for block in section.blocks:
                if (
                    block.type == BlockType.PARAGRAPH
                    and block.content
                    and block.content.strip()
                ):
                    leaf_chunk = ChunkResult(
                        content=block.content.strip(),
                        start=0,
                        end=len(block.content),
                        tokens=ChunkStrategy.approx_token_len(
                            block.content
                        ),
                        heading_path=heading_path,
                        domain="legal",
                        node_type="leaf",
                        chunk_index=counter[0],
                        block_type="clause",
                        relationships={"PARENT": parent_idx},
                    )
                    chunks.append(leaf_chunk)
                    counter[0] += 1

            # 递归子章节
            if section.subsections:
                self._traverse_sections(
                    section.subsections, current_path, chunks, counter
                )


# 全局单例
legal_chunker = LegalChunker()
