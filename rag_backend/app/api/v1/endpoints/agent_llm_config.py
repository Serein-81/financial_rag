"""
智能体LLM配置 API 端点

提供智能体级别的大语言模型配置管理功能
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_trace import AgentTrace
from app.schemas.agent_llm_config import (
    AgentLLMConfigSchema,
    TenantLLMConfigSchema,
    CreateAgentLLMConfigRequest
)
from app.api import deps
from app.models.user import User
from app.models.tenant_settings import TenantSettings
from app.agent_framework.llm.agent_llm_config import (
    AgentLLMConfig,
    AgentLLMConfigManager,
    AgentType
)
from app.agent_framework.llm.agent_adapter_factory import AgentLLMAdapterFactory

logger = logging.getLogger(__name__)
router = APIRouter()


class TestConnectionRequest(BaseModel):
    """测试模型连接请求"""
    provider: str = Field(..., description="LLM 提供商")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, description="API Key（本地模型可留空）")
    base_url: Optional[str] = Field(None, description="自定义 Base URL")


# provider id -> settings 中对应的「当前模型」字段名
_PROVIDER_MODEL_ATTR = {
    "gpt": "GPT_MODEL",
    "zhipu": "ZHIPU_MODEL",
    "minimax": "MINIMAX_MODEL",
    "openai": "OPENAI_MODEL",
    "claude": "CLAUDE_MODEL",
    "deepseek": "DEEPSEEK_MODEL",
    "qwen": "QWEN_MODEL",
    "ollama": "OLLAMA_CHAT_MODEL",
}


def _env_model_for(provider: Optional[str]) -> Optional[str]:
    """读取 .env 中该 provider 当前配置的模型名"""
    attr = _PROVIDER_MODEL_ATTR.get((provider or "").lower())
    return getattr(settings, attr, None) if attr else None


def _env_default_provider() -> str:
    """.env 中的全局默认对话提供商"""
    return settings.LLM_PROVIDER_DEFAULT or settings.LLM_PROVIDER or "zhipu"


@router.get("/llm-config", response_model=TenantLLMConfigSchema)
async def get_llm_config(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_admin_user)
):
    """
    获取当前租户的智能体LLM配置
    
    返回所有智能体的LLM配置，包括默认配置和每个智能体的自定义配置
    """
    tenant_id = current_user.tenant_id

    # .env 是全局默认的真实来源：未做租户覆盖时，前端应看到 .env 当前在用的 provider/model
    env_provider = _env_default_provider()
    env_model = _env_model_for(env_provider)

    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    tenant_settings = result.scalar_one_or_none()

    if not tenant_settings:
        return TenantLLMConfigSchema(default_provider=env_provider, default_model=env_model)

    llm_config = AgentLLMConfigManager.load_from_extra_settings(
        tenant_settings.extra_settings
    )

    return TenantLLMConfigSchema(
        default_provider=env_provider,
        default_model=env_model,
        agent_overrides={
            agent_type: AgentLLMConfigSchema(**config.model_dump())
            for agent_type, config in llm_config.agent_overrides.items()
        }
    )


@router.post("/llm-config/agent")
async def create_or_update_agent_llm_config(
    request: CreateAgentLLMConfigRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_admin_user)
):
    """
    创建或更新单个智能体的LLM配置
    
    支持为不同类型的智能体配置不同的LLM模型和API
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
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
    current_user: User = Depends(deps.require_admin_user)
):
    """
    删除指定智能体的LLM配置
    
    删除后该智能体将使用全局默认配置
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
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
    current_user: User = Depends(deps.require_admin_user)
):
    """
    获取指定智能体的LLM配置
    """
    tenant_id = current_user.tenant_id
    
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
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
async def get_supported_providers(
    current_user: User = Depends(deps.require_admin_user)
):
    """
    获取支持的 LLM 提供商目录（含分组与表单元数据）

    每个 provider 携带：
    - group:           分组（cloud=云端API / local=本地部署）
    - requires_api_key: 是否需要 API Key（本地模型为 false）
    - default_base_url: 默认 Base URL（可被前端覆盖）
    - supports_detect: 是否支持"检测本地已安装模型"
    - configured_model: .env 中当前实际配置的模型（会置顶到 models 列表）
    """
    providers = [
            {
                "id": "gpt", "name": "GPT (OpenRouter)", "group": "cloud",
                "requires_api_key": True, "default_base_url": "https://openrouter.ai/api/v1",
                "models": ["openai/gpt-5.4-nano", "openai/gpt-4o", "openai/gpt-4o-mini"]
            },
            {
                "id": "zhipu", "name": "智谱 GLM", "group": "cloud",
                "requires_api_key": True, "default_base_url": None,
                "models": ["glm-4", "glm-4-flash", "glm-4-plus"]
            },
            {
                "id": "minimax", "name": "MiniMax", "group": "cloud",
                "requires_api_key": True, "default_base_url": "https://api.minimax.chat/v1",
                "models": ["abab6-chat", "abab5.5-chat"]
            },
            {
                "id": "openai", "name": "OpenAI", "group": "cloud",
                "requires_api_key": True, "default_base_url": "https://api.openai.com/v1",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
            },
            {
                "id": "claude", "name": "Claude (Anthropic)", "group": "cloud",
                "requires_api_key": True, "default_base_url": "https://api.anthropic.com/v1",
                "models": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]
            },
            {
                "id": "deepseek", "name": "DeepSeek (OpenRouter)", "group": "cloud",
                "requires_api_key": True, "default_base_url": "https://openrouter.ai/api/v1",
                "models": ["deepseek/deepseek-chat-v3-0324", "deepseek/deepseek-coder-v2"]
            },
            {
                "id": "qwen", "name": "Qwen 通义千问 (OpenRouter)", "group": "cloud",
                "requires_api_key": True, "default_base_url": "https://openrouter.ai/api/v1",
                "models": ["qwen/qwen3.6-plus:free", "qwen/qwen3.6-plus", "qwen/qwen2.5-72b-instruct"]
            },
            {
                "id": "ollama", "name": "Ollama (本地部署)", "group": "local",
                "requires_api_key": False,
                "default_base_url": settings.OLLAMA_BASE_URL,
                "supports_detect": True,
                "note": "需选择支持 Function Calling 的本地模型（如 qwen2.5、llama3.1），否则工具调用不可用",
                "models": ["qwen2.5", "llama3.1", "mistral"]
            }
    ]

    # 注入 .env 实际配置的模型：置顶并标记 configured_model，让前端反映"当前在用"
    for p in providers:
        cm = _env_model_for(p["id"])
        p["configured_model"] = cm
        if cm and cm not in p["models"]:
            p["models"] = [cm] + p["models"]

    return {"providers": providers}


@router.get("/llm-config/ollama/models")
async def list_ollama_models(
    base_url: Optional[str] = Query(None, description="Ollama 服务地址，默认取配置"),
    current_user: User = Depends(deps.require_admin_user)
):
    """
    检测本地 Ollama 已安装的模型列表（代理 Ollama /api/tags）
    """
    target = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{target}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"无法连接 Ollama 服务：{target}，请确认已启动 `ollama serve`")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"读取 Ollama 模型列表失败：{e}")

    models = [
        {"name": m.get("name"), "size": m.get("size"), "modified_at": m.get("modified_at")}
        for m in data.get("models", [])
    ]
    return {"base_url": target, "models": models}


@router.post("/llm-config/test-connection")
async def test_llm_connection(
    request: TestConnectionRequest,
    current_user: User = Depends(deps.require_admin_user)
):
    """
    测试指定模型配置是否可用（发一次最小请求验证连通性与鉴权）
    """
    try:
        config = AgentLLMConfig(
            agent_type=AgentType.CHAT,
            provider=request.provider,
            model=request.model,
            api_key=request.api_key,
            base_url=request.base_url,
            enabled=True,
        )
        adapter = AgentLLMAdapterFactory.create_adapter(config)
    except Exception as e:
        return {"ok": False, "error": f"适配器创建失败：{e}"}

    start = time.monotonic()
    try:
        response = await asyncio.wait_for(
            adapter.generate("ping", temperature=0.0, max_tokens=8),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        return {"ok": False, "error": "连接超时（30s），请检查服务地址与网络"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        close = getattr(adapter, "close", None)
        if close:
            try:
                await close()
            except Exception:
                pass

    latency_ms = int((time.monotonic() - start) * 1000)
    content = (getattr(response, "content", "") or "")
    from app.agent_framework.llm.errors import ERROR_PREFIX
    if ERROR_PREFIX in content:
        return {"ok": False, "error": content, "latency_ms": latency_ms}

    return {
        "ok": True,
        "latency_ms": latency_ms,
        "model": getattr(response, "model", request.model),
        "sample": content[:120],
    }


# 使用概览中展示的对话角色
_OVERVIEW_ROLES = [
    ("chat", "默认对话"),
    ("finance", "金融专家"),
    ("tax", "税务专家"),
    ("legal", "法律专家"),
]


@router.get("/llm-config/usage-overview")
async def get_usage_overview(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_admin_user),
):
    """
    管理员视角：各企业 / 各角色当前生效模型 + 调用统计

    说明：agent_traces 未逐次持久化"实际使用的模型"，因此"当前生效模型"按配置解析
    （租户自定义优先，否则回退 .env 全局默认）；调用次数/最近对话时间来自 agent_traces。
    """
    # 1) 各企业配置
    ts_result = await db.execute(select(TenantSettings))
    tenants = ts_result.scalars().all()

    # 2) 各企业调用统计（按 tenant 聚合 agent_traces）
    usage_result = await db.execute(
        select(
            AgentTrace.tenant_id,
            func.count(AgentTrace.id),
            func.coalesce(func.sum(AgentTrace.tool_calls_count), 0),
            func.max(AgentTrace.created_at),
        ).group_by(AgentTrace.tenant_id)
    )
    usage_map = {
        row[0]: {
            "total_conversations": int(row[1] or 0),
            "total_tool_calls": int(row[2] or 0),
            "last_conversation_at": row[3],
        }
        for row in usage_result.all()
    }

    # 2b) 各企业「最近一次对话实际使用的模型」（DISTINCT ON tenant_id 取最新一条）
    last_model_result = await db.execute(
        select(AgentTrace.tenant_id, AgentTrace.model_name)
        .order_by(AgentTrace.tenant_id, desc(AgentTrace.created_at))
        .distinct(AgentTrace.tenant_id)
    )
    last_model_map = {row[0]: row[1] for row in last_model_result.all()}

    # 2c) 各企业「各模型调用次数」
    model_count_result = await db.execute(
        select(AgentTrace.tenant_id, AgentTrace.model_name, func.count(AgentTrace.id))
        .group_by(AgentTrace.tenant_id, AgentTrace.model_name)
        .order_by(AgentTrace.tenant_id, desc(func.count(AgentTrace.id)))
    )
    model_counts_map: dict = {}
    for tid, model, cnt in model_count_result.all():
        model_counts_map.setdefault(tid, []).append(
            {"model": model or "未记录", "count": int(cnt or 0)}
        )

    def resolve_roles(extra_settings):
        llm_config = AgentLLMConfigManager.load_from_extra_settings(extra_settings)
        rows = []
        for role, label in _OVERVIEW_ROLES:
            ov = llm_config.get_agent_config(role)
            if ov and ov.enabled:
                provider = ov.provider
                model = ov.model or _env_model_for(provider)
                source = "custom"
            else:
                provider = settings.get_llm_provider_for_agent(role)
                model = _env_model_for(provider)
                source = "default"
            rows.append({
                "role": role, "label": label,
                "provider": provider, "model": model, "source": source,
            })
        return rows

    tenants_out = []
    for t in tenants:
        usage = dict(usage_map.get(t.tenant_id, {
            "total_conversations": 0, "total_tool_calls": 0, "last_conversation_at": None,
        }))
        usage["last_model"] = last_model_map.get(t.tenant_id)
        usage["model_counts"] = model_counts_map.get(t.tenant_id, [])
        tenants_out.append({
            "tenant_id": t.tenant_id,
            "company_name": t.company_name,
            "roles": resolve_roles(t.extra_settings),
            "usage": usage,
        })

    env_provider = _env_default_provider()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "env_default": {"provider": env_provider, "model": _env_model_for(env_provider)},
        "note": "“当前生效模型”按配置解析（自定义优先，否则回退 .env 全局默认）；"
                "“最近对话模型 / 各模型调用次数”来自 agent_traces 实际记录（迁移前的旧对话显示为“未记录”）。",
        "tenants": tenants_out,
    }
