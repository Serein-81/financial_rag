"""
控制层：硬性规则审判引擎

职责：
- 接收认知层（大模型）提取的干净数据
- 执行纯粹的 Python 硬性规则判断
- 绝对不依赖大模型进行数字比较和阈值判定

架构原则：
- 大模型是数学白痴，缺乏对企业硬性边界的绝对控制力
- 硬性规则必须由 Python 代码执行，100% 确定性

复用组件：
- InvoiceLLMExtraction: app.services.invoice.cognition_service
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

from app.services.invoice.cognition_service import InvoiceLLMExtraction

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskDecision(BaseModel):
    """风险决策结果"""
    risk_level: RiskLevel = Field(..., description="风险等级")
    decision: str = Field(..., description="决策类型: auto_approved / pending_review")
    trigger_rules: List[str] = Field(default_factory=list, description="触发的规则列表")
    trigger_reasons: List[str] = Field(default_factory=list, description="触发原因描述")
    requires_human_review: bool = Field(..., description="是否需要人工审核")
    auto_approve: bool = Field(..., description="是否自动通过")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "risk_level": "high",
                "decision": "pending_review",
                "trigger_rules": [
                    "RULE_CONFIDENCE_THRESHOLD",
                    "RULE_HIGH_AMOUNT_THRESHOLD"
                ],
                "trigger_reasons": [
                    "置信度 0.52 低于阈值 0.60",
                    "金额 1500000 超过高风险阈值 1000000"
                ],
                "requires_human_review": True,
                "auto_approve": False
            }
        }
    }


class TenantRiskConfig(BaseModel):
    """
    租户风险配置
    
    允许租户自定义风险阈值
    """
    min_confidence_threshold: float = Field(
        default=0.6,
        description="最小置信度阈值（低于此值触发高风险）",
        ge=0.0,
        le=1.0
    )
    high_amount_threshold: float = Field(
        default=1000000.0,
        description="高风险金额阈值（超过此值触发高风险）",
        ge=0.0
    )
    medium_amount_threshold: float = Field(
        default=100000.0,
        description="中等风险金额阈值（超过此值触发中风险）",
        ge=0.0
    )
    max_missing_fields: int = Field(
        default=3,
        description="最大允许缺失字段数（超过此值触发高风险）",
        ge=0
    )
    auto_approve_low_risk: bool = Field(
        default=True,
        description="低风险是否自动通过"
    )
    
    required_fields: List[str] = Field(
        default_factory=lambda: [
            "amount",
            "invoice_number",
            "invoice_date"
        ],
        description="必填字段列表"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "min_confidence_threshold": 0.6,
                "high_amount_threshold": 1000000.0,
                "medium_amount_threshold": 100000.0,
                "max_missing_fields": 3,
                "auto_approve_low_risk": True,
                "required_fields": ["amount", "invoice_number", "invoice_date"]
            }
        }
    }


class RiskRule:
    """风险规则定义"""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        condition: callable,
        risk_level: RiskLevel,
        message: str,
        priority: int = 0
    ):
        self.rule_id = rule_id
        self.name = name
        self.condition = condition
        self.risk_level = risk_level
        self.message = message
        self.priority = priority


class RiskJudgeEngine:
    """
    硬性规则审判引擎（控制层）
    
    职责：
    - 完全由 Python 代码执行硬性规则判断
    - 大模型绝不参与数字比较和阈值判定
    - 提供可配置的租户级阈值
    
    架构边界：
    ┌─────────────────────────────────────────┐
    │  认知层（TaxSpecialist / 大模型）         │
    │  - 提取事实（金额、税率、发票号）         │
    │  - 语义层面的可疑性（建议性）             │
    │  - 输出 confidence                      │
    │  ❌ 不输出 risk_level                   │
    │  ❌ 不做数字比较                         │
    └─────────────────────────────────────────┘
                      ↓ InvoiceLLMExtraction
    ┌─────────────────────────────────────────┐
    │  控制层（RiskJudgeEngine / Python）       │
    │  - 硬性规则审判                         │
    │  - 数字比较和阈值判定                    │
    │  - 输出 risk_level                      │
    │  ✅ 纯粹的 if-else，100% 确定性         │
    └─────────────────────────────────────────┘
    """
    
    DEFAULT_RULES = [
        RiskRule(
            rule_id="RULE_CONFIDENCE_THRESHOLD",
            name="置信度阈值规则",
            condition=lambda e, c: e.confidence < c.min_confidence_threshold,
            risk_level=RiskLevel.HIGH,
            message="大模型提取置信度过低，无法保证准确性",
            priority=100
        ),
        RiskRule(
            rule_id="RULE_HIGH_AMOUNT",
            name="高金额风险规则",
            condition=lambda e, c: (e.amount is not None and 
                                   e.amount > c.high_amount_threshold),
            risk_level=RiskLevel.HIGH,
            message="发票金额超过高风险阈值，需人工审核",
            priority=90
        ),
        RiskRule(
            rule_id="RULE_MISSING_FIELDS",
            name="缺失字段风险规则",
            condition=lambda e, c: len(e.get_missing_fields(c.required_fields)) >= c.max_missing_fields,
            risk_level=RiskLevel.HIGH,
            message="缺少多个必填字段，信息不完整",
            priority=80
        ),
        RiskRule(
            rule_id="RULE_MEDIUM_AMOUNT",
            name="中等金额风险规则",
            condition=lambda e, c: (e.amount is not None and 
                                   e.amount > c.medium_amount_threshold and
                                   e.amount <= c.high_amount_threshold),
            risk_level=RiskLevel.MEDIUM,
            message="发票金额超过中等阈值，建议关注",
            priority=50
        ),
        RiskRule(
            rule_id="RULE_LOW_CONFIDENCE",
            name="低置信度关注规则",
            condition=lambda e, c: (e.confidence < 0.8 and 
                                   e.confidence >= c.min_confidence_threshold),
            risk_level=RiskLevel.MEDIUM,
            message="大模型置信度低于正常水平，可能存在提取不准确",
            priority=40
        ),
        RiskRule(
            rule_id="RULE_SEMANTIC_SUSPICION",
            name="语义可疑性关注规则",
            condition=lambda e, c: len(e.semantic_suspicion) > 0,
            risk_level=RiskLevel.MEDIUM,
            message="大模型检测到语义层面的可疑点，建议人工关注",
            priority=30
        )
    ]
    
    def __init__(self, config: Optional[TenantRiskConfig] = None):
        """
        初始化风险审判引擎
        
        Args:
            config: 租户风险配置（可选，默认使用系统默认值）
        """
        self.config = config or TenantRiskConfig()
        self.rules = self.DEFAULT_RULES.copy()
        logger.info(f"✅ [控制层] RiskJudgeEngine 初始化完成")
        logger.info(f"   - 置信度阈值: {self.config.min_confidence_threshold}")
        logger.info(f"   - 高风险金额阈值: {self.config.high_amount_threshold:,.2f}")
        logger.info(f"   - 中等风险金额阈值: {self.config.medium_amount_threshold:,.2f}")
    
    def _validate_and_fix_amount(self, extraction: InvoiceLLMExtraction) -> InvoiceLLMExtraction:
        """
        验证和修正金额字段
        
        检测常见的金额提取错误：
        - 金额过小（如 2.53 而不是 75.47）
        - 金额异常（如使用发票号码代替金额）
        - 金额为 0 但有税率
        
        Returns:
            InvoiceLLMExtraction: 修正后的提取结果
        """
        try:
            amount = extraction.amount
            tax_amount = extraction.tax_amount
            tax_rate = extraction.tax_rate
            
            # 如果金额为 0，尝试从税额和税率计算
            if amount == 0 and tax_amount > 0 and tax_rate > 0:
                calculated_amount = round(tax_amount / tax_rate, 2)
                logger.info(f"[控制层] 💰 金额为0，尝试计算: {tax_amount} / {tax_rate} = {calculated_amount}")
                
                # 如果计算结果合理（大于10且小于10000000），使用计算结果
                if 10 <= calculated_amount <= 10000000:
                    extraction.amount = calculated_amount
                    extraction.semantic_suspicion.append(
                        f"💡 系统自动计算金额：{calculated_amount}（根据税额和税率）"
                    )
                    logger.info(f"[控制层] ✅ 金额已修正: {calculated_amount}")
            
            # 如果金额过小（< 10）但有税率，尝试使用税额计算
            elif amount and amount < 10 and tax_rate > 0:
                calculated_amount = round(amount / tax_rate, 2)
                
                # 如果计算结果在合理范围内（10-10000000），修正金额
                if 10 <= calculated_amount <= 10000000:
                    original_amount = amount
                    extraction.amount = calculated_amount
                    extraction.semantic_suspicion.append(
                        f"⚠️ 金额异常（{original_amount}），系统自动修正为：{calculated_amount}（根据税率计算）"
                    )
                    logger.warning(f"[控制层] ⚠️ 金额异常已修正: {original_amount} -> {calculated_amount}")
            
            # 如果金额和税额都存在，验证关系
            if amount > 0 and tax_amount > 0 and tax_rate > 0:
                expected_tax = round(amount * tax_rate, 2)
                if abs(expected_tax - tax_amount) < 0.1:
                    logger.info(f"[控制层] ✅ 金额关系验证通过: {amount} × {tax_rate} = {expected_tax} ≈ {tax_amount}")
                else:
                    logger.warning(f"[控制层] ⚠️ 金额关系不一致: {amount} × {tax_rate} = {expected_tax}，但提取到 {tax_amount}")
                    
                    # 修正错误的税额（使用计算值）
                    original_tax_amount = extraction.tax_amount
                    extraction.tax_amount = expected_tax
                    extraction.semantic_suspicion.append(
                        f"⚠️ 税额异常已修正：{original_tax_amount} -> {expected_tax}（根据金额和税率计算）"
                    )
                    logger.info(f"[控制层] ✅ 税额已修正: {original_tax_amount} -> {expected_tax}")
                    
                    # 修正后重新验证
                    if abs(amount * tax_rate - extraction.tax_amount) < 0.1:
                        logger.info(f"[控制层] ✅ 修正后金额关系验证通过")
                        # 修正成功后，提高置信度
                        if extraction.confidence < 0.5:
                            old_confidence = extraction.confidence
                            extraction.confidence = min(0.85, extraction.confidence + 0.30)
                            logger.info(f"[控制层] 📈 置信度提升: {old_confidence:.2f} -> {extraction.confidence:.2f}")
            
            return extraction
            
        except Exception as e:
            logger.warning(f"⚠️ [控制层] 金额验证失败: {e}")
            return extraction
    
    def judge(self, extraction: InvoiceLLMExtraction) -> RiskDecision:
        """
        执行风险等级判定
        
        Args:
            extraction: 大模型提取的发票信息
            
        Returns:
            RiskDecision: 风险决策结果
        """
        logger.info(f"⚖️ [控制层] 开始风险审判...")
        logger.info(f"   - 置信度: {extraction.confidence:.2f}")
        logger.info(f"   - 金额: {extraction.amount}")
        logger.info(f"   - 语义可疑点: {len(extraction.semantic_suspicion)} 个")
        
        # 金额验证和修正
        extraction = self._validate_and_fix_amount(extraction)
        
        triggered_rules = []
        max_risk_level = RiskLevel.LOW
        
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            try:
                if rule.condition(extraction, self.config):
                    triggered_rules.append({
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "message": rule.message,
                        "risk_level": rule.risk_level.value
                    })
                    
                    if self._risk_level_to_int(rule.risk_level) > self._risk_level_to_int(max_risk_level):
                        max_risk_level = rule.risk_level
                    
                    logger.info(f"   🔴 触发规则: {rule.rule_id} - {rule.name}")
                    logger.info(f"       风险等级: {rule.risk_level.value}")
                    logger.info(f"       原因: {rule.message}")
                    
            except Exception as e:
                logger.warning(f"⚠️ [控制层] 规则 {rule.rule_id} 执行失败: {e}")
        
        decision = self._determine_decision(max_risk_level)
        
        result = RiskDecision(
            risk_level=max_risk_level,
            decision=decision,
            trigger_rules=[r["rule_id"] for r in triggered_rules],
            trigger_reasons=[r["message"] for r in triggered_rules],
            requires_human_review=max_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.MEDIUM],
            auto_approve=max_risk_level == RiskLevel.LOW and self.config.auto_approve_low_risk
        )
        
        logger.info(f"✅ [控制层] 风险审判完成:")
        logger.info(f"   - 风险等级: {result.risk_level.value}")
        logger.info(f"   - 决策: {result.decision}")
        logger.info(f"   - 需要人工审核: {result.requires_human_review}")
        logger.info(f"   - 自动通过: {result.auto_approve}")
        
        return result
    
    def _risk_level_to_int(self, level: RiskLevel) -> int:
        """将风险等级转换为整数（用于比较）"""
        level_map = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }
        return level_map.get(level, 0)
    
    def _determine_decision(self, risk_level: RiskLevel) -> str:
        """根据风险等级确定决策"""
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return "pending_review"
        elif risk_level == RiskLevel.MEDIUM:
            return "pending_review"
        else:
            return "auto_approved"
    
    def update_config(self, config: TenantRiskConfig):
        """
        更新租户风险配置
        
        Args:
            config: 新的风险配置
        """
        self.config = config
        logger.info(f"✅ [控制层] 风险配置已更新")
        logger.info(f"   - 置信度阈值: {config.min_confidence_threshold}")
        logger.info(f"   - 高风险金额阈值: {config.high_amount_threshold:,.2f}")
    
    def add_rule(self, rule: RiskRule):
        """
        添加自定义风险规则
        
        Args:
            rule: 风险规则
        """
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"✅ [控制层] 添加风险规则: {rule.rule_id} - {rule.name}")
    
    def remove_rule(self, rule_id: str):
        """
        移除风险规则
        
        Args:
            rule_id: 规则ID
        """
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        logger.info(f"✅ [控制层] 移除风险规则: {rule_id}")


def quick_judge(
    extraction: InvoiceLLMExtraction,
    config: Optional[TenantRiskConfig] = None
) -> RiskDecision:
    """
    快速风险判断（便捷函数）
    
    适用于单次判断场景，无需手动创建 RiskJudgeEngine
    
    Args:
        extraction: 大模型提取结果
        config: 风险配置（可选）
        
    Returns:
        RiskDecision: 风险决策
    """
    engine = RiskJudgeEngine(config)
    return engine.judge(extraction)


from app.services.invoice.cognition_service import InvoiceLLMExtraction as _BaseExtraction

class InvoiceLLMExtraction(_BaseExtraction):
    """扩展认知层提取结果，添加控制层辅助方法"""
    
    def get_missing_fields(self, required_fields: List[str]) -> List[str]:
        """获取缺失的必填字段"""
        missing = []
        for field in required_fields:
            value = getattr(self, field, None)
            if value is None or value == "" or (isinstance(value, float) and value == 0.0):
                missing.append(field)
        return missing
    
    def get_extracted_fields_count(self, all_fields: List[str]) -> int:
        """获取已提取的字段数量"""
        count = 0
        for field in all_fields:
            value = getattr(self, field, None)
            if value is not None and value != "" and not (isinstance(value, float) and value == 0.0):
                if isinstance(value, list):
                    count += 1
                elif isinstance(value, str) and value.strip():
                    count += 1
                elif isinstance(value, (int, float)) and value != 0:
                    count += 1
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    def to_control_layer_format(self) -> Dict[str, Any]:
        """转换为控制层格式"""
        return {
            "amount": self.amount,
            "tax_amount": self.tax_amount,
            "tax_rate": self.tax_rate,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "invoice_type": self.invoice_type,
            "seller_name": self.seller_name,
            "seller_tax_id": self.seller_tax_id,
            "buyer_name": self.buyer_name,
            "buyer_tax_id": self.buyer_tax_id,
            "items_count": len(self.items) if self.items else 0,
            "semantic_suspicion_count": len(self.semantic_suspicion),
            "confidence": self.confidence
        }