# app/services/adapters/base_adapter.py

"""
Embedding 适配器抽象基类

定义统一的接口规范，所有具体适配器必须实现 encode 和 encode_queries 方法
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np


class BaseEmbeddingAdapter(ABC):
    """
    Embedding 适配器抽象基类
    
    定义统一的接口规范，所有具体适配器必须实现：
    - _encode_single() : 单条文本编码（子类必须实现）
    - encode()         : 批量编码文本
    - encode_queries() : 编码查询文本
    """
    
    PROVIDER_NAME: str = "base"
    
    def __init__(
        self,
        api_key: str = "",
        model_name: str = "",
        base_url: str = "",
        **kwargs
    ):
        """
        初始化适配器
        
        Args:
            api_key: API 密钥
            model_name: 模型名称
            base_url: API 基础 URL
            **kwargs: 其他配置
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.config = kwargs
        
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        self.batch_size = kwargs.get("batch_size", 16)
        
        self.total_tokens = 0
        
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def _encode_single(self, text: str, task_type: str) -> List[float]:
        """
        单条文本编码（子类必须实现）
        
        Args:
            text: 输入文本
            task_type: 任务类型 ("document" 或 "query")
        
        Returns:
            文本的向量表示
        """
        pass
    
    async def encode(
        self, 
        texts: List[str], 
        task_type: str = "document",
        return_tokens: bool = True
    ) -> Tuple[List[List[float]], int]:
        """
        批量编码文本
        
        Args:
            texts: 文本列表
            task_type: 任务类型
            return_tokens: 是否返回 token 计数
        
        Returns:
            (embeddings, total_tokens) 元组
        """
        all_embeddings = []
        total_tokens = 0
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            batch_embeddings = []
            for text in batch:
                try:
                    embedding = await self._encode_single(text, task_type)
                    batch_embeddings.append(embedding)
                except Exception as e:
                    self.logger.error(f"编码失败: {text[:50]}... - {e}")
                    batch_embeddings.append([0.0] * 1024)
            
            all_embeddings.extend(batch_embeddings)
            
            if return_tokens:
                batch_tokens = sum(self._estimate_tokens(t) for t in batch)
                total_tokens += batch_tokens
        
        self.total_tokens = total_tokens
        return all_embeddings, total_tokens
    
    async def encode_queries(
        self, 
        query: str,
        return_tokens: bool = True
    ) -> Tuple[List[float], int]:
        """
        编码单个查询
        
        Args:
            query: 查询文本
            return_tokens: 是否返回 token 计数
        
        Returns:
            (embedding, token_count) 元组
        """
        embeddings, total_tokens = await self.encode(
            [query], 
            task_type="query",
            return_tokens=return_tokens
        )
        return embeddings[0], total_tokens
    
    def truncate_text(self, text: str, max_length: int = 8191) -> str:
        """
        截断过长文本
        
        Args:
            text: 输入文本
            max_length: 最大字符数
        
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length]
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量（粗略估计）
        
        Args:
            text: 输入文本
        
        Returns:
            估算的 token 数量
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 2 + other_chars / 4)
    
    async def _retry_on_failure(self, func, *args, **kwargs):
        """
        失败重试装饰器
        
        Args:
            func: 要重试的函数
            *args, **kwargs: 函数参数
        
        Returns:
            函数返回值
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
        
        raise last_exception
