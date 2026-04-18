# app/parsers/structured_word_parser.py
import io
import asyncio
from typing import List, Dict, Any
from docx import Document as DocxDocument
from .base_parser import FileParserStrategy


class StructuredWordParser(FileParserStrategy):
    """
    结构化Word文档解析器
    
    核心功能:
    1. 样式分析 -> 识别标题样式
    2. 段落层级 -> 构建文档结构
    3. 表格提取 -> 结构化表格数据
    4. 列表处理 -> 保留列表格式
    """
    
    def get_supported_mime_types(self) -> List[str]:
        return [
            "application/msword",  # .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # .docx
        ]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析Word文件，提取结构化内容
        
        Args:
            file_bytes: Word文件的字节流
            
        Returns:
            str: 结构化的Markdown格式文本
        """
        import sys
        print(f"[WordParser] 接收文件大小: {len(file_bytes)} bytes", file=sys.stderr)
        if not self.validate_file(file_bytes):
            print(f"[WordParser] 文件验证失败: file_bytes={len(file_bytes)}", file=sys.stderr)
            raise ValueError("Word文件为空或无效")
        
        # Word解析是CPU密集型操作，放到线程池执行
        structured_content = await asyncio.to_thread(
            self._extract_structured_content, file_bytes
        )
        
        if not structured_content.strip():
            raise ValueError("Word文件内容为空")
        
        return structured_content.strip()
    
    def _extract_structured_content(self, file_bytes: bytes) -> str:
        """同步结构化内容提取（在线程池中运行）"""
        import sys
        try:
            file_stream = io.BytesIO(file_bytes)
            doc = DocxDocument(file_stream)
            
            # 输出文档基本信息
            print(f"[WordParser] 文档段落总数: {len(doc.paragraphs)}", file=sys.stderr)
            print(f"[WordParser] 文档表格总数: {len(doc.tables)}", file=sys.stderr)
            
            # 1. 分析样式层级
            style_hierarchy = self._analyze_style_hierarchy(doc)
            print(f"[WordParser] 检测到的样式层级: {style_hierarchy}", file=sys.stderr)
            
            # 2. 提取结构化内容
            structured_blocks = self._extract_structured_blocks(doc, style_hierarchy)
            
            # 3. 构建Markdown格式
            markdown_content = self._build_markdown(structured_blocks)
            
            # 输出最终统计
            total_chars = len(markdown_content)
            total_words = len(markdown_content.split())
            print(f"[WordParser] 提取完成 - 总字符数: {total_chars}, 总词数: {total_words}", file=sys.stderr)
            
            return markdown_content
            
        except (ValueError, KeyError) as e:
            raise Exception(f"结构化Word解析数据错误: {str(e)}")
        except (OSError, IOError) as e:
            raise Exception(f"结构化Word解析IO错误: {str(e)}")
        except Exception as e:
            raise Exception(f"结构化Word解析失败: {str(e)}")
    
    def _analyze_style_hierarchy(self, doc) -> Dict[str, int]:
        """
        分析Word样式层级，推断标题级别
        
        算法思路:
        1. 识别内置标题样式 (Heading 1, Heading 2, ...)
        2. 分析字体大小和样式特征
        3. 构建样式名称到标题级别的映射
        
        Returns:
            Dict[str, int]: 样式名称 -> 标题级别的映射
        """
        style_hierarchy = {}
        
        # 内置标题样式映射
        builtin_headings = {
            'Heading 1': 1, 'Heading 2': 2, 'Heading 3': 3,
            'Heading 4': 4, 'Heading 5': 5, 'Heading 6': 6,
            '标题 1': 1, '标题 2': 2, '标题 3': 3,
            '标题 4': 4, '标题 5': 5, '标题 6': 6
        }
        
        # 收集所有段落样式信息
        style_info = {}
        
        for paragraph in doc.paragraphs:
            style_name = paragraph.style.name
            
            if style_name not in style_info:
                style_info[style_name] = {
                    'font_size': None,
                    'is_bold': False,
                    'count': 0,
                    'avg_length': 0
                }
            
            style_info[style_name]['count'] += 1
            
            # 分析字体特征
            if paragraph.runs:
                first_run = paragraph.runs[0]
                if first_run.font.size:
                    font_size = first_run.font.size.pt
                    if style_info[style_name]['font_size'] is None:
                        style_info[style_name]['font_size'] = font_size
                
                if first_run.font.bold:
                    style_info[style_name]['is_bold'] = True
            
            # 计算平均长度
            text_length = len(paragraph.text.strip())
            style_info[style_name]['avg_length'] = (
                style_info[style_name]['avg_length'] + text_length
            ) / 2
        
        # 1. 首先添加内置标题样式
        for style_name, level in builtin_headings.items():
            if style_name in style_info:
                style_hierarchy[style_name] = level
        
        # 2. 分析其他可能的标题样式
        # 标题特征：字体大、加粗、文本短、出现次数少
        for style_name, info in style_info.items():
            if style_name in style_hierarchy:
                continue
            
            # 启发式规则判断是否为标题
            is_heading = (
                info['is_bold'] and  # 加粗
                info['avg_length'] < 50 and  # 文本较短
                info['count'] < 20  # 出现次数不多
            )
            
            if is_heading:
                # 根据字体大小推断级别
                font_size = info.get('font_size', 12)
                if font_size >= 18:
                    level = 1
                elif font_size >= 16:
                    level = 2
                elif font_size >= 14:
                    level = 3
                else:
                    level = 4
                
                style_hierarchy[style_name] = level
        
        return style_hierarchy
    
    def _extract_structured_blocks(self, doc, style_hierarchy: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        提取结构化文档块
        
        Returns:
            List[Dict]: 结构化块列表
        """
        import sys
        
        structured_blocks = []
        empty_paragraphs = 0
        paragraphs_with_images = 0
        
        # 处理段落
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            style_name = paragraph.style.name
            
            # 检查段落是否包含图片
            has_images = False
            for run in paragraph.runs:
                if run._element.xpath('.//w:drawing') or run._element.xpath('.//w:pict'):
                    has_images = True
                    break
            
            if not text and not has_images:
                empty_paragraphs += 1
                continue
            
            if has_images and not text:
                # 只有图片的段落，记录但不添加
                paragraphs_with_images += 1
                continue
            
            # 判断是否为标题
            if style_name in style_hierarchy:
                structured_blocks.append({
                    "type": "heading",
                    "level": style_hierarchy[style_name],
                    "content": text
                })
            else:
                # 检查是否为列表项
                if self._is_list_paragraph(paragraph):
                    structured_blocks.append({
                        "type": "list_item",
                        "content": text
                    })
                else:
                    # 普通段落
                    structured_blocks.append({
                        "type": "paragraph",
                        "content": text
                    })
        
        # 处理表格
        for table in doc.tables:
            table_content = self._extract_table_content(table)
            if table_content:
                structured_blocks.append({
                    "type": "table",
                    "content": table_content
                })
        
        # 输出详细统计信息
        print(f"[WordParser] 空段落数: {empty_paragraphs}", file=sys.stderr)
        print(f"[WordParser] 只含图片段落数: {paragraphs_with_images}", file=sys.stderr)
        print(f"[WordParser] 段落总数: {len(doc.paragraphs)}", file=sys.stderr)
        print(f"[WordParser] 提取的块数: {len(structured_blocks)}", file=sys.stderr)
        
        return structured_blocks
    
    def _is_list_paragraph(self, paragraph) -> bool:
        """判断段落是否为列表项"""
        text = paragraph.text.strip()
        
        # 检查是否以列表标记开头
        list_markers = ['•', '·', '-', '*', '○', '□', '■']
        for marker in list_markers:
            if text.startswith(marker):
                return True
        
        # 检查是否以数字编号开头
        if text and text[0].isdigit():
            # 查找数字后的标点
            for i, char in enumerate(text):
                if char in '.、)':
                    return True
                elif not char.isdigit():
                    break
        
        return False
    
    def _extract_table_content(self, table) -> str:
        """提取表格内容并格式化为Markdown"""
        try:
            table_data = []
            
            for row in table.rows:
                row_data = []
                for cell in row.cells:
                    cell_text = cell.text.strip().replace('\n', ' ')
                    row_data.append(cell_text)
                table_data.append(row_data)
            
            if not table_data:
                return ""
            
            # 格式化为Markdown表格
            markdown_lines = []
            
            # 表头
            if table_data:
                header = table_data[0]
                markdown_lines.append("| " + " | ".join(header) + " |")
                markdown_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                
                # 表格内容
                for row in table_data[1:]:
                    markdown_lines.append("| " + " | ".join(row) + " |")
            
            return "\n".join(markdown_lines)
            
        except (ValueError, KeyError) as e:
            print(f"表格提取数据错误: {str(e)}")
            return ""
        except (OSError, IOError) as e:
            print(f"表格提取IO错误: {str(e)}")
            return ""
        except Exception as e:
            print(f"表格提取失败: {str(e)}")
            return ""
    
    def _build_markdown(self, structured_blocks: List[Dict[str, Any]]) -> str:
        """将结构化块转换为Markdown格式"""
        markdown_lines = []
        current_list_level = 0
        
        for block in structured_blocks:
            if block["type"] == "heading":
                # 标题：添加对应数量的#
                level = block["level"]
                heading_prefix = "#" * level
                markdown_lines.append(f"{heading_prefix} {block['content']}")
                markdown_lines.append("")  # 标题后空行
                current_list_level = 0
                
            elif block["type"] == "paragraph":
                # 段落：直接添加内容
                markdown_lines.append(block["content"])
                markdown_lines.append("")  # 段落后空行
                current_list_level = 0
                
            elif block["type"] == "list_item":
                # 列表项：添加Markdown列表格式
                content = block["content"]
                
                # 移除原有的列表标记
                for marker in ['•', '·', '-', '*', '○', '□', '■']:
                    if content.startswith(marker):
                        content = content[1:].strip()
                        break
                
                # 移除数字编号
                if content and content[0].isdigit():
                    for i, char in enumerate(content):
                        if char in '.、)':
                            content = content[i+1:].strip()
                            break
                
                markdown_lines.append(f"- {content}")
                current_list_level = 1
                
            elif block["type"] == "table":
                # 表格：添加表格内容
                if current_list_level > 0:
                    markdown_lines.append("")  # 列表后需要空行
                markdown_lines.append(block["content"])
                markdown_lines.append("")  # 表格后空行
                current_list_level = 0
        
        return "\n".join(markdown_lines)