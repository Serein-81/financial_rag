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
    """意图类别（与IntentRouterAgent保持一致）"""
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
    """单个专家智能体结果
    
    整合自：
    - schemas/multi_agent.py: 原始完整结构（analysis, entities, recommendations, risks）
    - langgraph/state.py: 执行追踪字段（query, response, tools_used, execution_time_ms）
    """
    specialist_type: SpecialistType
    specialist_name: str
    success: bool
    confidence: float = Field(ge=0.0, le=1.0)
    
    # 执行追踪（整合自 langgraph/state.py）
    query: str = Field(default="", description="原始查询")
    response: str = Field(default="", description="生成响应")
    tools_used: List[str] = Field(default_factory=list, description="使用的工具列表")
    execution_time_ms: float = Field(default=0.0, description="执行时间（毫秒）")
    
    # 分析结果（原始字段）
    analysis: Dict[str, Any] = Field(default_factory=dict)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    risks: List[Dict[str, Any]] = Field(default_factory=list)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float = Field(default=0.0, description="处理时间（秒）")
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


# ==========================================
# 监控 API 响应模型（前端监控页面使用）
# ==========================================

class MonitorComponentStatus(BaseModel):
    """监控组件状态"""
    rbac_service: bool = True
    task_scheduler: bool = True
    session_blackboard: bool = True
    hitl_manager: bool = True
    intent_classifier: bool = True


class MonitorSystemHealth(BaseModel):
    """前端监控系统健康状态"""
    status: Literal["healthy", "degraded", "down"] = "healthy"
    components: MonitorComponentStatus = Field(default_factory=MonitorComponentStatus)
    uptime: int = 0
    active_sessions: int = 0
    pending_approvals: int = 0


class AgentMetric(BaseModel):
    """Agent 指标"""
    agent_id: str
    agent_name: str
    total_requests: int = 0
    success_rate: float = 0.0
    avg_latency: float = 0.0
    last_execution: Optional[str] = None


class StreamingTask(BaseModel):
    """流式任务"""
    task_id: str
    agent_id: str
    agent_name: str
    status: Literal["pending", "running", "completed", "failed", "streaming"] = "pending"
    progress: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    estimated_time: Optional[float] = None


class IntentClassificationResult(BaseModel):
    """意图分类结果"""
    stage: Literal["keyword", "embedding", "slm"] = "keyword"
    intent: str = ""
    confidence: float = 0.0
    is_expense_related: bool = False
    should_process: bool = True
    matched_keywords: Optional[List[str]] = None
    embedding_score: Optional[float] = None
    reasoning: Optional[str] = None


class TaskPipeline(BaseModel):
    """任务管道"""
    pipeline_id: str
    session_id: str
    user_id: str
    query: str
    tasks: List[StreamingTask] = Field(default_factory=list)
    state: Literal["idle", "processing", "waiting", "completed"] = "idle"
    intent_classification: Optional[IntentClassificationResult] = None
    created_at: str
    updated_at: str


# ==========================================
# RBAC 模型
# ==========================================

class PermissionLevel(str, Enum):
    """权限级别"""
    PUBLIC = "public"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


class UserRole(BaseModel):
    """用户角色"""
    role_id: str
    role_name: str
    permissions: List[PermissionLevel] = Field(default_factory=list)


class RBACPolicy(BaseModel):
    """RBAC策略"""
    policy_id: str
    role: str
    allowed_operations: List[str] = Field(default_factory=list)
    denied_operations: List[str] = Field(default_factory=list)
    created_at: datetime


# ==========================================
# HITL (Human-In-The-Loop) 模型
# ==========================================

class ApprovalStatus(str, Enum):
    """审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class HITLApproval(BaseModel):
    """HITL审批"""
    approval_id: str
    task_id: str
    user_id: str
    user_name: Optional[str] = None
    applicant_user_id: Optional[str] = None
    applicant_name: Optional[str] = None
    operator_user_id: Optional[str] = None
    operator_name: Optional[str] = None
    operation: str
    details: Dict[str, Any] = Field(default_factory=dict)
    risk_level: PermissionLevel = PermissionLevel.SENSITIVE
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime
    expires_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None


class HITLApprovalCreate(BaseModel):
    """创建HITL审批请求"""
    task_id: str
    operation: str
    details: Dict[str, Any] = Field(default_factory=dict)
    risk_level: PermissionLevel = PermissionLevel.SENSITIVE


class HITLApprovalReview(BaseModel):
    """HITL审批审核"""
    action: Literal["approve", "reject"]
    notes: Optional[str] = None


# ==========================================
# 安全审计模型
# ==========================================

class SecurityEventType(str, Enum):
    """安全事件类型"""
    PERMISSION_DENIED = "permission_denied"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_COMPLETED = "approval_completed"
    PROMPT_INJECTION = "prompt_injection"
    ROLE_CHANGE = "role_change"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    HIGH_RISK_OPERATION = "high_risk_operation"


class SecurityEventSeverity(str, Enum):
    """安全事件严重级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(BaseModel):
    """安全事件"""
    event_id: str
    event_type: SecurityEventType
    user_id: str
    tenant_id: Optional[str] = None
    target_resource: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    severity: SecurityEventSeverity
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class SecurityStats(BaseModel):
    """安全统计"""
    total_events: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    recent_trends: List[Dict[str, Any]]


class PendingQuestion(BaseModel):
    """待处理问题"""
    question_id: str
    question: str
    context: Dict[str, Any] = Field(default_factory=dict)


class SessionContext(BaseModel):
    """会话上下文"""
    session_id: str
    user_id: str
    state: Literal["active", "waiting", "completed"] = "active"
    pending_questions: List[PendingQuestion] = Field(default_factory=list)
    historical_results: Dict[str, Any] = Field(default_factory=dict)
    current_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
