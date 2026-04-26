"""
控制层：人工审核触发器

职责：
- 当 RiskJudgeEngine 判定需要人工审核时，创建审核请求
- 复用现有的 ReviewRequest 表结构和 API

复用组件：
- ReviewRequest: app.models.review_request
- ReviewTrigger: app.multi_agent_system.human_review
- ReviewPriority: app.multi_agent_system.human_review
- human_review.py API: app.api.v1.endpoints.human_review
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.review_request import ReviewRequest
from app.multi_agent_system.human_review import (
    ReviewTrigger,
    ReviewPriority,
    ReviewStatus
)

logger = logging.getLogger(__name__)


@dataclass
class ReviewRequestCreate:
    """创建审核请求的数据类"""
    task_id: str
    tenant_id: str
    user_id: str
    trigger_reason: str
    review_type: str = "invoice"
    priority: str = "normal"
    trigger_details: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    document_ids: Optional[List[str]] = None


class HumanReviewTrigger:
    """
    人工审核触发器
    
    当控制层 RiskJudgeEngine 判定需要人工审核时，调用此类创建审核请求
    """
    
    SLA_HOURS = {
        "low": 72,
        "normal": 48,
        "high": 24,
        "urgent": 4
    }
    
    def __init__(self, db: AsyncSession):
        """
        初始化审核触发器
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def create_review_request(
        self,
        report_id: str,
        extraction_data: Dict[str, Any],
        risk_decision: Dict[str, Any],
        tenant_id: str,
        user_id: str
    ) -> Optional[str]:
        """
        创建人工审核请求
        
        Args:
            report_id: 税务报告ID
            extraction_data: 认知层提取的数据
            risk_decision: 控制层风险决策
            tenant_id: 租户ID
            user_id: 用户ID
            
        Returns:
            审核请求ID，如果创建失败返回 None
        """
        logger.info(f"📋 [控制层] 创建人工审核请求...")
        logger.info(f"   - 报告ID: {report_id}")
        logger.info(f"   - 风险等级: {risk_decision.get('risk_level')}")
        logger.info(f"   - 决策: {risk_decision.get('decision')}")
        
        try:
            review_id = str(uuid.uuid4())
            
            priority = self._map_risk_level_to_priority(
                risk_decision.get("risk_level", "medium")
            )
            
            sla_deadline = self._calculate_sla_deadline(priority)
            
            trigger_reason = self._determine_trigger_reason(risk_decision)
            
            review_request = ReviewRequest(
                id=review_id,
                task_id=report_id,
                tenant_id=tenant_id,
                user_id=user_id,
                review_type="tax",
                priority=priority,
                trigger_reason=trigger_reason,
                trigger_details={
                    "risk_level": risk_decision.get("risk_level"),
                    "trigger_rules": risk_decision.get("trigger_rules", []),
                    "trigger_reasons": risk_decision.get("trigger_reasons", []),
                    "confidence": extraction_data.get("confidence"),
                    "amount": extraction_data.get("amount"),
                    "tax_amount": extraction_data.get("tax_amount"),
                    "tax_rate": extraction_data.get("tax_rate"),
                    "invoice_number": extraction_data.get("invoice_number"),
                    "invoice_date": extraction_data.get("invoice_date"),
                    "invoice_type": extraction_data.get("invoice_type"),
                    "seller": extraction_data.get("seller_name"),
                    "buyer": extraction_data.get("buyer_name"),
                    "semantic_suspicion": extraction_data.get("semantic_suspicion", [])
                },
                title=f"税务发票审核 - {extraction_data.get('invoice_number', '未知')}",
                description=self._build_description(extraction_data, risk_decision),
                content={
                    "extraction": extraction_data,
                    "risk_decision": risk_decision,
                    "invoice_info": {
                        "amount": extraction_data.get("amount"),
                        "tax_amount": extraction_data.get("tax_amount"),
                        "tax_rate": extraction_data.get("tax_rate"),
                        "invoice_number": extraction_data.get("invoice_number"),
                        "invoice_date": extraction_data.get("invoice_date"),
                        "invoice_type": extraction_data.get("invoice_type"),
                        "seller_name": extraction_data.get("seller_name"),
                        "buyer_name": extraction_data.get("buyer_name")
                    }
                },
                document_ids=[report_id],
                status="pending",
                sla_deadline=sla_deadline
            )
            
            self.db.add(review_request)
            await self.db.commit()
            
            logger.info(f"✅ [控制层] 审核请求创建成功: {review_id}")
            logger.info(f"   - SLA截止时间: {sla_deadline}")
            logger.info(f"   - 优先级: {priority}")
            
            await self._update_report_review_status(report_id, review_id, tenant_id)
            
            return review_id
            
        except Exception as e:
            logger.error(f"❌ [控制层] 创建审核请求失败: {e}")
            await self.db.rollback()
            return None
    
    async def _update_report_review_status(
        self,
        report_id: str,
        review_request_id: str,
        tenant_id: str
    ):
        """更新税务报告的审核状态"""
        try:
            from app.models.tax_report import TaxReport
            from sqlalchemy import update
            
            await self.db.execute(
                update(TaxReport)
                .where(TaxReport.id == report_id)
                .where(TaxReport.tenant_id == tenant_id)
                .values(
                    status="pending_review",
                    needs_human_review="true",
                    review_request_id=review_request_id,
                    updated_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            
            logger.info(f"✅ [控制层] 税务报告状态已更新为 pending_review")
            
        except Exception as e:
            logger.warning(f"⚠️ [控制层] 更新报告状态失败: {e}")
            await self.db.rollback()
    
    def _map_risk_level_to_priority(self, risk_level: str) -> str:
        """将风险等级映射为优先级"""
        mapping = {
            "critical": "urgent",
            "high": "high",
            "medium": "normal",
            "low": "low"
        }
        return mapping.get(risk_level.lower(), "normal")
    
    def _calculate_sla_deadline(self, priority: str) -> datetime:
        """计算 SLA 截止时间"""
        hours = self.SLA_HOURS.get(priority, 48)
        return datetime.utcnow() + timedelta(hours=hours)
    
    def _determine_trigger_reason(self, risk_decision: Dict[str, Any]) -> str:
        """确定触发审核的原因"""
        trigger_rules = risk_decision.get("trigger_rules", [])
        
        rule_reason_map = {
            "RULE_CONFIDENCE_THRESHOLD": "low_confidence",
            "RULE_HIGH_AMOUNT": "high_amount_detected",
            "RULE_MISSING_FIELDS": "missing_mandatory_fields",
            "RULE_MEDIUM_AMOUNT": "medium_amount_flag",
            "RULE_LOW_CONFIDENCE": "confidence_below_normal",
            "RULE_SEMANTIC_SUSPICION": "semantic_anomaly_detected"
        }
        
        for rule in trigger_rules:
            if rule in rule_reason_map:
                return rule_reason_map[rule]
        
        return "risk_assessment_flagged"
    
    def _build_description(
        self,
        extraction_data: Dict[str, Any],
        risk_decision: Dict[str, Any]
    ) -> str:
        """构建审核描述"""
        amount = extraction_data.get("amount", 0)
        invoice_number = extraction_data.get("invoice_number", "未知")
        confidence = extraction_data.get("confidence", 0)
        
        parts = [
            f"发票号码: {invoice_number}",
            f"发票金额: ¥{amount:,.2f}" if amount else "发票金额: 未提取",
            f"AI置信度: {confidence:.2%}",
            f"风险等级: {risk_decision.get('risk_level', 'unknown').upper()}",
            "",
            "触发规则:"
        ]
        
        for reason in risk_decision.get("trigger_reasons", []):
            parts.append(f"- {reason}")
        
        if extraction_data.get("semantic_suspicion"):
            parts.append("")
            parts.append("语义可疑点:")
            for suspicion in extraction_data["semantic_suspicion"]:
                parts.append(f"- {suspicion}")
        
        return "\n".join(parts)
    
    async def get_pending_reviews(
        self,
        tenant_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取待审核列表
        
        Args:
            tenant_id: 租户ID
            status: 状态过滤（可选）
            
        Returns:
            审核请求列表
        """
        try:
            query = select(ReviewRequest).where(
                ReviewRequest.tenant_id == tenant_id
            )
            
            if status:
                query = query.where(ReviewRequest.status == status)
            
            query = query.order_by(ReviewRequest.created_at.desc())
            
            result = await self.db.execute(query)
            reviews = result.scalars().all()
            
            return [
                {
                    "id": str(review.id),
                    "task_id": str(review.task_id),
                    "title": review.title,
                    "description": review.description,
                    "priority": review.priority,
                    "status": review.status,
                    "trigger_reason": review.trigger_reason,
                    "created_at": review.created_at.isoformat() if review.created_at else None,
                    "sla_deadline": review.sla_deadline.isoformat() if review.sla_deadline else None,
                    "is_overdue": review.is_overdue,
                    "age_hours": review.age_hours
                }
                for review in reviews
            ]
            
        except Exception as e:
            logger.error(f"❌ [控制层] 获取待审核列表失败: {e}")
            return []
    
    async def approve_review(
        self,
        review_id: str,
        reviewer_id: str,
        comments: Optional[str] = None
    ) -> bool:
        """
        批准审核请求
        
        Args:
            review_id: 审核请求ID
            reviewer_id: 审核人ID
            comments: 审核意见
            
        Returns:
            是否成功
        """
        logger.info(f"✅ [控制层] 批准审核请求: {review_id}")
        
        try:
            await self.db.execute(
                update(ReviewRequest)
                .where(ReviewRequest.id == review_id)
                .values(
                    status="approved",
                    review_result={"decision": "approved", "comments": comments},
                    review_comments=comments,
                    reviewed_at=datetime.utcnow(),
                    reviewed_by=reviewer_id
                )
            )
            await self.db.commit()
            
            result = await self.db.execute(
                select(ReviewRequest).where(ReviewRequest.id == review_id)
            )
            review = result.scalar_one_or_none()
            
            if review and review.task_id:
                from app.models.tax_report import TaxReport
                await self.db.execute(
                    update(TaxReport)
                    .where(TaxReport.id == review.task_id)
                    .values(
                        status="completed",
                        updated_at=datetime.utcnow()
                    )
                )
                await self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [控制层] 批准审核失败: {e}")
            await self.db.rollback()
            return False
    
    async def reject_review(
        self,
        review_id: str,
        reviewer_id: str,
        reason: str
    ) -> bool:
        """
        拒绝审核请求
        
        Args:
            review_id: 审核请求ID
            reviewer_id: 审核人ID
            reason: 拒绝原因
            
        Returns:
            是否成功
        """
        logger.info(f"❌ [控制层] 拒绝审核请求: {review_id}")
        
        try:
            await self.db.execute(
                update(ReviewRequest)
                .where(ReviewRequest.id == review_id)
                .values(
                    status="rejected",
                    review_result={"decision": "rejected", "reason": reason},
                    review_comments=reason,
                    reviewed_at=datetime.utcnow(),
                    reviewed_by=reviewer_id
                )
            )
            await self.db.commit()
            
            result = await self.db.execute(
                select(ReviewRequest).where(ReviewRequest.id == review_id)
            )
            review = result.scalar_one_or_none()
            
            if review and review.task_id:
                from app.models.tax_report import TaxReport
                await self.db.execute(
                    update(TaxReport)
                    .where(TaxReport.id == review.task_id)
                    .values(
                        status="failed",
                        processing_message=f"审核拒绝: {reason}",
                        updated_at=datetime.utcnow()
                    )
                )
                await self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [控制层] 拒绝审核失败: {e}")
            await self.db.rollback()
            return False