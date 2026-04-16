# app/services/tenant_settings_service.py

"""
租户设置服务

提供租户设置的 CRUD 操作
支持企业管理员权限控制
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_settings import TenantSettings
from app.schemas.tenant_settings import (
    TenantSettingsCreate,
    TenantSettingsUpdate
)
from app.db.session import AsyncSessionLocal

import logging

logger = logging.getLogger(__name__)


class TenantSettingsService:
    """租户设置服务类"""

    async def get_settings_by_tenant_id(
        self,
        tenant_id: str,
        db: Optional[AsyncSession] = None
    ) -> Optional[TenantSettings]:
        """
        根据租户ID获取租户设置

        Args:
            tenant_id: 租户ID
            db: 数据库会话（可选）

        Returns:
            租户设置对象或None
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            result = await db.execute(
                select(TenantSettings).where(
                    TenantSettings.tenant_id == tenant_id
                )
            )
            return result.scalar_one_or_none()
        finally:
            if should_close_session:
                await db.close()

    async def create_settings(
        self,
        settings: TenantSettingsCreate,
        db: Optional[AsyncSession] = None
    ) -> TenantSettings:
        """
        创建租户设置

        Args:
            settings: 租户设置创建Schema
            db: 数据库会话（可选）

        Returns:
            创建的租户设置对象
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            db_settings = TenantSettings(**settings.model_dump())
            db.add(db_settings)
            await db.commit()
            await db.refresh(db_settings)

            logger.info(f"创建租户设置成功: tenant_id={settings.tenant_id}")
            return db_settings
        except Exception as e:
            await db.rollback()
            logger.error(f"创建租户设置失败: {str(e)}", exc_info=True)
            raise
        finally:
            if should_close_session:
                await db.close()

    async def update_settings(
        self,
        tenant_id: str,
        settings: TenantSettingsUpdate,
        db: Optional[AsyncSession] = None
    ) -> Optional[TenantSettings]:
        """
        更新租户设置

        Args:
            tenant_id: 租户ID
            settings: 租户设置更新Schema
            db: 数据库会话（可选）

        Returns:
            更新后的租户设置对象或None
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            result = await db.execute(
                select(TenantSettings).where(
                    TenantSettings.tenant_id == tenant_id
                )
            )
            db_settings = result.scalar_one_or_none()

            if not db_settings:
                logger.warning(f"租户设置不存在: tenant_id={tenant_id}")
                return None

            update_data = settings.model_dump(exclude_unset=True)
            logger.info(f"更新租户设置数据: tenant_id={tenant_id}, update_data={update_data}")
            for key, value in update_data.items():
                logger.info(f"设置属性: {key} = {value}")
                setattr(db_settings, key, value)

            db_settings.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(db_settings)

            logger.info(f"更新租户设置成功: tenant_id={tenant_id}")
            return db_settings
        except Exception as e:
            await db.rollback()
            logger.error(f"更新租户设置失败: {str(e)}", exc_info=True)
            raise
        finally:
            if should_close_session:
                await db.close()

    async def delete_settings(
        self,
        tenant_id: str,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        删除租户设置

        Args:
            tenant_id: 租户ID
            db: 数据库会话（可选）

        Returns:
            是否删除成功
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            result = await db.execute(
                select(TenantSettings).where(
                    TenantSettings.tenant_id == tenant_id
                )
            )
            db_settings = result.scalar_one_or_none()

            if not db_settings:
                logger.warning(f"租户设置不存在: tenant_id={tenant_id}")
                return False

            await db.delete(db_settings)
            await db.commit()

            logger.info(f"删除租户设置成功: tenant_id={tenant_id}")
            return True
        except Exception as e:
            await db.rollback()
            logger.error(f"删除租户设置失败: {str(e)}", exc_info=True)
            raise
        finally:
            if should_close_session:
                await db.close()

    async def toggle_feature(
        self,
        tenant_id: str,
        feature: str,
        enabled: bool,
        db: Optional[AsyncSession] = None
    ) -> Optional[TenantSettings]:
        """
        切换功能开关

        Args:
            tenant_id: 租户ID
            feature: 功能名称
            enabled: 是否启用
            db: 数据库会话（可选）

        Returns:
            更新后的租户设置对象或None
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            result = await db.execute(
                select(TenantSettings).where(
                    TenantSettings.tenant_id == tenant_id
                )
            )
            db_settings = result.scalar_one_or_none()

            if not db_settings:
                logger.warning(f"租户设置不存在: tenant_id={tenant_id}")
                return None

            if not hasattr(db_settings, feature):
                logger.warning(f"无效的功能名称: {feature}")
                return None

            setattr(db_settings, feature, enabled)
            db_settings.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(db_settings)

            logger.info(f"切换功能开关成功: tenant_id={tenant_id}, feature={feature}, enabled={enabled}")
            return db_settings
        except Exception as e:
            await db.rollback()
            logger.error(f"切换功能开关失败: {str(e)}", exc_info=True)
            raise
        finally:
            if should_close_session:
                await db.close()

    async def get_all_settings(
        self,
        db: Optional[AsyncSession] = None
    ) -> List[TenantSettings]:
        """
        获取所有租户设置（管理员专用）

        Args:
            db: 数据库会话（可选）

        Returns:
            所有租户设置列表
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            result = await db.execute(
                select(TenantSettings).order_by(TenantSettings.created_at.desc())
            )
            return list(result.scalars().all())
        finally:
            if should_close_session:
                await db.close()

    async def check_feature_enabled(
        self,
        tenant_id: str,
        feature: str
    ) -> bool:
        """
        检查租户功能是否启用

        Args:
            tenant_id: 租户ID
            feature: 功能名称

        Returns:
            是否启用
        """
        settings = await self.get_settings_by_tenant_id(tenant_id)
        if not settings:
            return False

        return getattr(settings, feature, False)

    async def initialize_settings_for_tenant(
        self,
        tenant_id: str,
        company_name: str,
        admin_email: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> TenantSettings:
        """
        为新租户初始化默认设置

        Args:
            tenant_id: 租户ID
            company_name: 企业名称
            admin_email: 管理员邮箱
            db: 数据库会话（可选）

        Returns:
            创建的租户设置对象
        """
        should_close_session = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_session = True

        try:
            existing = await self.get_settings_by_tenant_id(tenant_id, db)
            if existing:
                logger.info(f"租户设置已存在: tenant_id={tenant_id}")
                return existing

            settings = TenantSettings(
                tenant_id=tenant_id,
                company_name=company_name,
                admin_email=admin_email,
                is_trial=True
            )
            db.add(settings)
            await db.commit()
            await db.refresh(settings)

            logger.info(f"为租户初始化设置成功: tenant_id={tenant_id}")
            return settings
        except Exception as e:
            await db.rollback()
            logger.error(f"初始化租户设置失败: {str(e)}", exc_info=True)
            raise
        finally:
            if should_close_session:
                await db.close()


# 创建全局单例
tenant_settings_service = TenantSettingsService()
