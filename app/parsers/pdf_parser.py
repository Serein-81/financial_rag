# app/parsers/pdf_parser.py
import io
import asyncio
from pypdf import PdfReader
from .base_parser import FileParserStrategy


class PDFParser(FileParserStrategy):
    """PDF 文件解析器"""
    
    def get_supported_mime_types(self) -> list[str]:
        return ["application/pdf"]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析 PDF 文件，提取文本内容
        
        Args:
            file_bytes: PDF 文件的字节流
            
        Returns:
            str: 提取的文本内容
        """
        if not self.validate_file(file_bytes):
            raise ValueError("PDF 文件为空或无效")
        
        # PDF 解析是 CPU 密集型操作，放到线程池执行
        content = await asyncio.to_thread(self._extract_pdf_sync, file_bytes)
        
        if not content.strip():
            raise ValueError("PDF 文件内容为空")
        
        return content.strip()
    
    @staticmethod
    def _extract_pdf_sync(file_bytes: bytes) -> str:
        """同步 PDF 文本提取（在线程池中运行）"""
        content = ""
        file_stream = io.BytesIO(file_bytes)
        
        try:
            reader = PdfReader(file_stream)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        except Exception as e:
            raise Exception(f"PDF 解析失败: {str(e)}")
        
        return content
