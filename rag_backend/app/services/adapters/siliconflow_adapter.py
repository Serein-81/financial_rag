# app/services/adapters/siliconflow_adapter.py

"""
硅基流动 Embedding 适配器

使用硅基流动的 API，支持多种开源 embedding 模型
"""

from typing import List
import httpx
from .base_adapter import BaseEmbeddingAdapter


class SiliconFlowEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    硅基流动 Embedding 适配器
    
    使用硅基流动的 API，支持多种开源 embedding 模型
    推荐模型：BAAI/bge-large-zh-v1.5, Pro/BAAI/bge-m3
    """
    
    PROVIDER_NAME = "siliconflow"
    
    DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1/embeddings"
    MAX_LENGTH = 8191
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        base_url: str = None,
        **kwargs
    ):
        """
        初始化硅基流动适配器
        
        Args:
            api_key: API 密钥
            model_name: 模型名称
            base_url: API 基础 URL
        """
        if not api_key:
            raise ValueError("硅基流动 API Key 不能为空")
        
        base_url = base_url or self.DEFAULT_BASE_URL
        
        super().__init__(api_key, model_name, base_url, **kwargs)
        
        self.max_length = self.MAX_LENGTH
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

        # 只在首次初始化时打印详细信息
        if not getattr(SiliconFlowEmbeddingAdapter, '_initialized', False):
            SiliconFlowEmbeddingAdapter._initialized = True
            print("✅ 硅基流动 Embedding 适配器初始化完成")
            print(f"   - 模型: {self.model_name}")
            print(f"   - Base URL: {self.base_url}")
            print(f"   - 最大长度: {self.max_length}")
            print(f"   - API Key: {api_key[:8]}...{api_key[-4:]}")
    
    async def _encode_single(self, text: str, task_type: str) -> List[float]:
        """
        单条文本编码
        
        Args:
            text: 输入文本
            task_type: 任务类型
        
        Returns:
            文本的向量表示
        """
        self.logger.debug(f"[SiliconFlow] _encode_single 调用 | task_type={task_type} | text长度={len(text) if text else 0}")
        
        if not isinstance(text, str):
            self.logger.error(f"[SiliconFlow] text 不是字符串: {type(text)}")
            raise ValueError(f"Expected str, got {type(text)}: {text}")
        
        original_text = text
        text = self.truncate_text(text, self.max_length)
        self.logger.debug(f"[SiliconFlow] truncate 后 | 原始长度={len(original_text) if original_text else 0} | truncate后长度={len(text) if text else 0}")
        
        if not text or len(text.strip()) == 0:
            self.logger.warning(f"[SiliconFlow] 文本为空 (original='{original_text[:50]}...'), 跳过编码")
            return [0.0] * 1024
        
        payload = {
            "model": self.model_name,
            "input": text,
        }
        
        try:
            response = await self.client.post(
                self.base_url,
                headers=self.headers,
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
            return result["data"][0]["embedding"]
            
        except httpx.HTTPStatusError as e:
            try:
                error_text = e.response.text
                try:
                    error_detail = e.response.json()
                    error_code = error_detail.get("code", "unknown")
                    error_message = error_detail.get("message", error_text)
                except Exception:
                    error_message = error_text
                
                if error_code == 20015:
                    raise Exception(f"API 参数无效或账户余额不足: {error_message}")
                else:
                    raise Exception(f"API 请求失败: {e.response.status_code} - {error_message}")
            except Exception:
                raise
        except httpx.RequestError as e:
            raise Exception(f"HTTP 请求错误: {str(e)}")
