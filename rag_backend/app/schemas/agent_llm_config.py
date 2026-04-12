"""
智能体LLM配置 Pydantic Schemas
"""

from typing import Optional, Dict
from pydantic import BaseModel, Field


class AgentLLMConfigSchema(BaseModel):
    """单个智能体的LLM配置"""
    agent_type: str = Field(..., description="智能体类型")
    provider: str = Field(..., description="LLM提供商")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, description="API Key（可选）")
    base_url: Optional[str] = Field(None, description="Base URL")
    temperature: float = Field(0.1, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大Token数")
    enabled: bool = Field(True, description="是否启用")


class TenantLLMConfigSchema(BaseModel):
    """租户级LLM配置"""
    default_provider: str = Field("zhipu", description="默认LLM提供商")
    default_model: Optional[str] = Field(None, description="默认模型")
    agent_overrides: Dict[str, AgentLLMConfigSchema] = Field(
        default_factory=dict,
        description="智能体级别的LLM配置覆盖"
    )


class CreateAgentLLMConfigRequest(BaseModel):
    """创建/更新智能体LLM配置的请求"""
    agent_type: str = Field(..., description="智能体类型 (react, plan, reflect, output, report, reviewed, chat, greeting, finance, tax, legal)")
    provider: str = Field(..., description="LLM提供商 (gpt, zhipu, minimax, openai, claude, deepseek, qwen等)")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, description="API Key（可选，不填则使用全局配置）")
    base_url: Optional[str] = Field(None, description="Base URL（可选）")
    temperature: float = Field(0.1, description="温度参数", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="最大Token数", ge=1)
    enabled: bool = Field(True, description="是否启用此配置")


class UpdateAgentLLMConfigRequest(BaseModel):
    """更新智能体LLM配置的请求"""
    provider: Optional[str] = Field(None, description="LLM提供商")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, description="API Key")
    base_url: Optional[str] = Field(None, description="Base URL")
    temperature: Optional[float] = Field(None, description="温度参数", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="最大Token数", ge=1)
    enabled: Optional[bool] = Field(None, description="是否启用")


class DeleteAgentLLMConfigRequest(BaseModel):
    """删除智能体LLM配置的请求"""
    agent_type: str = Field(..., description="要删除的智能体类型")
