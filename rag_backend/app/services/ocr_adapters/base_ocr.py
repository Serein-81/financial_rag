"""
OCR引擎抽象接口
定义统一的OCR处理标准
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional


class BaseOCRAdapter(ABC):
    """OCR适配器抽象基类"""
    
    @abstractmethod
    async def extract_text(self, file_path: str) -> str:
        """从文件提取文本"""
        pass
    
    @abstractmethod
    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """从图片提取文本"""
        pass
    
    @abstractmethod
    def check_health(self) -> Tuple[bool, str]:
        """检查服务健康状态"""
        pass
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """引擎名称"""
        pass
    
    @property
    def priority(self) -> int:
        """优先级（数字越小优先级越高）"""
        return 100
    
    @property
    def supported_formats(self) -> List[str]:
        """支持的格式"""
        return [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
    
    def extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """提取表格（可选实现）"""
        return []
    
    def extract_layout(self, file_path: str) -> Dict[str, Any]:
        """提取布局信息（可选实现）"""
        return {}
