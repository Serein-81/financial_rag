# app/parsers/__init__.py
"""
文件解析器模块
使用策略模式 + 工厂模式实现可扩展的文件解析架构
"""

from .base_parser import FileParserStrategy
from .parser_factory import FileParserFactory
# 为了向后兼容，添加别名
ParserFactory = FileParserFactory
from .pdf_parser import PDFParser
from .word_parser import WordParser
from .text_parser import TextParser
from .image_parser import ImageParser
from .excel_parser import ExcelParser
from .structured_pdf_parser import StructuredPDFParser
from .structured_word_parser import StructuredWordParser

__all__ = [
    'FileParserStrategy',
    'FileParserFactory',
    'ParserFactory',  # 别名
    'PDFParser',
    'WordParser',
    'TextParser',
    'ImageParser',
    'ExcelParser',
    'StructuredPDFParser',
    'StructuredWordParser'
]
