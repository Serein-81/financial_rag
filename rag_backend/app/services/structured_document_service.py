# app/services/structured_document_service.py
from typing import List
from ..models.structured_document import (
    StructuredDocument, DocumentBlock, 
    DocumentMetadata, DocumentType, BlockType
)
from ..parsers.parser_factory import FileParserFactory
from ..chunkers.structured_document_chunker import StructuredDocumentChunker
from ..chunkers.base_chunker import ChunkResult


class StructuredDocumentService:
    """
    结构化文档服务
    
    核心功能:
    1. 将原始文档解析为结构化格式
    2. 提供统一的文档处理接口
    3. 支持结构化切块和检索
    """
    
    def __init__(self):
        self.chunker = StructuredDocumentChunker()
    
    async def parse_document(
        self,
        file_bytes: bytes,
        filename: str,
        file_type: str,
        tenant_id: str = "",
        document_id: str = "",
    ) -> StructuredDocument:
        """
        解析文档为结构化格式

        Args:
            file_bytes: 文件字节流
            filename: 文件名
            file_type: MIME类型
            tenant_id: 租户 ID（可选，供解析器存储原始图片用）
            document_id: 文档 ID（可选，同上）

        Returns:
            StructuredDocument: 结构化文档对象
            解析器产出的 image_map 写入 structured_doc.metadata.extra["image_map"]
        """
        # 1. 获取对应的解析器
        parser = FileParserFactory.get_parser(file_type)
        if not parser:
            raise ValueError(f"不支持的文件类型: {file_type}")

        # 传入库上下文（解析器按需使用，默认空实现无副作用）
        if tenant_id and document_id:
            parser.set_ingest_context(tenant_id, document_id)

        # 2. 解析文档内容
        try:
            # 检查是否为结构化解析器
            if hasattr(parser, '_extract_structured_content'):
                # 结构化解析器直接返回Markdown格式
                markdown_content = await parser.parse(file_bytes)
                structured_doc = self._parse_markdown_to_structured(
                    markdown_content, filename, file_type
                )
            else:
                # 基础解析器，提取纯文本后转换
                plain_text = await parser.parse(file_bytes)
                structured_doc = self._parse_plain_text_to_structured(
                    plain_text, filename, file_type
                )

            # 把解析器产出的 image_map 带回上层
            if hasattr(parser, 'image_map') and parser.image_map:
                structured_doc.metadata.extra["image_map"] = parser.image_map

            return structured_doc

        except Exception as e:
            raise Exception(f"文档解析失败: {str(e)}")
    
    def _parse_markdown_to_structured(
        self, 
        markdown_content: str, 
        filename: str, 
        file_type: str
    ) -> StructuredDocument:
        """将Markdown内容解析为结构化文档"""
        
        # 推断文档类型
        doc_type = self._infer_document_type(file_type)
        
        # 创建结构化文档
        structured_doc = StructuredDocument(
            title=self._extract_title_from_filename(filename),
            doc_type=doc_type,
            metadata=DocumentMetadata(
                source_format=file_type,
                extraction_method="structured_parsing"
            )
        )
        
        # 解析Markdown内容为块
        blocks = self._parse_markdown_blocks(markdown_content)
        
        # 添加块到文档
        for block in blocks:
            structured_doc.add_raw_block(block)
        
        # 构建层次结构
        structured_doc.build_hierarchy()
        
        return structured_doc
    
    def _parse_plain_text_to_structured(
        self, 
        plain_text: str, 
        filename: str, 
        file_type: str
    ) -> StructuredDocument:
        """将纯文本解析为结构化文档"""
        
        doc_type = self._infer_document_type(file_type)
        
        structured_doc = StructuredDocument(
            title=self._extract_title_from_filename(filename),
            doc_type=doc_type,
            metadata=DocumentMetadata(
                source_format=file_type,
                extraction_method="plain_text_parsing"
            )
        )
        
        # 将纯文本作为单个段落块
        if plain_text.strip():
            block = DocumentBlock(
                type=BlockType.PARAGRAPH,
                content=plain_text.strip()
            )
            structured_doc.add_raw_block(block)
        
        return structured_doc
    
    def _parse_markdown_blocks(self, markdown_content: str) -> List[DocumentBlock]:
        """解析Markdown内容为文档块"""
        import sys
        
        blocks = []
        lines = markdown_content.split('\n')
        current_block_lines = []
        current_block_type = BlockType.PARAGRAPH
        
        # 统计信息
        total_lines = len(lines)
        empty_lines = 0
        
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            
            # 检测标题
            if line.startswith('#'):
                # 保存之前的块
                if current_block_lines:
                    content = '\n'.join(current_block_lines).strip()
                    if content:
                        blocks.append(DocumentBlock(
                            type=current_block_type,
                            content=content
                        ))
                    current_block_lines = []
                
                # 解析标题
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                
                blocks.append(DocumentBlock(
                    type=BlockType.HEADING,
                    content=title,
                    level=level
                ))
                
                current_block_type = BlockType.PARAGRAPH
            
            # 检测表格
            elif line.startswith('|') and '|' in line[1:]:
                # 保存之前的块
                if current_block_lines:
                    content = '\n'.join(current_block_lines).strip()
                    if content:
                        blocks.append(DocumentBlock(
                            type=current_block_type,
                            content=content
                        ))
                    current_block_lines = []
                
                # 收集表格行
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    table_lines.append(lines[i])
                    i += 1
                i -= 1  # 回退一行
                
                if table_lines:
                    blocks.append(DocumentBlock(
                        type=BlockType.TABLE,
                        content='\n'.join(table_lines)
                    ))
                
                current_block_type = BlockType.PARAGRAPH
            
            # 空行 - 段落分隔
            elif line.strip() == '':
                empty_lines += 1
                if current_block_lines:
                    content = '\n'.join(current_block_lines).strip()
                    if content:
                        blocks.append(DocumentBlock(
                            type=current_block_type,
                            content=content
                        ))
                    current_block_lines = []
                current_block_type = BlockType.PARAGRAPH
            
            # 普通行
            else:
                current_block_lines.append(line)
            
            i += 1
        
        # 处理最后的块
        if current_block_lines:
            content = '\n'.join(current_block_lines).strip()
            if content:
                blocks.append(DocumentBlock(
                    type=current_block_type,
                    content=content
                ))
        
        # 输出统计信息
        print(f"[MarkdownParser] 总行数: {total_lines}, 空行数: {empty_lines}, 段落数: {len(blocks)}", file=sys.stderr)
        
        return blocks
    
    def _infer_document_type(self, file_type: str) -> DocumentType:
        """根据MIME类型推断文档类型"""
        file_type_lower = file_type.lower()
        
        if 'pdf' in file_type_lower:
            return DocumentType.PDF
        elif 'word' in file_type_lower or 'msword' in file_type_lower:
            return DocumentType.WORD
        elif 'markdown' in file_type_lower:
            return DocumentType.MARKDOWN
        elif 'image' in file_type_lower:
            return DocumentType.IMAGE
        else:
            return DocumentType.TEXT
    
    def _extract_title_from_filename(self, filename: str) -> str:
        """从文件名提取标题"""
        # 移除扩展名
        title = filename
        if '.' in filename:
            title = filename.rsplit('.', 1)[0]
        
        # 替换下划线和连字符为空格
        title = title.replace('_', ' ').replace('-', ' ')
        
        return title
    
    async def chunk_structured_document(
        self,
        structured_doc: StructuredDocument,
        chunk_tokens: int = 500,
        overlap_tokens: int = 50
    ) -> List[ChunkResult]:
        """
        对结构化文档进行切块
        
        Args:
            structured_doc: 结构化文档
            chunk_tokens: 每个切片的目标Token数量
            overlap_tokens: 切片之间的重叠Token数量
            
        Returns:
            List[ChunkResult]: 切块结果列表
        """
        return self.chunker.chunk_structured_document(
            structured_doc,
            chunk_tokens,
            overlap_tokens
        )
    
    def get_document_statistics(self, structured_doc: StructuredDocument) -> dict:
        """获取文档统计信息"""
        stats = structured_doc.get_statistics()
        
        # 添加字符数统计
        total_chars = sum(len(block.content) for block in structured_doc.raw_blocks if block.content)
        total_tokens = sum(self._approx_token_len(block.content) for block in structured_doc.raw_blocks if block.content)
        
        stats.update({
            "has_structure": len(structured_doc.sections) > 0,
            "extraction_method": structured_doc.metadata.extraction_method,
            "source_format": structured_doc.metadata.source_format,
            "estimated_chars": total_chars,
            "estimated_tokens": total_tokens,
            "avg_chunk_size": total_tokens / stats["total_blocks"] if stats["total_blocks"] > 0 else 0
        })
        
        return stats
    
    def _approx_token_len(self, text: str) -> int:
        """估算文本的Token数量"""
        if not text:
            return 0
        
        # 统计CJK字符数量
        cjk_count = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
        # 统计非CJK Token数量
        non_cjk_tokens = len([t for t in text.split() if t])
        
        return cjk_count + non_cjk_tokens


# 创建全局服务实例
structured_document_service = StructuredDocumentService()