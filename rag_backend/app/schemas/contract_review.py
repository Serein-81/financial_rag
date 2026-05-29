"""
合同审核智能助手 Pydantic Schema 定义
用于合同深度分析和审核系统
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ContractType(str, Enum):
    """合同类型"""
    SALES = "sales"  # 销售合同
    PURCHASE = "purchase"  # 采购合同
    SERVICE = "service"  # 服务合同
    LABOR = "labor"  # 劳动合同
    LEASE = "lease"  # 租赁合同
    LOAN = "loan"  # 借款合同
    PARTNERSHIP = "partnership"  # 合作协议
    CONFIDENTIALITY = "confidentiality"  # 保密协议
    OTHER = "other"


class RiskLevel(str, Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ClauseType(str, Enum):
    """条款类型"""
    PAYMENT = "payment"  # 付款条款
    DELIVERY = "delivery"  # 交付条款
    WARRANTY = "warranty"  # 保修条款
    LIABILITY = "liability"  # 责任条款
    TERMINATION = "termination"  # 终止条款
    CONFIDENTIALITY = "confidentiality"  # 保密条款
    INTELLECTUAL_PROPERTY = "ip"  # 知识产权条款
    DISPUTE_RESOLUTION = "dispute"  # 争议解决条款
    FORCE_MAJEURE = "force_majeure"  # 不可抗力条款
    INDEMNIFICATION = "indemnification"  # 赔偿条款
    ASSIGNMENT = "assignment"  # 转让条款
    GOVERNING_LAW = "governing_law"  # 适用法律条款
    OTHER = "other"  # 其他条款


class ReviewStatus(str, Enum):
    """审核状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ContractClause(BaseModel):
    """合同条款"""
    clause_id: str = Field(..., description="条款ID")
    clause_type: ClauseType = Field(..., description="条款类型")
    title: str = Field(..., description="条款标题")
    content: str = Field(..., description="条款内容")
    location: str = Field(..., description="条款位置（如：第X条第Y款）")
    risk_level: RiskLevel = Field(..., description="风险级别")
    risk_description: Optional[str] = Field(None, description="风险描述")
    is_standard_clause: bool = Field(default=True, description="是否为标准条款")
    deviations: List[str] = Field(default_factory=list, description="偏离标准的内容")
    importance: str = Field(..., description="重要程度：关键/重要/一般")
    requires_attention: bool = Field(default=False, description="是否需要特别关注")


class RiskAssessment(BaseModel):
    """风险评估"""
    risk_id: str = Field(..., description="风险ID")
    risk_type: str = Field(..., description="风险类型")
    risk_level: RiskLevel = Field(..., description="风险级别")
    description: str = Field(..., description="风险描述")
    affected_clauses: List[str] = Field(default_factory=list, description="涉及条款")
    potential_impact: str = Field(..., description="潜在影响")
    likelihood: float = Field(..., ge=0.0, le=1.0, description="发生概率")
    mitigation_suggestions: List[str] = Field(default_factory=list, description="缓解建议")
    requires_human_review: bool = Field(default=False, description="是否需要人工审核")


class ClauseComparison(BaseModel):
    """条款对比"""
    clause_type: ClauseType = Field(..., description="条款类型")
    your_clause: Optional[str] = Field(None, description="贵方条款")
    counterparty_clause: Optional[str] = Field(None, description="对方条款")
    standard_clause: Optional[str] = Field(None, description="标准条款")
    differences: List[str] = Field(default_factory=list, description="差异点")
    your_position_strength: str = Field(..., description="贵方立场强度：强/中/弱")
    negotiation_priority: str = Field(..., description="谈判优先级：高/中/低")


class ModificationSuggestion(BaseModel):
    """修改建议"""
    suggestion_id: str = Field(..., description="建议ID")
    clause_type: ClauseType = Field(..., description="条款类型")
    original_text: str = Field(..., description="原文")
    suggested_text: str = Field(..., description="建议修改为")
    reason: str = Field(..., description="修改原因")
    risk_reduction: str = Field(..., description="风险降低程度")
    priority: str = Field(..., description="优先级：高/中/低")


class ContractAnalysisRequest(BaseModel):
    """合同分析请求"""
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    contract_name: str = Field(..., description="合同名称")
    contract_type: ContractType = Field(..., description="合同类型")
    contract_content: str = Field(..., description="合同内容")
    counterparty_name: Optional[str] = Field(None, description="对方名称")
    contract_value: Optional[float] = Field(None, description="合同金额")
    effective_date: Optional[date] = Field(None, description="生效日期")
    expiration_date: Optional[date] = Field(None, description="到期日期")
    include_deep_analysis: bool = Field(default=True, description="是否包含深度分析")
    include_risk_assessment: bool = Field(default=True, description="是否包含风险评估")
    include_suggestions: bool = Field(default=True, description="是否包含修改建议")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "tenant_id": "tenant-456",
                "user_id": "user-123",
                "contract_name": "产品采购合同",
                "contract_type": "purchase",
                "contract_content": "甲方（买方）：XXX公司...",
                "counterparty_name": "YYY供应商",
                "contract_value": 500000.0,
                "include_deep_analysis": True,
                "include_risk_assessment": True
            }
        }
    )


