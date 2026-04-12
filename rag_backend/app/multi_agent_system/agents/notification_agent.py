"""
通知智能体 (Notification Agent)
负责企业匹配、个性化推送、追踪确认
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.models.policy import Policy, PolicyStatus, PolicyPriority
from app.models.enterprise_policy_match import EnterprisePolicyMatch, NotificationStatus, MatchStatus
from app.db.session import SessionLocal
from sqlalchemy import select, update, and_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MatchScore(BaseModel):
    """匹配评分"""
    total_score: float = Field(ge=0.0, le=1.0, description="总分")
    industry_score: float = Field(ge=0.0, le=1.0, description="行业匹配分")
    region_score: float = Field(ge=0.0, le=1.0, description="地区匹配分")
    scale_score: float = Field(ge=0.0, le=1.0, description="规模匹配分")
    tax_type_score: float = Field(ge=0.0, le=1.0, description="税种匹配分")


class MatchReason(BaseModel):
    """匹配原因"""
    category: str
    reason: str
    matched_items: List[str]


class EnterpriseProfile(BaseModel):
    """企业画像"""
    enterprise_id: str
    name: str
    industries: List[str] = []
    regions: List[str] = []
    scales: List[str] = []
    tax_types: List[str] = []
    preferences: Dict[str, Any] = {}


class NotificationMessage(BaseModel):
    """通知消息"""
    title: str
    content: str
    policy_id: str
    policy_title: str
    impact_level: str
    key_points: List[str]
    action_url: Optional[str] = None


class NotificationResult(BaseModel):
    """通知结果"""
    success: bool
    notification_status: NotificationStatus
    message: str
    sent_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class NotificationAgent:
    """
    通知智能体
    
    职责：
    1. 匹配: 企业画像与政策匹配
    2. 推送: 个性化政策通知
    3. 追踪: 用户确认状态
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        session: Optional[Session] = None
    ):
        """
        初始化通知智能体
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            session: 数据库会话（可选，不提供时自动创建）
        """
        self.llm_adapter = llm_adapter
        self.tool_manager = tool_manager
        
        if session is not None:
            self.session = session
        else:
            try:
                from app.db.session import SessionLocal
                self.session = SessionLocal()
            except Exception as e:
                logger.warning(f"⚠️ 无法创建数据库会话: {e}")
                self.session = None
        
        self.specialty = "notification"
        
        self.match_weights = {
            "industry": 0.3,
            "region": 0.2,
            "scale": 0.2,
            "tax_type": 0.3
        }
        
        self.notification_channels = ["in_app", "email", "wechat"]
        
        self.notification_templates = self._load_notification_templates()
        
        # 只在首次初始化时打印详细信息
        if not getattr(NotificationAgent, '_initialized', False):
            NotificationAgent._initialized = True
            print("🤖 [Notification Agent] 初始化完成")
            print(f"   - 职责: 企业匹配、个性化推送、追踪确认")
            print(f"   - 匹配权重: {self.match_weights}")
            print(f"   - 通知渠道: {len(self.notification_channels)} 个")
    
    def _load_notification_templates(self) -> Dict[str, str]:
        """加载通知模板"""
        return {
            "high_impact": """
📢 【重要政策提醒】

政策标题: {policy_title}
影响级别: 🔴 高

📋 政策要点:
{key_points}

💡 建议措施:
- 立即组织相关人员学习
- 评估对现有业务的影响
- 制定应对方案

📖 查看详情: {action_url}
            """,
            "medium_impact": """
📢 【政策更新通知】

政策标题: {policy_title}
影响级别: 🟡 中

📋 政策要点:
{key_points}

💡 建议措施:
- 了解政策变化内容
- 评估适用性

📖 查看详情: {action_url}
            """,
            "low_impact": """
📢 【政策动态】

政策标题: {policy_title}
影响级别: 🟢 低

📋 政策要点:
{key_points}

📖 查看详情: {action_url}
            """
        }
    
    async def match_enterprise(
        self,
        policy: Policy,
        enterprise_profile: EnterpriseProfile
    ) -> tuple[MatchScore, List[MatchReason]]:
        """
        匹配企业与政策
        
        Args:
            policy: 政策
            enterprise_profile: 企业画像
            
        Returns:
            匹配评分和匹配原因
        """
        logger.info(f"匹配企业与政策: {policy.policy_id} <-> {enterprise_profile.enterprise_id}")
        
        industry_score, industry_reasons = self._calculate_industry_score(
            policy.industries or [],
            enterprise_profile.industries
        )
        
        region_score, region_reasons = self._calculate_region_score(
            policy.regions or [],
            enterprise_profile.regions
        )
        
        scale_score, scale_reasons = self._calculate_scale_score(
            policy.scales or [],
            enterprise_profile.scales
        )
        
        tax_type_score, tax_reasons = self._calculate_tax_type_score(
            policy.tax_types or [],
            enterprise_profile.tax_types
        )
        
        total_score = (
            industry_score * self.match_weights["industry"] +
            region_score * self.match_weights["region"] +
            scale_score * self.match_weights["scale"] +
            tax_type_score * self.match_weights["tax_type"]
        )
        
        score = MatchScore(
            total_score=total_score,
            industry_score=industry_score,
            region_score=region_score,
            scale_score=scale_score,
            tax_type_score=tax_type_score
        )
        
        reasons = [
            MatchReason(category="行业", reason="行业匹配度", matched_items=industry_reasons),
            MatchReason(category="地区", reason="地区匹配度", matched_items=region_reasons),
            MatchReason(category="规模", reason="规模匹配度", matched_items=scale_reasons),
            MatchReason(category="税种", reason="税种匹配度", matched_items=tax_reasons)
        ]
        
        return score, reasons
    
    def _calculate_industry_score(
        self,
        policy_industries: List[str],
        enterprise_industries: List[str]
    ) -> tuple[float, List[str]]:
        """计算行业匹配分"""
        if not policy_industries or not enterprise_industries:
            return 0.0, []
        
        matched = set(policy_industries) & set(enterprise_industries)
        score = len(matched) / max(len(policy_industries), 1)
        
        return score, list(matched)
    
    def _calculate_region_score(
        self,
        policy_regions: List[str],
        enterprise_regions: List[str]
    ) -> tuple[float, List[str]]:
        """计算地区匹配分"""
        if not policy_regions or not enterprise_regions:
            return 0.0, []
        
        matched = set(policy_regions) & set(enterprise_regions)
        
        if "全国" in policy_regions or "全国范围内" in policy_regions:
            return 1.0, ["全国适用"]
        
        score = len(matched) / max(len(policy_regions), 1)
        
        return score, list(matched)
    
    def _calculate_scale_score(
        self,
        policy_scales: List[str],
        enterprise_scales: List[str]
    ) -> tuple[float, List[str]]:
        """计算规模匹配分"""
        if not policy_scales or not enterprise_scales:
            return 0.0, []
        
        matched = set(policy_scales) & set(enterprise_scales)
        score = len(matched) / max(len(policy_scales), 1)
        
        return score, list(matched)
    
    def _calculate_tax_type_score(
        self,
        policy_tax_types: List[str],
        enterprise_tax_types: List[str]
    ) -> tuple[float, List[str]]:
        """计算税种匹配分"""
        if not policy_tax_types or not enterprise_tax_types:
            return 0.0, []
        
        matched = set(policy_tax_types) & set(enterprise_tax_types)
        score = len(matched) / max(len(policy_tax_types), 1)
        
        return score, list(matched)
    
    async def save_match(
        self,
        enterprise_id: str,
        policy_id: UUID,
        score: MatchScore,
        reasons: List[MatchReason]
    ) -> UUID:
        """
        保存匹配记录
        
        Args:
            enterprise_id: 企业ID
            policy_id: 政策ID
            score: 匹配评分
            reasons: 匹配原因
            
        Returns:
            匹配记录ID
        """
        logger.info(f"保存匹配记录: {enterprise_id} <-> {policy_id}")
        
        match = EnterprisePolicyMatch(
            enterprise_id=enterprise_id,
            policy_id=policy_id,
            match_score=score.total_score,
            match_reasons=[
                {"category": r.category, "reason": r.reason, "items": r.matched_items}
                for r in reasons
            ],
            notification_status=NotificationStatus.PENDING,
            match_status=MatchStatus.ACTIVE
        )
        
        self.session.add(match)
        self.session.commit()
        self.session.refresh(match)
        
        return match.id
    
    async def generate_notification(
        self,
        policy: Policy,
        score: MatchScore,
        enterprise_profile: EnterpriseProfile
    ) -> NotificationMessage:
        """
        生成通知消息
        
        Args:
            policy: 政策
            score: 匹配评分
            enterprise_profile: 企业画像
            
        Returns:
            通知消息
        """
        logger.info(f"生成通知消息: {policy.policy_id}")
        
        meta_info = policy.meta_info or {}
        impact_level = meta_info.get("impact_level", "medium")
        
        if impact_level == "high":
            template = self.notification_templates["high_impact"]
        elif impact_level == "medium":
            template = self.notification_templates["medium_impact"]
        else:
            template = self.notification_templates["low_impact"]
        
        key_points = policy.tags[:3] if policy.tags else []
        key_points_text = "\n".join([f"- {point}" for point in key_points])
        
        title = f"【政策提醒】{policy.title[:50]}"
        
        content = template.format(
            policy_title=policy.title,
            key_points=key_points_text,
            action_url=f"/policies/{policy.policy_id}"
        )
        
        return NotificationMessage(
            title=title,
            content=content,
            policy_id=policy.policy_id,
            policy_title=policy.title,
            impact_level=impact_level,
            key_points=key_points,
            action_url=f"/policies/{policy.policy_id}"
        )
    
    async def send_notification(
        self,
        match: EnterprisePolicyMatch,
        notification: NotificationMessage
    ) -> NotificationResult:
        """
        发送通知
        
        Args:
            match: 匹配记录
            notification: 通知消息
            
        Returns:
            通知结果
        """
        logger.info(f"发送通知: {match.id}")
        
        try:
            match.notification_status = NotificationStatus.SENT
            match.notified_at = datetime.now()
            self.session.commit()
            
            return NotificationResult(
                success=True,
                notification_status=NotificationStatus.SENT,
                message="通知发送成功",
                sent_at=datetime.now()
            )
        
        except (ValueError, KeyError) as e:
            logger.error(f"发送通知数据失败: {e}")
        except (OSError, IOError) as e:
            logger.error(f"发送通知IO失败: {e}")
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            
            match.notification_status = NotificationStatus.FAILED
            self.session.commit()
            
            return NotificationResult(
                success=False,
                notification_status=NotificationStatus.FAILED,
                message="通知发送失败",
                failure_reason=str(e)
            )
    
    async def acknowledge_notification(
        self,
        match_id: UUID,
        feedback: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        确认通知
        
        Args:
            match_id: 匹配记录ID
            feedback: 用户反馈
            
        Returns:
            是否成功
        """
        logger.info(f"确认通知: {match_id}")
        
        stmt = select(EnterprisePolicyMatch).where(
            EnterprisePolicyMatch.id == match_id
        )
        match = self.session.execute(stmt).scalar_one_or_none()
        
        if not match:
            return False
        
        match.notification_status = NotificationStatus.ACKNOWLEDGED
        match.acknowledged_at = datetime.now()
        
        if feedback:
            match.feedback = feedback
        
        self.session.commit()
        
        return True
    
    async def dismiss_notification(
        self,
        match_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """
        忽略通知
        
        Args:
            match_id: 匹配记录ID
            reason: 忽略原因
            
        Returns:
            是否成功
        """
        logger.info(f"忽略通知: {match_id}")
        
        stmt = select(EnterprisePolicyMatch).where(
            EnterprisePolicyMatch.id == match_id
        )
        match = self.session.execute(stmt).scalar_one_or_none()
        
        if not match:
            return False
        
        match.notification_status = NotificationStatus.DISMISSED
        match.dismissed_at = datetime.now()
        
        if reason:
            match.feedback = {"dismiss_reason": reason}
        
        self.session.commit()
        
        return True
    
    async def get_pending_notifications(
        self,
        enterprise_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取待处理通知
        
        Args:
            enterprise_id: 企业ID
            limit: 返回数量
            
        Returns:
            待处理通知列表
        """
        logger.info(f"获取待处理通知: {enterprise_id}")
        
        stmt = select(
            EnterprisePolicyMatch, Policy
        ).join(
            Policy, EnterprisePolicyMatch.policy_id == Policy.id
        ).where(
            and_(
                EnterprisePolicyMatch.enterprise_id == enterprise_id,
                EnterprisePolicyMatch.notification_status == NotificationStatus.PENDING,
                EnterprisePolicyMatch.match_status == MatchStatus.ACTIVE
            )
        ).order_by(
            Policy.priority.desc(),
            Policy.created_at.desc()
        ).limit(limit)
        
        results = self.session.execute(stmt).all()
        
        notifications = []
        for match, policy in results:
            notifications.append({
                "match_id": str(match.id),
                "policy_id": policy.policy_id,
                "title": policy.title,
                "summary": policy.summary,
                "match_score": match.match_score,
                "match_reasons": match.match_reasons,
                "created_at": match.created_at.isoformat()
            })
        
        return notifications
    
    async def batch_notify(
        self,
        policy_id: UUID,
        min_score: float = 0.5,
        max_notifications: int = 100
    ) -> int:
        """
        批量通知
        
        Args:
            policy_id: 政策ID
            min_score: 最小匹配分数
            max_notifications: 最大通知数量
            
        Returns:
            发送的通知数量
        """
        logger.info(f"批量通知: {policy_id}, 最低分数: {min_score}")
        
        stmt = select(EnterprisePolicyMatch).where(
            and_(
                EnterprisePolicyMatch.policy_id == policy_id,
                EnterprisePolicyMatch.match_score >= min_score,
                EnterprisePolicyMatch.notification_status == NotificationStatus.PENDING,
                EnterprisePolicyMatch.match_status == MatchStatus.ACTIVE
            )
        ).order_by(
            EnterprisePolicyMatch.match_score.desc()
        ).limit(max_notifications)
        
        matches = self.session.execute(stmt).scalars().all()
        
        policy_stmt = select(Policy).where(Policy.id == policy_id)
        policy = self.session.execute(policy_stmt).scalar_one_or_none()
        
        if not policy:
            return 0
        
        sent_count = 0
        
        for match in matches:
            score = MatchScore(
                total_score=match.match_score,
                industry_score=0.5,
                region_score=0.5,
                scale_score=0.5,
                tax_type_score=0.5
            )
            
            notification = await self.generate_notification(
                policy,
                score,
                EnterpriseProfile(enterprise_id=match.enterprise_id, name="")
            )
            
            result = await self.send_notification(match, notification)
            
            if result.success:
                sent_count += 1
        
        return sent_count
