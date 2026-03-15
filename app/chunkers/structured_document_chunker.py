# app/chunkers/structured_document_chunker.py
from typing import List, Dict, Any
from ..models.structured_document import StructuredDocument, DocumentSection, DocumentBlock, BlockType
from .base_chunker import ChunkStrategy, ChunkResult


class StructuredDocumentChunker(ChunkStrategy):
    """
    结构化文档切块策略
    
    特性:
    1. 基于文档结构进行智能切分
    2. 保留完整的标题路径信息
    3. 支持表格、图片等多模态内容
    4. 智能合并小段落，避免过度碎片化
    """
    
    def get_supported_types(self) -> List[str]:
        return ["structured_document", "structured"]
    
    def chunk(
        self, 
        text: str, 
        chunk_tokens: int = 500, 
        overlap_tokens: int = 50
    ) -> List[ChunkResult]:
        """
        对结构化文档进行智能切分
        
        注意: text参数在这里不使用，而是通过structured_document参数传入
        """
        # 这个方法主要用于兼容，实际使用chunk_structured_document
        return []
    
    def chunk_structured_document(
        self,
        structured_doc: StructuredDocument,
        chunk_tokens: int = 500,
        overlap_tokens: int = 50
    ) -> List[ChunkResult]:
        """
        对结构化文档进行智能切分
        
        Args:
            structured_doc: 结构化文档对象
            chunk_tokens: 每个切片的目标Token数量
            overlap_tokens: 切片之间的重叠Token数量
            
        Returns:
            List[ChunkResult]: 切块结果列表
        """
        if not structured_doc.sections and not structured_doc.raw_blocks:
            return []
        
        # 如果有结构化章节，使用章节切分
        if structured_doc.sections:
            return self._chunk_by_sections(
                structured_doc.sections, 
                chunk_tokens, 
                overlap_tokens
            )
        
        # 否则使用原始块切分
        return self._chunk_by_blocks(
            structured_doc.raw_blocks,
            chunk_tokens,
            overlap_tokens
        )
    
    def _chunk_by_sections(
        self,
        sections: List[DocumentSection],
        chunk_tokens: int,
        overlap_tokens: int
    ) -> List[ChunkResult]:
        """基于章节结构进行切分"""
        chunks = []
        
        for section in sections:
            # 处理当前章节
            section_chunks = self._chunk_single_section(
                section, 
                chunk_tokens, 
                overlap_tokens
            )
            chunks.extend(section_chunks)
            
            # 递归处理子章节
            if section.subsections:
                subsection_chunks = self._chunk_by_sections(
                    section.subsections,
                    chunk_tokens,
                    overlap_tokens
                )
                chunks.extend(subsection_chunks)
        
        return chunks
    
    def _chunk_single_section(
        self,
        section: DocumentSection,
        chunk_tokens: int,
        overlap_tokens: int
    ) -> List[ChunkResult]:
        """切分单个章节"""
        chunks = []
        
        # 构建标题路径
        heading_path = section.heading
        
        # 收集章节内容块
        content_blocks = []
        
        # 添加章节描述内容
        if section.content.strip():
            content_blocks.append({
                "content": section.content,
                "type": "paragraph",
                "tokens": self.approx_token_len(section.content)
            })
        
        # 添加章节内的其他块
        for block in section.blocks:
            block_content = self._format_block_content(block)
            if block_content:
                content_blocks.append({
                    "content": block_content,
                    "type": block.type.value,
                    "tokens": self.approx_token_len(block_content),
                    "page": block.page
                })
        
        if not content_blocks:
            return chunks
        
        # 基于Token数量进行智能合并
        merged_chunks = self._merge_blocks_by_tokens(
            content_blocks,
            chunk_tokens,
            overlap_tokens
        )
        
        # 转换为ChunkResult
        for i, merged_chunk in enumerate(merged_chunks):
            chunk_result = ChunkResult(
                content=merged_chunk["content"],
                start=merged_chunk.get("start", 0),
                end=merged_chunk.get("end", len(merged_chunk["content"])),
                tokens=merged_chunk["tokens"],
                heading_path=heading_path,
                metadata={
                    "section_title": section.heading,
                    "section_level": section.level,
                    "chunk_index": i,
                    "block_types": merged_chunk.get("block_types", []),
                    "pages": merged_chunk.get("pages", [])
                }
            )
            chunks.append(chunk_result)
        
        return chunks
    
    def _chunk_by_blocks(
        self,
        blocks: List[DocumentBlock],
        chunk_tokens: int,
        overlap_tokens: int
    ) -> List[ChunkResult]:
        """基于原始块进行切分（无结构文档）"""
        chunks = []
        current_heading_path = None
        content_blocks = []
        
        for block in blocks:
            if block.type == BlockType.HEADING:
                # 处理之前积累的内容块
                if content_blocks:
                    block_chunks = self._create_chunks_from_blocks(
                        content_blocks,
                        current_heading_path,
                        chunk_tokens,
                        overlap_tokens
                    )
                    chunks.extend(block_chunks)
                    content_blocks = []
                
                # 更新当前标题路径
                current_heading_path = block.content
            
            else:
                # 添加到内容块
                block_content = self._format_block_content(block)
                if block_content:
                    content_blocks.append({
                        "content": block_content,
                        "type": block.type.value,
                        "tokens": self.approx_token_len(block_content),
                        "page": block.page
                    })
        
        # 处理最后的内容块
        if content_blocks:
            block_chunks = self._create_chunks_from_blocks(
                content_blocks,
                current_heading_path,
                chunk_tokens,
                overlap_tokens
            )
            chunks.extend(block_chunks)
        
        return chunks
    
    def _format_block_content(self, block: DocumentBlock) -> str:
        """格式化块内容"""
        if block.type == BlockType.TABLE and block.table_data:
            return block.table_data.to_markdown()
        elif block.type == BlockType.IMAGE and block.image_data:
            return block.image_data.to_markdown()
        else:
            return block.content
    
    def _merge_blocks_by_tokens(
        self,
        content_blocks: List[Dict[str, Any]],
        chunk_tokens: int,
        overlap_tokens: int
    ) -> List[Dict[str, Any]]:
        """基于Token数量合并内容块"""
        if not content_blocks:
            return []
        
        merged_chunks = []
        current_chunk = {
            "content": "",
            "tokens": 0,
            "block_types": [],
            "pages": [],
            "start": 0,
            "end": 0
        }
        
        for i, block in enumerate(content_blocks):
            block_tokens = block["tokens"]
            
            # 如果当前块加入后不超过限制，则合并
            if current_chunk["tokens"] + block_tokens <= chunk_tokens or current_chunk["tokens"] == 0:
                # 合并内容
                if current_chunk["content"]:
                    current_chunk["content"] += "\n\n" + block["content"]
                else:
                    current_chunk["content"] = block["content"]
                
                current_chunk["tokens"] += block_tokens
                current_chunk["block_types"].append(block["type"])
                
                if block.get("page"):
                    current_chunk["pages"].append(block["page"])
                
                current_chunk["end"] = current_chunk["start"] + len(current_chunk["content"])
            
            else:
                # 保存当前块
                if current_chunk["content"]:
                    merged_chunks.append(current_chunk.copy())
                
                # 开始新块
                current_chunk = {
                    "content": block["content"],
                    "tokens": block_tokens,
                    "block_types": [block["type"]],
                    "pages": [block["page"]] if block.get("page") else [],
                    "start": current_chunk["end"],
                    "end": current_chunk["end"] + len(block["content"])
                }
        
        # 添加最后一个块
        if current_chunk["content"]:
            merged_chunks.append(current_chunk)
        
        # 处理重叠
        if overlap_tokens > 0 and len(merged_chunks) > 1:
            merged_chunks = self._add_overlap(merged_chunks, overlap_tokens)
        
        return merged_chunks
    
    def _create_chunks_from_blocks(
        self,
        content_blocks: List[Dict[str, Any]],
        heading_path: str,
        chunk_tokens: int,
        overlap_tokens: int
    ) -> List[ChunkResult]:
        """从内容块创建切片"""
        merged_chunks = self._merge_blocks_by_tokens(
            content_blocks,
            chunk_tokens,
            overlap_tokens
        )
        
        chunks = []
        for i, merged_chunk in enumerate(merged_chunks):
            chunk_result = ChunkResult(
                content=merged_chunk["content"],
                start=merged_chunk.get("start", 0),
                end=merged_chunk.get("end", len(merged_chunk["content"])),
                tokens=merged_chunk["tokens"],
                heading_path=heading_path,
                metadata={
                    "chunk_index": i,
                    "block_types": merged_chunk.get("block_types", []),
                    "pages": merged_chunk.get("pages", [])
                }
            )
            chunks.append(chunk_result)
        
        return chunks
    
    def _add_overlap(
        self,
        chunks: List[Dict[str, Any]],
        overlap_tokens: int
    ) -> List[Dict[str, Any]]:
        """为切片添加重叠内容"""
        if len(chunks) <= 1:
            return chunks
        
        overlapped_chunks = [chunks[0]]
        
        for i in range(1, len(chunks)):
            current_chunk = chunks[i].copy()
            prev_chunk = chunks[i-1]
            
            # 从前一个切片末尾提取重叠内容
            prev_content = prev_chunk["content"]
            prev_words = prev_content.split()
            
            # 估算需要多少词来达到overlap_tokens
            overlap_words = min(overlap_tokens, len(prev_words) // 2)
            
            if overlap_words > 0:
                overlap_content = " ".join(prev_words[-overlap_words:])
                current_chunk["content"] = overlap_content + "\n\n" + current_chunk["content"]
                current_chunk["tokens"] += self.approx_token_len(overlap_content)
            
            overlapped_chunks.append(current_chunk)
        
        return overlapped_chunks