"""
政策通知服务
自动匹配并推送政策给企业用户
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from app.models.policy import Policy
from app.models.enterprise_policy_match import EnterprisePolicyMatch, NotificationStatus, MatchStatus
from app.db.session import SessionLocal
from sqlalchemy import select, and_, update
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PolicyNotificationService:
    """
    政策通知服务
    
    功能：
    1. 监控新政策入库
    2. 自动匹配企业用户
    3. 生成并发送通知
    4. 追踪通知状态
    """
    
    def __init__(self):
        self.match_threshold = 0.6
        self.batch_size = 100
    
    async def on_policy_added(
        self,
        policy_id: UUID,
        enterprise_ids: Optional[List[str]] = None
    ):
        """
        政策新增时触发匹配
        
        Args:
            policy_id: 政策ID
            enterprise_ids: 指定企业ID列表（None表示匹配所有）
        """
        logger.info(f"📋 触发政策匹配: {policy_id}")
        
        try:
            from .policy_retrieval_service import policy_retrieval_service
            
            policy_data = await policy_retrieval_service.get_policy_by_id(policy_id)
            
            if not policy_data:
                logger.warning(f"⚠️ 未找到政策: {policy_id}")
                return
            
            if enterprise_ids:
                await self._match_specific_enterprises(
                    policy_data,
                    enterprise_ids
                )
            else:
                await self._match_all_enterprises(policy_data)
            
            logger.info(f"✅ 政策匹配完成: {policy_id}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 政策匹配数据错误: {e}", exc_info=True)
        except (OSError, IOError) as e:
            logger.error(f"❌ 政策匹配IO错误: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ 政策匹配失败: {e}", exc_info=True)
    
    async def _match_all_enterprises(
        self,
        policy_data: Dict[str, Any]
    ):
        """
        匹配所有企业
        
        Args:
            policy_data: 政策数据
        """
        db = SessionLocal()
        
        try:
            from app.models.tenant import Tenant
            
            tenants = db.execute(select(Tenant)).scalars().all()
            
            logger.info(f"🏢 匹配 {len(tenants)} 个企业")
            
            for tenant in tenants:
                enterprise_profile = self._get_enterprise_profile(tenant)
                
                match_score = self._calculate_match_score(
                    policy_data,
                    enterprise_profile
                )
                
                if match_score >= self.match_threshold:
                    await self._create_match_and_notification(
                        str(tenant.id),
                        policy_data,
                        match_score
                    )
            
        finally:
            db.close()
    
    async def _match_specific_enterprises(
        self,
        policy_data: Dict[str, Any],
        enterprise_ids: List[str]
    ):
        """
        匹配指定企业
        
        Args:
            policy_data: 政策数据
            enterprise_ids: 企业ID列表
        """
        for enterprise_id in enterprise_ids:
            try:
                enterprise_profile = await self._get_enterprise_profile_by_id(
                    enterprise_id
                )
                
                if not enterprise_profile:
                    continue
                
                match_score = self._calculate_match_score(
                    policy_data,
                    enterprise_profile
                )
                
                if match_score >= self.match_threshold:
                    await self._create_match_and_notification(
                        enterprise_id,
                        policy_data,
                        match_score
                    )
                    
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 匹配企业数据错误 [{enterprise_id}]: {e}")
            except (OSError, IOError) as e:
                logger.error(f"❌ 匹配企业IO错误 [{enterprise_id}]: {e}")
            except Exception as e:
                logger.error(f"❌ 匹配企业失败 [{enterprise_id}]: {e}")
    
    async def _get_enterprise_profile_by_id(
        self,
        enterprise_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取企业画像
        
        Args:
            enterprise_id: 企业ID
            
        Returns:
            Optional[Dict]: 企业画像
        """
        db = SessionLocal()
        
        try:
            from app.models.tenant import Tenant
            
            tenant = db.execute(
                select(Tenant).where(Tenant.id == enterprise_id)
            ).scalar_one_or_none()
            
            if tenant:
                return self._get_enterprise_profile(tenant)
            
            return None
            
        finally:
            db.close()
    
    def _get_enterprise_profile(self, tenant) -> Dict[str, Any]:
        """
        从租户获取企业画像
        
        Args:
            tenant: 租户对象
            
        Returns:
            Dict: 企业画像
        """
        profile = {
            "industry": getattr(tenant, "industry", None),
            "region": getattr(tenant, "region", None),
            "scale": getattr(tenant, "scale", None),
            "tax_types": getattr(tenant, "tax_types", []),
            "keywords": []
        }
        
        if hasattr(tenant, "meta_info") and tenant.meta_info:
            profile["keywords"] = tenant.meta_info.get("keywords", [])
        
        return profile
    
    def _calculate_match_score(
        self,
        policy_data: Dict[str, Any],
        enterprise_profile: Dict[str, Any]
    ) -> float:
        """
        计算匹配分数
        
        Args:
            policy_data: 政策数据
            enterprise_profile: 企业画像
            
        Returns:
            float: 匹配分数
        """
        score = 0.0
        factors = 0
        
        if policy_data.get("industries") and enterprise_profile.get("industry"):
            if enterprise_profile["industry"] in policy_data["industries"]:
                score += 0.4
            factors += 1
        
        if policy_data.get("regions") and enterprise_profile.get("region"):
            if enterprise_profile["region"] in policy_data["regions"]:
                score += 0.2
            factors += 1
        
        if policy_data.get("tax_types") and enterprise_profile.get("tax_types"):
            matching = set(policy_data["tax_types"]) & set(enterprise_profile["tax_types"])
            if matching:
                score += 0.3
            factors += 1
        
        if policy_data.get("scales") and enterprise_profile.get("scale"):
            if enterprise_profile["scale"] in policy_data["scales"]:
                score += 0.1
            factors += 1
        
        if policy_data.get("priority") in ["critical", "high"]:
            score += 0.1
        
        if factors > 0:
            score = min(1.0, score)
        
        return score
    
    async def _create_match_and_notification(
        self,
        enterprise_id: str,
        policy_data: Dict[str, Any],
        match_score: float
    ):
        """
        创建匹配记录和通知
        
        Args:
            enterprise_id: 企业ID
            policy_data: 政策数据
            match_score: 匹配分数
        """
        db = SessionLocal()
        
        try:
            existing = db.execute(
                select(EnterprisePolicyMatch).where(
                    and_(
                        EnterprisePolicyMatch.enterprise_id == enterprise_id,
                        EnterprisePolicyMatch.policy_id == policy_data["policy_id"]
                    )
                )
            ).scalar_one_or_none()
            
            if existing:
                logger.debug(f"⏭️ 跳过已有匹配: {enterprise_id} - {policy_data['policy_id']}")
                return
            
            match = EnterprisePolicyMatch(
                enterprise_id=enterprise_id,
                policy_id=policy_data["policy_id"],
                match_score=match_score,
                match_status=MatchStatus.MATCHED,
                notification_status=NotificationStatus.PENDING,
                match_reasons=self._generate_match_reasons(
                    policy_data,
                    enterprise_id
                ),
                meta_info={
                    "policy_title": policy_data["title"],
                    "priority": policy_data.get("priority"),
                    "source": policy_data.get("source_name")
                }
            )
            
            db.add(match)
            await db.commit()
            
            logger.info(
                f"📬 创建匹配: {enterprise_id} - "
                f"{policy_data['title'][:30]}... (分数: {match_score:.2f})"
            )
            
            await self._send_notification(match, policy_data)
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 创建匹配数据错误: {e}", exc_info=True)
            await db.rollback()
        except (OSError, IOError) as e:
            logger.error(f"❌ 创建匹配IO错误: {e}", exc_info=True)
            await db.rollback()
        except Exception as e:
            logger.error(f"❌ 创建匹配失败: {e}", exc_info=True)
            await db.rollback()
        finally:
            db.close()
    
    def _generate_match_reasons(
        self,
        policy_data: Dict[str, Any],
        enterprise_id: str
    ) -> List[str]:
        """
        生成匹配原因
        
        Args:
            policy_data: 政策数据
            enterprise_id: 企业ID
            
        Returns:
            List[str]: 匹配原因列表
        """
        reasons = []
        
        if policy_data.get("industries"):
            reasons.append(f"适用于行业: {', '.join(policy_data['industries'][:3])}")
        
        if policy_data.get("regions"):
            reasons.append(f"适用地区: {', '.join(policy_data['regions'][:3])}")
        
        if policy_data.get("tax_types"):
            reasons.append(f"涉及税种: {', '.join(policy_data['tax_types'][:3])}")
        
        if policy_data.get("priority") in ["critical", "high"]:
            reasons.append("⚠️ 高优先级政策")
        
        return reasons
    
    async def _send_notification(
        self,
        match: EnterprisePolicyMatch,
        policy_data: Dict[str, Any]
    ):
        """
        发送通知
        
        Args:
            match: 匹配记录
            policy_data: 政策数据
        """
        try:
            logger.info(f"📨 发送通知: {match.id}")
            
            match.notification_status = NotificationStatus.SENT
            match.notified_at = datetime.now()
            
            db = SessionLocal()
            try:
                await db.commit()
            finally:
                db.close()
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 发送通知数据错误: {e}", exc_info=True)
            match.notification_status = NotificationStatus.FAILED
        except (OSError, IOError) as e:
            logger.error(f"❌ 发送通知IO错误: {e}", exc_info=True)
            match.notification_status = NotificationStatus.FAILED
        except Exception as e:
            logger.error(f"❌ 发送通知失败: {e}", exc_info=True)
            match.notification_status = NotificationStatus.FAILED
    
    async def batch_process_pending_notifications(
        self,
        limit: int = 100
    ) -> int:
        """
        批量处理待发送的通知
        
        Args:
            limit: 处理数量限制
            
        Returns:
            int: 处理的邮件数量
        """
        db = SessionLocal()
        
        try:
            pending = db.execute(
                select(EnterprisePolicyMatch).where(
                    EnterprisePolicyMatch.notification_status == NotificationStatus.PENDING
                ).limit(limit)
            ).scalars().all()
            
            count = 0
            for match in pending:
                try:
                    await self._send_notification(match, {})
                    count += 1
                except (ValueError, KeyError) as e:
                    logger.error(f"❌ 处理通知数据错误 [{match.id}]: {e}")
                except (OSError, IOError) as e:
                    logger.error(f"❌ 处理通知IO错误 [{match.id}]: {e}")
                except Exception as e:
                    logger.error(f"❌ 处理通知失败 [{match.id}]: {e}")
            
            logger.info(f"✅ 批量处理完成: {count}/{len(pending)}")
            return count
            
        finally:
            db.close()
    
    async def get_enterprise_notifications(
        self,
        enterprise_id: str,
        status: Optional[NotificationStatus] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取企业通知列表
        
        Args:
            enterprise_id: 企业ID
            status: 通知状态筛选
            limit: 返回数量
            
        Returns:
            List[Dict]: 通知列表
        """
        db = SessionLocal()
        
        try:
            query = select(EnterprisePolicyMatch).where(
                EnterprisePolicyMatch.enterprise_id == enterprise_id
            )
            
            if status:
                query = query.where(
                    EnterprisePolicyMatch.notification_status == status
                )
            
            query = query.order_by(
                EnterprisePolicyMatch.created_at.desc()
            ).limit(limit)
            
            matches = db.execute(query).scalars().all()
            
            results = []
            for match in matches:
                results.append({
                    "id": str(match.id),
                    "policy_id": match.policy_id,
                    "match_score": match.match_score,
                    "match_status": match.match_status.value,
                    "notification_status": match.notification_status.value,
                    "match_reasons": match.match_reasons,
                    "acknowledged": match.acknowledged_at is not None,
                    "acknowledged_at": match.acknowledged_at.isoformat() if match.acknowledged_at else None,
                    "created_at": match.created_at.isoformat() if match.created_at else None
                })
            
            return results
            
        finally:
            db.close()


policy_notification_service = PolicyNotificationService()
