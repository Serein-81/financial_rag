# app/agent_framework/llm/factory.py

"""
LLM 适配器工厂

根据配置自动创建对应的 LLM 适配器
"""

import logging
from typing import Optional

from app.core.config import settings
from .base_adapter import BaseLLMAdapter

logger = logging.getLogger(__name__)


class LLMAdapterFactory:
    """
    LLM 适配器工厂
    
    根据环境变量配置自动创建对应的适配器实例
    支持的提供商：zhipu, openai, claude, minimax, xinference, huggingface, modelscope, baichuan, gpt (OpenRouter)
    """
    
    @staticmethod
    def create_adapter(provider: Optional[str] = None) -> BaseLLMAdapter:
        """
        创建 LLM 适配器
        
        Args:
            provider: 提供商名称
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
        
        logger.debug(f"[LLM工厂] 创建适配器: {provider}")
        
        # 智谱 AI
        if provider == "zhipu":
            if not settings.ZHIPU_API_KEY:
                raise ValueError("智谱 AI API Key 未配置，请在 .env 中设置 ZHIPU_API_KEY")
            
            from .zhipu_adapter import ZhipuAdapter
            
            logger.debug(f"   - 模型: {settings.ZHIPU_MODEL}")
            logger.debug(f"   - API Key: {settings.ZHIPU_API_KEY[:8]}...{settings.ZHIPU_API_KEY[-4:]}")
            
            return ZhipuAdapter(
                api_key=settings.ZHIPU_API_KEY,
                model_name=settings.ZHIPU_MODEL
            )
        
        # OpenAI
        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")
            
            from .openai_adapter import OpenAIAdapter
            
            logger.debug(f"   - 模型: {settings.OPENAI_MODEL}")
            logger.debug(f"   - Base URL: {settings.OPENAI_BASE_URL}")
            
            return OpenAIAdapter(
                api_key=settings.OPENAI_API_KEY,
                model_name=settings.OPENAI_MODEL,
                base_url=settings.OPENAI_BASE_URL
            )
        
        # Claude
        elif provider == "claude":
            if not settings.CLAUDE_API_KEY:
                raise ValueError("Claude API Key 未配置，请在 .env 中设置 CLAUDE_API_KEY")
            
            from .claude_adapter import ClaudeAdapter
            
            logger.debug(f"   - 模型: {settings.CLAUDE_MODEL}")
            logger.debug(f"   - Base URL: {settings.CLAUDE_BASE_URL}")
            
            return ClaudeAdapter(
                api_key=settings.CLAUDE_API_KEY,
                model_name=settings.CLAUDE_MODEL,
                base_url=settings.CLAUDE_BASE_URL
            )
        
        # GPT（OpenAI API 兼容）
        elif provider == "gpt":
            if not settings.GPT_API_KEY:
                raise ValueError("GPT API Key 未配置，请在 .env 中设置 GPT_API_KEY")
            
            from .gpt_adapter import GPTAdapter
            
            logger.debug(f"   - 模型: {settings.GPT_MODEL}")
            logger.debug(f"   - Base URL: {settings.GPT_BASE_URL}")
            logger.debug(f"   - API Key: {settings.GPT_API_KEY[:12]}...{settings.GPT_API_KEY[-4:]}")
            
            return GPTAdapter(
                api_key=settings.GPT_API_KEY,
                model_name=settings.GPT_MODEL,
                base_url=settings.GPT_BASE_URL
            )
        
        # MiniMax ⭐用户要求
        elif provider == "minimax":
            if not settings.MINIMAX_API_KEY:
                raise ValueError("MiniMax API Key 未配置，请在 .env 中设置 MINIMAX_API_KEY")
            
            from .minimax_adapter import MiniMaxAdapter
            
            logger.debug(f"   - 模型: {settings.MINIMAX_MODEL}")
            logger.debug(f"   - Base URL: {settings.MINIMAX_BASE_URL}")
            logger.debug(f"   - Group ID: {settings.MINIMAX_GROUP_ID or 'N/A'}")
            
            return MiniMaxAdapter(
                api_key=settings.MINIMAX_API_KEY,
                model_name=settings.MINIMAX_MODEL,
                base_url=settings.MINIMAX_BASE_URL,
                group_id=settings.MINIMAX_GROUP_ID
            )
        
        # Xinference（本地部署）
        elif provider == "xinference":
            from .xinference_adapter import XinferenceAdapter
            
            logger.debug(f"   - 模型: {settings.XINFERENCE_MODEL or 'default'}")
            logger.debug(f"   - Base URL: {settings.XINFERENCE_BASE_URL}")
            
            return XinferenceAdapter(
                api_key=settings.XINFERENCE_API_KEY,
                model_name=settings.XINFERENCE_MODEL or "",
                base_url=settings.XINFERENCE_BASE_URL
            )
        
        # HuggingFace
        elif provider == "huggingface":
            if not settings.HUGGINGFACE_API_KEY:
                raise ValueError("HuggingFace API Key 未配置，请在 .env 中设置 HUGGINGFACE_API_KEY")
            
            from .huggingface_adapter import HuggingFaceAdapter
            
            logger.debug(f"   - 模型: {settings.HUGGINGFACE_MODEL}")
            logger.debug(f"   - Base URL: {settings.HUGGINGFACE_BASE_URL}")
            
            return HuggingFaceAdapter(
                api_key=settings.HUGGINGFACE_API_KEY,
                model_name=settings.HUGGINGFACE_MODEL,
                base_url=settings.HUGGINGFACE_BASE_URL
            )
        
        # ModelScope（魔塔）
        elif provider == "modelscope":
            if not settings.MODELSCOPE_API_KEY:
                raise ValueError("ModelScope API Key 未配置，请在 .env 中设置 MODELSCOPE_API_KEY")
            
            from .modelscope_adapter import ModelScopeAdapter
            
            logger.debug(f"   - 模型: {settings.MODELSCOPE_MODEL}")
            logger.debug(f"   - Base URL: {settings.MODELSCOPE_BASE_URL}")
            
            return ModelScopeAdapter(
                api_key=settings.MODELSCOPE_API_KEY,
                model_name=settings.MODELSCOPE_MODEL,
                base_url=settings.MODELSCOPE_BASE_URL
            )
        
        # BaiChuan（百川）
        elif provider == "baichuan":
            if not settings.BAICHUAN_API_KEY:
                raise ValueError("BaiChuan API Key 未配置，请在 .env 中设置 BAICHUAN_API_KEY")
            
            from .baichuan_adapter import BaiChuanAdapter
            
            logger.debug(f"   - 模型: {settings.BAICHUAN_MODEL}")
            logger.debug(f"   - Base URL: {settings.BAICHUAN_BASE_URL}")
            
            return BaiChuanAdapter(
                api_key=settings.BAICHUAN_API_KEY,
                secret_key=settings.BAICHUAN_SECRET_KEY,
                model_name=settings.BAICHUAN_MODEL,
                base_url=settings.BAICHUAN_BASE_URL
            )
        
        # DeepSeek（OpenRouter API）
        elif provider == "deepseek":
            api_key = settings.DEEPSEEK_API_KEY or settings.GPT_API_KEY
            if not api_key:
                raise ValueError("DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY 或 GPT_API_KEY")
            
            from .deepseek_adapter import DeepSeekAdapter
            
            logger.debug(f"   - 模型: {settings.DEEPSEEK_MODEL}")
            logger.debug(f"   - Base URL: {settings.DEEPSEEK_BASE_URL}")
            logger.debug(f"   - API Key: {api_key[:12]}...{api_key[-4:]}")
            
            return DeepSeekAdapter(
                api_key=api_key,
                model_name=settings.DEEPSEEK_MODEL,
                base_url=settings.DEEPSEEK_BASE_URL,
                verify_ssl=settings.DEEPSEEK_VERIFY_SSL
            )
        
        # Qwen（OpenRouter API）
        elif provider == "qwen":
            api_key = settings.QWEN_API_KEY or settings.GPT_API_KEY
            if not api_key:
                raise ValueError("Qwen API Key 未配置，请在 .env 中设置 QWEN_API_KEY 或 GPT_API_KEY")
            
            from .qwen_adapter import QwenAdapter
            
            logger.debug(f"   - 模型: {settings.QWEN_MODEL}")
            logger.debug(f"   - Base URL: {settings.QWEN_BASE_URL}")
            logger.debug(f"   - API Key: {api_key[:12]}...{api_key[-4:]}")
            
            return QwenAdapter(
                api_key=api_key,
                model_name=settings.QWEN_MODEL,
                base_url=settings.QWEN_BASE_URL,
                verify_ssl=settings.QWEN_VERIFY_SSL
            )

        # Ollama（本地部署，OpenAI 兼容端点）
        elif provider == "ollama":
            from .deepseek_adapter import DeepSeekAdapter

            base_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/v1"
            logger.debug(f"   - 模型: {settings.OLLAMA_CHAT_MODEL}")
            logger.debug(f"   - Base URL: {base_url}")

            return DeepSeekAdapter(
                api_key="ollama",
                model_name=settings.OLLAMA_CHAT_MODEL,
                base_url=base_url
            )

        # 不支持的提供商
        else:
            raise ValueError(
                f"不支持的 LLM 提供商: {provider}\n"
                f"支持的提供商: zhipu, openai, claude, minimax, xinference, huggingface, modelscope, baichuan, gpt, deepseek, qwen, ollama\n"
                f"请在 .env 中设置 LLM_PROVIDER"
            )
    
    @staticmethod
    def get_supported_providers() -> list:
        """
        获取支持的提供商列表
        
        Returns:
            支持的提供商名称列表
        """
        return [
            "zhipu",
            "openai",
            "claude",
            "minimax",
            "xinference",
            "huggingface",
            "modelscope",
            "baichuan",
            "gpt",
            "deepseek",
            "qwen",
            "ollama"
        ]
    
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
