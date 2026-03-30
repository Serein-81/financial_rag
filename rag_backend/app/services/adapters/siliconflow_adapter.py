# app/services/adapters/siliconflow_adapter.py

"""
硅基流动 Embedding 适配器

使用硅基流动的 API，支持多种开源 embedding 模型
"""

from typing import List
import requests
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
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"✅ 硅基流动 Embedding 适配器初始化完成")
        print(f"   - 模型: {self.model_name}")
        print(f"   - Base URL: {self.base_url}")
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
        text = self.truncate_text(text, self.max_length)
        
        payload = {
            "model": self.model_name,
            "input": text,
            "encoding_format": "float"
        }
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"API 请求失败: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["data"][0]["embedding"]
