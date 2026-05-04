"""
政策服务 (Policy Service)

统一管理政策全生命周期：
1. 政策采集 - 从官方渠道采集最新政策
2. 政策存储 - 结构化存储到数据库
3. 政策检索 - 语义检索和关键词搜索
4. 调度管理 - 定时同步任务管理
5. 通知触发 - 触发政策通知服务

整合了以下服务的能力：
- policy_crawler_service (采集)
- policy_scheduler_service (同步调度)
- policy_scheduler (调度配置)
- policy_retrieval_service (检索代理)
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from uuid import UUID

from app.services.policy_crawler_service import policy_crawler_service, CrawledPolicy, PolicySource
from app.models.policy import Policy, PolicyStatus, PolicyPriority
from app.db.session import SessionLocal
from app.core.config import settings
from sqlalchemy import select

logger = logging.getLogger(__name__)


class UpdateFrequency(str, Enum):
    """更新频率枚举"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class SchedulerConfig:
    """调度器配置"""
    frequency: UpdateFrequency = UpdateFrequency.DAILY
    keywords: List[str] = None
    enabled_sources: List[str] = None
    time_of_day: str = "03:00"


@dataclass
class SyncResult:
    """同步结果"""
    total_collected: int
    new_saved: int
    errors: List[str]
    sources: List[Dict[str, Any]]
    duration_seconds: float


