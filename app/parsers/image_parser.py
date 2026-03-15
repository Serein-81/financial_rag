# app/parsers/image_parser.py
from .base_parser import FileParserStrategy


class ImageParser(FileParserStrategy):
    """图片文件解析器（使用 OCR）"""
    
    def get_supported_mime_types(self) -> list[str]:
        return [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/bmp",
            "image/tiff"
        ]
    
    async def parse(self, file_bytes: bytes) -> str:
        """
        解析图片文件，使用 OCR 提取文本
        
        Args:
            file_bytes: 图片文件的字节流
            
        Returns:
            str: OCR 识别的文本内容
        """
        if not self.validate_file(file_bytes):
            raise ValueError("图片文件为空或无效")
        
        try:
            from app.services.ocr_service import ocr_service
            
            # 异步调用 OCR 服务
            content = await ocr_service.extract_text_from_image_bytes(file_bytes)
            
            if not content or content.strip() in ["[图片文件 - OCR功能未启用]", "[图片文件 - OCR识别失败]"]:
                raise ValueError("OCR 识别失败或未启用")
            
            return content.strip()
            
        except ImportError:
            raise Exception("OCR 依赖未安装，无法处理图片文件")
        except Exception as e:
            raise Exception(f"图片 OCR 识别失败: {str(e)}")
