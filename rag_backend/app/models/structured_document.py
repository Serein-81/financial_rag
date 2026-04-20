# app/models/structured_document.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class DocumentType(Enum):
    """文档类型枚举"""
    PDF = "pdf"
    WORD = "word"
    MARKDOWN = "markdown"
    TEXT = "text"
    IMAGE = "image"


class BlockType(Enum):
    """文档块类型枚举"""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    IMAGE = "image"
    CODE = "code"


@dataclass
class DocumentMetadata:
    """文档元数据"""
    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[str] = None
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    language: Optional[str] = None
    source_format: Optional[str] = None
    extraction_method: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "title": self.title,
            "author": self.author,
            "created_date": self.created_date,
            "page_count": self.page_count,
            "file_size": self.file_size,
            "language": self.language,
            "source_format": self.source_format,
            "extraction_method": self.extraction_method
        }


@dataclass
class TableData:
    """表格数据结构"""
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str] = None
    
    def to_markdown(self) -> str:
        """转换为Markdown表格格式"""
        if not self.headers or not self.rows:
            return ""
        
        lines = []
        
        # 表头
        lines.append("| " + " | ".join(self.headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        
        # 表格内容
        for row in self.rows:
            lines.append("| " + " | ".join(row) + " |")
        
        # 表格标题
        if self.caption:
            lines.insert(0, f"**{self.caption}**")
            lines.insert(1, "")
        
        return "\n".join(lines)


@dataclass
class ImageData:
    """图片数据结构"""
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    
    def to_markdown(self) -> str:
        """转换为Markdown图片格式"""
        alt = self.alt_text or self.caption or "图片"
        return f"![{alt}](image)"


@dataclass
class DocumentBlock:
    """文档块基础结构"""
    type: BlockType
    content: str
    level: Optional[int] = None  # 标题级别
    page: Optional[int] = None   # 页码
    position: Optional[int] = None  # 在文档中的位置
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 特殊数据
    table_data: Optional[TableData] = None
    image_data: Optional[ImageData] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "type": self.type.value,
            "content": self.content,
            "level": self.level,
            "page": self.page,
            "position": self.position,
            "metadata": self.metadata
        }
        
        if self.table_data:
            result["table_data"] = {
                "headers": self.table_data.headers,
                "rows": self.table_data.rows,
                "caption": self.table_data.caption
            }
        
        if self.image_data:
            result["image_data"] = {
                "caption": self.image_data.caption,
                "alt_text": self.image_data.alt_text,
                "width": self.image_data.width,
                "height": self.image_data.height,
                "format": self.image_data.format
            }
        
        return result


@dataclass
class DocumentSection:
    """文档章节结构"""
    heading: str
    level: int
    content: str = ""
    blocks: List[DocumentBlock] = field(default_factory=list)
    subsections: List['DocumentSection'] = field(default_factory=list)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    
    def add_block(self, block: DocumentBlock):
        """添加文档块"""
        self.blocks.append(block)
        
        # 更新页码范围
        if block.page:
            if self.page_start is None or block.page < self.page_start:
                self.page_start = block.page
            if self.page_end is None or block.page > self.page_end:
                self.page_end = block.page
    
    def add_subsection(self, subsection: 'DocumentSection'):
        """添加子章节"""
        self.subsections.append(subsection)
    
    def get_full_content(self) -> str:
        """获取完整内容（包括子章节）"""
        content_parts = [self.content]
        
        # 添加块内容
        for block in self.blocks:
            if block.type == BlockType.TABLE and block.table_data:
                content_parts.append(block.table_data.to_markdown())
            elif block.type == BlockType.IMAGE and block.image_data:
                content_parts.append(block.image_data.to_markdown())
            else:
                content_parts.append(block.content)
        
        # 添加子章节内容
        for subsection in self.subsections:
            content_parts.append(f"{'#' * subsection.level} {subsection.heading}")
            content_parts.append(subsection.get_full_content())
        
        return "\n\n".join(filter(None, content_parts))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
            "blocks": [block.to_dict() for block in self.blocks],
            "subsections": [sub.to_dict() for sub in self.subsections],
            "page_start": self.page_start,
            "page_end": self.page_end
        }


