# app/agent_framework/llm/base_adapter.py

"""
LLM 适配器抽象基类

定义统一的大模型调用接口
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional


class BaseLLMAdapter(ABC):
    """
    LLM 适配器抽象基类
    
    所有具体的 LLM 适配器都应该继承这个类
    """
    
    def __init__(self, model_name: str = "", **kwargs):
        """
        初始化适配器
        
        Args:
            model_name: 模型名称
            **kwargs: 其他配置参数
        """
        self.model_name = model_name
        self.config = kwargs
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        生成回答（非流式）
        
        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
            
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
    async def stream_generate(
        self, 
        prompt: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回答
        
        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
            
        Yields:
            逐步生成的文本片段
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            模型信息字典
        """
        return {
            "model_name": self.model_name,
            "adapter_type": self.__class__.__name__,
            "config": self.config
        }