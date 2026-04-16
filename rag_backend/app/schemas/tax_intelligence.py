"""
税务智能分析 Pydantic Schema 定义
用于税务合规智能助手 API
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class TaxAnalysisType(str, Enum):
    """税务分析类型"""
    QUARTERLY_VAT = "quarterly_vat"  # 季度增值税分析
    ANNUAL_INCOME = "annual_income"  # 年度所得税汇算
    TAX_BURDEN = "tax_burden"  # 税负分析
    POLICY_BENEFIT = "policy_benefit"  # 优惠政策享受分析
    RISK_ASSESSMENT = "risk_assessment"  # 税务风险评估
    COMPREHENSIVE = "comprehensive"  # 综合税务分析


class TaxPeriodType(str, Enum):
    """税务期间类型"""
    MONTHLY = "monthly"  # 月度
    QUARTERLY = "quarterly"  # 季度
    ANNUAL = "annual"  # 年度


class TaxIntelligenceStatus(str, Enum):
    """税务智能分析状态"""
    PENDING = "pending"  # 待处理
    ANALYZING = "analyzing"  # 分析中
    WAITING_REVIEW = "waiting_review"  # 等待审核
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class PolicyMatchLevel(str, Enum):
    """政策匹配级别"""
    FULL = "full"  # 完全匹配
    PARTIAL = "partial"  # 部分匹配
    POTENTIAL = "potential"  # 潜在适用


class TaxAnalysisRequest(BaseModel):
    """税务分析请求"""
    analysis_type: Optional[TaxAnalysisType] = Field(None, description="分析类型（可选，自动推断）")
    fiscal_year: int = Field(..., ge=2020, le=2100, description="财务年度")
    fiscal_quarter: Optional[int] = Field(None, ge=1, le=4, description="财务季度")
    fiscal_month: Optional[int] = Field(None, ge=1, le=12, description="财务月份")
    fiscal_period: Optional[str] = Field(None, description="财务期间（如Q4）")
    tax_types: Optional[List[str]] = Field(None, description="需要分析的税种")
    tax_type: Optional[str] = Field(None, description="税种类型（简写，接受中文）")
    company_name: Optional[str] = Field(None, description="公司名称")
    industry: Optional[str] = Field(None, description="行业")
    financial_data: Optional[Dict[str, Any]] = Field(None, description="财务数据")
    include_policy_benefits: bool = Field(True, description="是否包含优惠政策分析")
    include_risk_assessment: bool = Field(True, description="是否包含风险评估")
    user_id: Optional[str] = Field(None, description="用户ID（可选，自动填充）")
    tenant_id: Optional[str] = Field(None, description="租户ID（可选，自动填充）")

    @model_validator(mode='before')
    @classmethod
    def convert_simple_format(cls, data):
        if isinstance(data, dict):
            if data.get('tax_type') and not data.get('analysis_type'):
                tax_type = data.get('tax_type', '')
                if '企业所得' in tax_type:
                    data['analysis_type'] = 'annual_income'
                    data['tax_types'] = ['income_tax']
                elif '增值' in tax_type:
                    data['analysis_type'] = 'quarterly_vat'
                    data['tax_types'] = ['vat']
                elif '个人所得' in tax_type:
                    data['analysis_type'] = 'risk_assessment'
                    data['tax_types'] = ['personal_income_tax']
                elif '消费' in tax_type:
                    data['analysis_type'] = 'tax_burden'
                    data['tax_types'] = ['consumption_tax']
                elif '全税种' in tax_type:
                    data['analysis_type'] = 'comprehensive'
                    data['tax_types'] = ['vat', 'income_tax', 'consumption_tax']
                else:
                    data['analysis_type'] = 'comprehensive'
                    data['tax_types'] = ['vat', 'income_tax']

                if data.get('fiscal_period'):
                    period = str(data['fiscal_period']).upper()
                    if period in ['Q1', '1']:
                        data['fiscal_quarter'] = 1
                    elif period in ['Q2', '2']:
                        data['fiscal_quarter'] = 2
                    elif period in ['Q3', '3']:
                        data['fiscal_quarter'] = 3
                    elif period in ['Q4', '4']:
                        data['fiscal_quarter'] = 4
        return data

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_type": "quarterly_vat",
                "fiscal_year": 2024,
                "fiscal_quarter": 1,
                "tax_types": ["vat", "income_tax"],
                "include_policy_benefits": True,
                "include_risk_assessment": True,
                "user_id": "user-123",
                "tenant_id": "tenant-456"
            }
        }


class TaxCalculationResult(BaseModel):
    """税务计算结果"""
    tax_type: str = Field(..., description="税种")
    taxable_amount: float = Field(..., description="应税金额")
    tax_rate: float = Field(..., description="税率")
    calculated_tax: float = Field(..., description="计算税额")
    effective_rate: Optional[float] = Field(None, description="实际税率")
    input_tax: Optional[float] = Field(None, description="进项税额（增值税）")
    output_tax: Optional[float] = Field(None, description="销项税额（增值税）")
    net_tax_payable: Optional[float] = Field(None, description="应纳税额（增值税）")
    deductions: List[Dict[str, Any]] = Field(default_factory=list, description="扣除项目")
    exemptions: List[str] = Field(default_factory=list, description="免税项目")
    calculation_details: Dict[str, Any] = Field(default_factory=dict, description="计算明细")


class PolicyBenefitItem(BaseModel):
    """政策优惠项目"""
    policy_id: Optional[str] = Field(None, description="政策ID")
    policy_title: str = Field(..., description="政策名称")
    policy_source: str = Field(..., description="政策来源")
    match_level: PolicyMatchLevel = Field(..., description="匹配级别")
    applicability: float = Field(..., ge=0.0, le=1.0, description="适用性评分")
    potential_savings: float = Field(0.0, description="预估节省金额")
    conditions: List[str] = Field(default_factory=list, description="适用条件")
    implementation_suggestions: List[str] = Field(default_factory=list, description="实施建议")
    required_documents: List[str] = Field(default_factory=list, description="所需材料")
    compliance_requirements: List[str] = Field(default_factory=list, description="合规要求")


class TaxRiskItem(BaseModel):
    """税务风险项目"""
    risk_id: str = Field(..., description="风险ID")
    risk_type: str = Field(..., description="风险类型")
    severity: str = Field(..., description="严重程度：high/medium/low")
    description: str = Field(..., description="风险描述")
    legal_basis: List[str] = Field(default_factory=list, description="法律依据")
    affected_items: List[str] = Field(default_factory=list, description="影响项目")
    potential_penalty: Optional[str] = Field(None, description="潜在处罚")
    remediation_suggestions: List[str] = Field(default_factory=list, description="整改建议")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")


class TaxOptimizationSuggestion(BaseModel):
    """税务优化建议"""
    category: str = Field(..., description="优化类别")
    priority: str = Field(..., description="优先级：high/medium/low")
    current_situation: str = Field(..., description="现状分析")
    optimization_approach: str = Field(..., description="优化方案")
    expected_benefits: str = Field(..., description="预期收益")
    implementation_steps: List[str] = Field(default_factory=list, description="实施步骤")
    risks_and_mitigations: Dict[str, str] = Field(default_factory=dict, description="风险与缓解措施")
    applicable_policies: List[str] = Field(default_factory=list, description="适用政策")


class TaxAnalysisResult(BaseModel):
    """税务分析结果"""
    analysis_id: str = Field(..., description="分析ID")
    analysis_type: TaxAnalysisType = Field(..., description="分析类型")
    fiscal_year: int = Field(..., description="财务年度")
    fiscal_period: str = Field(..., description="财务期间")
    status: TaxIntelligenceStatus = Field(..., description="状态")
    
    financial_summary: Dict[str, Any] = Field(default_factory=dict, description="财务数据摘要")
    
    tax_calculations: List[TaxCalculationResult] = Field(default_factory=list, description="税务计算结果")
    total_tax_burden: float = Field(0.0, description="总税负")
    tax_burden_rate: float = Field(0.0, description="税负率")
    
    policy_benefits: List[PolicyBenefitItem] = Field(default_factory=list, description="可享受的优惠政策")
    total_potential_savings: float = Field(0.0, description="预估总节省金额")
    
    risk_assessment: List[TaxRiskItem] = Field(default_factory=list, description="风险评估结果")
    overall_risk_score: float = Field(0.0, description="综合风险评分")
    high_risk_count: int = Field(0, description="高风险数量")
    
    optimization_suggestions: List[TaxOptimizationSuggestion] = Field(default_factory=list, description="优化建议")
    
    current_step: int = Field(0, description="当前处理步骤")
    summary: str = Field("", description="执行摘要")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    processing_time: Optional[float] = Field(None, description="处理耗时（秒）")


class TaxIntelligenceAnalysisResponse(BaseModel):
    """税务智能分析响应"""
    analysis_id: str = Field(..., description="分析ID")
    status: TaxIntelligenceStatus = Field(..., description="分析状态")
    created_at: datetime = Field(..., description="创建时间")
    estimated_completion_time: Optional[str] = Field(None, description="预计完成时间")
    message: str = Field(..., description="状态消息")
    result: Optional[TaxAnalysisResult] = Field(None, description="分析结果（完成后返回）")

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "analysis-123",
                "status": "completed",
                "created_at": "2024-03-25T10:00:00Z",
                "message": "分析完成",
                "result": {
                    "analysis_id": "analysis-123",
                    "analysis_type": "quarterly_vat",
                    "fiscal_year": 2024,
                    "total_tax_burden": 150000.0,
                    "tax_burden_rate": 5.2
                }
            }
        }


class TaxCalculationRequest(BaseModel):
    """税务计算请求"""
    tax_type: str = Field(..., description="税种类型")
    taxable_amount: float = Field(..., description="应税金额")
    tax_rate: float = Field(..., description="税率")
    input_tax: Optional[float] = Field(0.0, description="进项税额（仅增值税）")
    is_small_enterprise: bool = Field(False, description="是否小微企业")
    user_id: str = Field(..., description="用户ID")
    tenant_id: str = Field(..., description="租户ID")

    class Config:
        json_schema_extra = {
            "example": {
                "tax_type": "vat",
                "taxable_amount": 1000000.0,
                "tax_rate": 0.13,
                "input_tax": 100000.0,
                "is_small_enterprise": False,
                "user_id": "user-123",
                "tenant_id": "tenant-456"
            }
        }


class TaxCalculationResponse(BaseModel):
    """税务计算响应"""
    calculation_id: str = Field(..., description="计算ID")
    tax_type: str = Field(..., description="税种")
    taxable_amount: float = Field(..., description="应税金额")
    tax_rate: float = Field(..., description="税率")
    calculated_tax: float = Field(..., description="计算税额")
    effective_rate: float = Field(..., description="实际税率")
    breakdown: Dict[str, Any] = Field(default_factory=dict, description="计算明细")
    timestamp: datetime = Field(default_factory=datetime.now, description="计算时间")


class PolicyQueryRequest(BaseModel):
    """政策查询请求"""
    query: str = Field(..., description="查询关键词")
    tax_types: Optional[List[str]] = Field(None, description="税种筛选")
    industries: Optional[List[str]] = Field(None, description="行业筛选")
    regions: Optional[List[str]] = Field(None, description="地区筛选")
    top_k: int = Field(10, ge=1, le=50, description="返回数量")
    user_id: str = Field(..., description="用户ID")
    tenant_id: str = Field(..., description="租户ID")


class PolicyQueryResponse(BaseModel):
    """政策查询响应"""
    query: str = Field(..., description="查询关键词")
    total_results: int = Field(..., description="结果总数")
    policies: List[PolicyBenefitItem] = Field(default_factory=list, description="匹配的政策")
    timestamp: datetime = Field(default_factory=datetime.now, description="查询时间")


class PolicySubscriptionRequest(BaseModel):
    """政策订阅请求"""
    user_id: str = Field(..., description="用户ID")
    tenant_id: str = Field(..., description="租户ID")
    subscription_type: str = Field(..., description="订阅类型：immediate/daily/weekly")
    tax_types: List[str] = Field(default_factory=list, description="关注的税种")
    industries: List[str] = Field(default_factory=list, description="所属行业")
    regions: List[str] = Field(default_factory=list, description="所在地区")
    keywords: List[str] = Field(default_factory=list, description="关注关键词")
    notification_email: Optional[str] = Field(None, description="通知邮箱")
    notification_webhook: Optional[str] = Field(None, description="通知Webhook")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "tenant_id": "tenant-456",
                "subscription_type": "weekly",
                "tax_types": ["vat", "income_tax"],
                "industries": ["technology", "manufacturing"],
                "regions": ["national", "provincial"],
                "keywords": ["加计扣除", "研发费用"],
                "notification_email": "tax@company.com"
            }
        }


class PolicySubscriptionResponse(BaseModel):
    """政策订阅响应"""
    subscription_id: str = Field(..., description="订阅ID")
    status: str = Field(..., description="订阅状态")
    subscription_type: str = Field(..., description="订阅类型")
    created_at: datetime = Field(..., description="创建时间")
    next_notification_time: Optional[datetime] = Field(None, description="下次通知时间")
    message: str = Field(..., description="状态消息")
