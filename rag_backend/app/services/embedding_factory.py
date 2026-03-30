# app/services/embedding_factory.py

"""
Embedding 适配器工厂

根据环境变量配置自动创建对应的适配器实例
"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingAdapterFactory:
    """
    Embedding 适配器工厂
    
    根据环境变量配置自动创建对应的适配器实例
    支持的提供商：
    - zhipu      : 智谱 AI
    - openai     : OpenAI
    - ollama     : Ollama 本地部署
    - siliconflow: 硅基流动
    """
    
    @staticmethod
    def create_adapter(provider: Optional[str] = None):
        """
        创建 Embedding 适配器
        
        Args:
            provider: 提供商名称（None 则使用配置）
        
        Returns:
            对应的适配器实例
        
        Raises:
            ValueError: 不支持的提供商或缺少必要配置
        """
        provider = provider or settings.EMBEDDING_PROVIDER
        provider = provider.lower().strip()
        
        logger.info(f"[Embedding工厂] 创建适配器: {provider}")
        
        if provider == "zhipu":
            if not settings.ZHIPU_API_KEY:
                raise ValueError("智谱 AI API Key 未配置，请设置 ZHIPU_API_KEY")
            
            from .adapters.zhipu_adapter import ZhipuEmbeddingAdapter
            
            return ZhipuEmbeddingAdapter(
                api_key=settings.ZHIPU_API_KEY,
                model_name=settings.ZHIPU_EMBEDDING_MODEL,
                batch_size=settings.EMBEDDING_BATCH_SIZE
            )
        
        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API Key 未配置，请设置 OPENAI_API_KEY")
            
            from .adapters.openai_adapter import OpenAIEmbeddingAdapter
            
            return OpenAIEmbeddingAdapter(
                api_key=settings.OPENAI_API_KEY,
                model_name=settings.OPENAI_EMBEDDING_MODEL,
                base_url=settings.OPENAI_BASE_URL,
                batch_size=settings.EMBEDDING_BATCH_SIZE
            )
        
        elif provider == "ollama":
            from .adapters.ollama_adapter import OllamaEmbeddingAdapter
            
            return OllamaEmbeddingAdapter(
                model_name=settings.OLLAMA_EMBEDDING_MODEL or "nomic-embed-text",
                base_url=settings.OLLAMA_BASE_URL or "http://localhost:11434",
                batch_size=settings.EMBEDDING_BATCH_SIZE
            )
        
        elif provider == "siliconflow":
            if not settings.SILICONFLOW_API_KEY:
                raise ValueError("硅基流动 API Key 未配置，请设置 SILICONFLOW_API_KEY")
            
            from .adapters.siliconflow_adapter import SiliconFlowEmbeddingAdapter
            
            return SiliconFlowEmbeddingAdapter(
                api_key=settings.SILICONFLOW_API_KEY,
                model_name=settings.SILICONFLOW_EMBEDDING_MODEL,
                batch_size=settings.EMBEDDING_BATCH_SIZE
            )
        
        else:
            raise ValueError(
                f"不支持的 Embedding 提供商: {provider}\n"
                f"支持的提供商: zhipu, openai, ollama, siliconflow"
            )
