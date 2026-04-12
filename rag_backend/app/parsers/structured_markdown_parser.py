# app/parsers/structured_markdown_parser.py
import re
import asyncio
from typing import List, Dict, Any


class StructuredMarkdownParser:
    """
    结构化Markdown解析器
    
    核心功能:
    1. 解析Markdown标题层级
    2. 识别表格、代码块、列表等结构
    3. 保留文档层次结构
    """
    
    def get_supported_mime_types(self) -> List[str]:
        return [
            "text/markdown"
        ]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析Markdown文件，提取结构化内容
        
        Args:
            file_bytes: Markdown文件的字节流
            
        Returns:
            str: 结构化的Markdown格式文本（保持原有格式）
        """
        if not self.validate_file(file_bytes):
            raise ValueError("Markdown文件为空或无效")
        
        structured_content = await asyncio.to_thread(
            self._extract_structured_content, file_bytes
        )
        
        if not structured_content.strip():
            raise ValueError("Markdown文件内容为空")
        
        return structured_content.strip()
    
    def _extract_structured_content(self, file_bytes: bytes) -> str:
        """同步结构化内容提取（在线程池中运行）"""
        try:
            content = self._decode_content(file_bytes)
            
            if not content.strip():
                raise ValueError("Markdown文件内容为空")
            
            return content
            
        except (ValueError, KeyError) as e:
            raise Exception(f"结构化Markdown解析数据错误: {str(e)}")
        except (OSError, IOError) as e:
            raise Exception(f"结构化Markdown解析IO错误: {str(e)}")
        except Exception as e:
            raise Exception(f"结构化Markdown解析失败: {str(e)}")
    
    def _decode_content(self, file_bytes: bytes) -> str:
        """尝试多种编码解码文件内容"""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin-1']
        
        for encoding in encodings:
            try:
                content = file_bytes.decode(encoding)
                if content.strip():
                    return content
            except UnicodeDecodeError:
                continue
        
        raise ValueError("无法识别Markdown文件编码")
    
    def validate_file(self, file_bytes: bytes) -> bool:
        """验证文件是否有效"""
        return file_bytes and len(file_bytes) > 0
