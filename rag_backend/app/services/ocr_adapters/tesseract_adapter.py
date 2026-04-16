"""
Tesseract OCR适配器
封装现有的OCR逻辑
"""
from typing import Any, Dict, List, Tuple
import logging
import io
from PIL import Image
import pytesseract
from .base_ocr import BaseOCRAdapter


class TesseractAdapter(BaseOCRAdapter):
    """Tesseract OCR引擎适配器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.languages = self.config.get("languages", "chi_sim+eng")
        self._logger = logging.getLogger(__name__)
    
    @property
    def engine_name(self) -> str:
        return "Tesseract"
    
    @property
    def priority(self) -> int:
        return 50
    
    def check_health(self) -> Tuple[bool, str]:
        try:
            version = pytesseract.get_tesseract_version()
            langs = pytesseract.get_languages()
            
            has_chi = 'chi_sim' in langs
            has_eng = 'eng' in langs
            
            if has_chi and has_eng:
                return True, f"Tesseract {version} OK (chi_sim+eng)"
            else:
                missing = []
                if not has_chi:
                    missing.append("chi_sim")
                if not has_eng:
                    missing.append("eng")
                return False, f"缺少语言包: {', '.join(missing)}"
        except Exception as e:
            return False, f"Tesseract健康检查失败: {str(e)}"
    
    async def extract_text(self, file_path: str) -> str:
        import asyncio
        from pypdf import PdfReader
        
        def _sync_extract():
            content = []
            try:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content.append(text)
                return "\n\n".join(content)
            except Exception as e:
                self._logger.error(f"Tesseract PDF提取失败: {e}")
                return ""
        
        return await asyncio.to_thread(_sync_extract)
    
    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        import asyncio
        
        def _sync_ocr():
            try:
                image = Image.open(io.BytesIO(image_bytes))
                text = pytesseract.image_to_string(image, lang=self.languages)
                return text
            except Exception as e:
                self._logger.error(f"Tesseract图片OCR失败: {e}")
                return ""
        
        return await asyncio.to_thread(_sync_ocr)
    
    def extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """Tesseract不直接支持表格提取，返回空列表"""
        self._logger.info("Tesseract不直接支持表格提取，建议使用MinerU或PaddleOCR")
        return []
    
    def extract_layout(self, file_path: str) -> Dict[str, Any]:
        """基础布局分析"""
        import fitz
        
        try:
            doc = fitz.open(file_path)
            layout_info = {
                "total_pages": doc.page_count,
                "sections": []
            }
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                blocks = page.get_text("dict")["blocks"]
                
                for block in blocks:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                layout_info["sections"].append({
                                    "page": page_num + 1,
                                    "type": "text",
                                    "text": span["text"][:50],
                                    "bbox": span["bbox"]
                                })
            
            doc.close()
            return layout_info
        except Exception as e:
            self._logger.error(f"Tesseract布局分析失败: {e}")
            return {}
    
    async def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取结构化内容"""
        import asyncio
        from pypdf import PdfReader
        
        def _sync_extract():
            text_content = []
            tables = []
            
            try:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                
                return {
                    "text": "\n\n".join(text_content),
                    "tables": tables,
                    "sections": text_content,
                    "engine": self.engine_name
                }
            except Exception as e:
                self._logger.error(f"Tesseract结构化提取失败: {e}")
                return {
                    "text": "",
                    "tables": [],
                    "sections": [],
                    "engine": self.engine_name,
                    "error": str(e)
                }
        
        return await asyncio.to_thread(_sync_extract)
