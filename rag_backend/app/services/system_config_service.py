# app/services/system_config_service.py

"""
部署级模型配置服务（Embedding / Rerank）

为什么是部署级而非租户级：
- 向量列维度固定（chunk.embedding = Vector(1024)），换不同维度的 Embedding 模型会破坏已建索引；
- embedding_service / rerank_service 是全局单例，无租户上下文。
因此 Embedding / Rerank 配置统一为部署级，管理员管控，存于 system_settings 表（DB 覆盖 → .env 兜底）。
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.system_settings import SystemSetting

logger = logging.getLogger(__name__)

# 主检索路径（chunk / 记忆）使用的向量维度，换 Embedding 模型必须匹配它
EMBEDDING_DIM = 1024

_KEY_EMBEDDING = "embedding_config"
_KEY_RERANK = "rerank_config"

# ---- Embedding 提供商目录（前端表单元数据）----
EMBEDDING_PROVIDERS = [
    {"id": "siliconflow", "name": "硅基流动 SiliconFlow", "group": "cloud",
     "requires_api_key": True, "default_base_url": None,
     "models": ["BAAI/bge-m3"]},
    {"id": "zhipu", "name": "智谱 AI", "group": "cloud",
     "requires_api_key": True, "default_base_url": None,
     "models": ["embedding-3"]},
    {"id": "openai", "name": "OpenAI", "group": "cloud",
     "requires_api_key": True, "default_base_url": "https://api.openai.com/v1",
     "models": ["text-embedding-3-small", "text-embedding-3-large"]},
    {"id": "ollama", "name": "Ollama (本地部署)", "group": "local",
     "requires_api_key": False, "default_base_url": None, "supports_detect": True,
     "note": f"必须选择输出 {EMBEDDING_DIM} 维的模型（如 bge-m3），否则与已建索引不兼容",
     "models": ["bge-m3", "nomic-embed-text"]},
]

# ---- Rerank 提供商目录 ----
RERANK_PROVIDERS = [
    {"id": "siliconflow", "name": "硅基流动 SiliconFlow", "group": "cloud",
     "requires_api_key": True, "default_base_url": "https://api.siliconflow.cn/v1/rerank",
     "models": ["Pro/BAAI/bge-reranker-v2-m3", "BAAI/bge-reranker-v2-m3"]},
]


def _embedding_env_model(provider: str) -> Optional[str]:
    return {
        "zhipu": settings.ZHIPU_EMBEDDING_MODEL,
        "openai": settings.OPENAI_EMBEDDING_MODEL,
        "siliconflow": settings.SILICONFLOW_EMBEDDING_MODEL,
        "ollama": settings.OLLAMA_EMBEDDING_MODEL,
    }.get((provider or "").lower())


def _embedding_env_key(provider: str) -> Optional[str]:
    return {
        "zhipu": settings.ZHIPU_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "siliconflow": settings.SILICONFLOW_API_KEY,
        "ollama": "",
    }.get((provider or "").lower())


def _embedding_env_base(provider: str) -> Optional[str]:
    return {
        "openai": settings.OPENAI_BASE_URL,
        "ollama": settings.OLLAMA_BASE_URL,
    }.get((provider or "").lower())


async def _read(key: str, db: Optional[AsyncSession]) -> dict:
    async def _do(session: AsyncSession) -> dict:
        row = await session.get(SystemSetting, key)
        return dict(row.value) if row and row.value else {}

    try:
        if db is not None:
            return await _do(db)
        async with AsyncSessionLocal() as session:
            return await _do(session)
    except Exception as e:  # 表不存在 / DB 异常 → 回退空覆盖（用 env）
        logger.warning(f"[SystemConfig] 读取 {key} 失败，回退 .env 默认: {e}")
        return {}


async def _write(key: str, value: dict, db: Optional[AsyncSession]) -> None:
    async def _do(session: AsyncSession) -> None:
        row = await session.get(SystemSetting, key)
        if row:
            row.value = value
        else:
            session.add(SystemSetting(key=key, value=value))
        await session.commit()

    if db is not None:
        await _do(db)
    else:
        async with AsyncSessionLocal() as session:
            await _do(session)


# ==================== Embedding ====================

async def get_embedding_config(db: Optional[AsyncSession] = None) -> dict:
    """有效 Embedding 配置：DB 覆盖 → .env 兜底"""
    override = await _read(_KEY_EMBEDDING, db)
    provider = override.get("provider") or settings.EMBEDDING_PROVIDER
    return {
        "provider": provider,
        "model": override.get("model") or _embedding_env_model(provider),
        "api_key": override.get("api_key") or _embedding_env_key(provider),
        "base_url": override.get("base_url") or _embedding_env_base(provider),
        "is_custom": bool(override),
    }


async def save_embedding_config(cfg: dict, db: Optional[AsyncSession] = None) -> None:
    payload = {k: cfg.get(k) for k in ("provider", "model", "api_key", "base_url") if cfg.get(k)}
    await _write(_KEY_EMBEDDING, payload, db)


# ==================== Rerank ====================

async def get_rerank_config(db: Optional[AsyncSession] = None) -> dict:
    """有效 Rerank 配置：DB 覆盖 → .env 兜底"""
    override = await _read(_KEY_RERANK, db)
    provider = override.get("provider") or "siliconflow"
    enabled = override["enabled"] if "enabled" in override else settings.ENABLE_RERANK
    return {
        "provider": provider,
        "model": override.get("model") or settings.SILICONFLOW_RERANK_MODEL,
        "api_key": override.get("api_key") or settings.SILICONFLOW_API_KEY,
        "base_url": override.get("base_url") or "https://api.siliconflow.cn/v1/rerank",
        "enabled": bool(enabled),
        "top_k": override.get("top_k") or settings.RERANK_TOP_K,
        "is_custom": bool(override),
    }


async def save_rerank_config(cfg: dict, db: Optional[AsyncSession] = None) -> None:
    payload = {}
    for k in ("provider", "model", "api_key", "base_url", "top_k"):
        if cfg.get(k):
            payload[k] = cfg.get(k)
    if "enabled" in cfg and cfg["enabled"] is not None:
        payload["enabled"] = bool(cfg["enabled"])
    await _write(_KEY_RERANK, payload, db)
