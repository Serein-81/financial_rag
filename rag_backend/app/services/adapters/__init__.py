# app/services/adapters/__init__.py

"""
Embedding 适配器模块

支持多种 Embedding 提供商：
- zhipu      : 智谱 AI
- openai     : OpenAI
- ollama     : Ollama 本地部署
- siliconflow: 硅基流动
"""

from .base_adapter import BaseEmbeddingAdapter
from .zhipu_adapter import ZhipuEmbeddingAdapter
from .openai_adapter import OpenAIEmbeddingAdapter
from .ollama_adapter import OllamaEmbeddingAdapter
from .siliconflow_adapter import SiliconFlowEmbeddingAdapter

__all__ = [
    "BaseEmbeddingAdapter",
    "ZhipuEmbeddingAdapter",
    "OpenAIEmbeddingAdapter",
    "OllamaEmbeddingAdapter",
    "SiliconFlowEmbeddingAdapter",
]