class PolicyService:
    """
    统一政策服务
    
    功能：
    1. 采集 - 从官方渠道采集政策
    2. 同步 - 入库并触发通知
    3. 检索 - 代理到 PolicyRetrievalService
    4. 调度 - 定时同步管理
    """

    def __init__(self):
        self._scheduler_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_run: Optional[datetime] = None
        self._last_status: Optional[Dict[str, Any]] = None
        self._run_history: List[Dict[str, Any]] = []
        self._config = SchedulerConfig()
        
        logger.info("✅ PolicyService 初始化完成")

    async def crawl_policies(self, max_per_source: int = 20) -> List[CrawledPolicy]:
        """
        采集政策 — 使用增强版爬虫（RSS + Sitemap + ETag 缓存 + 多级降级）

        Args:
            max_per_source: 每个来源最大采集数量

        Returns:
            List[CrawledPolicy]: 采集的政策列表
        """
        logger.info(f"🔍 开始采集政策（每来源最大: {max_per_source}）...")

        try:
            from app.services.policy_crawler_enhanced import crawl_all_sources_enhanced
            policies = await crawl_all_sources_enhanced(
                max_per_source=max_per_source,
                include_sample=settings.POLICY_SAMPLE_FALLBACK_ENABLED,
            )
            
            logger.info(f"✅ 采集完成: {len(policies)} 条政策")
            return policies
            
        except Exception as e:
            logger.error(f"❌ 采集失败: {e}", exc_info=True)
            return []

    async def sync_policies(
        self,
        max_per_source: int = 20,
        notify_enterprises: bool = True
    ) -> SyncResult:
        """
        同步政策（采集 + 入库 + 触发通知）
        
        Args:
            max_per_source: 每个来源最大采集数量
            notify_enterprises: 是否触发通知
            
        Returns:
            SyncResult: 同步结果
        """
        logger.info("🔄 开始政策同步...")
        
        start_time = datetime.now()
        errors = []
        sources_info = []
        saved_count = 0
        
        try:
            policies = await self.crawl_policies(max_per_source)
            
            if not policies:
                logger.warning("⚠️ 未采集到任何政策")
                return SyncResult(
                    total_collected=0,
                    new_saved=0,
                    errors=["未采集到政策"],
                    sources=sources_info,
                    duration_seconds=0
                )
            
            sources_info.append({
                "source": "crawl_all",
                "collected": len(policies),
                "status": "success"
            })
            
            for policy in policies:
                try:
                    if await self._save_policy(policy):
                        saved_count += 1
                        
                        if notify_enterprises:
                            await self._trigger_notification(policy)
                            
                except Exception as e:
                    error_msg = f"保存政策失败 [{policy.title}]: {e}"
                    logger.error(f"❌ {error_msg}")
                    errors.append(error_msg)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result = SyncResult(
                total_collected=len(policies),
                new_saved=saved_count,
                errors=errors,
                sources=sources_info,
                duration_seconds=duration
            )
            
            self._last_status = {
                "start_time": start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "total_collected": result.total_collected,
                "new_saved": result.new_saved,
                "errors": errors,
                "status": "success" if not errors else "partial"
            }
            
            logger.info(
                f"✅ 同步完成: 采集 {result.total_collected} 条, "
                f"新增 {result.new_saved} 条, 耗时 {duration:.2f}秒"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"同步失败: {e}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            errors.append(error_msg)
            
            return SyncResult(
                total_collected=0,
                new_saved=0,
                errors=[error_msg],
                sources=sources_info,
                duration_seconds=0
            )

    async def sync_now(self) -> Dict[str, Any]:
        """
        立即执行一次同步（手动触发）
        
        Returns:
            Dict: 同步结果
        """
        logger.info("🔧 手动触发政策同步...")
        
        result = await self.sync_policies()
        
        return {
            "message": "政策同步任务已完成",
            "status": "success" if result.new_saved > 0 else "warning",
            "collected": result.total_collected,
            "saved": result.new_saved,
            "errors": result.errors
        }

    async def _save_policy(self, crawled: CrawledPolicy) -> bool:
        """
        保存政策到数据库
        
        Args:
            crawled: 采集的政策数据
            
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
                logger.debug(f"⏭️ 政策已存在: {crawled.title}")
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
            db.refresh(policy)
            
            logger.info(f"💾 保存政策: {policy.title} (ID: {policy.id})")
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 保存政策失败 [{crawled.title}]: {e}", exc_info=True)
            raise e
        finally:
            db.close()

    async def _trigger_notification(self, crawled: CrawledPolicy):
        """
        触发政策通知
        
        Args:
            crawled: 采集的政策数据
        """
        try:
            from app.services.policy_notification_service import policy_notification_service
            
            policy_id = None
            
            db = SessionLocal()
            try:
                existing = db.execute(
                    select(Policy).where(
                        Policy.title == crawled.title,
                        Policy.source_name == crawled.source
                    )
                ).scalar_one_or_none()
                
                if existing:
                    policy_id = existing.id
            finally:
                db.close()
            
            if policy_id:
                asyncio.create_task(
                    policy_notification_service.on_policy_added(
                        policy_id=policy_id,
                        enterprise_ids=None
                    )
                )
                logger.debug(f"📬 已触发政策通知: {crawled.title}")
                
        except Exception as e:
            logger.warning(f"⚠️ 触发通知失败 [{crawled.title}]: {e}")

    async def start_scheduler(self):
        """启动定时同步调度器"""
        if self._is_running:
            logger.warning("⚠️ PolicyService 调度器已在运行")
            return
        
        self._is_running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        logger.info(f"🚀 PolicyService 调度器已启动（频率: {self._config.frequency.value}）")

    async def stop_scheduler(self):
        """停止定时同步调度器"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        await policy_crawler_service.close()
        logger.info("🛑 PolicyService 调度器已停止")

    async def _run_scheduler(self):
        """运行调度循环"""
        interval_map = {
            UpdateFrequency.HOURLY: 3600,
            UpdateFrequency.DAILY: 86400,
            UpdateFrequency.WEEKLY: 604800,
            UpdateFrequency.MONTHLY: 2592000,
        }
        
        interval_seconds = interval_map.get(self._config.frequency, 86400)
        
        logger.info(f"⏰ 调度器运行中，间隔: {interval_seconds}秒")
        
        while self._is_running:
            try:
                self._last_run = datetime.now()
                await self.sync_policies()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 调度同步失败: {e}", exc_info=True)
            
            await asyncio.sleep(interval_seconds)

    def configure_scheduler(self, config: SchedulerConfig):
        """
        配置调度器
        
        Args:
            config: 调度配置
        """
        self._config = config
        logger.info(f"⚙️ 调度器配置已更新: frequency={config.frequency.value}")
        
        if config.keywords:
            logger.info(f"   关键词: {', '.join(config.keywords[:5])}...")

    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        获取调度器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "running": self._is_running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_status": self._last_status,
            "config": {
                "frequency": self._config.frequency.value,
                "keywords": self._config.keywords or [],
                "enabled_sources": self._config.enabled_sources,
                "time_of_day": self._config.time_of_day
            },
            "history_count": len(self._run_history)
        }

    async def trigger_manual_update(
        self,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        手动触发更新
        
        Args:
            keywords: 关键词列表
            
        Returns:
            Dict: 更新结果
        """
        logger.info("🔧 手动触发政策更新...")
        
        original_keywords = self._config.keywords
        
        if keywords:
            self._config.keywords = keywords
        
        result = await self.sync_policies()
        
        self._config.keywords = original_keywords
        
        return {
            "status": "completed",
            "collected": result.total_collected,
            "saved": result.new_saved,
            "errors": result.errors
        }

    async def get_policy_by_id(self, policy_id: UUID) -> Optional[Dict[str, Any]]:
        """
        获取政策详情（代理到 PolicyRetrievalService）
        
        Args:
            policy_id: 政策ID
            
        Returns:
            Optional[Dict]: 政策数据
        """
        try:
            from app.services.policy_retrieval_service import PolicyRetrievalService
            
            service = PolicyRetrievalService()
            return await service.get_policy_by_id(policy_id)
            
        except Exception as e:
            logger.error(f"❌ 获取政策详情失败: {e}", exc_info=True)
            return None

    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        语义检索政策（代理到 PolicyRetrievalService）
        
        Args:
            query: 检索查询
            top_k: 返回数量
            filters: 筛选条件
            tenant_id: 租户ID
            
        Returns:
            List[Dict]: 检索结果列表
        """
        try:
            from app.services.policy_retrieval_service import PolicyRetrievalService
            
            service = PolicyRetrievalService()
            return await service.semantic_search(
                query=query,
                top_k=top_k,
                filters=filters,
                tenant_id=tenant_id
            )
            
        except Exception as e:
            logger.error(f"❌ 语义检索失败: {e}", exc_info=True)
            return []

    async def get_recent_policies(
        self,
        days: int = 7,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取最近更新的政策（代理到 PolicyRetrievalService）
        
        Args:
            days: 最近天数
            top_k: 返回数量
            
        Returns:
            List[Dict]: 政策列表
        """
        try:
            from app.services.policy_retrieval_service import PolicyRetrievalService
            
            service = PolicyRetrievalService()
            return await service.get_recent_policies(days=days, top_k=top_k)
            
        except Exception as e:
            logger.error(f"❌ 获取最近政策失败: {e}", exc_info=True)
            return []

    async def match_enterprise_policies(
        self,
        enterprise_profile: Dict[str, Any],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        企业政策匹配（代理到 PolicyRetrievalService）
        
        Args:
            enterprise_profile: 企业画像
            top_k: 返回数量
            
        Returns:
            List[Dict]: 匹配结果
        """
        try:
            from app.services.policy_retrieval_service import PolicyRetrievalService
            
            service = PolicyRetrievalService()
            return await service.match_enterprise_policies(
                enterprise_profile=enterprise_profile,
                top_k=top_k
            )
            
        except Exception as e:
            logger.error(f"❌ 企业政策匹配失败: {e}", exc_info=True)
            return []


policy_service = PolicyService()
