"""
PaddleOCR适配器
支持远程API和本地推理
"""
from typing import Any, Dict, List, Tuple
import logging
import os
import io
from PIL import Image
from .base_ocr import BaseOCRAdapter


class PaddleOCRAdapter(BaseOCRAdapter):
    """PaddleOCR引擎适配器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_url = self.config.get("paddleocr_api_url", "")
        self.algorithm = self.config.get("paddleocr_algorithm", "PaddleOCR-VL")
        self.access_token = self.config.get("paddleocr_access_token", "")
        
        self._parser = None
        self._logger = logging.getLogger(__name__)
    
    @property
    def engine_name(self) -> str:
        return "PaddleOCR"
    
    @property
    def priority(self) -> int:
        return 20
    
    def check_health(self) -> Tuple[bool, str]:
        try:
            from deepdoc.parser.paddleocr_parser import PaddleOCRParser
            
            parser = PaddleOCRParser(
                api_url=self.api_url,
                access_token=self.access_token,
                algorithm=self.algorithm
            )
            
            return parser.check_installation()
        except ImportError:
            return False, "PaddleOCR未安装: pip install paddleocr deepdoc"
        except Exception as e:
            return False, f"PaddleOCR健康检查失败: {str(e)}"
    
    def _get_parser(self):
        """延迟初始化解析器"""
        if self._parser is None:
            from deepdoc.parser.paddleocr_parser import PaddleOCRParser
            self._parser = PaddleOCRParser(
                api_url=self.api_url,
                access_token=self.access_token,
                algorithm=self.algorithm
            )
        return self._parser
    
    async def extract_text(self, file_path: str) -> str:
        import asyncio
        
        def _sync_extract():
            parser = self._get_parser()
            
            sections, tables = parser.parse_pdf(
                filepath=file_path
            )
            
            content_parts = []
            
            for section in sections:
                content_parts.append(section.get("text", ""))
            
            for table in tables:
                content_parts.append(table.get("text", ""))
            
            return "\n\n".join(filter(None, content_parts))
        
        return await asyncio.to_thread(_sync_extract)
    
    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        import asyncio
        
        def _sync_ocr():
            try:
                image = Image.open(io.BytesIO(image_bytes))
                
                if self.api_url:
                    return self._ocr_via_api(image)
                else:
                    return self._ocr_via_local(image)
            except Exception as e:
                self._logger.warning(f"PaddleOCR图片处理失败: {e}")
                return ""
        
        return await asyncio.to_thread(_sync_ocr)
    
    def _ocr_via_api(self, image: Image.Image) -> str:
        """通过API调用进行OCR"""
        import base64
        import json
        import urllib.request
        
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        payload = json.dumps({
            "image": img_base64,
            "algorithm": self.algorithm
        }).encode("utf-8")
        
        req = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}" if self.access_token else ""
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                return result.get("text", "")
        except Exception as e:
            self._logger.error(f"PaddleOCR API调用失败: {e}")
            return self._ocr_via_local(image)
    
    def _ocr_via_local(self, image: Image.Image) -> str:
        """使用本地Tesseract作为降级方案"""
        import pytesseract
        
        return pytesseract.image_to_string(image, lang='chi_sim+eng')
    
    def extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """提取表格"""
        try:
            parser = self._get_parser()
            _, tables = parser.parse_pdf(filepath=file_path)
            return tables
        except Exception as e:
            self._logger.error(f"PaddleOCR表格提取失败: {e}")
            return []
    
    def extract_layout(self, file_path: str) -> Dict[str, Any]:
        """提取布局信息"""
        try:
            parser = self._get_parser()
            sections, _ = parser.parse_pdf(filepath=file_path)
            
            layout_info = {
                "total_pages": len(sections),
                "sections": []
            }
            
            for section in sections:
                layout_info["sections"].append({
                    "page": section.get("page"),
                    "type": section.get("type", "unknown"),
                    "bbox": section.get("bbox", [])
                })
            
            return layout_info
        except Exception as e:
            self._logger.error(f"PaddleOCR布局分析失败: {e}")
            return {}
    
    async def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取结构化内容"""
        import asyncio
        
        def _sync_extract():
            parser = self._get_parser()
            
            sections, tables = parser.parse_pdf(filepath=file_path)
            
            return {
                "text": "\n\n".join([s.get("text", "") for s in sections]),
                "tables": tables,
                "sections": sections,
                "engine": self.engine_name
            }
        
        return await asyncio.to_thread(_sync_extract)
