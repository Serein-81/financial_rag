# app/parsers/pdf_parser.py
import io
import asyncio
from pypdf import PdfReader
from .base_parser import FileParserStrategy


class PDFParser(FileParserStrategy):
    """PDF 文件解析器（支持图片型/扫描件 PDF）"""
    
    def get_supported_mime_types(self) -> list[str]:
        return ["application/pdf"]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析 PDF 文件，提取文本内容
        
        支持：
        1. 文本型 PDF - 直接提取文本
        2. 图片型/扫描件 PDF - 使用 OCR 识别
        
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
        """同步 PDF 文本提取（在线程池中运行）- 支持 OCR 备选方案"""
        file_stream = io.BytesIO(file_bytes)
        
        # 方案1: 使用 PyMuPDF 提取文本（支持更好）
        try:
            import fitz
            doc = fitz.open(stream=file_stream, filetype="pdf")
            text_content = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # 检查是否为图片型 PDF（文本过少）
                if len(page_text.strip()) < 50:
                    # 该页面可能是扫描件，尝试 OCR
                    ocr_text = PDFParser._ocr_page_with_pymupdf(page)
                    text_content += f"\n[第 {page_num + 1} 页 OCR 内容]\n{ocr_text}\n"
                else:
                    text_content += page_text + "\n"
            
            doc.close()
            
            # 如果提取的文本太少，尝试整体 OCR
            if len(text_content.strip()) < 100:
                file_stream.seek(0)
                ocr_content = PDFParser._ocr_entire_pdf(file_bytes)
                if ocr_content:
                    return ocr_content
            
            return text_content
            
        except ImportError:
            # PyMuPDF 未安装，降级到 PyPDF2
            pass
        except (ValueError, KeyError) as e:
            print(f"PyMuPDF 提取数据错误: {str(e)}，尝试 PyPDF2")
        except (OSError, IOError) as e:
            print(f"PyMuPDF 提取IO错误: {str(e)}，尝试 PyPDF2")
        except Exception as e:
            print(f"PyMuPDF 提取失败: {str(e)}，尝试 PyPDF2")
        
        # 方案2: 使用 PyPDF2 提取文本
        try:
            file_stream.seek(0)
            reader = PdfReader(file_stream)
            text_content = ""
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n"
            
            # PyPDF2 提取的文本太少，尝试 OCR
            if len(text_content.strip()) < 100:
                ocr_content = PDFParser._ocr_entire_pdf(file_bytes)
                if ocr_content:
                    return ocr_content
            
            return text_content
            
        except (ValueError, KeyError) as e:
            raise Exception(f"PDF 解析数据错误: {str(e)}")
        except (OSError, IOError) as e:
            raise Exception(f"PDF 解析IO错误: {str(e)}")
        except Exception as e:
            raise Exception(f"PDF 解析失败: {str(e)}")
    
    @staticmethod
    def _ocr_page_with_pymupdf(page) -> str:
        """使用 PyMuPDF 对单个 PDF 页面进行 OCR"""
        try:
            from PIL import Image
            import pytesseract
            import io
            
            # 将页面转换为图片
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            
            # OCR
            image = Image.open(io.BytesIO(img_bytes))
            ocr_text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            
            return ocr_text if ocr_text.strip() else "[该页面 OCR 识别失败]"
            
        except ImportError as e:
            return f"[OCR 依赖未安装: {str(e)}]"
        except (ValueError, KeyError) as e:
            return f"[OCR 处理数据错误: {str(e)}]"
        except (OSError, IOError) as e:
            return f"[OCR 处理IO错误: {str(e)}]"
        except Exception as e:
            return f"[OCR 处理失败: {str(e)}]"
    
    @staticmethod
    def _ocr_entire_pdf(file_bytes: bytes) -> str:
        """对整个 PDF 进行 OCR 处理"""
        try:
            import fitz
            from PIL import Image
            import pytesseract
            import io
            
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
            all_ocr_text = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 将页面转换为高分辨率图片
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                
                # OCR
                image = Image.open(io.BytesIO(img_bytes))
                ocr_text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                
                if ocr_text.strip():
                    all_ocr_text.append(f"[第 {page_num + 1} 页]\n{ocr_text}")
                else:
                    all_ocr_text.append(f"[第 {page_num + 1} 页] - 未识别到文本")
            
            doc.close()
            
            return "\n\n".join(all_ocr_text)
            
        except ImportError as e:
            print(f"OCR 依赖未安装: {str(e)}")
            return ""
        except (ValueError, KeyError) as e:
            print(f"PDF OCR 处理数据错误: {str(e)}")
            return ""
        except (OSError, IOError) as e:
            print(f"PDF OCR 处理IO错误: {str(e)}")
            return ""
        except Exception as e:
            print(f"PDF OCR 处理失败: {str(e)}")
            return ""
