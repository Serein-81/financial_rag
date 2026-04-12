# app/parsers/text_parser.py
from .base_parser import FileParserStrategy


class TextParser(FileParserStrategy):
    """纯文本文件解析器"""
    
    def get_supported_mime_types(self) -> list[str]:
        return [
            "text/plain",
            "text/csv"
        ]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析纯文本文件
        
        Args:
            file_bytes: 文本文件的字节流
            
        Returns:
            str: 文本内容
        """
        if not self.validate_file(file_bytes):
            raise ValueError("文本文件为空或无效")
        
        try:
            # 尝试多种编码
            for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                try:
                    content = file_bytes.decode(encoding)
                    if content.strip():
                        return content.strip()
                except UnicodeDecodeError:
                    continue
            
            raise ValueError("无法识别文本文件编码")
            
        except Exception as e:
            raise Exception(f"文本解析失败: {str(e)}")
