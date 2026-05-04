# app/parsers/structured_pdf_parser.py
import io
import os
import asyncio
from typing import List, Dict, Any
import fitz  # PyMuPDF
from collections import Counter
import logging
from .base_parser import FileParserStrategy

logger = logging.getLogger(__name__)

ENABLE_UNSTRUCTURED = os.getenv("ENABLE_UNSTRUCTURED_PARSER", "false").lower() == "true"
UNSTRUCTURED_API_URL = os.getenv("UNSTRUCTURED_API_URL", "http://unstructured-api:8000")

# 扫描件判定阈值：提取字符数 < 文件字节数 × 此比例 时判断为扫描件
SCAN_THRESHOLD_RATIO = 0.08


class StructuredPDFParser(FileParserStrategy):
    """
    结构化PDF解析器（混合模式）

    解析策略（自适应三级降级）:
    1. pymupdf4llm: 本地快速解析，文字型 PDF 首选（200MB，<2秒/100页）
    2. unstructured-api: 扫描件/OCR 场景，需要高质量识别时启用（可能耗尽内存）
    3. PyMuPDF 启发式: 无条件降级兜底

    选择逻辑:
    - 先用 pymupdf4llm 快速解析
    - 如果提取文本量 < 文件大小的 8%，判定为扫描件，走 unstructured-api（如果启用）
    - 如果 pymupdf4llm 不可用或 unstructured 也不可用，最终降级到 PyMuPDF 启发式
    """

    def get_supported_mime_types(self) -> List[str]:
        return ["application/pdf"]

    async def parse(self, file_bytes: bytes) -> str:
        """
        解析PDF文件，提取结构化内容（自适应混合模式）

        Args:
            file_bytes: PDF文件的字节流

        Returns:
            str: 结构化的Markdown格式文本
        """
        if not self.validate_file(file_bytes):
            raise ValueError("PDF文件为空或无效")

        # ── 第1级: 尝试 pymupdf4llm 快速解析（文字型 PDF）──
        fallback_markdown = None
        try:
            markdown = await self._parse_with_pymupdf4llm(file_bytes)
            if markdown and markdown.strip():
                text_len = len(markdown.strip())
                file_size = len(file_bytes)
                ratio = text_len / file_size if file_size > 0 else 0

                # 提取文本量 > 阈值 → 文字型 PDF，直接返回
                if ratio >= SCAN_THRESHOLD_RATIO:
                    logger.info(
                        f"pymupdf4llm 解析成功: 文本 {text_len} / 文件 {file_size} "
                        f"= {ratio:.1%}, 文字型 PDF"
                    )
                    return markdown.strip()

                # 提取文本量 < 阈值 → 疑似扫描件，保存结果作为 fallback
                logger.info(
                    f"pymupdf4llm 提取文本过少 ({ratio:.1%} < {SCAN_THRESHOLD_RATIO:.0%}), "
                    f"疑似扫描件，尝试 OCR 引擎"
                )
                fallback_markdown = markdown.strip()
            else:
                logger.info("pymupdf4llm 返回空，尝试 OCR 引擎")

        except ImportError:
            logger.warning("pymupdf4llm 未安装，尝试降级到启发式解析")
        except Exception as e:
            logger.warning(f"pymupdf4llm 解析失败: {e}，尝试降级方案")

        # ── 第2级: 扫描件 → 尝试 unstructured-api OCR ──
        if ENABLE_UNSTRUCTURED:
            logger.info(f"启用重型解析引擎 (OCR): {UNSTRUCTURED_API_URL}")
            try:
                return await self._parse_with_unstructured(file_bytes)
            except Exception as e:
                logger.warning(f"Unstructured API 解析失败: {e}")
                if fallback_markdown:
                    logger.info("使用 pymupdf4llm 已有结果作为 fallback")
                    return fallback_markdown
        else:
            if fallback_markdown:
                logger.info("重型解析引擎未启用，使用 pymupdf4llm 已有结果")
                return fallback_markdown

        # ── 第3级: PyMuPDF 启发式解析（无条件兜底）──
        logger.info("启用轻量解析模式 (PyMuPDF + 启发式规则)")
        structured_content = await asyncio.to_thread(
            self._extract_structured_content, file_bytes
        )
        if not structured_content.strip():
            raise ValueError("PDF文件内容为空")
        return structured_content.strip()

    async def _parse_with_pymupdf4llm(self, file_bytes: bytes) -> str:
        """
        使用 pymupdf4llm 进行本地快速解析（带表格识别）。

        优势：
        - 内存 < 200MB，无需 GPU
        - 文字型 PDF 表格识别质量接近 unstructured
        - 速度约 1-2秒/100页

        pymupdf4llm.to_markdown() 接受文件路径字符串或 pymupdf.Document 对象，
        不支持直接传 bytes。因此先用 fitz.open(stream=...) 打开。
        """
        import pymupdf4llm

        def _sync_convert() -> str:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            try:
                result = pymupdf4llm.to_markdown(
                    doc,
                    page_chunks=False,
                    show_progress=False,
                    write_images=False,
                )
                return result or ""
            finally:
                doc.close()

        return await asyncio.to_thread(_sync_convert)

    async def _parse_with_unstructured(self, file_bytes: bytes) -> str:
        """使用 Unstructured API 进行重型版面解析（OCR + 表格识别）"""
        import requests

        try:
            response = requests.post(
                f"{UNSTRUCTURED_API_URL}/general/v0/general",
                files={"files": ("document.pdf", file_bytes, "application/pdf")}
            )
            response.raise_for_status()

            result = response.json()

            if isinstance(result, list) and len(result) > 0:
                return self._parse_unstructured_response(result)
            else:
                logger.warning("Unstructured API 返回格式异常，fallback 到轻量解析")
                return await asyncio.to_thread(
                    self._extract_structured_content, file_bytes
                )

        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到 Unstructured API: {UNSTRUCTURED_API_URL}")
            logger.info("降级到轻量解析模式...")
            return await asyncio.to_thread(
                self._extract_structured_content, file_bytes
            )
        except Exception as e:
            logger.error(f"Unstructured API 调用失败: {e}")
            return await asyncio.to_thread(
                self._extract_structured_content, file_bytes
            )
    
    def _parse_unstructured_response(self, result: List[Dict]) -> str:
        """解析 Unstructured API 返回的结果"""
        markdown_blocks = []
        
        for element in result:
            element_type = element.get("type", "").lower()
            text = element.get("text", "")
            
            if not text:
                continue
            
            if "title" in element_type or "heading" in element_type:
                markdown_blocks.append(f"## {text}")
            elif "NarrativeText" in element_type or "Text" in element_type:
                markdown_blocks.append(text)
            elif "Table" in element_type:
                table_data = element.get("metadata", {}).get("text_as_html", "")
                if table_data:
                    markdown_blocks.append(self._html_table_to_markdown(table_data))
            else:
                markdown_blocks.append(text)
            
            markdown_blocks.append("")
        
        return "\n".join(markdown_blocks)
    
    def _html_table_to_markdown(self, html_table: str) -> str:
        """将 HTML 表格转换为 Markdown 格式"""
        import re
        
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html_table, re.DOTALL)
        if not rows:
            return html_table
        
        markdown_rows = []
        for i, row in enumerate(rows):
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            if cells:
                clean_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
                markdown_rows.append(f"| {' | '.join(clean_cells)} |")
                
                if i == 0:
                    markdown_rows.append(f"| {' | '.join(['---'] * len(clean_cells))} |")
        
        return "\n".join(markdown_rows) if markdown_rows else html_table
    
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
        
        except Exception:
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