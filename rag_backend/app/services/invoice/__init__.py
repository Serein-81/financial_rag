"""
发票智能分析服务模块

四层架构：
- 认知层 (Cognition): TaxSpecialist 独立唤醒，提取发票事实
- 控制层 (Control): 硬性规则审判 + 人工审核触发
- 交易层 (Transaction): 纯计算引擎（无 AI）

复用组件：
- TaxSpecialist: app.multi_agent_system.agents.tax_specialist
- ReviewRequest: app.models.review_request
- human_review.py: app.api.v1.endpoints.human_review
"""

from .cognition_service import InvoiceCognitionService, InvoiceLLMExtraction
from .risk_judge_engine import RiskJudgeEngine, RiskDecision, TenantRiskConfig
from .human_review_trigger import HumanReviewTrigger, ReviewRequestCreate
from .calculation_engine import TaxCalculationEngine, VATResult, IncomeTaxResult, TaxSubmission

__all__ = [
    # 认知层
    "InvoiceCognitionService",
    "InvoiceLLMExtraction",
    
    # 控制层 - 风险审判
    "RiskJudgeEngine",
    "RiskDecision",
    "TenantRiskConfig",
    
    # 控制层 - 人工审核
    "HumanReviewTrigger",
    "ReviewRequestCreate",
    
    # 交易层
    "TaxCalculationEngine",
    "VATResult",
    "IncomeTaxResult",
    "TaxSubmission",
]