"""
邀请码管理API端点
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.models.invite_code import InviteCode
from app.schemas.invite_code import (
    InviteCodeCreate, InviteCodeUpdate, InviteCodeOut, InviteCodeSummary,
    InviteCodeValidation, InviteCodeValidationResult, InviteCodeUsageOut,
    InviteCodeStats, InviteCodeBatchCreate, InviteCodeBatchResult
)
from app.services.invite_code_service import InviteCodeService
from app.db.session import get_db

router = APIRouter()


# =======================
# 权限检查辅助函数
# =======================

def require_admin_user(current_user: User = Depends(deps.get_current_user)) -> User:
    """要求当前用户是管理员"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# =======================
# 邀请码创建和管理
# =======================

@router.post("/", response_model=InviteCodeOut)
async def create_invite_code(
    invite_data: InviteCodeCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    创建邀请码
    - 只有企业管理员可以创建邀请码
    - 邀请码用于邀请普通用户加入企业租户
    """
    try:
        invite_code = InviteCodeService.create_invite_code(
            db=db,
            creator_id=str(admin_user.id),
            tenant_id=admin_user.tenant_id,
            invite_data=invite_data
        )
        return invite_code
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建邀请码失败: {str(e)}")


@router.post("/batch", response_model=InviteCodeBatchResult)
async def batch_create_invite_codes(
    batch_data: InviteCodeBatchCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    批量创建邀请码
    - 一次最多创建50个邀请码
    - 适用于大量用户邀请场景
    """
    try:
        invite_codes = InviteCodeService.batch_create_invite_codes(
            db=db,
            creator_id=str(admin_user.id),
            tenant_id=admin_user.tenant_id,
            batch_data=batch_data
        )
        
        codes = [code.code for code in invite_codes]
        
        return InviteCodeBatchResult(
            success=True,
            created_count=len(invite_codes),
            codes=codes,
            message=f"成功创建 {len(invite_codes)} 个邀请码"
        )
    except Exception as e:
        return InviteCodeBatchResult(
            success=False,
            created_count=0,
            codes=[],
            message=f"批量创建失败: {str(e)}"
        )


@router.get("/", response_model=List[InviteCodeSummary])
async def list_invite_codes(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    include_inactive: bool = Query(False, description="是否包含非活跃的邀请码"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取企业的邀请码列表
    - 只显示当前企业租户的邀请码
    - 支持分页和过滤
    """
    invite_codes = InviteCodeService.get_tenant_invite_codes(
        db=db,
        tenant_id=admin_user.tenant_id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive
    )
    return invite_codes


@router.get("/stats", response_model=InviteCodeStats)
async def get_invite_code_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取邀请码统计信息
    - 总数、活跃数、过期数等统计
    - 用于管理后台展示
    """
    return InviteCodeService.get_invite_code_stats(
        db=db,
        tenant_id=admin_user.tenant_id
    )


@router.get("/{invite_code_id}", response_model=InviteCodeOut)
async def get_invite_code(
    invite_code_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取单个邀请码详情
    - 只能查看本企业的邀请码
    """
    invite_code = db.query(InviteCode).filter(
        InviteCode.id == invite_code_id,
        InviteCode.tenant_id == admin_user.tenant_id
    ).first()
    
    if not invite_code:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    return invite_code


@router.put("/{invite_code_id}", response_model=InviteCodeOut)
async def update_invite_code(
    invite_code_id: str,
    update_data: InviteCodeUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    更新邀请码
    - 可以启用/禁用邀请码
    - 可以修改描述信息
    """
    invite_code = InviteCodeService.update_invite_code(
        db=db,
        invite_code_id=invite_code_id,
        tenant_id=admin_user.tenant_id,
        update_data=update_data
    )
    
    if not invite_code:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    return invite_code


@router.delete("/{invite_code_id}")
async def delete_invite_code(
    invite_code_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    删除邀请码
    - 会同时删除相关的使用记录
    - 谨慎操作，删除后无法恢复
    """
    success = InviteCodeService.delete_invite_code(
        db=db,
        invite_code_id=invite_code_id,
        tenant_id=admin_user.tenant_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    return {"message": "邀请码删除成功"}


# =======================
# 邀请码验证和使用（公开接口）
# =======================

@router.post("/validate", response_model=InviteCodeValidationResult)
async def validate_invite_code(
    validation_data: InviteCodeValidation,
    db: Session = Depends(get_db)
):
    """
    验证邀请码
    - 公开接口，用于注册时验证邀请码
    - 返回邀请码的基本信息
    """
    return InviteCodeService.validate_invite_code(
        db=db,
        code=validation_data.code
    )


@router.post("/use/{code}")
async def use_invite_code(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    使用邀请码
    - 用户加入企业租户
    - 记录使用信息
    """
    # 获取客户端信息
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    success, message, tenant_id = InviteCodeService.use_invite_code(
        db=db,
        code=code,
        user_id=str(current_user.id),
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # 更新用户的租户ID
    current_user.tenant_id = tenant_id
    db.commit()
    
    return {
        "message": message,
        "tenant_id": tenant_id
    }


# =======================
# 邀请码使用记录
# =======================

@router.get("/{invite_code_id}/usages", response_model=List[InviteCodeUsageOut])
async def get_invite_code_usages(
    invite_code_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    获取邀请码的使用记录
    - 显示谁使用了这个邀请码
    - 包含使用时间、IP等信息
    """
    # 验证邀请码属于当前租户
    invite_code = db.query(InviteCode).filter(
        InviteCode.id == invite_code_id,
        InviteCode.tenant_id == admin_user.tenant_id
    ).first()
    
    if not invite_code:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    # 获取使用记录
    from app.models.invite_code import InviteCodeUsage
    usages = db.query(InviteCodeUsage).filter(
        InviteCodeUsage.invite_code_id == invite_code_id
    ).order_by(InviteCodeUsage.used_at.desc()).offset(skip).limit(limit).all()
    
    # 添加用户信息
    result = []
    for usage in usages:
        user = db.query(User).filter(User.id == usage.user_id).first()
        usage_dict = {
            "id": usage.id,
            "invite_code_id": usage.invite_code_id,
            "user_id": usage.user_id,
            "used_at": usage.used_at,
            "ip_address": usage.ip_address,
            "user_agent": usage.user_agent,
            "user_email": user.email if user else None,
            "user_name": user.nickname or user.full_name if user else None
        }
        result.append(InviteCodeUsageOut(**usage_dict))
    
    return result