# app/services/adapters/zhipu_adapter.py

"""
智谱 AI Embedding 适配器

使用智谱 AI 的 embedding-2 或 embedding-3 模型
"""

from typing import List
try:
    from zhipuai import ZhipuAI
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    ZhipuAI = None

from .base_adapter import BaseEmbeddingAdapter


class ZhipuEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    智谱 AI Embedding 适配器
    
    使用智谱 AI 的 embedding-2 或 embedding-3 模型
    """
    
    PROVIDER_NAME = "zhipu"
    
    MAX_LENGTHS = {
        "embedding-2": 512,
        "embedding-3": 3072,
    }
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "embedding-3",
        **kwargs
    ):
        """
        初始化智谱 AI 适配器
        
        Args:
            api_key: API 密钥
            model_name: 模型名称（embedding-2 或 embedding-3）
        """
        if not ZHIPU_AVAILABLE:
            raise ImportError("zhipuai 包未安装，请运行: pip install zhipuai")
        
        if not api_key:
            raise ValueError("智谱 AI API Key 不能为空")
        
        super().__init__(api_key, model_name, **kwargs)
        
        self.client = ZhipuAI(api_key=api_key)
        self.max_length = self.MAX_LENGTHS.get(model_name, 3072)
        
        # 只在首次初始化时打印详细信息
        if not getattr(ZhipuEmbeddingAdapter, '_initialized', False):
            ZhipuEmbeddingAdapter._initialized = True
            print(f"✅ 智谱 AI Embedding 适配器初始化完成")
            print(f"   - 模型: {self.model_name}")
            print(f"   - 最大长度: {self.max_length}")
            print(f"   - API Key: {api_key[:8]}...{api_key[-4:]}")
    
    async def _encode_single(self, text: str, task_type: str) -> List[float]:
        """
        单条文本编码
        
        Args:
            text: 输入文本
            task_type: 任务类型（目前智谱不支持区分）
        
        Returns:
            文本的向量表示
        """
        text = self.truncate_text(text, self.max_length)
        
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text
        )
        
        return response.data[0].embedding
