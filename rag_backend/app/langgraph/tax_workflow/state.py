"""
税务提交工作流状态定义

定义税务提交流程的完整状态结构，包括验证、财务数据、税务计算、风险评估等
"""

from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class SubmissionStatus(str, Enum):
    """提交状态"""
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    FETCHING_FINANCIAL_DATA = "fetching_financial_data"
    FINANCIAL_DATA_FETCHED = "financial_data_fetched"
    CALCULATING_TAXES = "calculating_taxes"
    TAXES_CALCULATED = "taxes_calculated"
    ASSESSING_RISK = "assessing_risk"
    RISK_ASSESSED = "risk_assessed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    HUMAN_REVIEW_APPROVED = "human_review_approved"
    HUMAN_REVIEW_REJECTED = "human_review_rejected"
    SAVING = "saving"
    SAVED = "saved"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationLevel(str, Enum):
    """验证级别"""
    STRICT = "strict"
    NORMAL = "normal"
    LENIENT = "lenient"


class ValidationResult(BaseModel):
    """验证结果"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validation_level: ValidationLevel = ValidationLevel.NORMAL
    validated_fields: List[str] = Field(default_factory=list)


class FinancialData(BaseModel):
    """财务数据"""
    total_revenue: float = 0.0
    taxable_sales: float = 0.0
    total_expenses: float = 0.0
    input_tax: float = 0.0
    output_tax: float = 0.0
    taxable_income: float = 0.0
    data_status: str = "complete"


class TaxCalculationItem(BaseModel):
    """税务计算项"""
    tax_type: str
    taxable_amount: float
    tax_rate: float
    calculated_tax: float
    effective_rate: float
    input_tax: float = 0.0
    output_tax: float = 0.0
    net_tax_payable: float = 0.0
    calculation_details: Dict[str, Any] = Field(default_factory=dict)


class RiskItem(BaseModel):
    """风险项"""
    risk_id: str
    risk_type: str
    severity: str
    description: str
    legal_basis: List[str] = Field(default_factory=list)
    potential_penalty: str = ""
    remediation_suggestions: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class PolicyBenefit(BaseModel):
    """政策优惠"""
    policy_id: str
    policy_title: str
    match_level: str = "partial"
    applicability: float = 0.0
    potential_savings: float = 0.0
    conditions: List[str] = Field(default_factory=list)


class HumanReviewRequest(BaseModel):
    """人工审核请求"""
    review_id: str
    reason: str
    requested_at: datetime
    requested_by: str
    status: str = "pending"
    reviewed_at: Optional[datetime] = None
    reviewer_comments: Optional[str] = None


class TaxSubmissionState(TypedDict):
    """
    税务提交工作流状态
    
    完整的状态定义，包含税务提交流程的所有阶段数据
    """
    # 基础信息
    session_id: str
    tenant_id: str
    user_id: str
    analysis_id: str
    fiscal_year: int
    fiscal_period: Optional[str]
    tax_types: List[str]
    
    # 分析配置
    include_policy_benefits: bool
    include_risk_assessment: bool
    validation_level: ValidationLevel
    
    # 当前状态
    current_status: SubmissionStatus
    current_step: int
    total_steps: int
    
    # 验证阶段
    validation_result: Optional[ValidationResult]
    
    # 财务数据
    financial_data: Optional[FinancialData]
    
    # 税务计算
    tax_calculations: List[TaxCalculationItem]
    total_tax_burden: float
    tax_burden_rate: float
    
    # 风险评估
    risk_items: List[RiskItem]
    overall_risk_score: float
    high_risk_count: int
    
    # 政策优惠
    policy_benefits: List[PolicyBenefit]
    total_potential_savings: float
    
    # 人工审核
    human_review_request: Optional[HumanReviewRequest]
    
    # 最终结果
    final_summary: Optional[str]
    approved: bool
    approval_comments: Optional[str]
    
    # 错误和追踪
    errors: List[str]
    warnings: List[str]
    trace_id: Optional[str]
    
    # 元数据
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


def create_initial_submission_state(
    session_id: str,
    tenant_id: str,
    user_id: str,
    fiscal_year: int,
    fiscal_period: Optional[str],
    tax_types: List[str],
    include_policy_benefits: bool = True,
    include_risk_assessment: bool = True
) -> TaxSubmissionState:
    """
    创建初始税务提交状态
    
    Args:
        session_id: 会话ID
        tenant_id: 租户ID
        user_id: 用户ID
        fiscal_year: 财政年度
        fiscal_period: 财政期间（季度/月份）
        tax_types: 税种列表
        include_policy_benefits: 是否包含政策优惠匹配
        include_risk_assessment: 是否包含风险评估
    
    Returns:
        TaxSubmissionState: 初始状态
    """
    from datetime import datetime as dt
    
    return TaxSubmissionState(
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        analysis_id=f"tax_submission_{session_id}",
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        tax_types=tax_types,
        include_policy_benefits=include_policy_benefits,
        include_risk_assessment=include_risk_assessment,
        validation_level=ValidationLevel.NORMAL,
        current_status=SubmissionStatus.PENDING,
        current_step=0,
        total_steps=6,
        validation_result=None,
        financial_data=None,
        tax_calculations=[],
        total_tax_burden=0.0,
        tax_burden_rate=0.0,
        risk_items=[],
        overall_risk_score=0.0,
        high_risk_count=0,
        policy_benefits=[],
        total_potential_savings=0.0,
        human_review_request=None,
        final_summary=None,
        approved=True,
        approval_comments=None,
        errors=[],
        warnings=[],
        trace_id=None,
        created_at=dt.now(),
        updated_at=dt.now(),
        completed_at=None
    )


def update_submission_status(
    state: TaxSubmissionState,
    status: SubmissionStatus,
    step: Optional[int] = None
) -> TaxSubmissionState:
    """
    更新提交状态
    
    Args:
        state: 当前状态
        status: 新状态
        step: 当前步骤
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    from datetime import datetime as dt
    
    state["current_status"] = status
    state["updated_at"] = dt.now()
    
    if step is not None:
        state["current_step"] = step
    
    return state


def add_validation_error(state: TaxSubmissionState, error: str) -> TaxSubmissionState:
    """添加验证错误"""
    if state.get("validation_result"):
        state["validation_result"].errors.append(error)
    state["errors"].append(error)
    return state


def add_risk_item(state: TaxSubmissionState, risk: RiskItem) -> TaxSubmissionState:
    """添加风险项"""
    state["risk_items"].append(risk)
    state["overall_risk_score"] = calculate_risk_score(state["risk_items"])
    if risk.severity == "high":
        state["high_risk_count"] += 1
    return state


def calculate_risk_score(risk_items: List[RiskItem]) -> float:
    """计算总体风险评分"""
    if not risk_items:
        return 0.0
    
    weights = {"high": 1.0, "medium": 0.5, "low": 0.2}
    total_weight = sum(weights.get(r.severity, 0.3) for r in risk_items)
    return min(total_weight / len(risk_items), 1.0)
