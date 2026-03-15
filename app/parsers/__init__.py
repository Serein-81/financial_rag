# app/parsers/__init__.py
"""
文件解析器模块
使用策略模式 + 工厂模式实现可扩展的文件解析架构
"""

from .base_parser import FileParserStrategy
from .parser_factory import FileParserFactory
from .pdf_parser import PDFParser
from .word_parser import WordParser
from .text_parser import TextParser
from .image_parser import ImageParser

__all__ = [
    'FileParserStrategy',
    'FileParserFactory',
    'PDFParser',
    'WordParser',
    'TextParser',
    'ImageParser'
]
