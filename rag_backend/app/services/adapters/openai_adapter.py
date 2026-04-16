# app/services/adapters/openai_adapter.py

"""
OpenAI Embedding 适配器

使用 OpenAI 的 text-embedding-3-small 或 text-embedding-3-large 模型
"""

from typing import List
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

from .base_adapter import BaseEmbeddingAdapter


class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    OpenAI Embedding 适配器
    
    使用 OpenAI 的 text-embedding-3-small 或 text-embedding-3-large 模型
    """
    
    PROVIDER_NAME = "openai"
    
    MAX_LENGTH = 8191
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        **kwargs
    ):
        """
        初始化 OpenAI 适配器
        
        Args:
            api_key: API 密钥
            model_name: 模型名称
            base_url: API 基础 URL
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai 包未安装，请运行: pip install openai")
        
        if not api_key:
            raise ValueError("OpenAI API Key 不能为空")
        
        super().__init__(api_key, model_name, base_url, **kwargs)
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.max_length = self.MAX_LENGTH
        
        # 只在首次初始化时打印详细信息
        if not getattr(OpenAIEmbeddingAdapter, '_initialized', False):
            OpenAIEmbeddingAdapter._initialized = True
            print("✅ OpenAI Embedding 适配器初始化完成")
            print(f"   - 模型: {self.model_name}")
            print(f"   - Base URL: {self.base_url}")
            print(f"   - API Key: {api_key[:8]}...{api_key[-4:]}")
    
    async def _encode_single(self, text: str, task_type: str) -> List[float]:
        """
        单条文本编码
        
        Args:
            text: 输入文本
            task_type: 任务类型（目前 OpenAI 不支持区分）
        
        Returns:
            文本的向量表示
        """
        text = self.truncate_text(text, self.max_length)
        
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text
        )
        
        return response.data[0].embedding
