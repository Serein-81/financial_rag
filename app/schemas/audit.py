"""
审查相关的 Pydantic Schema 定义
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class AuditTypeEnum(str, Enum):
    """审查类型枚举"""
    FINANCE = "finance"
    TAX = "tax"
    LEGAL = "legal"
    COMPREHENSIVE = "comprehensive"


class RiskLevelEnum(str, Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentTypeEnum(str, Enum):
    """文档类型枚举"""
    FINANCIAL_STATEMENT = "financial_statement"
    TAX_RETURN = "tax_return"
    CONTRACT = "contract"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    LEGAL_DOCUMENT = "legal_document"
    UNKNOWN = "unknown"


# ========== 请求 Schema ==========

class DocumentInfo(BaseModel):
    """文档信息"""
    id: str = Field(..., description="文档ID")
    filename: Optional[str] = Field(None, description="文件名")
    content: str = Field(..., description="文档内容")
    type: Optional[str] = Field(None, description="文档类型")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class AuditTaskCreate(BaseModel):
    """创建审查任务请求"""
    audit_type: AuditTypeEnum = Field(..., description="审查类型")
    documents: List[DocumentInfo] = Field(..., min_items=1, description="待审查文档列表")
    priority: Optional[str] = Field("medium", description="任务优先级")
    description: Optional[str] = Field(None, description="任务描述")
    
    @validator('documents')
    def validate_documents(cls, v):
        if not v:
            raise ValueError("至少需要一个文档")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "audit_type": "comprehensive",
                "documents": [
                    {
                        "id": "doc_001",
                        "filename": "财务报表.pdf",
                        "content": "资产负债表内容...",
                        "type": "financial_statement"
                    }
                ],
                "priority": "high",
                "description": "年度财务审查"
            }
        }


# ========== 响应 Schema ==========

class FindingSchema(BaseModel):
    """审查发现"""
    id: str = Field(..., description="发现ID")
    agent_name: str = Field(..., description="发现该问题的Agent")
    category: str = Field(..., description="问题类别")
    description: str = Field(..., description="问题描述")
    risk_level: RiskLevelEnum = Field(..., description="风险等级")
    risk_score: float = Field(..., ge=0, le=1, description="风险分数 (0-1)")
    confidence: float = Field(..., ge=0, le=1, description="置信度 (0-1)")
    evidence: List[str] = Field(default_factory=list, description="证据列表")
    legal_basis: Optional[List[str]] = Field(None, description="法律依据")
    recommendations: Optional[List[str]] = Field(None, description="改进建议")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "finding_001",
                "agent_name": "finance_agent",
                "category": "资产负债",
                "description": "资产负债表不平衡，资产总额与负债及所有者权益总额存在差异",
                "risk_level": "high",
                "risk_score": 0.85,
                "confidence": 0.92,
                "evidence": [
                    "资产总额: 1,000,000元",
                    "负债及所有者权益总额: 950,000元",
                    "差异: 50,000元"
                ],
                "recommendations": [
                    "重新核对各项资产和负债的计算",
                    "检查是否有遗漏的会计科目"
                ]
            }
        }


class ConflictSchema(BaseModel):
    """冲突检测"""
    id: str = Field(..., description="冲突ID")
    finding_ids: List[str] = Field(..., description="冲突的发现ID列表")
    conflict_type: str = Field(..., description="冲突类型")
    description: str = Field(..., description="冲突描述")
    severity: str = Field(..., description="严重程度")
    resolution_suggestion: Optional[str] = Field(None, description="解决建议")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "conflict_001",
                "finding_ids": ["finding_001", "finding_002"],
                "conflict_type": "risk_assessment_conflict",
                "description": "财务Agent和税务Agent对同一问题的风险评估存在显著差异",
                "severity": "medium",
                "resolution_suggestion": "需要进一步审查以确定准确的风险等级"
            }
        }


class AuditStatistics(BaseModel):
    """审查统计信息"""
    total_findings: int = Field(..., description="发现总数")
    total_conflicts: int = Field(..., description="冲突总数")
    risk_level_distribution: Dict[str, int] = Field(..., description="风险等级分布")
    agent_contribution: Dict[str, int] = Field(..., description="各Agent贡献")
    category_distribution: Dict[str, int] = Field(..., description="类别分布")
    average_confidence: float = Field(..., description="平均置信度")
    average_risk_score: float = Field(..., description="平均风险分数")


class AuditResultResponse(BaseModel):
    """审查结果响应"""
    task_id: str = Field(..., description="任务ID")
    tenant_id: str = Field(..., description="租户ID")
    audit_type: AuditTypeEnum = Field(..., description="审查类型")
    findings: List[FindingSchema] = Field(..., description="审查发现列表")
    conflicts: List[ConflictSchema] = Field(..., description="冲突列表")
    overall_risk_score: float = Field(..., ge=0, le=100, description="综合风险分数 (0-100)")
    summary: str = Field(..., description="审查摘要")
    recommendations: List[str] = Field(..., description="总体建议")
    statistics: AuditStatistics = Field(..., description="统计信息")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_001",
                "tenant_id": "tenant_001",
                "audit_type": "comprehensive",
                "findings": [],
                "conflicts": [],
                "overall_risk_score": 75.5,
                "summary": "共发现3个问题，其中高风险1个，中风险2个",
                "recommendations": [
                    "建议立即处理高风险问题",
                    "制定中风险问题的改进计划"
                ],
                "statistics": {
                    "total_findings": 3,
                    "total_conflicts": 0,
                    "risk_level_distribution": {"high": 1, "medium": 2},
                    "agent_contribution": {"finance_agent": 2, "tax_agent": 1},
                    "category_distribution": {"资产负债": 1, "税务合规": 2},
                    "average_confidence": 0.87,
                    "average_risk_score": 0.68
                },
                "created_at": "2024-03-15T10:30:00Z"
            }
        }


class AuditTaskResponse(BaseModel):
    """审查任务响应"""
    id: str = Field(..., description="任务ID")
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    audit_type: AuditTypeEnum = Field(..., description="审查类型")
    status: str = Field(..., description="任务状态")
    documents: List[Dict[str, Any]] = Field(..., description="文档信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "task_001",
                "tenant_id": "tenant_001", 
                "user_id": "user_001",
                "audit_type": "comprehensive",
                "status": "processing",
                "documents": [
                    {
                        "id": "doc_001",
                        "filename": "财务报表.pdf",
                        "type": "financial_statement"
                    }
                ],
                "created_at": "2024-03-15T10:00:00Z",
                "completed_at": None,
                "error_message": None
            }
        }


# ========== 协作记录 Schema ==========

class AgentCollaborationResponse(BaseModel):
    """Agent协作记录响应"""
    id: str = Field(..., description="协作记录ID")
    task_id: str = Field(..., description="任务ID")
    from_agent: str = Field(..., description="发送方Agent")
    to_agent: str = Field(..., description="接收方Agent")
    message_type: str = Field(..., description="消息类型")
    message_content: Dict[str, Any] = Field(..., description="消息内容")
    timestamp: datetime = Field(..., description="时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "collab_001",
                "task_id": "task_001",
                "from_agent": "finance_agent",
                "to_agent": "tax_agent",
                "message_type": "request",
                "message_content": {
                    "request_type": "data_verification",
                    "data": "税务相关数据需要验证"
                },
                "timestamp": "2024-03-15T10:15:00Z"
            }
        }


# ========== 任务分解 Schema ==========

class DocumentAnalysis(BaseModel):
    """文档分析结果"""
    document_id: str = Field(..., description="文档ID")
    document_type: DocumentTypeEnum = Field(..., description="文档类型")
    priority: str = Field(..., description="优先级")
    content_length: int = Field(..., description="内容长度")
    filename: str = Field(..., description="文件名")


class TaskDecompositionResponse(BaseModel):
    """任务分解响应"""
    document_analysis: List[DocumentAnalysis] = Field(..., description="文档分析结果")
    required_audit_types: List[str] = Field(..., description="需要的审查类型")
    task_plan: Dict[str, Any] = Field(..., description="任务计划")
    estimated_time_seconds: int = Field(..., description="预估执行时间(秒)")
    total_documents: int = Field(..., description="文档总数")
    high_priority_documents: int = Field(..., description="高优先级文档数")
    
    class Config:
        schema_extra = {
            "example": {
                "document_analysis": [
                    {
                        "document_id": "doc_001",
                        "document_type": "financial_statement",
                        "priority": "high",
                        "content_length": 5000,
                        "filename": "财务报表.pdf"
                    }
                ],
                "required_audit_types": ["finance", "tax"],
                "task_plan": {
                    "execution_order": ["finance_agent", "tax_agent"],
                    "parallel_execution": True
                },
                "estimated_time_seconds": 180,
                "total_documents": 1,
                "high_priority_documents": 1
            }
        }