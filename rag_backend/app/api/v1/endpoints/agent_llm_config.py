"""
智能体LLM配置 API 端点

提供智能体级别的大语言模型配置管理功能
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent_llm_config import (
    AgentLLMConfigSchema,
    TenantLLMConfigSchema,
    CreateAgentLLMConfigRequest
)
from app.api import deps
from app.models.user import User
from app.models.tenant_settings import TenantSettings
from app.agent_framework.llm.agent_llm_config import (
    AgentLLMConfigManager,
    AgentType
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/llm-config", response_model=TenantLLMConfigSchema)
async def get_llm_config(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取当前租户的智能体LLM配置
    
    返回所有智能体的LLM配置，包括默认配置和每个智能体的自定义配置
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        TenantSettings.__table__.select().where(TenantSettings.tenant_id == tenant_id)
    )
    tenant_settings = result.scalar_one_or_none()
    
    if not tenant_settings:
        return TenantLLMConfigSchema()
    
    llm_config = AgentLLMConfigManager.load_from_extra_settings(
        tenant_settings.extra_settings
    )
    
    return TenantLLMConfigSchema(
        default_provider=llm_config.default_provider,
        default_model=llm_config.default_model,
        agent_overrides={
            agent_type: AgentLLMConfigSchema(**config.model_dump())
            for agent_type, config in llm_config.agent_overrides.items()
        }
    )


@router.post("/llm-config/agent")
async def create_or_update_agent_llm_config(
    request: CreateAgentLLMConfigRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    创建或更新单个智能体的LLM配置
    
    支持为不同类型的智能体配置不同的LLM模型和API
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        TenantSettings.__table__.select().where(TenantSettings.tenant_id == tenant_id)
    )
    tenant_settings = result.scalar_one_or_none()
    
    extra_settings = tenant_settings.extra_settings if tenant_settings else {}
    
    llm_config = AgentLLMConfigManager.load_from_extra_settings(extra_settings)
    
    agent_config = AgentLLMConfigManager.create_agent_config(
        agent_type=AgentType(request.agent_type),
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        enabled=request.enabled
    )
    
    llm_config.agent_overrides[request.agent_type] = agent_config
    
    new_extra_settings = AgentLLMConfigManager.save_to_extra_settings(
        extra_settings, llm_config
    )
    
    if tenant_settings:
        tenant_settings.extra_settings = new_extra_settings
    else:
        tenant_settings = TenantSettings(
            tenant_id=tenant_id,
            company_name=f"Tenant-{tenant_id}",
            extra_settings=new_extra_settings
        )
        db.add(tenant_settings)
    
    await db.commit()
    
    logger.info(f"[智能体LLM配置] 租户 {tenant_id} 更新了智能体 {request.agent_type} 的配置: {request.provider}/{request.model}")
    
    return {
        "message": "配置已更新",
        "agent_type": request.agent_type,
        "provider": request.provider,
        "model": request.model
    }


@router.delete("/llm-config/agent/{agent_type}")
async def delete_agent_llm_config(
    agent_type: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    删除指定智能体的LLM配置
    
    删除后该智能体将使用全局默认配置
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        TenantSettings.__table__.select().where(TenantSettings.tenant_id == tenant_id)
    )
    tenant_settings = result.scalar_one_or_none()
    
    if not tenant_settings:
        raise HTTPException(status_code=404, detail="租户配置不存在")
    
    extra_settings = tenant_settings.extra_settings or {}
    llm_config = AgentLLMConfigManager.load_from_extra_settings(extra_settings)
    
    if agent_type in llm_config.agent_overrides:
        del llm_config.agent_overrides[agent_type]
        tenant_settings.extra_settings = AgentLLMConfigManager.save_to_extra_settings(
            extra_settings, llm_config
        )
        await db.commit()
        
        logger.info(f"[智能体LLM配置] 租户 {tenant_id} 删除了智能体 {agent_type} 的配置")
        
        return {"message": "配置已删除", "agent_type": agent_type}
    else:
        raise HTTPException(status_code=404, detail=f"智能体 {agent_type} 没有自定义配置")


@router.get("/llm-config/agent/{agent_type}")
async def get_agent_llm_config(
    agent_type: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取指定智能体的LLM配置
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        TenantSettings.__table__.select().where(TenantSettings.tenant_id == tenant_id)
    )
    tenant_settings = result.scalar_one_or_none()
    
    if not tenant_settings:
        raise HTTPException(status_code=404, detail="租户配置不存在")
    
    llm_config = AgentLLMConfigManager.load_from_extra_settings(
        tenant_settings.extra_settings
    )
    
    agent_config = llm_config.get_agent_config(agent_type)
    
    if agent_config:
        return AgentLLMConfigSchema(**agent_config.model_dump())
    else:
        return {
            "agent_type": agent_type,
            "provider": None,
            "model": None,
            "message": "该智能体使用全局默认配置"
        }


@router.get("/supported-providers")
async def get_supported_providers():
    """
    获取支持的LLM提供商列表
    """
    return {
        "providers": [
            {
                "id": "gpt",
                "name": "GPT (OpenRouter)",
                "models": ["openai/gpt-5.4-nano", "openai/gpt-4o", "openai/gpt-4o-mini"]
            },
            {
                "id": "zhipu",
                "name": "智谱 GLM",
                "models": ["glm-4", "glm-4-flash", "glm-4-plus"]
            },
            {
                "id": "minimax",
                "name": "MiniMax",
                "models": ["abab6-chat", "abab5.5-chat"]
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
            },
            {
                "id": "claude",
                "name": "Claude (Anthropic)",
                "models": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]
            },
            {
                "id": "deepseek",
                "name": "DeepSeek (OpenRouter)",
                "models": ["deepseek/deepseek-chat-v3-0324", "deepseek/deepseek-coder-v2"]
            },
            {
                "id": "qwen",
                "name": "Qwen 通义千问 (OpenRouter)",
                "models": ["qwen/qwen3.6-plus:free", "qwen/qwen3.6-plus", "qwen/qwen2.5-72b-instruct"]
            }
        ]
    }
