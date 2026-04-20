"""
OCR 文档识别服务

支持 PDF、图片等文档的文字识别
"""

from typing import List, Dict, Any
import io
from pathlib import Path


class OCRService:
    """
    OCR 服务
    
    支持：
    - PDF 文档
    - 图片（PNG, JPG, JPEG）
    - 扫描件
    """
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff']
    
    async def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        从 PDF 提取文本
        
        Returns:
            [{"page": 1, "text": "...", "images": [...]}, ...]
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("请安装 PyMuPDF: pip install pymupdf")
        
        pages = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # 提取文本
            text = page.get_text()
            
            # 提取图片
            images = []
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                
                # 对图片进行 OCR
                image_bytes = base_image["image"]
                ocr_text = await self._ocr_image_bytes(image_bytes)
                
                images.append({
                    "index": img_index,
                    "ocr_text": ocr_text
                })
            
            pages.append({
                "page": page_num + 1,
                "text": text,
                "images": images
            })
        
        doc.close()
        return pages
    
    async def extract_text_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        从图片字节流提取文本（异步方法）
        
        Args:
            image_bytes: 图片文件的字节数据
            
        Returns:
            str: 识别出的文本内容
        """
        try:
            from PIL import Image
            import pytesseract
            import asyncio
        except ImportError:
            raise ImportError("请安装: pip install pillow pytesseract")
        
        # OCR是CPU密集型操作，放到线程池执行避免阻塞事件循环
        def _ocr_sync():
            image = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(image, lang='chi_sim+eng')
        
        # 在线程池中异步执行OCR
        text = await asyncio.to_thread(_ocr_sync)
        return text
    
    async def extract_text_from_image(self, image_path: str) -> str:
        """
        从图片文件提取文本（异步方法）
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            str: 识别出的文本内容
        """
        try:
            from PIL import Image
            import pytesseract
            import asyncio
        except ImportError:
            raise ImportError("请安装: pip install pillow pytesseract")
        
        # OCR是CPU密集型操作，放到线程池执行
        def _ocr_sync():
            image = Image.open(image_path)
            return pytesseract.image_to_string(image, lang='chi_sim+eng')
        
        text = await asyncio.to_thread(_ocr_sync)
        return text
    
    async def _ocr_image_bytes(self, image_bytes: bytes) -> str:
        """对图片字节进行 OCR"""
        try:
            from PIL import Image
            import pytesseract
            import io
        except ImportError:
            return ""
        
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text
        except Exception:
            return ""
    
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        处理文档（自动识别格式）
        
        Returns:
            {
                "file_name": "...",
                "file_type": "pdf/image",
                "doc_category": "invoice/contract/bank_statement/...",  # 新增
                "total_pages": 10,
                "content": "完整文本",
                "pages": [...]
            }
        """
        file_path = Path(file_path)
        file_ext = file_path.suffix.lower()
        
        if file_ext not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {file_ext}")
        
        result = {
            "file_name": file_path.name,
            "file_type": "",
            "doc_category": "unknown",  # 新增
            "total_pages": 0,
            "content": "",
            "pages": []
        }
        
        # PDF 处理
        if file_ext == '.pdf':
            result["file_type"] = "pdf"
            pages = await self.extract_text_from_pdf(str(file_path))
            result["pages"] = pages
            result["total_pages"] = len(pages)
            
            # 合并所有文本
            all_text = []
            for page in pages:
                all_text.append(page["text"])
                # 添加图片 OCR 文本
                for img in page["images"]:
                    if img["ocr_text"]:
                        all_text.append(img["ocr_text"])
            
            result["content"] = "\n\n".join(all_text)
        
        # 图片处理
        else:
            result["file_type"] = "image"
            text = await self.extract_text_from_image(str(file_path))
            result["content"] = text
            result["total_pages"] = 1
            result["pages"] = [{"page": 1, "text": text}]
        
        # 🎯 新增: 文档分类
        if result["content"]:
            result["doc_category"] = self._classify_ocr_document(result["content"])
        
        return result
    
    def _classify_ocr_document(self, text: str) -> str:
        """
        分类OCR识别的文档类型
        
        Args:
            text: OCR识别的文本内容
            
        Returns:
            str: 文档类型 (invoice/contract/bank_statement/id_card/business_license/unknown)
        """
        text_lower = text.lower()
        
        # 发票识别
        invoice_keywords = ['发票', '税号', '增值税', '纳税人识别号', '价税合计', '开票日期']
        if any(keyword in text for keyword in invoice_keywords):
            return 'invoice'
        
        # 合同识别
        contract_keywords = ['合同', '甲方', '乙方', '协议', '签订日期', '违约责任', '争议解决']
        if any(keyword in text for keyword in contract_keywords):
            return 'contract'
        
        # 银行流水识别
        bank_keywords = ['银行', '账号', '余额', '交易', '借方', '贷方', '流水', '对账单']
        if any(keyword in text for keyword in bank_keywords):
            return 'bank_statement'
        
        # 身份证识别
        id_keywords = ['居民身份证', '公民身份', '出生', '住址', '签发机关']
        if any(keyword in text for keyword in id_keywords):
            return 'id_card'
        
        # 营业执照识别
        license_keywords = ['营业执照', '统一社会信用代码', '注册资本', '法定代表人', '经营范围']
        if any(keyword in text for keyword in license_keywords):
            return 'business_license'
        
        # 财务报表识别
        financial_keywords = ['资产负债表', '利润表', '现金流量表', '所有者权益', '营业收入', '净利润']
        if any(keyword in text for keyword in financial_keywords):
            return 'financial_statement'
        
        # 税务申报表识别
        tax_keywords = ['税务申报', '应纳税额', '税款所属期', '申报表', '增值税纳税申报']
        if any(keyword in text for keyword in tax_keywords):
            return 'tax_return'
        
        return 'unknown'
    
    async def extract_structured_data(self, text: str) -> Dict[str, Any]:
        """
        从文本提取结构化数据（使用 LLM）
        
        可以提取：
        - 表格
        - 列表
        - 关键信息
        """
        from app.services.llm_service import llm_service
        
        prompt = f"""
从以下文本中提取结构化信息，返回 JSON 格式：

文本：
{text[:2000]}  # 限制长度

请提取：
1. 关键实体（人名、地名、组织等）
2. 重要日期和数字
3. 主要观点或结论

返回格式：
{{
    "entities": ["实体1", "实体2", ...],
    "dates": ["日期1", "日期2", ...],
    "numbers": ["数字1", "数字2", ...],
    "key_points": ["观点1", "观点2", ...]
}}
"""
        
        response = await llm_service.get_answer(prompt, [], [])
        
        try:
            import re
            import json
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return {
            "entities": [],
            "dates": [],
            "numbers": [],
            "key_points": []
        }


# 全局实例
ocr_service = OCRService()
