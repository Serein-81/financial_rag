# app/parsers/structured_pdf_parser.py
import io
import asyncio
from typing import List, Dict, Any, Tuple
import fitz  # PyMuPDF
from collections import defaultdict, Counter
from .base_parser import FileParserStrategy


class StructuredPDFParser(FileParserStrategy):
    """
    结构化PDF解析器
    
    核心功能:
    1. 字体大小分析 -> 推断标题层级
    2. 布局分析 -> 识别段落边界  
    3. 表格检测 -> 结构化表格数据
    4. 构建文档树 -> 统一结构化格式
    """
    
    def get_supported_mime_types(self) -> List[str]:
        return ["application/pdf"]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析PDF文件，提取结构化内容
        
        Args:
            file_bytes: PDF文件的字节流
            
        Returns:
            str: 结构化的Markdown格式文本
        """
        if not self.validate_file(file_bytes):
            raise ValueError("PDF文件为空或无效")
        
        # PDF解析是CPU密集型操作，放到线程池执行
        structured_content = await asyncio.to_thread(
            self._extract_structured_content, file_bytes
        )
        
        if not structured_content.strip():
            raise ValueError("PDF文件内容为空")
        
        return structured_content.strip()
    
    def _extract_structured_content(self, file_bytes: bytes) -> str:
        """同步结构化内容提取（在线程池中运行）"""
        try:
            file_stream = io.BytesIO(file_bytes)
            doc = fitz.open(stream=file_stream, filetype="pdf")
            
            # 1. 分析字体层级
            font_hierarchy = self._analyze_font_hierarchy(doc)
            
            # 2. 提取结构化内容
            structured_blocks = self._extract_structured_blocks(doc, font_hierarchy)
            
            # 3. 构建Markdown格式
            markdown_content = self._build_markdown(structured_blocks)
            
            doc.close()
            return markdown_content
            
        except Exception as e:
            raise Exception(f"结构化PDF解析失败: {str(e)}")
    
    def _analyze_font_hierarchy(self, doc) -> Dict[float, int]:
        """
        分析字体大小层级，推断标题级别
        
        算法思路:
        1. 统计所有字体大小的出现频率
        2. 按字体大小降序排列
        3. 最大字体 -> H1，次大 -> H2，以此类推
        4. 正文字体（最频繁）不作为标题
        
        Returns:
            Dict[float, int]: 字体大小 -> 标题级别的映射
        """
        font_sizes = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_size = span["size"]
                            text = span["text"].strip()
                            
                            # 过滤空文本和特殊字符
                            if text and len(text) > 2:
                                font_sizes.append(font_size)
        
        if not font_sizes:
            return {}
        
        # 统计字体大小频率
        font_counter = Counter(font_sizes)
        
        # 找出正文字体（出现最频繁的）
        body_font_size = font_counter.most_common(1)[0][0]
        
        # 获取所有大于正文字体的字体大小，按降序排列
        heading_fonts = sorted([
            size for size in font_counter.keys() 
            if size > body_font_size
        ], reverse=True)
        
        # 构建字体大小到标题级别的映射
        font_hierarchy = {}
        for i, font_size in enumerate(heading_fonts[:6]):  # 最多6级标题
            font_hierarchy[font_size] = i + 1
        
        return font_hierarchy
    
    def _extract_structured_blocks(self, doc, font_hierarchy: Dict[float, int]) -> List[Dict[str, Any]]:
        """
        提取结构化文本块
        
        Returns:
            List[Dict]: 结构化块列表，每个块包含:
                - type: "heading" | "paragraph" | "table"
                - level: 标题级别（仅heading）
                - content: 文本内容
                - page: 页码
        """
        structured_blocks = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            # 提取表格
            tables = self._extract_tables(page)
            
            for block in blocks:
                if "lines" in block:
                    # 文本块处理
                    block_text = ""
                    block_font_size = None
                    
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span["text"]
                            if block_font_size is None:
                                block_font_size = span["size"]
                    
                    block_text += line_text.strip() + "\n"
                    
                    block_text = block_text.strip()
                    if not block_text:
                        continue
                    
                    # 判断是否为标题
                    if block_font_size in font_hierarchy:
                        structured_blocks.append({
                            "type": "heading",
                            "level": font_hierarchy[block_font_size],
                            "content": block_text,
                            "page": page_num + 1
                        })
                    else:
                        # 普通段落
                        structured_blocks.append({
                            "type": "paragraph", 
                            "content": block_text,
                            "page": page_num + 1
                        })
            
            # 添加表格
            for table in tables:
                structured_blocks.append({
                    "type": "table",
                    "content": table,
                    "page": page_num + 1
                })
        
        return structured_blocks
    
    def _extract_tables(self, page) -> List[str]:
        """
        提取页面中的表格
        
        使用PyMuPDF的表格检测功能
        """
        tables = []
        try:
            # 查找表格
            table_list = page.find_tables()
            
            for table in table_list:
                # 提取表格数据
                table_data = table.extract()
                
                if table_data:
                    # 转换为Markdown表格格式
                    markdown_table = self._format_table_as_markdown(table_data)
                    tables.append(markdown_table)
        
        except Exception as e:
            # 表格提取失败不影响整体解析
            pass
        
        return tables
    
    def _format_table_as_markdown(self, table_data: List[List[str]]) -> str:
        """将表格数据格式化为Markdown表格"""
        if not table_data:
            return ""
        
        markdown_lines = []
        
        # 表头
        header = table_data[0]
        markdown_lines.append("| " + " | ".join(header) + " |")
        markdown_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        # 表格内容
        for row in table_data[1:]:
            markdown_lines.append("| " + " | ".join(row) + " |")
        
        return "\n".join(markdown_lines)
    
    def _build_markdown(self, structured_blocks: List[Dict[str, Any]]) -> str:
        """
        将结构化块转换为Markdown格式
        
        Args:
            structured_blocks: 结构化块列表
            
        Returns:
            str: Markdown格式的文档内容
        """
        markdown_lines = []
        
        for block in structured_blocks:
            if block["type"] == "heading":
                # 标题：添加对应数量的#
                level = block["level"]
                heading_prefix = "#" * level
                markdown_lines.append(f"{heading_prefix} {block['content']}")
                markdown_lines.append("")  # 标题后空行
                
            elif block["type"] == "paragraph":
                # 段落：直接添加内容
                markdown_lines.append(block["content"])
                markdown_lines.append("")  # 段落后空行
                
            elif block["type"] == "table":
                # 表格：添加表格内容
                markdown_lines.append(block["content"])
                markdown_lines.append("")  # 表格后空行
        
        return "\n".join(markdown_lines)