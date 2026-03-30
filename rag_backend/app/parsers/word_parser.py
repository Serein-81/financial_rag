# app/parsers/word_parser.py
import io
import asyncio
from docx import Document as DocxDocument
from .base_parser import FileParserStrategy


class WordParser(FileParserStrategy):
    """Word 文件解析器"""
    
    def get_supported_mime_types(self) -> list[str]:
        return [
            "application/msword",  # .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # .docx
        ]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析 Word 文件，提取文本内容
        
        Args:
            file_bytes: Word 文件的字节流
            
        Returns:
            str: 提取的文本内容
        """
        if not self.validate_file(file_bytes):
            raise ValueError("Word 文件为空或无效")
        
        # Word 解析是 CPU 密集型操作，放到线程池执行
        content = await asyncio.to_thread(self._extract_word_sync, file_bytes)
        
        if not content.strip():
            raise ValueError("Word 文件内容为空")
        
        return content.strip()
    
    @staticmethod
    def _extract_word_sync(file_bytes: bytes) -> str:
        """同步 Word 文本提取（在线程池中运行）"""
        content = ""
        file_stream = io.BytesIO(file_bytes)
        
        try:
            doc = DocxDocument(file_stream)
            for para in doc.paragraphs:
                content += para.text + "\n"
        except Exception as e:
            raise Exception(f"Word 解析失败: {str(e)}")
        
        return content
