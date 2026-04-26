"""
MinerU OCR适配器
使用 MinerU CLI 进行 PDF 解析（兼容 MinerU 2.7.6+）
"""
from typing import Any, Dict, List, Tuple
import logging
import os
import json
import tempfile
import subprocess
import asyncio
from pathlib import Path
from .base_ocr import BaseOCRAdapter


class MinerUAdapter(BaseOCRAdapter):
    """MinerU OCR引擎适配器（MinerU 2.7.6+ CLI版本）"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.output_dir = self.config.get("mineru_output_dir", "/tmp/mineru_output")
        self.backend_type = self.config.get("mineru_backend", "hybrid-auto-engine")
        self._logger = logging.getLogger(__name__)
    
    @property
    def engine_name(self) -> str:
        return "MinerU"
    
    @property
    def priority(self) -> int:
        return 10
    
    def check_health(self) -> Tuple[bool, str]:
        """检查 MinerU CLI 是否可用"""
        try:
            result = subprocess.run(
                ['mineru', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 or 'mineru' in result.stdout.lower():
                return True, "MinerU CLI 可用"
            else:
                return False, "MinerU CLI 不可用"
        except FileNotFoundError:
            return False, "mineru 命令未找到，请安装: pip install git+https://github.com/opendatalab/MinerU.git"
        except Exception as e:
            return False, f"MinerU 检查失败: {str(e)}"
    
    def _run_mineru_cli(self, pdf_path: str, output_dir: str) -> Dict[str, Any]:
        """运行 mineru CLI 命令"""
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = [
            'mineru',
            '--pdf-path', pdf_path,
            '--output-dir', output_dir,
            '--backend', self.backend_type,
            '--output-format', 'json'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"MinerU CLI 失败: {result.stderr}")
            
            # 查找输出的 JSON 文件
            json_files = list(Path(output_dir).glob('*.json'))
            if json_files:
                with open(json_files[0], 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return {}
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("MinerU 处理超时")
        except Exception as e:
            raise RuntimeError(f"MinerU 执行失败: {e}")
    
    async def extract_text(self, file_path: str) -> str:
        """使用 CLI 提取文本"""
        
        def _sync_extract():
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    result = self._run_mineru_cli(file_path, tmp_dir)
                    
                    content_parts = []
                    
                    if isinstance(result, dict):
                        if "text" in result:
                            content_parts.append(result["text"])
                        if "markdown" in result:
                            content_parts.append(result["markdown"])
                        if "sections" in result:
                            for section in result["sections"]:
                                if isinstance(section, dict) and "text" in section:
                                    content_parts.append(section["text"])
                    
                    return "\n\n".join(filter(None, content_parts))
                    
            except Exception as e:
                self._logger.error(f"MinerU 文本提取失败: {e}")
                return ""
        
        return await asyncio.to_thread(_sync_extract)
    
    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """图片 OCR - 使用 Tesseract"""
        import tempfile
        import asyncio
        from PIL import Image
        import pytesseract
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            
            try:
                image = Image.open(tmp_path)
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                return text
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        except Exception as e:
            self._logger.error(f"MinerU 图片 OCR 失败: {e}")
            raise RuntimeError(f"图片 OCR 失败: {e}")
    
    async def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取结构化内容"""
        
        def _sync_extract():
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = self._run_mineru_cli(file_path, tmp_dir)
                
                return {
                    "text": result.get("text", ""),
                    "markdown": result.get("markdown", ""),
                    "tables": result.get("table_bodies", []),
                    "sections": result.get("sections", []),
                    "images": result.get("image_paths", []),
                    "engine": self.engine_name
                }
        
        return await asyncio.to_thread(_sync_extract)
    
    def extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """提取表格"""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = self._run_mineru_cli(file_path, tmp_dir)
                return result.get("table_bodies", [])
        except Exception as e:
            self._logger.error(f"MinerU 表格提取失败: {e}")
            return []
    
    def extract_layout(self, file_path: str) -> Dict[str, Any]:
        """提取布局信息"""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = self._run_mineru_cli(file_path, tmp_dir)
                
                sections = result.get("sections", [])
                
                layout_info = {
                    "total_pages": len(sections),
                    "sections": []
                }
                
                for section in sections:
                    if isinstance(section, dict):
                        layout_info["sections"].append({
                            "page": section.get("page", 0),
                            "type": section.get("type", "unknown"),
                            "bbox": section.get("bbox", [])
                        })
                
                return layout_info
        except Exception as e:
            self._logger.error(f"MinerU 布局分析失败: {e}")
            return {}
