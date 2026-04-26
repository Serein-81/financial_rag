"""
Unstructured API OCR 适配器
支持 YOLOX 和 Detectron2 版面分析模型
"""
from typing import Any, Dict, List, Tuple
import logging
import httpx
import io
import os
from PIL import Image
from .base_ocr import BaseOCRAdapter


class UnstructuredAdapter(BaseOCRAdapter):
    """Unstructured API OCR 引擎适配器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_url = self.config.get("unstructured_api_url", "http://unstructured-api:8000")
        self.logger = logging.getLogger(__name__)
    
    @property
    def engine_name(self) -> str:
        return "Unstructured API"
    
    @property
    def priority(self) -> int:
        return 10
    
    @property
    def supported_formats(self) -> List[str]:
        return [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
    
    def check_health(self) -> Tuple[bool, str]:
        try:
            import httpx
            
            # 尝试多个可能的健康检查端点
            health_endpoints = [
                ("/redoc", 200),  # FastAPI 自动文档
                ("/general/v0/general", [200, 422]),  # 主要 API 端点（422 表示端点存在但请求格式需要调整）
                ("/docs", 200),  # Swagger 文档
            ]
            
            for endpoint, expected_status in health_endpoints:
                try:
                    response = httpx.get(f"{self.api_url}{endpoint}", timeout=5.0)
                    if isinstance(expected_status, list):
                        if response.status_code in expected_status:
                            return True, f"Unstructured API 可用（{endpoint}）: {self.api_url}"
                    elif response.status_code == expected_status:
                        return True, f"Unstructured API 可用（{endpoint}）: {self.api_url}"
                except:
                    continue
            
            return False, f"Unstructured API 所有端点都不可用: {self.api_url}"
            
        except httpx.ConnectError:
            return False, f"Unstructured API 连接失败: {self.api_url} 未运行（需要启动 --profile heavy）"
        except Exception as e:
            return False, f"Unstructured API 检查失败: {str(e)}"
    
    async def extract_text(self, file_path: str) -> str:
        """从文件路径提取文本"""
        import httpx
        import time
        from fastapi import HTTPException
        
        step_start = time.time()
        self.logger.info(f"[Unstructured] 开始提取文件: {file_path}")
        
        try:
            file_size = os.path.getsize(file_path)
            self.logger.info(f"[Unstructured] 文件大小: {file_size} bytes ({file_size/1024:.2f} KB)")
            
            # 尝试不同的策略，从最稳定到最高质量
            strategies = ["auto", "fast", "hi_res"]
            
            for strategy in strategies:
                try:
                    self.logger.info(f"[Unstructured] 尝试策略: {strategy}")
                    
                    with open(file_path, "rb") as f:
                        files = {"files": f}
                        data = {
                            "api_version": "v0",
                            "strategy": strategy,
                            "encoding": "UTF-8"
                        }
                        
                        self.logger.info(f"[Unstructured] 发送请求到 {self.api_url}/general/v0/general")
                        self.logger.info(f"[Unstructured] 请求参数: strategy={strategy}, encoding=UTF-8")
                        
                        # 使用更短的超时时间，避免长时间等待失败的请求
                        timeout = 30.0 if strategy == "auto" or strategy == "fast" else 60.0
                        
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            response = await client.post(
                                f"{self.api_url}/general/v0/general",
                                files=files,
                                data=data
                            )
                            
                            duration = time.time() - step_start
                            self.logger.info(f"[Unstructured] API 响应时间: {duration:.2f}s, 状态码: {response.status_code}")
                            
                            if response.status_code == 200:
                                result = response.json()
                                self.logger.info(f"[Unstructured] 收到 {len(result) if isinstance(result, list) else 0} 个元素")
                                
                                text = self._parse_unstructured_result(result)
                                
                                if text and len(text.strip()) > 10:
                                    self.logger.info(f"[Unstructured] ✅ 提取成功: {len(text)} 字符")
                                    self.logger.info(f"[Unstructured] 内容预览: {text[:300]}...")
                                    return text
                                else:
                                    self.logger.warning(f"[Unstructured] ⚠️ 策略 {strategy} 提取结果为空，继续尝试")
                                    continue
                                    
                            elif response.status_code == 500:
                                # 500 错误通常是模型加载失败，快速回退
                                error_detail = response.text[:500]
                                self.logger.warning(f"[Unstructured] ⚠️ 策略 {strategy} 返回 500 错误（可能是 table-transformer 模型问题）: {error_detail[:200]}")
                                
                                # 如果是 hi_res 策略的 table-transformer 问题，立即回退
                                if "table-transformer" in error_detail or "Can't load image processor" in error_detail:
                                    self.logger.warning(f"[Unstructured] ⚠️ 检测到 table-transformer 模型加载失败，跳过此策略")
                                    continue
                                else:
                                    self.logger.error(f"[Unstructured] API 失败（500）: {error_detail}")
                                    break
                                    
                            elif response.status_code == 422:
                                # 422 通常是参数不支持，尝试下一个策略
                                self.logger.warning(f"[Unstructured] ⚠️ 策略 {strategy} 不支持（422），尝试下一个策略")
                                continue
                                
                            else:
                                self.logger.error(f"[Unstructured] API 失败: {response.status_code} - {response.text[:300]}")
                                break
                                
                except httpx.TimeoutException:
                    self.logger.warning(f"[Unstructured] ⚠️ 策略 {strategy} 请求超时（{timeout}秒）")
                    continue
                except Exception as strategy_error:
                    self.logger.warning(f"[Unstructured] ⚠️ 策略 {strategy} 执行失败: {str(strategy_error)}")
                    continue
            
            # 所有策略都失败
            self.logger.error(f"[Unstructured] ❌ 所有策略都失败")
            return ""
            
        except FileNotFoundError:
            self.logger.error(f"[Unstructured] 文件不存在: {file_path}")
            return ""
        except Exception as e:
            self.logger.error(f"[Unstructured] 提取失败: {str(e)}")
            import traceback
            self.logger.error(f"[Unstructured] 详细错误: {traceback.format_exc()}")
            return ""
    
    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """从图片字节流提取文本"""
        import httpx
        
        # 尝试不同的策略，从最稳定到最高质量
        strategies = ["auto", "fast"]
        
        for strategy in strategies:
            try:
                files = {"file": ("image.png", image_bytes, "image/png")}
                data = {
                    "api_version": "v1",
                    "strategy": strategy
                }
                
                self.logger.info(f"[Unstructured] 图片 OCR 尝试策略: {strategy}")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.api_url}/general/v0/general",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        text = self._parse_unstructured_result(result)
                        
                        if text and len(text.strip()) > 5:
                            self.logger.info(f"[Unstructured] 图片 OCR 成功（策略 {strategy}）: {len(text)} 字符")
                            return text
                        else:
                            self.logger.warning(f"[Unstructured] 图片 OCR 策略 {strategy} 结果为空")
                            continue
                            
                    elif response.status_code == 500:
                        error_detail = response.text[:500]
                        self.logger.warning(f"[Unstructured] 图片 OCR 策略 {strategy} 返回 500: {error_detail[:200]}")
                        
                        if "table-transformer" in error_detail or "Can't load image processor" in error_detail:
                            continue  # 尝试下一个策略
                        else:
                            break
                            
                    elif response.status_code == 422:
                        self.logger.warning(f"[Unstructured] 图片 OCR 策略 {strategy} 不支持（422）")
                        continue
                    else:
                        self.logger.warning(f"[Unstructured] 图片 OCR 策略 {strategy} 失败: {response.status_code}")
                        break
                        
            except httpx.TimeoutException:
                self.logger.warning(f"[Unstructured] 图片 OCR 策略 {strategy} 超时（30秒）")
                continue
            except Exception as e:
                self.logger.warning(f"[Unstructured] 图片 OCR 策略 {strategy} 异常: {str(e)}")
                continue
        
        self.logger.error(f"[Unstructured] 图片 OCR 所有策略都失败")
        return ""
    
    def _parse_unstructured_result(self, result: Dict[str, Any]) -> str:
        """解析 Unstructured API 返回结果"""
        text_parts = []
        
        if isinstance(result, list):
            for element in result:
                if isinstance(element, dict):
                    text = element.get("text", "")
                    if text:
                        text_parts.append(text)
                elif isinstance(element, str):
                    text_parts.append(element)
        elif isinstance(result, dict):
            if "text" in result:
                return result["text"]
            for value in result.values():
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
        
        return "\n".join(text_parts)
