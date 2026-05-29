"""
多模态配置管理 API

用户可以通过这些接口配置多模态功能。
全部使用 AsyncSession (SQLAlchemy 2.0 风格)。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.user_multimodal_config import (
    UserMultiModalConfig,
    UserMultiModalUsageLog
)
from app.middleware.tenant_middleware import get_current_tenant_id
from app.utils.crypto import encrypt_secret, decrypt_secret, mask_secret

router = APIRouter()


# ==================== 内部工具 ====================

def _serialize_config(config: UserMultiModalConfig) -> dict:
    """Convert ORM row to API dict with API key masked (G4: never leak plaintext).

    ``to_dict()`` may include ``user_api_key_encrypted`` verbatim — we strip it
    and emit a display-safe ``user_api_key_masked`` instead.
    """
    data = config.to_dict() if hasattr(config, "to_dict") else {}
    encrypted = getattr(config, "user_api_key_encrypted", None)
    plaintext = decrypt_secret(encrypted) if encrypted else None
    data["user_api_key_masked"] = mask_secret(plaintext) if plaintext else ""
    data["has_user_api_key"] = bool(plaintext)
    # Never return ciphertext or plaintext to the client
    data.pop("user_api_key_encrypted", None)
    data.pop("user_api_key", None)
    return data


async def _get_config_by_tenant(db: AsyncSession, tenant_id: str) -> Optional[UserMultiModalConfig]:
    stmt = select(UserMultiModalConfig).where(UserMultiModalConfig.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ==================== Pydantic 模型 ====================

class MultiModalConfigCreate(BaseModel):
    """创建/更新多模态配置"""
    enabled: bool = Field(True, description="是否启用多模态功能")
    table_mode: str = Field("rule_based", description="表格解析模式: basic/rule_based/ai_enhanced")
    chart_mode: str = Field("rule_based", description="图表解析模式: basic/rule_based/ai_enhanced")
    image_mode: str = Field("basic", description="图片解析模式: basic/rule_based/ai_enhanced")
    vision_model: Optional[str] = Field("gpt-4o", description="Vision模型")
    llm_model: Optional[str] = Field("gpt-4o-mini", description="LLM模型")
    use_own_api_key: bool = Field(False, description="是否使用自己的API Key")
    user_api_key: Optional[str] = Field(None, description="用户API Key（如果使用）")
    daily_ai_limit: int = Field(100, description="每日AI调用限制")
    enable_cache: bool = Field(True, description="是否启用缓存")
    ai_timeout: int = Field(30, description="AI超时时间（秒）")
    max_concurrent: int = Field(3, description="最大并发数")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "table_mode": "rule_based",
                "chart_mode": "rule_based",
                "image_mode": "basic",
                "vision_model": "gpt-4o",
                "llm_model": "gpt-4o-mini",
                "use_own_api_key": False,
                "daily_ai_limit": 100,
                "enable_cache": True
            }
        }


class MultiModalConfigUpdate(BaseModel):
    """更新多模态配置（部分字段可选）"""
    enabled: Optional[bool] = None
    table_mode: Optional[str] = None
    chart_mode: Optional[str] = None
    image_mode: Optional[str] = None
    vision_model: Optional[str] = None
    llm_model: Optional[str] = None
    use_own_api_key: Optional[bool] = None
    user_api_key: Optional[str] = None
    daily_ai_limit: Optional[int] = None
    enable_cache: Optional[bool] = None
    ai_timeout: Optional[int] = None
    max_concurrent: Optional[int] = None


class UsageStatsResponse(BaseModel):
    """使用统计响应"""
    daily_limit: int
    daily_used: int
    daily_remaining: int
    total_calls: int
    cost_estimate: dict


# ==================== API 端点 ====================

@router.get("/config", summary="获取多模态配置")
async def get_multimodal_config(
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前租户的多模态配置

    如果租户没有配置，返回默认配置。
    """
    config = await _get_config_by_tenant(db, tenant_id)

    if not config:
        # 返回默认配置
        return {
            "tenant_id": tenant_id,
            "enabled": True,
            "modes": {
                "table": "rule_based",
                "chart": "rule_based",
                "image": "basic"
            },
            "models": {
                "vision": "gpt-4o",
                "llm": "gpt-4o-mini"
            },
            "use_own_api_key": False,
            "cost_control": {
                "daily_limit": 100,
                "daily_used": 0,
                "total_calls": 0
            },
            "performance": {
                "enable_cache": True,
                "ai_timeout": 30,
                "max_concurrent": 3
            },
            "is_default": True
        }

    return _serialize_config(config)