class ContractAnalysisResponse(BaseModel):
    """合同分析响应"""
    analysis_id: str = Field(..., description="分析ID")
    status: ReviewStatus = Field(..., description="审核状态")
    contract_name: str = Field(..., description="合同名称")
    contract_type: ContractType = Field(..., description="合同类型")
    
    overall_risk_level: RiskLevel = Field(..., description="整体风险级别")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="风险评分")
    
    clauses_extracted: List[ContractClause] = Field(default_factory=list, description="提取的条款")
    risk_assessments: List[RiskAssessment] = Field(default_factory=list, description="风险评估列表")
    
    key_findings: List[str] = Field(default_factory=list, description="关键发现")
    high_risk_items: List[str] = Field(default_factory=list, description="高风险项目")
    recommended_actions: List[str] = Field(default_factory=list, description="建议措施")
    
    summary: str = Field(..., description="审核摘要")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class DeepClauseAnalysisRequest(BaseModel):
    """深度条款分析请求"""
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    contract_id: Optional[str] = Field(None, description="合同ID（已有分析结果时）")
    clause_content: str = Field(..., description="条款内容")
    clause_type: ClauseType = Field(..., description="条款类型")
    context: Optional[str] = Field(None, description="上下文信息")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "tenant_id": "tenant-456",
                "user_id": "user-123",
                "clause_content": "甲方应于收到货物后30日内完成验收...",
                "clause_type": "delivery"
            }
        }
    )


class DeepClauseAnalysisResponse(BaseModel):
    """深度条款分析响应"""
    analysis_id: str = Field(..., description="分析ID")
    clause_type: ClauseType = Field(..., description="条款类型")
    clause_summary: str = Field(..., description="条款摘要")
    
    legal_interpretation: str = Field(..., description="法律解释")
    potential_issues: List[str] = Field(default_factory=list, description="潜在问题")
    industry_practices: List[str] = Field(default_factory=list, description="行业惯例")
    
    comparison_with_standard: Dict[str, Any] = Field(default_factory=dict, description="与标准条款对比")
    risk_factors: List[str] = Field(default_factory=list, description="风险因素")
    
    suggestions: List[str] = Field(default_factory=list, description="建议")
    references: List[Dict[str, str]] = Field(default_factory=list, description="参考法规/案例")
    
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class ContractComparisonRequest(BaseModel):
    """合同对比请求"""
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    contract1_id: Optional[str] = Field(None, description="合同1 ID")
    contract2_id: Optional[str] = Field(None, description="合同2 ID")
    contract1_content: Optional[str] = Field(None, description="合同1 内容")
    contract2_content: Optional[str] = Field(None, description="合同2 内容")
    compare_type: str = Field(default="both", description="对比类型：both/standards/versions")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "tenant_id": "tenant-456",
                "user_id": "user-123",
                "compare_type": "versions",
                "contract1_id": "contract-001",
                "contract2_id": "contract-002"
            }
        }
    )


class ContractComparisonResponse(BaseModel):
    """合同对比响应"""
    comparison_id: str = Field(..., description="对比ID")
    contract1_name: str = Field(..., description="合同1名称")
    contract2_name: str = Field(..., description="合同2名称")
    
    clause_comparisons: List[ClauseComparison] = Field(default_factory=list, description="条款对比")
    
    key_differences: List[str] = Field(default_factory=list, description="关键差异")
    advantage_summary: str = Field(..., description="优势总结")
    risk_summary: str = Field(..., description="风险总结")
    
    negotiation_points: List[str] = Field(default_factory=list, description="谈判要点")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class BatchReviewRequest(BaseModel):
    """批量审核请求"""
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    contract_ids: List[str] = Field(..., min_length=1, description="合同ID列表")
    review_criteria: List[str] = Field(default_factory=list, description="审核标准")
    priority: str = Field(default="normal", description="优先级：urgent/normal/low")


class BatchReviewResponse(BaseModel):
    """批量审核响应"""
    batch_id: str = Field(..., description="批次ID")
    total_contracts: int = Field(..., description="总合同数")
    completed_count: int = Field(..., description="已完成数")
    failed_count: int = Field(..., description="失败数")
    high_risk_count: int = Field(..., description="高风险合同数")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="审核结果列表")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class ContractSummary(BaseModel):
    """合同摘要"""
    contract_id: str = Field(..., description="合同ID")
    contract_name: str = Field(..., description="合同名称")
    contract_type: ContractType = Field(..., description="合同类型")
    counterparty: Optional[str] = Field(None, description="对方")
    contract_value: Optional[float] = Field(None, description="金额")
    effective_date: Optional[date] = Field(None, description="生效日期")
    expiration_date: Optional[date] = Field(None, description="到期日期")
    status: ReviewStatus = Field(..., description="状态")
    risk_level: RiskLevel = Field(..., description="风险级别")
    key_points: List[str] = Field(default_factory=list, description="关键点")
    last_reviewed_at: datetime = Field(default_factory=datetime.now, description="最后审核时间")
