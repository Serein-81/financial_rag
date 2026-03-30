"""
邀请码 API 端点（异步版本）
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_user, get_current_admin_user
from app.models.user import User
from app.models.invite_code import InviteCode
from app.schemas.invite_code import (
    InviteCodeResponse, InviteCodeCreate, InviteCodeUpdate,
    InviteCodeValidationResult, InviteCodeStats, InviteCodeBatchCreate
)
from app.services.invite_code_service import InviteCodeService


router = APIRouter()


@router.get("/validate/{code}", response_model=InviteCodeValidationResult)
async def validate_invite_code(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    验证邀请码（不需要认证）
    """
    return await InviteCodeService.validate_invite_code(db, code)


@router.post("/validate", response_model=InviteCodeValidationResult)
async def validate_invite_code_post(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    验证邀请码（POST 方式）
    """
    return await InviteCodeService.validate_invite_code(db, code)


@router.get("/stats", response_model=InviteCodeStats)
async def get_invite_code_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取邀请码统计信息（需要管理员权限）
    """
    return await InviteCodeService.get_invite_code_stats(db, current_user.tenant_id)


@router.get("", response_model=List[InviteCodeResponse])
async def get_invite_codes(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    include_inactive: bool = Query(False, description="是否包含已停用的邀请码"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取邀请码列表（需要管理员权限）
    """
    return await InviteCodeService.get_tenant_invite_codes(
        db=db,
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive
    )


@router.post("", response_model=InviteCodeResponse, status_code=201)
async def create_invite_code(
    invite_data: InviteCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    创建邀请码（需要管理员权限）
    """
    return await InviteCodeService.create_invite_code(
        db=db,
        creator_id=current_user.id,
        tenant_id=current_user.tenant_id,
        invite_data=invite_data
    )


@router.post("/batch", response_model=List[InviteCodeResponse], status_code=201)
async def batch_create_invite_codes(
    batch_data: InviteCodeBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    批量创建邀请码（需要管理员权限）
    """
    return await InviteCodeService.batch_create_invite_codes(
        db=db,
        creator_id=current_user.id,
        tenant_id=current_user.tenant_id,
        batch_data=batch_data
    )


@router.get("/{invite_code_id}", response_model=InviteCodeResponse)
async def get_invite_code(
    invite_code_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取单个邀请码详情（需要管理员权限）
    """
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.id == invite_code_id,
            InviteCode.tenant_id == current_user.tenant_id
        )
    )
    invite_code = result.scalar_one_or_none()
    
    if not invite_code:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    return invite_code


@router.put("/{invite_code_id}", response_model=InviteCodeResponse)
async def update_invite_code(
    invite_code_id: str,
    update_data: InviteCodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    更新邀请码（需要管理员权限）
    """
    invite_code = await InviteCodeService.update_invite_code(
        db=db,
        invite_code_id=invite_code_id,
        tenant_id=current_user.tenant_id,
        update_data=update_data
    )
    
    if not invite_code:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    return invite_code


@router.delete("/{code}", status_code=204)
async def delete_invite_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    删除邀请码（需要管理员权限）
    """
    success = await InviteCodeService.delete_invite_code_by_code(
        db=db,
        code=code,
        tenant_id=current_user.tenant_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="邀请码不存在")
