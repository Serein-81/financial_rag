"""
邀请码服务
处理邀请码的创建、验证、使用等业务逻辑（异步版本）
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, select, func, delete
from fastapi import HTTPException

from app.models.invite_code import InviteCode, InviteCodeUsage
from app.models.user import User
from app.schemas.invite_code import (
    InviteCodeCreate, InviteCodeUpdate, InviteCodeValidationResult,
    InviteCodeStats, InviteCodeBatchCreate
)


class InviteCodeService:
    """邀请码服务类（异步版本）"""
    
    @staticmethod
    def generate_code(length: int = 12) -> str:
        """
        生成邀请码
        """
        alphabet = string.ascii_uppercase + string.digits
        alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
        
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    async def create_invite_code(
        db: AsyncSession,
        creator_id: str,
        tenant_id: str,
        invite_data: InviteCodeCreate
    ) -> InviteCode:
        """
        创建邀请码
        """
        max_attempts = 10
        code = None
        
        for _ in range(max_attempts):
            code = InviteCodeService.generate_code()
            result = await db.execute(
                select(InviteCode).where(InviteCode.code == code)
            )
            existing = result.scalar_one_or_none()
            if not existing:
                break
        else:
            raise HTTPException(status_code=500, detail="无法生成唯一的邀请码")
        
        expires_at = None
        if invite_data.expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=invite_data.expires_hours)
        
        invite_code = InviteCode(
            code=code,
            tenant_id=tenant_id,
            created_by=creator_id,
            max_uses=invite_data.max_uses,
            expires_at=expires_at,
            description=invite_data.description,
            role=invite_data.role
        )
        
        db.add(invite_code)
        await db.commit()
        await db.refresh(invite_code)
        
        return invite_code
    
    @staticmethod
    async def batch_create_invite_codes(
        db: AsyncSession,
        creator_id: str,
        tenant_id: str,
        batch_data: InviteCodeBatchCreate
    ) -> List[InviteCode]:
        """
        批量创建邀请码
        """
        created_codes = []
        
        expires_at = None
        if batch_data.expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=batch_data.expires_hours)
        
        for i in range(batch_data.count):
            max_attempts = 10
            code = None
            
            for _ in range(max_attempts):
                code = InviteCodeService.generate_code()
                result = await db.execute(
                    select(InviteCode).where(InviteCode.code == code)
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    break
            else:
                continue
            
            description = batch_data.description_template
            if description and "{index}" in description:
                description = description.replace("{index}", str(i + 1))
            
            invite_code = InviteCode(
                code=code,
                tenant_id=tenant_id,
                created_by=creator_id,
                max_uses=batch_data.max_uses,
                expires_at=expires_at,
                description=description,
                role=batch_data.role
            )
            
            db.add(invite_code)
            created_codes.append(invite_code)
        
        await db.commit()
        
        for invite_code in created_codes:
            await db.refresh(invite_code)
        
        return created_codes
    
    @staticmethod
    async def validate_invite_code(
        db: AsyncSession,
        code: str
    ) -> InviteCodeValidationResult:
        """
        验证邀请码
        """
        result = await db.execute(
            select(InviteCode).where(InviteCode.code == code)
        )
        invite_code = result.scalar_one_or_none()
        
        if not invite_code:
            return InviteCodeValidationResult(
                valid=False,
                message="邀请码不存在"
            )
        
        if not invite_code.is_active:
            return InviteCodeValidationResult(
                valid=False,
                message="邀请码已被禁用"
            )
        
        if invite_code.is_expired:
            return InviteCodeValidationResult(
                valid=False,
                message="邀请码已过期"
            )
        
        if invite_code.is_exhausted:
            return InviteCodeValidationResult(
                valid=False,
                message="邀请码使用次数已用完"
            )
        
        creator_result = await db.execute(
            select(User).where(User.id == invite_code.created_by)
        )
        creator = creator_result.scalar_one_or_none()
        creator_name = None
        company_name = None
        
        if creator:
            creator_name = creator.nickname or creator.full_name or creator.email
            company_name = creator.company_name
        
        return InviteCodeValidationResult(
            valid=True,
            message="邀请码有效",
            tenant_id=invite_code.tenant_id,
            company_name=company_name,
            creator_name=creator_name,
            description=invite_code.description,
            expires_at=invite_code.expires_at,
            remaining_uses=invite_code.remaining_uses
        )
    
    @staticmethod
    async def use_invite_code(
        db: AsyncSession,
        code: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        使用邀请码
        """
        validation_result = await InviteCodeService.validate_invite_code(db, code)
        if not validation_result.valid:
            return False, validation_result.message, None
        
        result = await db.execute(
            select(InviteCode).where(InviteCode.code == code)
        )
        invite_code = result.scalar_one_or_none()
        
        existing_usage_result = await db.execute(
            select(InviteCodeUsage).where(
                and_(
                    InviteCodeUsage.invite_code_id == invite_code.id,
                    InviteCodeUsage.user_id == user_id
                )
            )
        )
        existing_usage = existing_usage_result.scalar_one_or_none()
        
        if existing_usage:
            return False, "您已经使用过这个邀请码", None
        
        usage = InviteCodeUsage(
            invite_code_id=invite_code.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(usage)
        invite_code.used_count += 1
        
        await db.commit()
        
        return True, "邀请码使用成功", invite_code.tenant_id
    
    @staticmethod
    async def get_tenant_invite_codes(
        db: AsyncSession,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False
    ) -> List[InviteCode]:
        """
        获取租户的邀请码列表
        """
        query = select(InviteCode).where(InviteCode.tenant_id == tenant_id)
        
        if not include_inactive:
            query = query.where(InviteCode.is_active.is_(True))
        
        query = query.order_by(desc(InviteCode.created_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_invite_code_stats(db: AsyncSession, tenant_id: str) -> InviteCodeStats:
        """
        获取邀请码统计信息
        """
        total_codes_result = await db.execute(
            select(func.count(InviteCode.id)).where(InviteCode.tenant_id == tenant_id)
        )
        total_codes = total_codes_result.scalar()
        
        active_codes_result = await db.execute(
            select(func.count(InviteCode.id)).where(
                and_(InviteCode.tenant_id == tenant_id, InviteCode.is_active.is_(True))
            )
        )
        active_codes = active_codes_result.scalar()
        
        now = datetime.now(timezone.utc)
        expired_codes_result = await db.execute(
            select(func.count(InviteCode.id)).where(
                and_(
                    InviteCode.tenant_id == tenant_id,
                    InviteCode.expires_at < now
                )
            )
        )
        expired_codes = expired_codes_result.scalar()
        
        exhausted_codes_result = await db.execute(
            select(func.count(InviteCode.id)).where(
                and_(
                    InviteCode.tenant_id == tenant_id,
                    InviteCode.used_count >= InviteCode.max_uses
                )
            )
        )
        exhausted_codes = exhausted_codes_result.scalar()
        
        total_uses_result = await db.execute(
            select(func.count(InviteCodeUsage.id))
            .join(InviteCode)
            .where(InviteCode.tenant_id == tenant_id)
        )
        total_uses = total_uses_result.scalar()
        
        total_invited_users_result = await db.execute(
            select(func.count(InviteCodeUsage.user_id.distinct()))
            .join(InviteCode)
            .where(InviteCode.tenant_id == tenant_id)
        )
        total_invited_users = total_invited_users_result.scalar()
        
        return InviteCodeStats(
            total_codes=total_codes,
            active_codes=active_codes,
            expired_codes=expired_codes,
            exhausted_codes=exhausted_codes,
            total_uses=total_uses,
            total_invited_users=total_invited_users
        )
    
    @staticmethod
    async def update_invite_code(
        db: AsyncSession,
        invite_code_id: str,
        tenant_id: str,
        update_data: InviteCodeUpdate
    ) -> Optional[InviteCode]:
        """
        更新邀请码
        """
        result = await db.execute(
            select(InviteCode).where(
                and_(
                    InviteCode.id == invite_code_id,
                    InviteCode.tenant_id == tenant_id
                )
            )
        )
        invite_code = result.scalar_one_or_none()
        
        if not invite_code:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(invite_code, field, value)
        
        await db.commit()
        await db.refresh(invite_code)
        
        return invite_code
    
    @staticmethod
    async def delete_invite_code(
        db: AsyncSession,
        invite_code_id: str,
        tenant_id: str
    ) -> bool:
        """
        删除邀请码（按ID）
        """
        result = await db.execute(
            select(InviteCode).where(
                and_(
                    InviteCode.id == invite_code_id,
                    InviteCode.tenant_id == tenant_id
                )
            )
        )
        invite_code = result.scalar_one_or_none()

        if not invite_code:
            return False

        await db.execute(
            delete(InviteCodeUsage).where(InviteCodeUsage.invite_code_id == invite_code_id)
        )

        await db.delete(invite_code)
        await db.commit()

        return True

    @staticmethod
    async def delete_invite_code_by_code(
        db: AsyncSession,
        code: str,
        tenant_id: str
    ) -> bool:
        """
        删除邀请码（按code）
        """
        result = await db.execute(
            select(InviteCode).where(
                and_(
                    InviteCode.code == code,
                    InviteCode.tenant_id == tenant_id
                )
            )
        )
        invite_code = result.scalar_one_or_none()

        if not invite_code:
            return False

        await db.execute(
            delete(InviteCodeUsage).where(InviteCodeUsage.invite_code_id == str(invite_code.id))
        )

        await db.delete(invite_code)
        await db.commit()

        return True
