"""
OCR适配器模块

提供统一的OCR引擎接口，支持MinerU、PaddleOCR和Tesseract
"""
from .base_ocr import BaseOCRAdapter
from .tesseract_adapter import TesseractAdapter
from .mineru_adapter import MinerUAdapter
from .paddleocr_adapter import PaddleOCRAdapter

__all__ = [
    "BaseOCRAdapter",
    "TesseractAdapter",
    "MinerUAdapter",
    "PaddleOCRAdapter",
]
