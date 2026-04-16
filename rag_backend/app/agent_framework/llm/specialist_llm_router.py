# app/agent_framework/llm/specialist_llm_router.py

"""
专家智能体LLM路由器

根据智能体类型自动路由到对应的LLM配置
"""

import logging
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tenant_settings import TenantSettings
from .agent_llm_config import AgentLLMConfig, AgentLLMConfigManager, AgentType
from .agent_adapter_factory import AgentLLMAdapterFactory
from .base_adapter import BaseLLMAdapter

logger = logging.getLogger(__name__)


class SpecialistLLMRouter:
    """
    专家智能体LLM路由器
    
    根据智能体类型自动选择合适的LLM适配器
    支持：
    - 对话/闲聊智能体 -> 使用 LLM_PROVIDER_DEFAULT（默认）
    - 专家智能体（金融、税务、法律） -> 使用 LLM_PROVIDER_SPECIALIST
    
    配置优先级：
    1. 如果专家智能体供应商有值，专家智能体使用专家配置，其他使用默认配置
    2. 如果专家智能体供应商为空，所有智能体都使用 LLM_PROVIDER 的值
    """
    
    @classmethod
    def _get_provider_for_type(cls, agent_type: AgentType) -> str:
        """
        根据智能体类型获取 LLM 提供商
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            LLM 提供商名称
        """
        return settings.get_llm_provider_for_agent(agent_type.value)
    
    @classmethod
    def _get_model_for_provider(cls, provider: str) -> Optional[str]:
        """
        根据提供商获取默认模型
        
        Args:
            provider: LLM 提供商
            
        Returns:
            默认模型名称
        """
        model_map = {
            "deepseek": "deepseek/deepseek-chat-v3-0324",
            "qwen": "qwen/qwen3.6-plus:free",
            "zhipu": "glm-4-flash",
            "gpt": "openai/gpt-4o-mini",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-sonnet-20240229",
            "minimax": "MiniMax-Text-01",
        }
        return model_map.get(provider.lower())
    
    @classmethod
    def get_default_adapter(cls) -> BaseLLMAdapter:
        """
        获取默认适配器（使用 LLM_PROVIDER）
        
        Returns:
            LLM 适配器实例
        """
        provider = settings.LLM_PROVIDER or "zhipu"
        model = cls._get_model_for_provider(provider)
        
        print(f"🔧 [LLM路由] 获取默认适配器: provider={provider}, model={model}")
        
        config = AgentLLMConfig(
            agent_type=AgentType.REACT,
            provider=provider,
            model=model,
            enabled=True
        )
        
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    async def get_adapter_for_specialist(
        cls,
        agent_type: AgentType,
        tenant_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> BaseLLMAdapter:
        """
        获取专家智能体对应的LLM适配器
        
        Args:
            agent_type: 智能体类型
            tenant_id: 租户ID（用于获取租户自定义配置）
            db: 数据库会话
            
        Returns:
            LLM适配器实例
        """
        logger.info(f"[智能体LLM路由] 获取适配器: {agent_type.value}")
        
        agent_type_str = agent_type.value
        
        custom_config = None
        if tenant_id and db:
            custom_config = await cls._get_tenant_agent_config(tenant_id, agent_type_str, db)
        
        if custom_config and custom_config.enabled:
            logger.info(f"[智能体LLM路由] 使用租户自定义配置: {custom_config.provider}/{custom_config.model}")
            return AgentLLMAdapterFactory.create_adapter(custom_config)
        
        provider = cls._get_provider_for_type(agent_type)
        model = cls._get_model_for_provider(provider)
        
        config = AgentLLMConfig(
            agent_type=agent_type,
            provider=provider,
            model=model,
            enabled=True
        )
        
        logger.info(f"[智能体LLM路由] 使用配置: provider={provider}, model={model}")
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    async def _get_tenant_agent_config(
        cls,
        tenant_id: str,
        agent_type: str,
        db: AsyncSession
    ) -> Optional[AgentLLMConfig]:
        """
        从租户配置中获取智能体的自定义LLM配置
        
        Args:
            tenant_id: 租户ID
            agent_type: 智能体类型
            db: 数据库会话
            
        Returns:
            自定义配置，如果未设置则返回None
        """
        try:
            result = await db.execute(
                TenantSettings.__table__.select().where(TenantSettings.tenant_id == tenant_id)
            )
            tenant_settings = result.scalar_one_or_none()
            
            if not tenant_settings:
                return None
            
            llm_config = AgentLLMConfigManager.load_from_extra_settings(
                tenant_settings.extra_settings
            )
            
            return llm_config.get_agent_config(agent_type)
            
        except Exception as e:
            logger.warning(f"[智能体LLM路由] 获取租户配置失败: {e}")
            return None
    
    @classmethod
    def get_chat_adapter(cls) -> BaseLLMAdapter:
        """
        获取对话/闲聊智能体的适配器
        
        Returns:
            LLM适配器实例
        """
        provider = cls._get_provider_for_type(AgentType.CHAT)
        model = cls._get_model_for_provider(provider)
        print(f"🔧 [LLM路由] 获取 Chat 适配器: provider={provider}, model={model}")
        
        config = AgentLLMConfig(
            agent_type=AgentType.CHAT,
            provider=provider,
            model=model,
            enabled=True
        )
        
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    def get_greeting_adapter(cls) -> BaseLLMAdapter:
        """
        获取问候/闲聊智能体的适配器
        
        Returns:
            LLM适配器实例
        """
        provider = cls._get_provider_for_type(AgentType.GREETING)
        model = cls._get_model_for_provider(provider)
        print(f"🔧 [LLM路由] 获取 Greeting 适配器: provider={provider}, model={model}")
        
        config = AgentLLMConfig(
            agent_type=AgentType.GREETING,
            provider=provider,
            model=model,
            enabled=True
        )
        
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    def get_finance_adapter(cls) -> BaseLLMAdapter:
        """
        获取金融专家智能体的适配器
        
        Returns:
            LLM适配器实例
        """
        provider = cls._get_provider_for_type(AgentType.FINANCE)
        model = cls._get_model_for_provider(provider)
        print(f"🔧 [LLM路由] 获取 Finance 适配器: provider={provider}, model={model}")
        
        config = AgentLLMConfig(
            agent_type=AgentType.FINANCE,
            provider=provider,
            model=model,
            enabled=True
        )
        
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    def get_tax_adapter(cls) -> BaseLLMAdapter:
        """
        获取税务专家智能体的适配器
        
        Returns:
            LLM适配器实例
        """
        provider = cls._get_provider_for_type(AgentType.TAX)
        model = cls._get_model_for_provider(provider)
        print(f"🔧 [LLM路由] 获取 Tax 适配器: provider={provider}, model={model}")
        
        config = AgentLLMConfig(
            agent_type=AgentType.TAX,
            provider=provider,
            model=model,
            enabled=True
        )
        
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    def get_legal_adapter(cls) -> BaseLLMAdapter:
        """
        获取法律专家智能体的适配器
        
        Returns:
            LLM适配器实例
        """
        provider = cls._get_provider_for_type(AgentType.LEGAL)
        model = cls._get_model_for_provider(provider)
        print(f"🔧 [LLM路由] 获取 Legal 适配器: provider={provider}, model={model}")
        
        config = AgentLLMConfig(
            agent_type=AgentType.LEGAL,
            provider=provider,
            model=model,
            enabled=True
        )
        
        return AgentLLMAdapterFactory.create_adapter(config)
    
    @classmethod
    def get_all_default_mappings(cls) -> Dict[str, tuple]:
        """
        获取所有默认的智能体-LLM映射
        
        Returns:
            映射字典 {agent_type: (provider, model)}
        """
        return {
            "chat": (cls._get_provider_for_type(AgentType.CHAT), cls._get_model_for_provider(cls._get_provider_for_type(AgentType.CHAT))),
            "greeting": (cls._get_provider_for_type(AgentType.GREETING), cls._get_model_for_provider(cls._get_provider_for_type(AgentType.GREETING))),
            "finance": (cls._get_provider_for_type(AgentType.FINANCE), cls._get_model_for_provider(cls._get_provider_for_type(AgentType.FINANCE))),
            "tax": (cls._get_provider_for_type(AgentType.TAX), cls._get_model_for_provider(cls._get_provider_for_type(AgentType.TAX))),
            "legal": (cls._get_provider_for_type(AgentType.LEGAL), cls._get_model_for_provider(cls._get_provider_for_type(AgentType.LEGAL))),
        }
