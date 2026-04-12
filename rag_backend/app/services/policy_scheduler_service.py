"""
税务政策定时同步调度器

功能：
1. 定时从官方渠道采集最新政策
2. 自动去重后入库
3. 生成政策更新通知
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from app.services.policy_crawler_service import policy_crawler_service, CrawledPolicy
from app.models.policy import Policy, PolicyStatus, PolicyPriority
from app.db.session import SessionLocal
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PolicySyncScheduler:
    """政策同步调度器"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._is_running = False
        self._sync_interval_hours = 24

    async def start(self):
        """启动定时同步任务"""
        if self._is_running:
            logger.warning("政策同步调度器已在运行")
            return

        self._is_running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info(f"✅ 政策同步调度器已启动（间隔: {self._sync_interval_hours}小时）")

    async def stop(self):
        """停止调度器"""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await policy_crawler_service.close()
        logger.info("政策同步调度器已停止")

    async def _run_scheduler(self):
        """运行调度循环"""
        while self._is_running:
            try:
                await self._sync_once()
            except (ValueError, KeyError) as e:
                logger.error(f"政策同步数据错误: {e}")
            except (OSError, IOError) as e:
                logger.error(f"政策同步IO错误: {e}")
            except Exception as e:
                logger.error(f"政策同步失败: {e}")

            await asyncio.sleep(self._sync_interval_hours * 3600)

    async def _sync_once(self):
        """执行一次同步"""
        logger.info("🔄 开始政策同步...")

        policies = await policy_crawler_service.crawl_all_sources(max_per_source=20)

        if not policies:
            logger.warning("⚠️ 未采集到任何政策")
            return

        saved_count = 0
        for policy in policies:
            try:
                if await self._save_policy(policy):
                    saved_count += 1
            except (ValueError, KeyError) as e:
                logger.error(f"保存政策数据错误 [{policy.title}]: {e}")
            except (OSError, IOError) as e:
                logger.error(f"保存政策IO错误 [{policy.title}]: {e}")
            except Exception as e:
                logger.error(f"保存政策失败 [{policy.title}]: {e}")

        logger.info(f"✅ 政策同步完成: 采集 {len(policies)} 条, 新增 {saved_count} 条")

    async def _save_policy(self, crawled: CrawledPolicy) -> bool:
        """
        保存政策到数据库

        Returns:
            bool: 是否新增（True）或已存在（False）
        """
        db = SessionLocal()
        try:
            existing = db.execute(
                select(Policy).where(
                    Policy.title == crawled.title,
                    Policy.source_name == crawled.source
                )
            ).scalar_one_or_none()

            if existing:
                return False

            policy = Policy(
                policy_id=crawled.policy_id,
                title=crawled.title,
                content=crawled.content or f"来源: {crawled.source_url}",
                summary=crawled.summary or "",
                source_name=crawled.source,
                source_url=crawled.source_url,
                status=PolicyStatus.ACTIVE,
                priority=PolicyPriority.MEDIUM,
                tax_types=crawled.tax_types or [],
                industries=crawled.industries or [],
                regions=crawled.regions or [],
            )

            db.add(policy)
            db.commit()
            return True

        except (ValueError, KeyError) as e:
            db.rollback()
            logger.error(f"保存政策数据错误 [{crawled.title}]: {e}")
        except (OSError, IOError) as e:
            db.rollback()
            logger.error(f"保存政策IO错误 [{crawled.title}]: {e}")
        except Exception as e:
            db.rollback()
            logger.error(f"保存政策失败 [{crawled.title}]: {e}")
            raise e
        finally:
            db.close()

    async def sync_now(self):
        """立即执行一次同步（手动触发）"""
        logger.info("🔄 手动触发政策同步...")
        await self._sync_once()


policy_sync_scheduler = PolicySyncScheduler()
