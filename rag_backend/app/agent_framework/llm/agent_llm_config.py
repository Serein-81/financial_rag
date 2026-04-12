# app/agent_framework/llm/agent_llm_config.py

"""
智能体LLM配置模型

支持每个智能体独立配置不同的大语言模型
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class AgentType(str, Enum):
    """智能体类型枚举"""
    REACT = "react"
    PLAN = "plan"
    REFLECT = "reflect"
    OUTPUT = "output"
    REPORT = "report"
    REVIEWED = "reviewed"
    CHAT = "chat"
    GREETING = "greeting"
    FINANCE = "finance"
    TAX = "tax"
    LEGAL = "legal"


class AgentLLMConfig(BaseModel):
    """
    单个智能体的LLM配置
    """
    agent_type: AgentType = Field(..., description="智能体类型")
    provider: str = Field(..., description="LLM提供商 (gpt, zhipu, minimax, openai, claude等)")
    model: Optional[str] = Field(None, description="模型名称，不填则使用提供商默认")
    api_key: Optional[str] = Field(None, description="API Key，不填则使用全局配置")
    base_url: Optional[str] = Field(None, description="API Base URL")
    temperature: float = Field(0.1, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大Token数")
    enabled: bool = Field(True, description="是否启用此配置")


class TenantLLMConfig(BaseModel):
    """
    租户级LLM配置

    包含全局默认配置和每个智能体的独立配置
    """
    default_provider: str = Field("zhipu", description="默认LLM提供商")
    default_model: Optional[str] = Field(None, description="默认模型")
    
    agent_overrides: Dict[str, AgentLLMConfig] = Field(
        default_factory=dict,
        description="智能体级别的LLM配置覆盖"
    )
    
    def get_agent_config(self, agent_type: str) -> Optional[AgentLLMConfig]:
        """
        获取指定智能体类型的配置
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            智能体配置，如果未设置则返回None
        """
        return self.agent_overrides.get(agent_type)
    
    def is_agent_customized(self, agent_type: str) -> bool:
        """
        检查指定智能体是否配置了自定义LLM
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            是否已自定义
        """
        config = self.get_agent_config(agent_type)
        return config is not None and config.enabled


class AgentLLMConfigManager:
    """
    智能体LLM配置管理器
    
    从数据库加载和管理配置
    """
    
    @staticmethod
    def load_from_extra_settings(extra_settings: Optional[Dict[str, Any]]) -> TenantLLMConfig:
        """
        从extra_settings加载配置
        
        Args:
            extra_settings: 数据库中的extra_settings字段
            
        Returns:
            TenantLLMConfig对象
        """
        if not extra_settings:
            return TenantLLMConfig()
        
        llm_config_data = extra_settings.get("llm_config")
        if not llm_config_data:
            return TenantLLMConfig()
        
        return TenantLLMConfig(**llm_config_data)
    
    @staticmethod
    def save_to_extra_settings(
        extra_settings: Optional[Dict[str, Any]], 
        config: TenantLLMConfig
    ) -> Dict[str, Any]:
        """
        保存配置到extra_settings
        
        Args:
            extra_settings: 现有的extra_settings
            config: 要保存的配置
            
        Returns:
            更新后的extra_settings
        """
        if extra_settings is None:
            extra_settings = {}
        
        extra_settings = extra_settings.copy()
        extra_settings["llm_config"] = config.model_dump()
        
        return extra_settings
    
    @staticmethod
    def create_agent_config(
        agent_type: AgentType,
        provider: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        enabled: bool = True
    ) -> AgentLLMConfig:
        """
        创建单个智能体的LLM配置
        
        Args:
            agent_type: 智能体类型
            provider: LLM提供商
            model: 模型名称
            api_key: API Key
            base_url: Base URL
            temperature: 温度
            max_tokens: 最大Token
            enabled: 是否启用
            
        Returns:
            AgentLLMConfig对象
        """
        return AgentLLMConfig(
            agent_type=agent_type,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            enabled=enabled
        )
