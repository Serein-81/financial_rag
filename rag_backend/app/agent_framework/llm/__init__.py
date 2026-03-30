# app/agent_framework/llm/__init__.py

"""
LLM 适配器模块

提供统一的大模型调用接口，支持多种模型提供商
"""

# 基础组件
from .base_adapter import BaseLLMAdapter, LLMResponse
from .errors import LLMErrorCode, LLMError, ErrorClassifier, ERROR_PREFIX
from .model_policies import apply_model_family_policies, model_policy_manager
from .token_utils import num_tokens_from_string, total_token_count_from_response
from .notifications import get_length_notification, append_length_notification

# 工厂
from .factory import LLMAdapterFactory, create_llm_adapter

# 各提供商适配器
from .zhipu_adapter import ZhipuAdapter
from .openai_adapter import OpenAIAdapter
from .claude_adapter import ClaudeAdapter
from .minimax_adapter import MiniMaxAdapter
from .xinference_adapter import XinferenceAdapter
from .huggingface_adapter import HuggingFaceAdapter
from .modelscope_adapter import ModelScopeAdapter
from .baichuan_adapter import BaiChuanAdapter

__all__ = [
    # 基础组件
    "BaseLLMAdapter",
    "LLMResponse",
    "LLMErrorCode",
    "LLMError",
    "ErrorClassifier",
    "ERROR_PREFIX",
    "apply_model_family_policies",
    "model_policy_manager",
    "num_tokens_from_string",
    "total_token_count_from_response",
    "get_length_notification",
    "append_length_notification",
    
    # 工厂
    "LLMAdapterFactory",
    "create_llm_adapter",
    
    # 各提供商适配器
    "ZhipuAdapter",
    "OpenAIAdapter",
    "ClaudeAdapter",
    "MiniMaxAdapter",
    "XinferenceAdapter",
    "HuggingFaceAdapter",
    "ModelScopeAdapter",
    "BaiChuanAdapter",
]

# 便捷函数：获取支持的提供商列表
def get_supported_providers():
    """获取支持的 LLM 提供商列表"""
    return LLMAdapterFactory.get_supported_providers()

def get_current_provider():
    """获取当前配置的 LLM 提供商"""
    return LLMAdapterFactory.get_current_provider()
