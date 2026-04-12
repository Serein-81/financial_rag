# app/api/v1/endpoints/tenant_settings.py

"""
租户设置 API 端点

提供租户设置的 CRUD 操作
权限控制：管理员拥有所有权限，普通用户只能查看
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.tenant_settings import (
    TenantSettingsCreate,
    TenantSettingsUpdate,
    TenantSettingsResponse,
    TenantSettingsPublicResponse,
    FeatureToggleRequest,
    TenantSettingsListResponse
)
from app.services.tenant_settings_service import tenant_settings_service
from app.db.session import get_db
from app.api.deps import get_current_user, require_admin_user

get_current_active_user = get_current_user

router = APIRouter(prefix="/tenant-settings", tags=["租户设置"])


@router.get("/me", response_model=TenantSettingsResponse)
async def get_my_tenant_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前用户所在企业的设置
    - 所有用户都可以查看
    """
    settings = await tenant_settings_service.get_settings_by_tenant_id(
        current_user.tenant_id,
        db
    )

    if not settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return settings


import logging
logger = logging.getLogger(__name__)

@router.put("/me", response_model=TenantSettingsResponse)
async def update_my_tenant_settings(
    settings: TenantSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    更新当前用户所在企业的设置
    - 只有企业管理员可以执行
    """
    logger.info(f"收到更新请求: tenant_id={current_user.tenant_id}, data={settings.model_dump()}")
    updated_settings = await tenant_settings_service.update_settings(
        current_user.tenant_id,
        settings,
        db
    )

    if not updated_settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return updated_settings


@router.get("/public/{tenant_id}", response_model=TenantSettingsPublicResponse)
async def get_public_tenant_settings(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取公开的租户设置（不含敏感信息）
    - 任何人可访问
    """
    settings = await tenant_settings_service.get_settings_by_tenant_id(
        tenant_id,
        db
    )

    if not settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return TenantSettingsPublicResponse(
        tenant_id=settings.tenant_id,
        company_name=settings.company_name,
        company_logo=settings.company_logo,
        company_description=settings.company_description,
        company_website=settings.company_website,
        primary_color=settings.primary_color,
        secondary_color=settings.secondary_color
    )


@router.get("/", response_model=TenantSettingsListResponse)
async def list_all_tenant_settings(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    获取所有租户设置列表
    - 管理员可以访问
    """
    all_settings = await tenant_settings_service.get_all_settings(db)
    total = len(all_settings)

    paginated_settings = all_settings[skip:skip + limit]

    return TenantSettingsListResponse(
        settings=[TenantSettingsResponse.model_validate(s) for s in paginated_settings],
        total=total
    )


@router.post("/", response_model=TenantSettingsResponse, status_code=201)
async def create_tenant_settings(
    settings: TenantSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    创建租户设置
    - 管理员可以执行
    """
    existing = await tenant_settings_service.get_settings_by_tenant_id(
        settings.tenant_id,
        db
    )

    if existing:
        raise HTTPException(status_code=400, detail="该租户的设置已存在")

    new_settings = await tenant_settings_service.create_settings(settings, db)
    return new_settings


@router.get("/{tenant_id}", response_model=TenantSettingsResponse)
async def get_tenant_settings(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    获取指定租户的设置
    - 管理员可以查看所有租户的设置
    """
    settings_obj = await tenant_settings_service.get_settings_by_tenant_id(
        tenant_id,
        db
    )

    if not settings_obj:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return settings_obj


@router.put("/{tenant_id}", response_model=TenantSettingsResponse)
async def update_tenant_settings(
    tenant_id: str,
    settings: TenantSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    更新指定租户的设置
    - 管理员可以更新所有租户的设置
    """
    updated_settings = await tenant_settings_service.update_settings(
        tenant_id,
        settings,
        db
    )

    if not updated_settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return updated_settings


@router.delete("/{tenant_id}")
async def delete_tenant_settings(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    删除租户设置
    - 管理员可以删除任何租户的设置
    """
    deleted = await tenant_settings_service.delete_settings(tenant_id, db)

    if not deleted:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return {"message": "租户设置已删除"}


@router.post("/feature-toggle")
async def toggle_feature(
    request: FeatureToggleRequest,
    tenant_id: Optional[str] = Query(None, description="租户ID，不提供则操作当前企业"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    切换功能开关
    - 管理员可以操作所有企业的功能开关
    - 如果不提供 tenant_id，则操作当前企业
    """
    target_tenant_id = tenant_id if tenant_id else current_user.tenant_id

    updated_settings = await tenant_settings_service.toggle_feature(
        target_tenant_id,
        request.feature,
        request.enabled,
        db
    )

    if not updated_settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return {
        "message": f"功能 {request.feature} 已{'启用' if request.enabled else '禁用'}",
        "feature": request.feature,
        "enabled": request.enabled,
        "tenant_id": target_tenant_id
    }


@router.get("/features/check")
async def check_features(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    检查当前租户的功能开关状态
    """
    settings = await tenant_settings_service.get_settings_by_tenant_id(
        current_user.tenant_id,
        db
    )

    if not settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return {
        "tenant_id": current_user.tenant_id,
        "features": {
            "enable_group_chat": settings.enable_group_chat,
            "enable_multi_agent": settings.enable_multi_agent,
            "enable_knowledge_graph": settings.enable_knowledge_graph,
            "enable_human_review": settings.enable_human_review,
            "enable_audit": settings.enable_audit,
            "enable_tax_report": settings.enable_tax_report,
            "enable_financial_data": settings.enable_financial_data
        }
    }


@router.get("/features/{tenant_id}/check")
async def check_features_by_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    检查指定租户的功能开关状态
    - 管理员可以查看所有租户的功能状态
    """
    settings = await tenant_settings_service.get_settings_by_tenant_id(
        tenant_id,
        db
    )

    if not settings:
        raise HTTPException(status_code=404, detail="租户设置不存在")

    return {
        "tenant_id": tenant_id,
        "features": {
            "enable_group_chat": settings.enable_group_chat,
            "enable_multi_agent": settings.enable_multi_agent,
            "enable_knowledge_graph": settings.enable_knowledge_graph,
            "enable_human_review": settings.enable_human_review,
            "enable_audit": settings.enable_audit,
            "enable_tax_report": settings.enable_tax_report,
            "enable_financial_data": settings.enable_financial_data
        }
    }


@router.post("/initialize")
async def initialize_tenant_settings(
    company_name: str = Query(..., min_length=1, max_length=200, description="企业名称"),
    admin_email: Optional[str] = Query(None, description="管理员邮箱"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    为当前企业初始化默认设置
    - 管理员可以初始化自己企业的设置
    """
    settings = await tenant_settings_service.initialize_settings_for_tenant(
        current_user.tenant_id,
        company_name,
        admin_email,
        db
    )

    return {
        "message": "租户设置初始化成功",
        "settings": TenantSettingsResponse.model_validate(settings)
    }
