# app/chunkers/chunk_factory.py
from .base_chunker import ChunkStrategy
from .markdown_chunker import MarkdownChunkStrategy
from .plain_text_chunker import PlainTextChunkStrategy
from .structured_document_chunker import StructuredDocumentChunker


class ChunkStrategyFactory:
    """
    切块策略工厂
    
    职责:
    1. 管理所有已注册的切块策略
    2. 根据文档类型返回对应的策略
    3. 支持动态注册新的策略
    """
    
    # 类变量:存储所有已注册的策略实例
    _strategies: dict[str, ChunkStrategy] = {}
    _initialized: bool = False
    
    @classmethod
    def _initialize(cls):
        """初始化默认策略(懒加载)"""
        if cls._initialized:
            return
        
        # 注册基础策略
        cls.register_strategy(MarkdownChunkStrategy())
        cls.register_strategy(PlainTextChunkStrategy())
        
        # 注册结构化策略
        cls.register_strategy(StructuredDocumentChunker())
        
        cls._initialized = True
    
    @classmethod
    def register_strategy(cls, strategy: ChunkStrategy):
        """
        注册新的切块策略
        
        Args:
            strategy: 实现了 ChunkStrategy 接口的策略实例
        """
        for doc_type in strategy.get_supported_types():
            cls._strategies[doc_type.lower()] = strategy
    
    @classmethod
    def get_strategy(cls, doc_type: str) -> ChunkStrategy:
        """
        根据文档类型获取对应的切块策略
        
        Args:
            doc_type: 文档类型标识(如 "markdown", "text")
            
        Returns:
            ChunkStrategy: 对应的策略实例,如果不支持则返回默认策略
        """
        cls._initialize()  # 确保已初始化
        
        # 标准化文档类型
        normalized_type = doc_type.lower().strip()
        
        # 精确匹配
        if normalized_type in cls._strategies:
            return cls._strategies[normalized_type]
        
        # 模糊匹配
        for key, strategy in cls._strategies.items():
            if key in normalized_type or normalized_type in key:
                return cls._strategies[key]
        
        # 返回默认策略(纯文本)
        return cls._strategies.get("default", PlainTextChunkStrategy())
    
    @classmethod
    def get_supported_types(cls) -> list[str]:
        """
        获取所有支持的文档类型列表
        
        Returns:
            list[str]: 支持的文档类型列表
        """
        cls._initialize()
        return list(cls._strategies.keys())
    
    @classmethod
    def is_supported(cls, doc_type: str) -> bool:
        """
        检查是否支持指定的文档类型
        
        Args:
            doc_type: 文档类型标识
            
        Returns:
            bool: 是否支持
        """
        cls._initialize()
        normalized_type = doc_type.lower().strip()
        return normalized_type in cls._strategies
