"""
专业智能体审查结果Schema
定义财务、税务、法务审查结果的数据结构
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SpecialtyType(str, Enum):
    """专业类型"""
    FINANCE = "finance"
    TAX = "tax"
    LEGAL = "legal"


class BaseFinding(BaseModel):
    """基础发现Schema"""
    id: str = Field(..., description="发现ID")
    agent_name: str = Field(..., description="发现该问题的智能体名称")
    category: str = Field(..., description="问题类别")
    description: str = Field(..., description="问题描述")
    risk_level: RiskLevel = Field(..., description="风险等级")
    risk_score: float = Field(..., ge=0, le=1, description="风险分数(0-1)")
    confidence: float = Field(..., ge=0, le=1, description="置信度(0-1)")
    evidence: List[str] = Field(default_factory=list, description="证据列表")
    legal_basis: Optional[List[str]] = Field(default=None, description="法律依据")
    recommendations: Optional[List[str]] = Field(default=None, description="改进建议")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


class FinanceFinding(BaseFinding):
    """财务审查发现"""
    financial_indicator: Optional[str] = Field(default=None, description="财务指标名称")
    indicator_value: Optional[float] = Field(default=None, description="指标值")
    benchmark_value: Optional[float] = Field(default=None, description="基准值")
    variance_percentage: Optional[float] = Field(default=None, description="偏差百分比")
    affected_statements: Optional[List[str]] = Field(default=None, description="影响的财务报表")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "fin_001",
                "agent_name": "finance_agent",
                "category": "资产负债表",
                "description": "资产负债率过高，达到85%",
                "risk_level": "high",
                "risk_score": 0.85,
                "confidence": 0.9,
                "evidence": ["资产总额: 1000万", "负债总额: 850万"],
                "recommendations": ["降低负债水平", "增加资本投入"],
                "financial_indicator": "资产负债率",
                "indicator_value": 85.0,
                "benchmark_value": 70.0,
                "variance_percentage": 21.4,
                "affected_statements": ["资产负债表"]
            }
        }
    )


class TaxFinding(BaseFinding):
    """税务审查发现"""
    tax_type: Optional[str] = Field(default=None, description="税种类型")
    tax_rate: Optional[float] = Field(default=None, description="适用税率")
    tax_amount: Optional[float] = Field(default=None, description="涉及税额")
    compliance_status: Optional[str] = Field(default=None, description="合规状态")
    related_regulations: Optional[List[str]] = Field(default=None, description="相关法规")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "tax_001",
                "agent_name": "tax_agent",
                "category": "增值税",
                "description": "增值税税率适用错误",
                "risk_level": "high",
                "risk_score": 0.8,
                "confidence": 0.85,
                "evidence": ["销售货物适用6%税率", "应适用13%税率"],
                "legal_basis": ["《增值税暂行条例》"],
                "recommendations": ["更正税率适用", "补缴税款"],
                "tax_type": "增值税",
                "tax_rate": 0.06,
                "tax_amount": 50000.0,
                "compliance_status": "不合规",
                "related_regulations": ["增值税暂行条例第2条"]
            }
        }
    )


class LegalFinding(BaseFinding):
    """法务审查发现"""
    legal_area: Optional[str] = Field(default=None, description="法律领域")
    contract_type: Optional[str] = Field(default=None, description="合同类型")
    clause_type: Optional[str] = Field(default=None, description="条款类型")
    compliance_level: Optional[str] = Field(default=None, description="合规等级")
    potential_liability: Optional[str] = Field(default=None, description="潜在责任")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "leg_001",
                "agent_name": "legal_agent",
                "category": "合同条款",
                "description": "合同缺少违约责任条款",
                "risk_level": "medium",
                "risk_score": 0.6,
                "confidence": 0.8,
                "evidence": ["合同文本中未发现违约责任相关条款"],
                "legal_basis": ["《合同法》第12条"],
                "recommendations": ["补充违约责任条款", "明确违约后果"],
                "legal_area": "合同法",
                "contract_type": "服务合同",
                "clause_type": "违约责任",
                "compliance_level": "部分合规",
                "potential_liability": "违约风险"
            }
        }
    )


class SpecialistResult(BaseModel):
    """专业智能体审查结果"""
    task_id: str = Field(..., description="任务ID")
    tenant_id: str = Field(..., description="租户ID")
    specialty: SpecialtyType = Field(..., description="专业类型")
    agent_name: str = Field(..., description="智能体名称")
    
    total_findings: int = Field(..., description="发现问题总数")
    findings: List[BaseFinding] = Field(..., description="具体发现列表")
    
    overall_risk_score: float = Field(..., ge=0, le=1, description="综合风险分数")
    risk_distribution: Dict[str, int] = Field(..., description="风险等级分布")
    
    average_confidence: float = Field(..., ge=0, le=1, description="平均置信度")
    confidence_distribution: Dict[str, int] = Field(..., description="置信度分布")
    
    categories_analyzed: List[str] = Field(..., description="分析的类别")
    documents_processed: int = Field(..., description="处理的文档数量")
    
    priority_recommendations: List[str] = Field(..., description="优先建议")
    all_recommendations: List[str] = Field(..., description="所有建议")
    
    execution_time: float = Field(..., description="执行时间(秒)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "audit_123",
                "tenant_id": "tenant_001",
                "specialty": "finance",
                "agent_name": "finance_agent",
                "total_findings": 3,
                "findings": [],
                "overall_risk_score": 0.65,
                "risk_distribution": {"low": 1, "medium": 1, "high": 1, "critical": 0},
                "average_confidence": 0.85,
                "confidence_distribution": {"0.8-1.0": 2, "0.6-0.8": 1, "0.4-0.6": 0, "0.0-0.4": 0},
                "categories_analyzed": ["资产负债表", "现金流量表", "利润表"],
                "documents_processed": 5,
                "priority_recommendations": ["降低资产负债率", "改善现金流管理"],
                "all_recommendations": ["降低资产负债率", "改善现金流管理", "加强财务监控"],
                "execution_time": 45.2
            }
        }
    )


class CombinedAuditResult(BaseModel):
    """综合审查结果"""
    task_id: str = Field(..., description="任务ID")
    tenant_id: str = Field(..., description="租户ID")
    audit_type: str = Field(..., description="审查类型")
    
    finance_result: Optional[SpecialistResult] = Field(default=None, description="财务审查结果")
    tax_result: Optional[SpecialistResult] = Field(default=None, description="税务审查结果")
    legal_result: Optional[SpecialistResult] = Field(default=None, description="法务审查结果")
    
    total_findings: int = Field(..., description="总发现数")
    overall_risk_score: float = Field(..., ge=0, le=1, description="综合风险分数")
    overall_risk_level: RiskLevel = Field(..., description="综合风险等级")
    
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="冲突列表")
    
    executive_summary: str = Field(..., description="执行摘要")
    key_risks: List[str] = Field(..., description="关键风险")
    priority_actions: List[str] = Field(..., description="优先行动")
    
    total_execution_time: float = Field(..., description="总执行时间(秒)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "audit_123",
                "tenant_id": "tenant_001",
                "audit_type": "comprehensive",
                "total_findings": 8,
                "overall_risk_score": 0.72,
                "overall_risk_level": "high",
                "conflicts": [],
                "executive_summary": "本次审查发现8个问题，主要集中在财务和税务领域...",
                "key_risks": ["资产负债率过高", "增值税税率错误", "合同条款不完整"],
                "priority_actions": ["立即纠正税率错误", "制定债务削减计划", "完善合同条款"],
                "total_execution_time": 120.5
            }
        }
    )


class AuditRequest(BaseModel):
    """审查请求"""
    tenant_id: str = Field(..., description="租户ID")
    audit_type: str = Field(..., description="审查类型", pattern="^(finance|tax|legal|comprehensive)$")
    documents: List[Dict[str, Any]] = Field(..., description="待审查文档")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="审查选项")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "tenant_001",
                "audit_type": "comprehensive",
                "documents": [
                    {"id": "doc_001", "type": "资产负债表", "content": "..."},
                    {"id": "doc_002", "type": "增值税申报表", "content": "..."}
                ],
                "options": {
                    "include_recommendations": True,
                    "detailed_analysis": True
                }
            }
        }
    )


class AuditResponse(BaseModel):
    """审查响应"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    message: str = Field(..., description="响应消息")
    result: Optional[CombinedAuditResult] = Field(default=None, description="审查结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "task_id": "audit_123",
                "message": "审查完成",
                "result": {},
                "error": None
            }
        }
    )