@router.post("/config", summary="创建/更新多模态配置")
async def upsert_multimodal_config(
    config_data: MultiModalConfigCreate,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    创建或更新多模态配置

    如果租户已有配置，则更新；否则创建新配置。
    """
    # 验证模式值
    valid_modes = ["basic", "rule_based", "ai_enhanced"]
    if config_data.table_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"无效的table_mode: {config_data.table_mode}")
    if config_data.chart_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"无效的chart_mode: {config_data.chart_mode}")
    if config_data.image_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"无效的image_mode: {config_data.image_mode}")

    config = await _get_config_by_tenant(db, tenant_id)

    if config:
        # 更新现有配置
        config.enabled = config_data.enabled
        config.table_mode = config_data.table_mode
        config.chart_mode = config_data.chart_mode
        config.image_mode = config_data.image_mode
        config.vision_model = config_data.vision_model
        config.llm_model = config_data.llm_model
        config.use_own_api_key = config_data.use_own_api_key
        config.daily_ai_limit = config_data.daily_ai_limit
        config.enable_cache = config_data.enable_cache
        config.ai_timeout = config_data.ai_timeout
        config.max_concurrent = config_data.max_concurrent

        # 如果提供了API Key，加密存储（G4: Fernet, key derived from SECRET_KEY）
        if config_data.user_api_key:
            config.user_api_key_encrypted = encrypt_secret(config_data.user_api_key)

    else:
        # 创建新配置
        config = UserMultiModalConfig(
            tenant_id=tenant_id,
            enabled=config_data.enabled,
            table_mode=config_data.table_mode,
            chart_mode=config_data.chart_mode,
            image_mode=config_data.image_mode,
            vision_model=config_data.vision_model,
            llm_model=config_data.llm_model,
            use_own_api_key=config_data.use_own_api_key,
            daily_ai_limit=config_data.daily_ai_limit,
            enable_cache=config_data.enable_cache,
            ai_timeout=config_data.ai_timeout,
            max_concurrent=config_data.max_concurrent
        )

        if config_data.user_api_key:
            config.user_api_key_encrypted = encrypt_secret(config_data.user_api_key)

        db.add(config)

    await db.commit()
    await db.refresh(config)

    return {
        "message": "配置保存成功",
        "config": _serialize_config(config)
    }


@router.patch("/config", summary="部分更新多模态配置")
async def update_multimodal_config(
    config_data: MultiModalConfigUpdate,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    部分更新多模态配置

    只更新提供的字段。
    """
    config = await _get_config_by_tenant(db, tenant_id)

    if not config:
        raise HTTPException(status_code=404, detail="配置不存在，请先创建配置")

    # 更新提供的字段
    if config_data.enabled is not None:
        config.enabled = config_data.enabled
    if config_data.table_mode is not None:
        config.table_mode = config_data.table_mode
    if config_data.chart_mode is not None:
        config.chart_mode = config_data.chart_mode
    if config_data.image_mode is not None:
        config.image_mode = config_data.image_mode
    if config_data.vision_model is not None:
        config.vision_model = config_data.vision_model
    if config_data.llm_model is not None:
        config.llm_model = config_data.llm_model
    if config_data.use_own_api_key is not None:
        config.use_own_api_key = config_data.use_own_api_key
    if config_data.daily_ai_limit is not None:
        config.daily_ai_limit = config_data.daily_ai_limit
    if config_data.enable_cache is not None:
        config.enable_cache = config_data.enable_cache
    if config_data.ai_timeout is not None:
        config.ai_timeout = config_data.ai_timeout
    if config_data.max_concurrent is not None:
        config.max_concurrent = config_data.max_concurrent

    if config_data.user_api_key:
        config.user_api_key_encrypted = encrypt_secret(config_data.user_api_key)

    await db.commit()
    await db.refresh(config)

    return {
        "message": "配置更新成功",
        "config": _serialize_config(config)
    }


@router.get("/config/cost-estimate", summary="获取成本估算")
async def get_cost_estimate(
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前配置的成本估算

    返回每1000个文档的预估成本。
    """
    config = await _get_config_by_tenant(db, tenant_id)

    if not config:
        # 返回默认配置的成本估算
        return {
            "modes": {
                "table": "rule_based",
                "chart": "rule_based",
                "image": "basic"
            },
            "cost_per_1k_objects": {
                "table": "免费",
                "chart": "免费",
                "image": "免费"
            },
            "total_cost_per_1k_docs": "$0.00",
            "note": "使用默认配置（免费）"
        }

    return config.get_cost_estimate()


@router.get("/usage/stats", summary="获取使用统计")
async def get_usage_stats(
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前租户的AI使用统计

    包括今日使用量、总使用量、成本估算等。
    """
    config = await _get_config_by_tenant(db, tenant_id)

    if not config:
        return {
            "daily_limit": 100,
            "daily_used": 0,
            "daily_remaining": 100,
            "total_calls": 0,
            "cost_estimate": {
                "total_cost_per_1k_docs": "$0.00"
            }
        }

    # 检查是否需要重置每日计数
    now = datetime.now()
    if config.last_reset_at and (now - config.last_reset_at).days >= 1:
        config.reset_daily_usage()
        await db.commit()

    daily_remaining = config.daily_ai_limit - config.daily_ai_used
    if config.daily_ai_limit == 0:
        daily_remaining = -1  # 表示无限制

    return {
        "daily_limit": config.daily_ai_limit,
        "daily_used": config.daily_ai_used,
        "daily_remaining": daily_remaining,
        "total_calls": config.total_ai_calls,
        "cost_estimate": config.get_cost_estimate()
    }


@router.get("/usage/logs", summary="获取使用日志")
async def get_usage_logs(
    limit: int = Query(50, ge=1, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    content_type: Optional[str] = Query(None, description="内容类型过滤"),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取AI使用日志

    用于审计和分析AI使用情况。
    """
    # 计数查询
    count_stmt = select(func.count(UserMultiModalUsageLog.id)).where(
        UserMultiModalUsageLog.tenant_id == tenant_id
    )
    if content_type:
        count_stmt = count_stmt.where(UserMultiModalUsageLog.content_type == content_type)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 列表查询
    stmt = (
        select(UserMultiModalUsageLog)
        .where(UserMultiModalUsageLog.tenant_id == tenant_id)
    )
    if content_type:
        stmt = stmt.where(UserMultiModalUsageLog.content_type == content_type)
    stmt = stmt.order_by(UserMultiModalUsageLog.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [log.to_dict() for log in logs]
    }


@router.get("/usage/summary", summary="获取使用汇总")
async def get_usage_summary(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取过去N天的使用汇总

    按内容类型、模式、成功率等维度统计。
    """
    start_date = datetime.now() - timedelta(days=days)

    # 按内容类型统计
    content_type_stmt = (
        select(
            UserMultiModalUsageLog.content_type,
            func.count(UserMultiModalUsageLog.id).label("count"),
            func.sum(UserMultiModalUsageLog.total_tokens).label("total_tokens"),
            func.avg(UserMultiModalUsageLog.response_time_ms).label("avg_response_time")
        )
        .where(
            UserMultiModalUsageLog.tenant_id == tenant_id,
            UserMultiModalUsageLog.created_at >= start_date
        )
        .group_by(UserMultiModalUsageLog.content_type)
    )
    content_type_stats = (await db.execute(content_type_stmt)).all()

    # 按解析模式统计
    mode_stmt = (
        select(
            UserMultiModalUsageLog.parse_mode,
            func.count(UserMultiModalUsageLog.id).label("count")
        )
        .where(
            UserMultiModalUsageLog.tenant_id == tenant_id,
            UserMultiModalUsageLog.created_at >= start_date
        )
        .group_by(UserMultiModalUsageLog.parse_mode)
    )
    mode_stats = (await db.execute(mode_stmt)).all()

    # 成功率统计
    success_stmt = (
        select(
            UserMultiModalUsageLog.success,
            func.count(UserMultiModalUsageLog.id).label("count")
        )
        .where(
            UserMultiModalUsageLog.tenant_id == tenant_id,
            UserMultiModalUsageLog.created_at >= start_date
        )
        .group_by(UserMultiModalUsageLog.success)
    )
    success_stats = (await db.execute(success_stmt)).all()

    total_calls = sum(stat.count for stat in success_stats)
    success_count = next((stat.count for stat in success_stats if stat.success), 0)
    success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0

    return {
        "period": f"最近{days}天",
        "total_calls": total_calls,
        "success_rate": f"{success_rate:.2f}%",
        "by_content_type": [
            {
                "content_type": stat.content_type,
                "count": stat.count,
                "total_tokens": stat.total_tokens or 0,
                "avg_response_time_ms": int(stat.avg_response_time or 0)
            }
            for stat in content_type_stats
        ],
        "by_mode": [
            {
                "mode": stat.parse_mode,
                "count": stat.count
            }
            for stat in mode_stats
        ]
    }


@router.get("/models/available", summary="获取可用模型列表")
async def get_available_models():
    """
    获取可用的AI模型列表

    供前端选择。
    """
    return {
        "vision_models": [
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "OpenAI",
                "cost": "低",
                "speed": "快",
                "quality": "高",
                "recommended": True
            },
            {
                "id": "gpt-4-turbo",
                "name": "GPT-4 Turbo",
                "provider": "OpenAI",
                "cost": "中",
                "speed": "中",
                "quality": "很高",
                "recommended": False
            },
            {
                "id": "claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "provider": "Anthropic",
                "cost": "中",
                "speed": "快",
                "quality": "很高",
                "recommended": True
            },
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "provider": "Google",
                "cost": "低",
                "speed": "快",
                "quality": "高",
                "recommended": False
            }
        ],
        "llm_models": [
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "OpenAI",
                "cost": "很低",
                "speed": "很快",
                "quality": "高",
                "recommended": True
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "OpenAI",
                "cost": "低",
                "speed": "快",
                "quality": "很高",
                "recommended": False
            },
            {
                "id": "claude-3-haiku",
                "name": "Claude 3 Haiku",
                "provider": "Anthropic",
                "cost": "很低",
                "speed": "很快",
                "quality": "中",
                "recommended": False
            }
        ]
    }


@router.delete("/config", summary="删除多模态配置")
async def delete_multimodal_config(
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    删除多模态配置，恢复为默认配置
    """
    config = await _get_config_by_tenant(db, tenant_id)

    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    await db.delete(config)
    await db.commit()

    return {
        "message": "配置已删除，已恢复为默认配置"
    }
