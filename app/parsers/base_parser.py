# app/parsers/base_parser.py
from abc import ABC, abstractmethod


class FileParserStrategy(ABC):
    """
    文件解析策略接口
    
    所有具体的文件解析器都必须实现此接口
    符合开闭原则：对扩展开放，对修改关闭
    """
    
    @abstractmethod
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析文件内容，提取文本
        
        Args:
            file_bytes: 文件的字节流
            
        Returns:
            str: 提取的文本内容
            
        Raises:
            Exception: 解析失败时抛出异常
        """
        pass
    
    @abstractmethod
    def get_supported_mime_types(self) -> list[str]:
        """
        返回该解析器支持的 MIME 类型列表
        
        Returns:
            list[str]: MIME 类型列表
        """
        pass
    
    def validate_file(self, file_bytes: bytes) -> bool:
        """
        验证文件是否有效（可选实现）
        
        Args:
            file_bytes: 文件的字节流
            
        Returns:
            bool: 文件是否有效
        """
        return len(file_bytes) > 0
