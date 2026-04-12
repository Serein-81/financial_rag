# app/agent_framework/llm/agent_adapter_factory.py

"""
智能体专属适配器工厂

根据智能体配置创建对应的LLM适配器
支持每个智能体使用不同的模型和API配置
"""

import logging
from typing import Optional

from app.core.config import settings
from .base_adapter import BaseLLMAdapter
from .agent_llm_config import AgentLLMConfig, AgentType

logger = logging.getLogger(__name__)


class AgentLLMAdapterFactory:
    """
    智能体LLM适配器工厂
    
    根据AgentLLMConfig创建对应的适配器实例
    支持覆盖全局配置中的API Key和Base URL
    """
    
    @staticmethod
    def create_adapter(config: AgentLLMConfig) -> BaseLLMAdapter:
        """
        根据配置创建LLM适配器
        
        Args:
            config: 智能体LLM配置
            
        Returns:
            对应的适配器实例
        """
        provider = config.provider
        model = config.model
        api_key = config.api_key
        base_url = config.base_url
        
        logger.info(f"[智能体适配器工厂] 创建适配器: provider={provider}, model={model}")
        
        if provider == "gpt":
            from .gpt_adapter import GPTAdapter
            
            api_key = api_key or settings.GPT_API_KEY
            base_url = base_url or settings.GPT_BASE_URL
            model = model or settings.GPT_MODEL
            
            return GPTAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "zhipu":
            from .zhipu_adapter import ZhipuAdapter
            
            api_key = api_key or settings.ZHIPU_API_KEY
            model = model or settings.ZHIPU_MODEL
            
            return ZhipuAdapter(
                api_key=api_key,
                model_name=model
            )
        
        elif provider == "minimax":
            from .minimax_adapter import MiniMaxAdapter
            
            api_key = api_key or settings.MINIMAX_API_KEY
            base_url = base_url or settings.MINIMAX_BASE_URL
            model = model or settings.MINIMAX_MODEL
            
            return MiniMaxAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url,
                group_id=settings.MINIMAX_GROUP_ID
            )
        
        elif provider == "openai":
            from .openai_adapter import OpenAIAdapter
            
            api_key = api_key or settings.OPENAI_API_KEY
            base_url = base_url or settings.OPENAI_BASE_URL
            model = model or settings.OPENAI_MODEL
            
            return OpenAIAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "claude":
            from .claude_adapter import ClaudeAdapter
            
            api_key = api_key or settings.CLAUDE_API_KEY
            base_url = base_url or settings.CLAUDE_BASE_URL
            model = model or settings.CLAUDE_MODEL
            
            return ClaudeAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "xinference":
            from .xinference_adapter import XinferenceAdapter
            
            api_key = api_key or settings.XINFERENCE_API_KEY
            base_url = base_url or settings.XINFERENCE_BASE_URL
            model = model or settings.XINFERENCE_MODEL
            
            return XinferenceAdapter(
                api_key=api_key,
                model_name=model or "",
                base_url=base_url
            )
        
        elif provider == "huggingface":
            from .huggingface_adapter import HuggingFaceAdapter
            
            api_key = api_key or settings.HUGGINGFACE_API_KEY
            base_url = base_url or settings.HUGGINGFACE_BASE_URL
            model = model or settings.HUGGINGFACE_MODEL
            
            return HuggingFaceAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "modelscope":
            from .modelscope_adapter import ModelScopeAdapter
            
            api_key = api_key or settings.MODELSCOPE_API_KEY
            base_url = base_url or settings.MODELSCOPE_BASE_URL
            model = model or settings.MODELSCOPE_MODEL
            
            return ModelScopeAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "baichuan":
            from .baichuan_adapter import BaiChuanAdapter
            
            api_key = api_key or settings.BAICHUAN_API_KEY
            base_url = base_url or settings.BAICHUAN_BASE_URL
            model = model or settings.BAICHUAN_MODEL
            
            return BaiChuanAdapter(
                api_key=api_key,
                secret_key=settings.BAICHUAN_SECRET_KEY,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "deepseek":
            from .deepseek_adapter import DeepSeekAdapter
            
            api_key = api_key or settings.GPT_API_KEY
            base_url = base_url or settings.GPT_BASE_URL
            model = model or "deepseek/deepseek-chat-v3-0324"
            
            return DeepSeekAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        elif provider == "qwen":
            from .qwen_adapter import QwenAdapter
            
            api_key = api_key or settings.GPT_API_KEY
            base_url = base_url or settings.GPT_BASE_URL
            model = model or "qwen/qwen3.6-plus:free"
            
            return QwenAdapter(
                api_key=api_key,
                model_name=model,
                base_url=base_url
            )
        
        else:
            logger.warning(f"[智能体适配器工厂] 不支持的提供商: {provider}，使用默认适配器")
            from .factory import create_llm_adapter
            return create_llm_adapter()
    
    @staticmethod
    def get_default_adapter() -> BaseLLMAdapter:
        """
        获取默认的LLM适配器（使用全局配置）
        
        Returns:
            默认适配器实例
        """
        from .factory import create_llm_adapter
        return create_llm_adapter()
