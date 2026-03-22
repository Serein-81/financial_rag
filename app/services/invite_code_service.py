"""
邀请码服务
处理邀请码的创建、验证、使用等业务逻辑
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from fastapi import HTTPException

from app.models.invite_code import InviteCode, InviteCodeUsage
from app.models.user import User
from app.schemas.invite_code import (
    InviteCodeCreate, InviteCodeUpdate, InviteCodeValidationResult,
    InviteCodeStats, InviteCodeBatchCreate
)


class InviteCodeService:
    """邀请码服务类"""
    
    @staticmethod
    def generate_code(length: int = 12) -> str:
        """
        生成邀请码
        
        Args:
            length: 邀请码长度
            
        Returns:
            str: 生成的邀请码
        """
        # 使用大写字母和数字，避免容易混淆的字符
        alphabet = string.ascii_uppercase + string.digits
        alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
        
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def create_invite_code(
        db: Session,
        creator_id: str,
        tenant_id: str,
        invite_data: InviteCodeCreate
    ) -> InviteCode:
        """
        创建邀请码
        
        Args:
            db: 数据库会话
            creator_id: 创建者ID
            tenant_id: 租户ID
            invite_data: 邀请码创建数据
            
        Returns:
            InviteCode: 创建的邀请码
        """
        # 生成唯一的邀请码
        max_attempts = 10
        for _ in range(max_attempts):
            code = InviteCodeService.generate_code()
            existing = db.query(InviteCode).filter(InviteCode.code == code).first()
            if not existing:
                break
        else:
            raise HTTPException(status_code=500, detail="无法生成唯一的邀请码")
        
        # 计算过期时间
        expires_at = None
        if invite_data.expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=invite_data.expires_hours)
        
        # 创建邀请码
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
        db.commit()
        db.refresh(invite_code)
        
        return invite_code
    
    @staticmethod
    def batch_create_invite_codes(
        db: Session,
        creator_id: str,
        tenant_id: str,
        batch_data: InviteCodeBatchCreate
    ) -> List[InviteCode]:
        """
        批量创建邀请码
        
        Args:
            db: 数据库会话
            creator_id: 创建者ID
            tenant_id: 租户ID
            batch_data: 批量创建数据
            
        Returns:
            List[InviteCode]: 创建的邀请码列表
        """
        created_codes = []
        
        # 计算过期时间
        expires_at = None
        if batch_data.expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=batch_data.expires_hours)
        
        for i in range(batch_data.count):
            # 生成唯一的邀请码
            max_attempts = 10
            for _ in range(max_attempts):
                code = InviteCodeService.generate_code()
                existing = db.query(InviteCode).filter(InviteCode.code == code).first()
                if not existing:
                    break
            else:
                continue  # 跳过这个邀请码，继续下一个
            
            # 生成描述
            description = batch_data.description_template
            if description and "{index}" in description:
                description = description.replace("{index}", str(i + 1))
            
            # 创建邀请码
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
        
        db.commit()
        
        # 刷新所有创建的邀请码
        for invite_code in created_codes:
            db.refresh(invite_code)
        
        return created_codes
    
    @staticmethod
    def validate_invite_code(
        db: Session,
        code: str
    ) -> InviteCodeValidationResult:
        """
        验证邀请码
        
        Args:
            db: 数据库会话
            code: 邀请码
            
        Returns:
            InviteCodeValidationResult: 验证结果
        """
        # 查找邀请码
        invite_code = db.query(InviteCode).filter(InviteCode.code == code).first()
        
        if not invite_code:
            return InviteCodeValidationResult(
                valid=False,
                message="邀请码不存在"
            )
        
        # 检查邀请码状态
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
        
        # 获取创建者信息
        creator = db.query(User).filter(User.id == invite_code.created_by).first()
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
    def use_invite_code(
        db: Session,
        code: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        使用邀请码
        
        Args:
            db: 数据库会话
            code: 邀请码
            user_id: 使用者ID
            ip_address: IP地址
            user_agent: 用户代理
            
        Returns:
            Tuple[bool, str, Optional[str]]: (成功标志, 消息, 租户ID)
        """
        # 验证邀请码
        validation_result = InviteCodeService.validate_invite_code(db, code)
        if not validation_result.valid:
            return False, validation_result.message, None
        
        # 获取邀请码
        invite_code = db.query(InviteCode).filter(InviteCode.code == code).first()
        
        # 检查用户是否已经使用过这个邀请码
        existing_usage = db.query(InviteCodeUsage).filter(
            and_(
                InviteCodeUsage.invite_code_id == invite_code.id,
                InviteCodeUsage.user_id == user_id
            )
        ).first()
        
        if existing_usage:
            return False, "您已经使用过这个邀请码", None
        
        # 记录使用
        usage = InviteCodeUsage(
            invite_code_id=invite_code.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(usage)
        
        # 更新使用次数
        invite_code.used_count += 1
        
        db.commit()
        
        return True, "邀请码使用成功", invite_code.tenant_id
    
    @staticmethod
    def get_tenant_invite_codes(
        db: Session,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False
    ) -> List[InviteCode]:
        """
        获取租户的邀请码列表
        
        Args:
            db: 数据库会话
            tenant_id: 租户ID
            skip: 跳过数量
            limit: 限制数量
            include_inactive: 是否包含非活跃的邀请码
            
        Returns:
            List[InviteCode]: 邀请码列表
        """
        query = db.query(InviteCode).filter(InviteCode.tenant_id == tenant_id)
        
        if not include_inactive:
            query = query.filter(InviteCode.is_active == True)
        
        return query.order_by(desc(InviteCode.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_invite_code_stats(db: Session, tenant_id: str) -> InviteCodeStats:
        """
        获取邀请码统计信息
        
        Args:
            db: 数据库会话
            tenant_id: 租户ID
            
        Returns:
            InviteCodeStats: 统计信息
        """
        # 基础统计
        total_codes = db.query(InviteCode).filter(InviteCode.tenant_id == tenant_id).count()
        active_codes = db.query(InviteCode).filter(
            and_(InviteCode.tenant_id == tenant_id, InviteCode.is_active == True)
        ).count()
        
        # 过期和用完的邀请码
        now = datetime.now(timezone.utc)
        expired_codes = db.query(InviteCode).filter(
            and_(
                InviteCode.tenant_id == tenant_id,
                InviteCode.expires_at < now
            )
        ).count()
        
        exhausted_codes = db.query(InviteCode).filter(
            and_(
                InviteCode.tenant_id == tenant_id,
                InviteCode.used_count >= InviteCode.max_uses
            )
        ).count()
        
        # 使用统计
        total_uses = db.query(InviteCodeUsage).join(InviteCode).filter(
            InviteCode.tenant_id == tenant_id
        ).count()
        
        # 邀请的用户数（去重）
        total_invited_users = db.query(InviteCodeUsage.user_id).join(InviteCode).filter(
            InviteCode.tenant_id == tenant_id
        ).distinct().count()
        
        return InviteCodeStats(
            total_codes=total_codes,
            active_codes=active_codes,
            expired_codes=expired_codes,
            exhausted_codes=exhausted_codes,
            total_uses=total_uses,
            total_invited_users=total_invited_users
        )
    
    @staticmethod
    def update_invite_code(
        db: Session,
        invite_code_id: str,
        tenant_id: str,
        update_data: InviteCodeUpdate
    ) -> Optional[InviteCode]:
        """
        更新邀请码
        
        Args:
            db: 数据库会话
            invite_code_id: 邀请码ID
            tenant_id: 租户ID
            update_data: 更新数据
            
        Returns:
            Optional[InviteCode]: 更新后的邀请码
        """
        invite_code = db.query(InviteCode).filter(
            and_(
                InviteCode.id == invite_code_id,
                InviteCode.tenant_id == tenant_id
            )
        ).first()
        
        if not invite_code:
            return None
        
        # 更新字段
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(invite_code, field, value)
        
        db.commit()
        db.refresh(invite_code)
        
        return invite_code
    
    @staticmethod
    def delete_invite_code(
        db: Session,
        invite_code_id: str,
        tenant_id: str
    ) -> bool:
        """
        删除邀请码
        
        Args:
            db: 数据库会话
            invite_code_id: 邀请码ID
            tenant_id: 租户ID
            
        Returns:
            bool: 是否删除成功
        """
        invite_code = db.query(InviteCode).filter(
            and_(
                InviteCode.id == invite_code_id,
                InviteCode.tenant_id == tenant_id
            )
        ).first()
        
        if not invite_code:
            return False
        
        # 删除相关的使用记录
        db.query(InviteCodeUsage).filter(
            InviteCodeUsage.invite_code_id == invite_code_id
        ).delete()
        
        # 删除邀请码
        db.delete(invite_code)
        db.commit()
        
        return True