# app/services/adapters/ollama_adapter.py

"""
Ollama 本地 Embedding 适配器

使用 Ollama 本地部署的 embedding 模型
"""

from typing import List
try:
    from ollama import Client
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    Client = None

from .base_adapter import BaseEmbeddingAdapter


class OllamaEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    Ollama 本地 Embedding 适配器
    
    使用 Ollama 本地部署的 embedding 模型
    支持的模型：nomic-embed-text, mxbai-embed-large 等
    """
    
    PROVIDER_NAME = "ollama"
    
    MAX_LENGTH = 8191
    
    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        **kwargs
    ):
        """
        初始化 Ollama 适配器
        
        Args:
            model_name: 模型名称（默认 nomic-embed-text）
            base_url: Ollama 服务地址
        """
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama 包未安装，请运行: pip install ollama")
        
        super().__init__("", model_name, base_url, **kwargs)
        
        self.client = Client(host=base_url)
        self.keep_alive = kwargs.get("ollama_keep_alive", -1)
        
        # 只在首次初始化时打印详细信息
        if not getattr(OllamaEmbeddingAdapter, '_initialized', False):
            OllamaEmbeddingAdapter._initialized = True
            print("✅ Ollama Embedding 适配器初始化完成")
            print(f"   - 模型: {self.model_name}")
            print(f"   - Base URL: {self.base_url}")
            print(f"   - Keep Alive: {self.keep_alive}s")
    
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
        
        response = self.client.embeddings(
            prompt=text,
            model=self.model_name,
            options={"use_mmap": True},
            keep_alive=self.keep_alive
        )
        
        return response["embedding"]
