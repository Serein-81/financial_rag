# app/services/embedding_service.py

"""
Embedding 服务门面类

提供统一的调用接口，兼容现有代码
"""

import os
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding 服务门面类（单例）
    
    职责：
    1. 维护适配器实例（懒加载）
    2. 提供统一接口
    3. 兼容现有代码（async/await）
    """
    
    _instance = None
    _adapter = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _ensure_adapter(self):
        """懒加载适配器：优先用部署级配置（DB），失败回退 .env"""
        if self._adapter is not None:
            return self._adapter

        from app.services.embedding_factory import EmbeddingAdapterFactory
        try:
            from app.services import system_config_service
            cfg = await system_config_service.get_embedding_config()
            self._adapter = EmbeddingAdapterFactory.create_adapter(
                provider=cfg.get("provider"),
                model=cfg.get("model"),
                api_key=cfg.get("api_key"),
                base_url=cfg.get("base_url"),
            )
            logger.info(f"[EmbeddingService] 使用配置: {cfg.get('provider')}/{cfg.get('model')}")
        except Exception as e:
            logger.warning(f"[EmbeddingService] 加载部署级配置失败，回退 .env: {e}")
            self._adapter = EmbeddingAdapterFactory.create_adapter()
        return self._adapter

    async def reload(self) -> None:
        """重置适配器，下次调用按最新配置重建（保存配置后调用）"""
        self._adapter = None
        logger.info("[EmbeddingService] 适配器已重置，将按最新配置重建")
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        获取单条文本的向量（兼容现有接口）
        
        Args:
            text: 输入文本
        
        Returns:
            向量列表
        """
        logger.debug(f"[EmbeddingService] get_embedding 调用 | text长度={len(text) if text else 0}")
        adapter = await self._ensure_adapter()
        embedding, _ = await adapter.encode_queries(text, return_tokens=False)
        logger.debug(f"[EmbeddingService] get_embedding 返回 | embedding长度={len(embedding) if embedding else 0}")
        return embedding
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取文本向量
        
        Args:
            texts: 文本列表
        
        Returns:
            向量列表
        """
        adapter = await self._ensure_adapter()
        embeddings, _ = await adapter.encode(texts, task_type="document")
        return embeddings
    
    async def get_embedding_with_tokens(self, text: str) -> Tuple[List[float], int]:
        """
        获取向量并返回 Token 计数
        
        Args:
            text: 输入文本
        
        Returns:
            (embedding, token_count) 元组
        """
        adapter = await self._ensure_adapter()
        return await adapter.encode_queries(text, return_tokens=True)
    
    async def get_embeddings_with_tokens(
        self, 
        texts: List[str]
    ) -> Tuple[List[List[float]], int]:
        """
        批量获取向量并返回 Token 计数
        
        Args:
            texts: 文本列表
        
        Returns:
            (embeddings, total_tokens) 元组
        """
        adapter = await self._ensure_adapter()
        return await adapter.encode(texts, task_type="document", return_tokens=True)
    
    def get_current_provider(self) -> str:
        """获取当前提供商"""
        from app.core.config import settings
        return settings.EMBEDDING_PROVIDER
    
    def switch_provider(self, provider: str) -> None:
        """
        切换提供商（不推荐在生产环境使用）
        
        Args:
            provider: 提供商名称
        """
        os.environ["EMBEDDING_PROVIDER"] = provider
        self._adapter = None
        logger.info(f"[Embedding服务] 已切换提供商: {provider}")


embedding_service = EmbeddingService()
