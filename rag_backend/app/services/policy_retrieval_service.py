"""
政策检索服务
提供政策语义检索、关键词匹配和企业匹配功能
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
import uuid

from app.models.policy import Policy, PolicyStatus, PolicyPriority
from app.db.session import SessionLocal
from sqlalchemy import select, and_, or_, desc

logger = logging.getLogger(__name__)


class PolicyRetrievalService:
    """
    政策检索服务
    
    功能：
    1. 语义检索 - 使用向量相似度
    2. 关键词检索 - 全文搜索
    3. 筛选检索 - 按行业/地区/税种筛选
    4. 企业匹配 - 根据企业属性推荐政策（集成PolicyAgent + NotificationAgent）
    """
    
    def __init__(self):
        self.default_top_k = 10
        self.min_score_threshold = 0.5
        self._initialize_agents()
    
    def _initialize_agents(self):
        """初始化PolicyETLService和NotificationService"""
        try:
            from app.services.policy_etl_service import PolicyETLService
            from app.services.notification_service import NotificationService
            
            self.policy_service = PolicyETLService()
            self.notification_service = NotificationService()
            
            logger.info("✅ PolicyRetrievalService: PolicyETLService和NotificationService初始化成功")
            
        except Exception as e:
            logger.warning(f"⚠️ PolicyRetrievalService: Service初始化失败: {e}")
            self.policy_service = None
            self.notification_service = None
    
    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        语义检索政策
        
        Args:
            query: 检索查询
            top_k: 返回数量
            filters: 筛选条件
            tenant_id: 租户ID
            
        Returns:
            List[Dict]: 检索结果列表
        """
        logger.info(f"🔍 语义检索政策: {query[:50]}...")
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            embedding_service = EmbeddingService()
            query_embedding = await embedding_service.get_embedding(query)
            
            results = await self._vector_search(
                query_embedding,
                top_k,
                filters
            )
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 语义检索失败: {e}", exc_info=True)
            return []
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量检索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            filters: 筛选条件
            
        Returns:
            List[Dict]: 检索结果
        """
        db = SessionLocal()
        
        try:
            query = select(Policy).where(Policy.status == PolicyStatus.ACTIVE)
            
            if filters:
                if "industries" in filters and filters["industries"]:
                    query = query.where(
                        Policy.industries.overlap(filters["industries"])
                    )
                if "regions" in filters and filters["regions"]:
                    query = query.where(
                        Policy.regions.overlap(filters["regions"])
                    )
                if "tax_types" in filters and filters["tax_types"]:
                    query = query.where(
                        Policy.tax_types.overlap(filters["tax_types"])
                    )
            
            policies = db.execute(query).scalars().all()
            
            scored_policies = []
            for policy in policies:
                if policy.embedding:
                    similarity = self._cosine_similarity(
                        query_embedding,
                        policy.embedding
                    )
                    
                    if similarity >= self.min_score_threshold:
                        scored_policies.append({
                            "policy_id": str(policy.id),
                            "title": policy.title,
                            "summary": policy.summary,
                            "score": float(similarity),
                            "source_name": policy.source_name,
                            "published_date": policy.published_date.isoformat() if policy.published_date else None,
                            "priority": policy.priority.value,
                            "industries": policy.industries,
                            "regions": policy.regions,
                            "tax_types": policy.tax_types
                        })
            
            scored_policies.sort(key=lambda x: x["score"], reverse=True)
            
            return scored_policies[:top_k]
            
        finally:
            db.close()
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            float: 相似度分数
        """
        if not vec1 or not vec2:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def keyword_search(
        self,
        keywords: List[str],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        关键词检索
        
        Args:
            keywords: 关键词列表
            top_k: 返回数量
            filters: 筛选条件
            
        Returns:
            List[Dict]: 检索结果
        """
        logger.info(f"🔑 关键词检索: {keywords[:3]}...")
        
        db = SessionLocal()
        
        try:
            query = select(Policy).where(Policy.status == PolicyStatus.ACTIVE)
            
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(Policy.title.ilike(f"%{keyword}%"))
                keyword_conditions.append(Policy.content.ilike(f"%{keyword}%"))
            
            if keyword_conditions:
                query = query.where(or_(*keyword_conditions))
            
            if filters:
                if "industries" in filters:
                    query = query.where(
                        Policy.industries.overlap(filters["industries"])
                    )
                if "regions" in filters:
                    query = query.where(
                        Policy.regions.overlap(filters["regions"])
                    )
            
            query = query.order_by(desc(Policy.published_date))
            
            policies = db.execute(query.limit(top_k)).scalars().all()
            
            results = []
            for policy in policies:
                results.append({
                    "policy_id": str(policy.id),
                    "title": policy.title,
                    "summary": policy.summary,
                    "score": 1.0,
                    "source_name": policy.source_name,
                    "published_date": policy.published_date.isoformat() if policy.published_date else None,
                    "priority": policy.priority.value,
                    "industries": policy.industries,
                    "regions": policy.regions,
                    "tax_types": policy.tax_types
                })
            
            return results
            
        finally:
            db.close()
    
    async def match_enterprise_policies(
        self,
        enterprise_profile: Dict[str, Any],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        企业政策匹配（集成PolicyAgent + NotificationAgent）
        
        Args:
            enterprise_profile: 企业画像
            top_k: 返回数量
            
        Returns:
            List[Dict]: 匹配的政策列表，包含增强的匹配信息
        """
        logger.info(f"🎯 企业政策匹配: {enterprise_profile.get('industry', 'unknown')}")
        
        filters = {}
        
        if enterprise_profile.get("industry"):
            filters["industries"] = [enterprise_profile["industry"]]
        
        if enterprise_profile.get("region"):
            filters["regions"] = [enterprise_profile["region"]]
        
        if enterprise_profile.get("tax_types"):
            filters["tax_types"] = enterprise_profile["tax_types"]
        
        query_text = self._build_match_query(enterprise_profile)
        
        results = await self.semantic_search(
            query=query_text,
            top_k=top_k,
            filters=filters
        )
        
        for result in results:
            result["match_reasons"] = self._explain_match(
                result,
                enterprise_profile
            )
        
        logger.info(f"🔍 检查是否需要增强: notification_service={self.notification_service is not None}, enterprise_profile={enterprise_profile}")
        
        if self.notification_service and enterprise_profile:
            logger.info("✅ 开始使用NotificationService增强匹配结果")
            results = await self._enhance_with_notification_service(
                results,
                enterprise_profile
            )
        else:
            logger.warning(f"⚠️ 跳过NotificationService增强: "
                          f"service={'存在' if self.notification_service else '不存在'}, "
                          f"profile={'有数据' if enterprise_profile else '为空'}")
        
        results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        
        return results
    
    async def _enhance_with_notification_service(
        self,
        results: List[Dict[str, Any]],
        enterprise_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        使用NotificationService增强匹配结果
        
        Args:
            results: 原始匹配结果
            enterprise_profile: 企业画像
            
        Returns:
            List[Dict]: 增强后的匹配结果
        """
        try:
            from app.services.notification_service import EnterpriseProfile
            
            ep = EnterpriseProfile(
                enterprise_id=enterprise_profile.get("enterprise_id", str(uuid.uuid4())),
                name=enterprise_profile.get("name", "未知企业"),
                industries=[enterprise_profile.get("industry")] if enterprise_profile.get("industry") else [],
                regions=[enterprise_profile.get("region")] if enterprise_profile.get("region") else [],
                scales=[enterprise_profile.get("scale")] if enterprise_profile.get("scale") else [],
                tax_types=enterprise_profile.get("tax_types", [])
            )
            
            for result in results:
                policy_id = result.get("policy_id")
                if not policy_id:
                    continue
                
                try:
                    db = SessionLocal()
                    try:
                        policy = db.execute(
                            select(Policy).where(Policy.id == UUID(policy_id))
                        ).scalar_one_or_none()
                        
                        if policy:
                            match_score, match_reasons = await self.notification_service.match_enterprise(
                                policy=policy,
                                enterprise_profile=ep
                            )
                            
                            result["match_score"] = match_score.total_score
                            result["industry_score"] = match_score.industry_score
                            result["region_score"] = match_score.region_score
                            result["scale_score"] = match_score.scale_score
                            result["tax_type_score"] = match_score.tax_type_score
                            
                            result["match_reasons"] = [
                                {"category": r.category, "reason": r.reason, "items": r.matched_items}
                                for r in match_reasons
                            ]
                            
                            result["risk_level"] = self._determine_risk_level(
                                match_score.total_score,
                                policy.priority
                            )
                            
                            result["recommendations"] = self._generate_recommendations(
                                match_score,
                                policy.priority
                            )
                    finally:
                        db.close()
                        
                except Exception as e:
                    logger.warning(f"⚠️ 增强政策匹配失败: {result.get('policy_id')}: {e}")
                    continue
            
            if enterprise_profile.get("enterprise_id"):
                await self._sync_enterprise_profile_to_settings(
                    enterprise_profile.get("enterprise_id"),
                    enterprise_profile
                )
            
            return results
            
        except Exception as e:
            logger.warning(f"⚠️ NotificationService增强失败: {e}")
            return results
    
    async def _sync_enterprise_profile_to_settings(
        self,
        tenant_id: str,
        enterprise_profile: Dict[str, Any]
    ):
        """
        同步企业画像到租户设置
        
        Args:
            tenant_id: 租户ID
            enterprise_profile: 企业画像数据
        """
        try:
            from app.services.tenant_settings_service import tenant_settings_service
            from app.schemas.tenant_settings import TenantSettingsUpdate
            
            logger.info(f"🔄 开始同步企业画像: tenant_id={tenant_id}")
            logger.debug(f"📋 企业画像数据: {enterprise_profile}")
            
            update_data = {}
            
            if enterprise_profile.get("industry"):
                update_data["industry"] = enterprise_profile["industry"]
                logger.debug(f"✅ 同步行业: {enterprise_profile['industry']}")
            
            if enterprise_profile.get("region"):
                update_data["region"] = enterprise_profile["region"]
                logger.debug(f"✅ 同步地区: {enterprise_profile['region']}")
            
            if enterprise_profile.get("scale"):
                update_data["scale"] = enterprise_profile["scale"]
                logger.debug(f"✅ 同步规模: {enterprise_profile['scale']}")
            
            if enterprise_profile.get("tax_types"):
                update_data["tax_types"] = enterprise_profile["tax_types"]
                logger.debug(f"✅ 同步税种: {enterprise_profile['tax_types']}")
            
            if not update_data:
                logger.warning(f"⚠️ 无需同步企业画像: tenant_id={tenant_id}, 所有字段都为空")
                return
            
            logger.info(f"📦 待更新的数据: {update_data}")
            
            settings_update = TenantSettingsUpdate(**update_data)
            
            result = await tenant_settings_service.update_settings(
                tenant_id,
                settings_update
            )
            
            if result:
                logger.info(f"✅ 企业画像已同步到租户设置: tenant_id={tenant_id}, "
                          f"industry={enterprise_profile.get('industry')}, "
                          f"region={enterprise_profile.get('region')}, "
                          f"scale={enterprise_profile.get('scale')}, "
                          f"tax_types={enterprise_profile.get('tax_types')}")
            else:
                logger.error(f"❌ 租户设置不存在，无法同步: tenant_id={tenant_id}")
                logger.error("❌ 可能的原因：1) 租户设置未初始化 2) tenant_id不匹配")
                logger.error(f"❌ 请检查 tenant_settings 表中是否存在 tenant_id={tenant_id} 的记录")
                
        except Exception as e:
            logger.error(f"❌ 同步企业画像到租户设置失败: {e}", exc_info=True)
            import traceback
            logger.error(f"❌ 详细错误: {traceback.format_exc()}")
    
    def _determine_risk_level(self, match_score: float, priority: str) -> str:
        """确定风险级别"""
        if priority in ["CRITICAL", "HIGH"]:
            return "high"
        if match_score >= 0.8:
            return "high"
        elif match_score >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, match_score, priority: str) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if priority in ["CRITICAL", "HIGH"]:
            recommendations.append("建议优先关注并评估影响")
        
        if match_score.industry_score >= 0.8:
            recommendations.append("该政策与您的行业高度相关")
        
        if match_score.tax_type_score >= 0.8:
            recommendations.append("该政策涉及您的主要税种")
        
        if not recommendations:
            recommendations.append("建议详细了解政策内容")
        
        return recommendations
    
    def _build_match_query(self, profile: Dict[str, Any]) -> str:
        """
        构建匹配查询文本
        
        Args:
            profile: 企业画像
            
        Returns:
            str: 查询文本
        """
        parts = []
        
        if profile.get("industry"):
            parts.append(f"{profile['industry']}行业")
        
        if profile.get("scale"):
            parts.append(f"{profile['scale']}企业")
        
        if profile.get("tax_types"):
            parts.append(" ".join(profile["tax_types"]))
        
        if profile.get("keywords"):
            parts.extend(profile["keywords"][:5])
        
        if not parts:
            parts = ["税务政策", "优惠政策", "企业税收"]
        
        return " ".join(parts)
    
    def _explain_match(
        self,
        policy: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> List[str]:
        """
        解释匹配原因
        
        Args:
            policy: 政策
            profile: 企业画像
            
        Returns:
            List[str]: 匹配原因列表
        """
        reasons = []
        
        if policy.get("industries") and profile.get("industry"):
            if profile["industry"] in policy["industries"]:
                reasons.append(f"适用于{profile['industry']}行业")
        
        if policy.get("regions") and profile.get("region"):
            if profile["region"] in policy["regions"]:
                reasons.append(f"在{profile['region']}适用")
        
        if policy.get("tax_types") and profile.get("tax_types"):
            matching_tax_types = set(policy["tax_types"]) & set(profile["tax_types"])
            if matching_tax_types:
                reasons.append(f"涉及相关税种: {', '.join(matching_tax_types)}")
        
        if policy.get("priority") in [PolicyPriority.CRITICAL.value, PolicyPriority.HIGH.value]:
            reasons.append("高优先级政策")
        
        if not reasons:
            reasons.append("与您的企业相关")
        
        return reasons
    
    async def get_policy_by_id(
        self,
        policy_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        根据ID获取政策详情
        
        Args:
            policy_id: 政策ID
            
        Returns:
            Optional[Dict]: 政策详情
        """
        db = SessionLocal()
        
        try:
            policy = db.execute(
                select(Policy).where(Policy.id == policy_id)
            ).scalar_one_or_none()
            
            if not policy:
                return None
            
            return {
                "policy_id": str(policy.id),
                "policy_id_external": policy.policy_id,
                "title": policy.title,
                "content": policy.content,
                "summary": policy.summary,
                "source_name": policy.source_name,
                "source_url": policy.source_url,
                "published_date": policy.published_date.isoformat() if policy.published_date else None,
                "effective_date": policy.effective_date.isoformat() if policy.effective_date else None,
                "expiry_date": policy.expiry_date.isoformat() if policy.expiry_date else None,
                "priority": policy.priority.value,
                "status": policy.status.value,
                "industries": policy.industries,
                "regions": policy.regions,
                "scales": policy.scales,
                "tax_types": policy.tax_types,
                "tags": policy.tags,
                "meta_info": policy.meta_info,
                "view_count": policy.view_count,
                "created_at": policy.created_at.isoformat() if policy.created_at else None,
                "updated_at": policy.updated_at.isoformat() if policy.updated_at else None
            }
            
        finally:
            db.close()
    
    async def get_recent_policies(
        self,
        days: int = 7,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取最近更新的政策
        
        Args:
            days: 天数
            top_k: 返回数量
            filters: 筛选条件
            
        Returns:
            List[Dict]: 政策列表
        """
        db = SessionLocal()
        
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = select(Policy).where(
                and_(
                    Policy.status == PolicyStatus.ACTIVE,
                    Policy.updated_at >= cutoff_date
                )
            )
            
            if filters:
                if "priority" in filters:
                    query = query.where(Policy.priority == filters["priority"])
                if "industries" in filters:
                    query = query.where(
                        Policy.industries.overlap(filters["industries"])
                    )
            
            query = query.order_by(desc(Policy.updated_at))
            
            policies = db.execute(query.limit(top_k)).scalars().all()
            
            results = []
            for policy in policies:
                results.append({
                    "policy_id": str(policy.id),
                    "title": policy.title,
                    "summary": policy.summary,
                    "source_name": policy.source_name,
                    "published_date": policy.published_date.isoformat() if policy.published_date else None,
                    "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
                    "priority": policy.priority.value
                })
            
            return results
            
        finally:
            db.close()
    
    async def list_policies(
        self,
        query: Optional[str] = None,
        industries: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        tax_types: Optional[List[str]] = None,
        scales: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        获取政策列表（分页）
        
        Args:
            query: 搜索关键词
            industries: 行业筛选
            regions: 地区筛选
            tax_types: 税种筛选
            scales: 企业规模筛选
            page: 页码
            page_size: 每页数量
            tenant_id: 租户ID
            
        Returns:
            Dict: 包含 policies, total, page, page_size
        """
        db = SessionLocal()
        
        try:
            stmt = select(Policy).where(
                Policy.status == PolicyStatus.ACTIVE
            )
            
            if industries:
                stmt = stmt.where(Policy.industries.overlap(industries))
            if regions:
                stmt = stmt.where(Policy.regions.overlap(regions))
            if tax_types:
                stmt = stmt.where(Policy.tax_types.overlap(tax_types))
            
            if query:
                search_filter = or_(
                    Policy.title.ilike(f"%{query}%"),
                    Policy.summary.ilike(f"%{query}%"),
                    Policy.content.ilike(f"%{query}%")
                )
                stmt = stmt.where(search_filter)
            
            total = len(db.execute(stmt).scalars().all())
            
            stmt = stmt.order_by(desc(Policy.published_date))
            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)
            
            policies = db.execute(stmt).scalars().all()
            
            results = []
            for policy in policies:
                results.append({
                    "id": str(policy.id),
                    "policy_id": policy.policy_id,
                    "title": policy.title,
                    "summary": policy.summary,
                    "content": policy.content[:500] + "..." if policy.content and len(policy.content) > 500 else policy.content,
                    "source_name": policy.source_name,
                    "source_url": policy.source_url,
                    "published_date": policy.published_date.isoformat() if policy.published_date else None,
                    "effective_date": policy.effective_date.isoformat() if policy.effective_date else None,
                    "expiry_date": policy.expiry_date.isoformat() if policy.expiry_date else None,
                    "status": policy.status.value,
                    "priority": policy.priority.value if policy.priority else None,
                    "industries": policy.industries or [],
                    "regions": policy.regions or [],
                    "tax_types": policy.tax_types or [],
                    "scales": policy.scales or [],
                    "tags": policy.tags or [],
                    "view_count": policy.view_count or 0,
                    "created_at": policy.created_at.isoformat() if policy.created_at else None,
                    "updated_at": policy.updated_at.isoformat() if policy.updated_at else None
                })
            
            return {
                "policies": results,
                "total": total,
                "page": page,
                "page_size": page_size
            }
            
        finally:
            db.close()


policy_retrieval_service = PolicyRetrievalService()
