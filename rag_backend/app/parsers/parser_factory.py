# app/parsers/parser_factory.py
from typing import Optional
from .base_parser import FileParserStrategy
from .text_parser import TextParser
from .image_parser import ImageParser
from .structured_pdf_parser import StructuredPDFParser
from .structured_word_parser import StructuredWordParser
from .structured_markdown_parser import StructuredMarkdownParser
from .structured_excel_parser import StructuredExcelParser


class FileParserFactory:
    """
    文件解析器工厂
    
    职责：
    1. 管理所有已注册的解析器
    2. 根据 MIME 类型返回对应的解析器
    3. 支持动态注册新的解析器
    
    设计模式：工厂模式 + 单例模式
    """
    
    # 类变量：存储所有已注册的解析器实例
    _parsers: dict[str, FileParserStrategy] = {}
    _initialized: bool = False
    
    @classmethod
    def _initialize(cls):
        """初始化默认解析器（懒加载）"""
        if cls._initialized:
            return
        
        # 注册基础解析器
        cls.register_parser(TextParser())
        cls.register_parser(ImageParser())
        
        # 注册结构化解析器（优先级更高，会覆盖基础解析器）
        cls.register_parser(StructuredPDFParser())
        cls.register_parser(StructuredWordParser())
        cls.register_parser(StructuredMarkdownParser())
        cls.register_parser(StructuredExcelParser())
        
        cls._initialized = True
    
    @classmethod
    def register_parser(cls, parser: FileParserStrategy):
        """
        注册新的解析器
        
        Args:
            parser: 实现了 FileParserStrategy 接口的解析器实例
        """
        for mime_type in parser.get_supported_mime_types():
            cls._parsers[mime_type.lower()] = parser
    
    @classmethod
    def get_parser(cls, file_type: str) -> Optional[FileParserStrategy]:
        """
        根据 MIME 类型获取对应的解析器
        
        Args:
            file_type: 文件的 MIME 类型（如 "application/pdf"）
            
        Returns:
            FileParserStrategy: 对应的解析器实例，如果不支持则返回 None
        """
        cls._initialize()  # 确保已初始化
        
        # 标准化 MIME 类型
        normalized_type = file_type.lower().strip()
        
        # 精确匹配
        if normalized_type in cls._parsers:
            return cls._parsers[normalized_type]
        
        # 模糊匹配（兼容旧代码）
        for mime_type, parser in cls._parsers.items():
            if mime_type in normalized_type or normalized_type in mime_type:
                return parser
        
        return None
    
    @classmethod
    def get_supported_types(cls) -> list[str]:
        """
        获取所有支持的 MIME 类型列表
        
        Returns:
            list[str]: 支持的 MIME 类型列表
        """
        cls._initialize()
        return list(cls._parsers.keys())
    
    @classmethod
    def is_supported(cls, file_type: str) -> bool:
        """
        检查是否支持指定的文件类型
        
        Args:
            file_type: 文件的 MIME 类型
            
        Returns:
            bool: 是否支持
        """
        return cls.get_parser(file_type) is not None
