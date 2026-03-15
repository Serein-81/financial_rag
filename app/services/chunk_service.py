# app/services/chunk_service.py
"""
文本切块服务 - 重构版
使用策略模式支持多种切块策略
"""
from typing import List, Union
from app.chunkers import ChunkStrategyFactory, ChunkResult


class ChunkService:
    """
    文本切块服务
    
    职责:
    1. 根据文档类型选择合适的切块策略
    2. 提供统一的切块接口
    3. 支持向后兼容(返回纯文本列表)
    """
    
    def __init__(self):
        self.strategy_factory = ChunkStrategyFactory
    
    def split_text(
        self, 
        text: str, 
        doc_type: str = "text",
        chunk_tokens: int = 500,
        overlap_tokens: int = 50,
        return_metadata: bool = False
    ) -> Union[List[str], List[ChunkResult]]:
        """
        切分文本
        
        Args:
            text: 待切分的文本
            doc_type: 文档类型 ("markdown", "text" 等)
            chunk_tokens: 每个切片的目标 Token 数量
            overlap_tokens: 切片之间的重叠 Token 数量
            return_metadata: 是否返回元数据(True=ChunkResult对象, False=纯文本)
            
        Returns:
            List[str] 或 List[ChunkResult]: 切块结果
        """
        if not text:
            return []
        
        # 1. 获取对应的切块策略
        strategy = self.strategy_factory.get_strategy(doc_type)
        
        # 2. 执行切块
        chunk_results = strategy.chunk(text, chunk_tokens, overlap_tokens)
        
        # 3. 根据参数决定返回格式
        if return_metadata:
            return chunk_results
        else:
            # 向后兼容: 只返回文本内容
            return [chunk.content for chunk in chunk_results]
    
    def split_text_simple(self, text: str) -> List[str]:
        """
        简化版切块方法(向后兼容)
        
        使用默认参数,只返回文本列表
        """
        return self.split_text(
            text=text,
            doc_type="text",
            chunk_tokens=500,
            overlap_tokens=50,
            return_metadata=False
        )
    
    def get_supported_types(self) -> List[str]:
        """
        获取所有支持的文档类型
        
        Returns:
            List[str]: 支持的文档类型列表
        """
        return self.strategy_factory.get_supported_types()


# 实例化单例，供外部调用
chunk_service = ChunkService()