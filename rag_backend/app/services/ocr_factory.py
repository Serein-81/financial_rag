"""
OCR工厂类
根据配置自动选择最优OCR引擎
"""
from typing import Dict, Any, List, Optional
import logging
import os
from .ocr_adapters.base_ocr import BaseOCRAdapter
from .ocr_adapters.mineru_adapter import MinerUAdapter
from .ocr_adapters.paddleocr_adapter import PaddleOCRAdapter
from .ocr_adapters.tesseract_adapter import TesseractAdapter
try:
    from .ocr_adapters.unstructured_adapter import UnstructuredAdapter
    HAS_UNSTRUCTURED = True
except ImportError:
    HAS_UNSTRUCTURED = False


class OCRFactory:
    """OCR引擎工厂"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._adapters: Dict[str, BaseOCRAdapter] = {}
        self._active_adapter: Optional[BaseOCRAdapter] = None
        self._logger = logging.getLogger(__name__)
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化所有适配器"""
        ocr_config = {
            "mineru_api": os.getenv("MINERU_API_KEY", ""),
            "mineru_output_dir": os.getenv("MINERU_OUTPUT_DIR", "/tmp/mineru_output"),
            "mineru_backend": os.getenv("MINERU_BACKEND", "pipeline"),
            "mineru_server_url": os.getenv("UNSTRUCTURED_API_URL", ""),
            "mineru_delete_output": os.getenv("MINERU_DELETE_OUTPUT", "1") == "1",
            "paddleocr_api_url": os.getenv("PADDLEOCR_API_URL", ""),
            "paddleocr_algorithm": os.getenv("PADDLEOCR_ALGORITHM", "PaddleOCR-VL"),
            "paddleocr_access_token": os.getenv("PADDLEOCR_ACCESS_TOKEN", ""),
            "unstructured_api_url": os.getenv("UNSTRUCTURED_API_URL", ""),
        }
        
        self._adapters["unstructured"] = UnstructuredAdapter(ocr_config)
        self._adapters["mineru"] = MinerUAdapter(ocr_config)
        self._adapters["paddleocr"] = PaddleOCRAdapter(ocr_config)
        self._adapters["tesseract"] = TesseractAdapter()
        
        self._select_best_adapter()
    
    def _select_best_adapter(self):
        """自动选择最健康的适配器（优先选择 docker-compose 中的服务）"""
        available_adapters = []
        
        for name, adapter in self._adapters.items():
            is_healthy, msg = adapter.check_health()
            if is_healthy:
                available_adapters.append((adapter.priority, name, adapter))
                self._logger.info(f"OCR引擎 {name} 可用: {msg}")
            else:
                self._logger.warning(f"OCR引擎 {name} 不可用: {msg}")
        
        if available_adapters:
            available_adapters.sort(key=lambda x: x[0])
            self._active_adapter = available_adapters[0][2]
            self._logger.info(f"自动选择OCR引擎: {self._active_adapter.engine_name}")
        else:
            self._logger.error("没有可用的 OCR 引擎！")
    
    @property
    def active_engine(self) -> Optional[str]:
        """获取当前活跃引擎名称"""
        return self._active_adapter.engine_name if self._active_adapter else None
    
    @property
    def available_engines(self) -> List[str]:
        """获取所有可用的引擎列表（按优先级排序）"""
        available = []
        priority_map = {
            'unstructured': 1,
            'mineru': 2,
            'paddleocr': 3,
            'tesseract': 4
        }
        
        for name, adapter in self._adapters.items():
            if adapter.check_health()[0]:
                available.append(name)
        
        # 按优先级排序，Unstructured API 优先
        available.sort(key=lambda x: priority_map.get(x, 99))
        return available
    
    def get_adapter(self, engine: str = None) -> Optional[BaseOCRAdapter]:
        """获取指定引擎的适配器"""
        if engine:
            return self._adapters.get(engine.lower())
        return self._active_adapter
    
    def set_preferred_engine(self, engine: str) -> bool:
        """手动设置首选引擎"""
        if engine.lower() in self._adapters:
            adapter = self._adapters[engine.lower()]
            is_healthy, msg = adapter.check_health()
            
            if is_healthy:
                self._active_adapter = adapter
                self._logger.info(f"已切换到OCR引擎: {adapter.engine_name}")
                return True
            else:
                self._logger.warning(f"引擎 {engine} 不可用: {msg}")
                return False
        else:
            self._logger.error(f"未知的OCR引擎: {engine}")
            return False
    
    async def extract_text(self, file_path: str, engine: str = None) -> str:
        """提取文本"""
        adapter = self.get_adapter(engine)
        if not adapter:
            raise RuntimeError("没有可用的OCR引擎")
        
        return await adapter.extract_text(file_path)
    
    async def extract_text_from_image(self, image_bytes: bytes, engine: str = None) -> str:
        """从图片提取文本"""
        adapter = self.get_adapter(engine)
        if not adapter:
            raise RuntimeError("没有可用的OCR引擎")
        
        return await adapter.extract_text_from_image(image_bytes)
    
    async def extract_structured(self, file_path: str, engine: str = None) -> Dict[str, Any]:
        """提取结构化内容"""
        adapter = self.get_adapter(engine)
        if not adapter:
            raise RuntimeError("没有可用的OCR引擎")
        
        if hasattr(adapter, 'extract_structured'):
            return await adapter.extract_structured(file_path)
        else:
            text = await adapter.extract_text(file_path)
            return {
                "text": text,
                "tables": [],
                "sections": [],
                "engine": adapter.engine_name
            }
    
    def extract_tables(self, file_path: str, engine: str = None) -> List[Dict[str, Any]]:
        """提取表格"""
        adapter = self.get_adapter(engine)
        if not adapter:
            raise RuntimeError("没有可用的OCR引擎")
        
        return adapter.extract_tables(file_path)
    
    def extract_layout(self, file_path: str, engine: str = None) -> Dict[str, Any]:
        """提取布局"""
        adapter = self.get_adapter(engine)
        if not adapter:
            raise RuntimeError("没有可用的OCR引擎")
        
        return adapter.extract_layout(file_path)
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有引擎的状态"""
        status = {
            "active_engine": self.active_engine,
            "engines": {}
        }
        
        for name, adapter in self._adapters.items():
            is_healthy, msg = adapter.check_health()
            status["engines"][name] = {
                "healthy": is_healthy,
                "message": msg,
                "priority": adapter.priority,
                "supported_formats": adapter.supported_formats
            }
        
        return status


ocr_factory = OCRFactory()
