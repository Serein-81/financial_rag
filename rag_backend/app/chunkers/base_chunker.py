# app/chunkers/base_chunker.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ChunkResult:
    """
    切块结果数据类
    
    包含切片内容和丰富的元数据信息
    """
    content: str                    # 切片文本内容
    start: int                      # 在原文中的起始位置
    end: int                        # 在原文中的结束位置
    tokens: int                     # Token 数量估算
    heading_path: str = None        # 标题路径(如: "第一章 > 1.1节")
    metadata: Dict[str, Any] = None # 额外的元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "content": self.content,
            "start": self.start,
            "end": self.end,
            "tokens": self.tokens,
            "heading_path": self.heading_path,
            "metadata": self.metadata or {}
        }


class ChunkStrategy(ABC):
    """
    文本切块策略接口
    
    所有具体的切块策略都必须实现此接口
    """
    
    @abstractmethod
    def chunk(
        self, 
        text: str, 
        chunk_tokens: int = 500, 
        overlap_tokens: int = 50
    ) -> List[ChunkResult]:
        """
        将文本切分为多个块
        
        Args:
            text: 待切分的文本
            chunk_tokens: 每个切片的目标 Token 数量
            overlap_tokens: 切片之间的重叠 Token 数量
            
        Returns:
            List[ChunkResult]: 切块结果列表
        """
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """
        返回该策略支持的文档类型
        
        Returns:
            List[str]: 支持的文档类型标识列表
        """
        pass
    
    @staticmethod
    def approx_token_len(text: str) -> int:
        """
        估算文本的 Token 长度
        
        规则:
        - CJK 字符(中日韩): 1 字符 ≈ 1 token
        - 非 CJK 字符: 按空格分割计数
        
        Args:
            text: 待估算的文本
            
        Returns:
            int: 估算的 Token 数量
        """
        if not text:
            return 0
        
        # 统计 CJK 字符数量
        cjk_count = sum(1 for ch in text if ChunkStrategy._is_cjk(ch))
        
        # 统计非 CJK Token 数量
        non_cjk_tokens = len([t for t in text.split() if t])
        
        return cjk_count + non_cjk_tokens
    
    @staticmethod
    def _is_cjk(ch: str) -> bool:
        """
        判断字符是否为 CJK 字符
        
        CJK Unicode 范围:
        - 0x4E00-0x9FFF: 中日韩统一表意文字
        - 0x3400-0x4DBF: 中日韩统一表意文字扩展A
        - 0x20000-0x2A6DF: 中日韩统一表意文字扩展B
        - 0x2A700-0x2B73F: 中日韩统一表意文字扩展C
        - 0x2B740-0x2B81F: 中日韩统一表意文字扩展D
        - 0x2B820-0x2CEAF: 中日韩统一表意文字扩展E
        - 0xF900-0xFAFF: 中日韩兼容表意文字
        - 0x2F800-0x2FA1F: 中日韩兼容表意文字补充
        """
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF or      # 基本汉字
            0x3400 <= code <= 0x4DBF or      # 扩展A
            0x20000 <= code <= 0x2A6DF or    # 扩展B
            0x2A700 <= code <= 0x2B73F or    # 扩展C
            0x2B740 <= code <= 0x2B81F or    # 扩展D
            0x2B820 <= code <= 0x2CEAF or    # 扩展E
            0xF900 <= code <= 0xFAFF or      # 兼容汉字
            0x2F800 <= code <= 0x2FA1F       # 兼容补充
        )
