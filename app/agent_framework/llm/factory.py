# app/agent_framework/llm/factory.py

"""
LLM 适配器工厂

根据配置自动创建对应的 LLM 适配器
"""

import logging
from typing import Optional

from app.core.config import settings
from .base_adapter import BaseLLMAdapter
from .zhipu_adapter import ZhipuAdapter

logger = logging.getLogger(__name__)


class LLMAdapterFactory:
    """
    LLM 适配器工厂
    
    根据环境变量配置自动创建对应的适配器实例
    支持的提供商：zhipu, openai, claude
    """
    
    @staticmethod
    def create_adapter(provider: Optional[str] = None) -> BaseLLMAdapter:
        """
        创建 LLM 适配器
        
        Args:
            provider: 提供商名称（zhipu, openai, claude）
                     如果为 None，则使用配置文件中的 LLM_PROVIDER
        
        Returns:
            对应的适配器实例
            
        Raises:
            ValueError: 不支持的提供商或缺少必要配置
        
        Examples:
            # 使用默认配置
            adapter = LLMAdapterFactory.create_adapter()
            
            # 指定提供商
            adapter = LLMAdapterFactory.create_adapter("zhipu")
        """
        # 使用指定的提供商或配置文件中的默认值
        provider = provider or settings.LLM_PROVIDER
        provider = provider.lower().strip()
        
        logger.info(f"🏭 [LLM工厂] 创建适配器: {provider}")
        
        # 智谱 AI
        if provider == "zhipu":
            if not settings.ZHIPU_API_KEY:
                raise ValueError("智谱 AI API Key 未配置，请在 .env 中设置 ZHIPU_API_KEY")
            
            logger.info(f"   - 模型: {settings.ZHIPU_MODEL}")
            logger.info(f"   - API Key: {settings.ZHIPU_API_KEY[:8]}...{settings.ZHIPU_API_KEY[-4:]}")
            
            return ZhipuAdapter(
                api_key=settings.ZHIPU_API_KEY,
                model_name=settings.ZHIPU_MODEL
            )
        
        # OpenAI
        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")
            
            # 动态导入 OpenAI 适配器（如果已实现）
            try:
                from .openai_adapter import OpenAIAdapter
                
                logger.info(f"   - 模型: {settings.OPENAI_MODEL}")
                logger.info(f"   - Base URL: {settings.OPENAI_BASE_URL}")
                
                return OpenAIAdapter(
                    api_key=settings.OPENAI_API_KEY,
                    model_name=settings.OPENAI_MODEL,
                    base_url=settings.OPENAI_BASE_URL
                )
            except ImportError:
                raise NotImplementedError(
                    "OpenAI 适配器尚未实现，请先创建 openai_adapter.py"
                )
        
        # Claude
        elif provider == "claude":
            if not settings.CLAUDE_API_KEY:
                raise ValueError("Claude API Key 未配置，请在 .env 中设置 CLAUDE_API_KEY")
            
            # 动态导入 Claude 适配器（如果已实现）
            try:
                from .claude_adapter import ClaudeAdapter
                
                logger.info(f"   - 模型: {settings.CLAUDE_MODEL}")
                
                return ClaudeAdapter(
                    api_key=settings.CLAUDE_API_KEY,
                    model_name=settings.CLAUDE_MODEL
                )
            except ImportError:
                raise NotImplementedError(
                    "Claude 适配器尚未实现，请先创建 claude_adapter.py"
                )
        
        # 不支持的提供商
        else:
            raise ValueError(
                f"不支持的 LLM 提供商: {provider}\n"
                f"支持的提供商: zhipu, openai, claude\n"
                f"请在 .env 中设置 LLM_PROVIDER"
            )
    
    @staticmethod
    def get_supported_providers() -> list:
        """
        获取支持的提供商列表
        
        Returns:
            支持的提供商名称列表
        """
        return ["zhipu", "openai", "claude"]
    
    @staticmethod
    def get_current_provider() -> str:
        """
        获取当前配置的提供商
        
        Returns:
            当前提供商名称
        """
        return settings.LLM_PROVIDER


# 便捷函数
def create_llm_adapter(provider: Optional[str] = None) -> BaseLLMAdapter:
    """
    创建 LLM 适配器的便捷函数
    
    Args:
        provider: 提供商名称，如果为 None 则使用配置文件中的默认值
    
    Returns:
        对应的适配器实例
    """
    return LLMAdapterFactory.create_adapter(provider)
