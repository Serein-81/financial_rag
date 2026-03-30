"""
多智能体系统请求/响应模型
定义与多智能体编排系统交互的API数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class SpecialistType(str, Enum):
    """专家智能体类型"""
    FINANCE = "finance"
    TAX = "tax"
    LEGAL = "legal"
    REFLECTION = "reflection"
    REPORT = "report"


class IntentCategory(str, Enum):
    """意图类别（与IntentAgent保持一致）"""
    FINANCIAL_INQUIRY = "financial_inquiry"
    TAX_PLANNING = "tax_planning"
    CONTRACT_REVIEW = "contract_review"
    COMPLIANCE_CHECK = "compliance_check"
    INVESTMENT_ADVICE = "investment_advice"
    BUDGET_PLANNING = "budget_planning"
    COST_ANALYSIS = "cost_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    REGULATORY_QUERY = "regulatory_query"
    GENERAL = "general"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    REPORT_GENERATION = "report_generation"
    COMPLEX_ANALYSIS = "complex_analysis"


class RoutingStrategy(str, Enum):
    """路由策略"""
    DIRECT_ANSWER = "direct_answer"
    RAG_RETRIEVAL = "rag_retrieval"
    SINGLE_SPECIALIST = "single_specialist"
    MULTI_SPECIALIST_PARALLEL = "multi_specialist_parallel"
    MULTI_SPECIALIST_SEQUENTIAL = "multi_specialist_sequential"
    REPORT_QUEUE = "report_queue"


class ComplexityLevel(str, Enum):
    """复杂度级别"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class MultiAgentRequest(BaseModel):
    """多智能体系统主请求"""
    query: str = Field(..., description="用户查询", min_length=1)
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加上下文")
    language: str = Field(default="zh", description="响应语言")
    max_specialists: int = Field(default=3, ge=1, le=5, description="最大并行专家数")
    enable_reflection: bool = Field(default=True, description="是否启用反思机制")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="置信度阈值")
    require_human_review: bool = Field(default=False, description="是否需要人工审核")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class SpecialistResult(BaseModel):
    """单个专家智能体结果"""
    specialist_type: SpecialistType
    specialist_name: str
    success: bool
    confidence: float = Field(ge=0.0, le=1.0)
    analysis: Dict[str, Any]
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    risks: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float
    error_message: Optional[str] = None


class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    primary_intent: IntentCategory
    secondary_intents: List[IntentCategory] = Field(default_factory=list)
    complexity: ComplexityLevel
    routing_strategy: RoutingStrategy
    confidence: float = Field(ge=0.0, le=1.0)
    required_specialists: List[SpecialistType] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReflectionResult(BaseModel):
    """反思机制结果"""
    quality_score: float = Field(ge=0.0, le=1.0)
    quality_level: str
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    needs_revision: bool
    revision_required: List[str] = Field(default_factory=list)


class MultiAgentResponse(BaseModel):
    """多智能体系统主响应"""
    session_id: str
    request_id: str
    user_query: str
    intent_analysis: IntentAnalysisResult
    specialist_results: List[SpecialistResult]
    reflection_result: Optional[ReflectionResult] = None
    final_response: str
    needs_human_review: bool
    confidence: float = Field(ge=0.0, le=1.0)
    processing_time: float
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiAgentStreamResponse(BaseModel):
    """多智能体流式响应"""
    event_type: Literal["intent", "specialist_start", "specialist_complete", "reflection", "final"]
    session_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class SpecialistQueryRequest(BaseModel):
    """单独调用专家智能体的请求"""
    specialist_type: SpecialistType
    query: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SpecialistQueryResponse(BaseModel):
    """单独调用专家智能体的响应"""
    specialist_type: SpecialistType
    success: bool
    result: Dict[str, Any]
    processing_time: float
    error_message: Optional[str] = None


class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    user_id: str
    tenant_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SessionCreateResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionStatus(BaseModel):
    """会话状态"""
    session_id: str
    user_id: str
    tenant_id: Optional[str]
    message_count: int
    last_activity: datetime
    created_at: datetime
    status: Literal["active", "completed", "archived"]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentHealthStatus(BaseModel):
    """智能体健康状态"""
    agent_type: SpecialistType
    is_available: bool
    response_time: Optional[float]
    last_heartbeat: datetime
    status_message: Optional[str] = None


class SystemHealthResponse(BaseModel):
    """系统健康检查响应"""
    overall_status: Literal["healthy", "degraded", "unhealthy"]
    agents: List[AgentHealthStatus]
    orchestrator_status: str
    database_status: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ReportGenerationRequest(BaseModel):
    """报告生成请求"""
    session_id: str
    report_type: Literal["comprehensive", "executive", "technical", "specialist"]
    format: Literal["json", "markdown", "html", "pdf", "text"]
    include_sections: Optional[List[str]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReportGenerationResponse(BaseModel):
    """报告生成响应"""
    report_id: str
    session_id: str
    report_type: str
    format: str
    content: str
    generated_at: datetime
    download_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """错误响应"""
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