@dataclass
class StructuredDocument:
    """统一的结构化文档模型"""
    title: str
    doc_type: DocumentType
    sections: List[DocumentSection] = field(default_factory=list)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    raw_blocks: List[DocumentBlock] = field(default_factory=list)
    
    def add_section(self, section: DocumentSection):
        """添加章节"""
        self.sections.append(section)
    
    def add_raw_block(self, block: DocumentBlock):
        """添加原始块（用于无结构文档）"""
        self.raw_blocks.append(block)
    
    def build_hierarchy(self):
        """
        从原始块构建层次结构
        
        算法思路:
        1. 遍历所有块，识别标题
        2. 根据标题级别构建层次关系
        3. 将段落、表格等分配到对应章节
        """
        if not self.raw_blocks:
            return
        
        current_sections = {}  # level -> section
        
        for block in self.raw_blocks:
            if block.type == BlockType.HEADING:
                level = block.level or 1
                
                # 创建新章节
                section = DocumentSection(
                    heading=block.content,
                    level=level,
                    page_start=block.page,
                    page_end=block.page
                )
                
                # 找到父章节
                parent_section = None
                for parent_level in range(level - 1, 0, -1):
                    if parent_level in current_sections:
                        parent_section = current_sections[parent_level]
                        break
                
                # 添加到父章节或根级别
                if parent_section:
                    parent_section.add_subsection(section)
                else:
                    self.add_section(section)
                
                # 更新当前章节映射
                current_sections[level] = section
                
                # 清除更深层级的章节
                levels_to_remove = [lvl for lvl in current_sections.keys() if lvl > level]
                for lvl in levels_to_remove:
                    del current_sections[lvl]
            
            else:
                # 非标题块，添加到最近的章节
                target_section = None
                for level in sorted(current_sections.keys(), reverse=True):
                    target_section = current_sections[level]
                    break
                
                if target_section:
                    target_section.add_block(block)
                else:
                    # 没有章节，创建默认章节
                    if not self.sections:
                        default_section = DocumentSection(
                            heading="内容",
                            level=1
                        )
                        self.add_section(default_section)
                        current_sections[1] = default_section
                    
                    self.sections[0].add_block(block)
    
    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        markdown_parts = []
        
        # 文档标题
        if self.title:
            markdown_parts.append(f"# {self.title}")
            markdown_parts.append("")
        
        # 章节内容
        for section in self.sections:
            markdown_parts.append(f"{'#' * section.level} {section.heading}")
            markdown_parts.append("")
            markdown_parts.append(section.get_full_content())
            markdown_parts.append("")
        
        # 如果没有章节，使用原始块
        if not self.sections and self.raw_blocks:
            for block in self.raw_blocks:
                if block.type == BlockType.HEADING:
                    level = block.level or 1
                    markdown_parts.append(f"{'#' * level} {block.content}")
                elif block.type == BlockType.TABLE and block.table_data:
                    markdown_parts.append(block.table_data.to_markdown())
                elif block.type == BlockType.IMAGE and block.image_data:
                    markdown_parts.append(block.image_data.to_markdown())
                else:
                    markdown_parts.append(block.content)
                
                markdown_parts.append("")
        
        return "\n".join(markdown_parts).strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "title": self.title,
            "doc_type": self.doc_type.value,
            "sections": [section.to_dict() for section in self.sections],
            "metadata": self.metadata.to_dict(),
            "raw_blocks": [block.to_dict() for block in self.raw_blocks]
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取文档统计信息"""
        stats = {
            "total_sections": len(self.sections),
            "total_blocks": len(self.raw_blocks),
            "block_types": {},
            "heading_levels": {},
            "page_count": self.metadata.page_count or 0,
            "estimated_words": 0
        }
        
        # 统计块类型
        for block in self.raw_blocks:
            block_type = block.type.value
            stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
            
            if block.type == BlockType.HEADING and block.level:
                level = f"H{block.level}"
                stats["heading_levels"][level] = stats["heading_levels"].get(level, 0) + 1
            
            # 估算字数
            if block.content:
                stats["estimated_words"] += len(block.content.split())
        
        return stats