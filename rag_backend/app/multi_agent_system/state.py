"""
全局状态定义
用于多智能体系统的状态管理

融合自：
- state.py: AuditState, Finding, Conflict, Report 等核心状态类
- task_blackboard.py: TaskStatus, TaskPriority, AgentRole, TaskContext 等任务管理类
"""

from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AuditType(str, Enum):
    """审查类型"""
    FINANCE = "finance"
    TAX = "tax"
    LEGAL = "legal"
    COMPREHENSIVE = "comprehensive"


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INFO = "info"


class TaskStatus(str, Enum):
    """任务状态（整合自 task_blackboard.py）"""
    PENDING = "pending"          # 待处理
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 取消
    WAITING_DEPENDENCY = "waiting_dependency"  # 等待依赖


class TaskPriority(int, Enum):
    """任务优先级（整合自 task_blackboard.py）"""
    CRITICAL = 1   # 最高优先级
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class AgentRole(str, Enum):
    """智能体角色（整合自 task_blackboard.py）"""
    COORDINATOR = "coordinator"      # 协调者
    SPECIALIST = "specialist"        # 专家
    HELPER = "helper"                # 助手
    SYNTHESIZER = "synthesizer"      # 合成器
    MONITOR = "monitor"              # 监控者


@dataclass
class TaskContext:
    """任务上下文（整合自 task_blackboard.py）
    
    提供完整的任务生命周期管理能力：
    - 依赖关系管理
    - 优先级调度
    - 重试机制
    - 执行时间跟踪
    """
    task_id: str
    task_type: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    assigned_to: Optional[str] = None
    
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: set = field(default_factory=set)
    
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "priority": self.priority.value if isinstance(self.priority, TaskPriority) else self.priority,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "intermediate_results": self.intermediate_results,
            "metadata": self.metadata,
            "tags": list(self.tags),
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time": self.execution_time
        }


@dataclass
class AgentRegistry:
    """智能体注册信息（整合自 task_blackboard.py）
    
    用于追踪多智能体系统中的智能体状态和性能
    """
    agent_id: str
    agent_name: str
    role: AgentRole
    status: str = "idle"  # idle, busy, waiting, error
    current_task_id: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    expertise: List[str] = field(default_factory=list)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    registered_at: datetime = field(default_factory=datetime.now)
    
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role.value if isinstance(self.role, AgentRole) else self.role,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "capabilities": self.capabilities,
            "expertise": self.expertise,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "avg_execution_time": self.avg_execution_time
        }


@dataclass
class BlackboardEvent:
    """黑板事件（整合自 task_blackboard.py）
    
    用于多智能体系统中的事件驱动通信
    """
    event_id: str
    event_type: str
    source: str
    target: Optional[str] = None
    task_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "target": self.target,
            "task_id": self.task_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "priority": self.priority
        }


@dataclass
class Finding:
    """审查发现"""
    id: str
    agent_name: str  # 发现该问题的 Agent
    category: str  # 问题类别
    description: str  # 问题描述
    risk_level: RiskLevel  # 风险等级
    risk_score: float  # 风险评分 0-100
    confidence: float  # 置信度 0-1
    evidence: List[str]  # 证据列表
    legal_basis: Optional[List[str]] = None  # 法律依据
    recommendations: Optional[List[str]] = None  # 改进建议
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "category": self.category,
            "description": self.description,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "legal_basis": self.legal_basis,
            "recommendations": self.recommendations
        }


@dataclass
class Conflict:
    """冲突检测"""
    id: str
    finding_ids: List[str]  # 冲突的发现 ID
    conflict_type: str  # 冲突类型
    description: str  # 冲突描述
    severity: str  # 严重程度
    resolution_suggestion: Optional[str] = None  # 解决建议
    
    # 新增字段
    agent1: str = ""  # 冲突方1
    agent2: str = ""  # 冲突方2
    finding1: Optional[Dict] = None  # 发现1
    finding2: Optional[Dict] = None  # 发现2
    resolution_needed: bool = True  # 是否需要解决
    resolved: bool = False  # 是否已解决
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "finding_ids": self.finding_ids,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "severity": self.severity,
            "resolution_suggestion": self.resolution_suggestion,
            "agent1": self.agent1,
            "agent2": self.agent2,
            "finding1": self.finding1,
            "finding2": self.finding2,
            "resolution_needed": self.resolution_needed,
            "resolved": self.resolved
        }


@dataclass
class Report:
    """最终报告"""
    task_id: str
    tenant_id: str
    audit_type: AuditType
    findings: List[Finding]
    conflicts: List[Conflict]
    overall_risk_score: float  # 综合风险评分
    summary: str  # 总结
    recommendations: List[str]  # 总体建议
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "audit_type": self.audit_type.value if isinstance(self.audit_type, AuditType) else self.audit_type,
            "findings": [f.to_dict() for f in self.findings],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "overall_risk_score": self.overall_risk_score,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat()
        }


class AuditState(TypedDict, total=False):
    """
    审查全局状态
    使用 TypedDict 确保类型安全
    """
    # ========== 任务信息 ==========
    task_id: str
    tenant_id: str
    user_id: str
    audit_type: str  # finance/tax/legal/comprehensive
    documents: List[Dict[str, Any]]  # 待审查的文档列表
    
    # ========== 数据摄入阶段 ==========
    parsed_docs: List[Dict[str, Any]]  # 解析后的文档
    entities: List[Dict[str, Any]]  # 提取的实体
    relations: List[Dict[str, Any]]  # 提取的关系
    ocr_results: Optional[Dict[str, Any]]  # OCR 识别结果
    
    # ========== 门卫阶段 ==========
    triage_results: List[Dict[str, Any]]  # 门卫Agent分类结果
    triage_passed: bool  # 是否通过门卫审查
    triage_rejected_docs: List[Dict[str, Any]]  # 被门卫拒绝的文档
    
    # ========== 审查结果阶段 ==========
    finance_findings: List[Dict[str, Any]]  # 财务审查发现
    tax_findings: List[Dict[str, Any]]  # 税务审查发现
    legal_findings: List[Dict[str, Any]]  # 法务审查发现
    
    # ========== 反思阶段 ==========
    conflicts: List[Dict[str, Any]]  # 冲突列表
    evidence_gaps: List[str]  # 证据缺口
    confidence_scores: Dict[str, float]  # 各 Agent 的置信度
    reflection_summary: str  # 反思总结
    
    # ========== 税务验证阶段 ==========
    tax_validation: Dict[str, Any]  # 税务逻辑验证结果
    tax_indicators: List[Dict[str, Any]]  # 税务指标（含异常检测）
    tax_errors: List[Dict[str, Any]]  # 税务逻辑错误
    
    # ========== RAG增强阶段 ==========
    rag_contexts: List[Dict[str, Any]]  # RAG检索上下文
    rag_enhanced_findings: List[Dict[str, Any]]  # RAG增强后的发现
    
    # ========== 重做标记 ==========
    need_rework: bool  # 是否需要重做
    rework_agents: List[str]  # 需要重做的 Agent 列表
    rework_count: int  # 重做次数
    rework_reason: str  # 重做原因
    
    # ========== 企业记忆 ==========
    historical_risks: List[Dict[str, Any]]  # 历史风险记录
    semantic_facts: List[Dict[str, Any]]  # 语义事实
    
    # ========== 人工介入相关 ==========
    needs_human_review: bool  # 是否需要人工审核
    review_request_id: Optional[str]  # 审核请求ID
    review_status: Optional[str]  # pending/in_progress/approved/rejected/escalated
    review_decision: Optional[str]  # 审核决定
    review_feedback: Optional[str]  # 审核反馈
    review_trigger_reason: Optional[str]  # 触发审核的原因
    human_review_completed: bool  # 人工审核是否完成
    
    # ========== PII脱敏相关 ==========
    pii_mapping: Dict[str, str]  # PII脱敏映射
    
    # ========== 任务管理相关（整合自 task_blackboard.py） ==========
    task_contexts: Dict[str, Dict[str, Any]]  # 任务上下文映射
    agent_registries: Dict[str, Dict[str, Any]]  # 智能体注册信息
    task_dependencies: Dict[str, List[str]]  # 任务依赖关系
    
    # ========== 最终输出 ==========
    final_report: Optional[Dict[str, Any]]  # 最终报告
    
    # ========== 元数据 ==========
    created_at: str
    updated_at: str
    status: str  # pending/processing/completed/failed/pending_review
    error_message: Optional[str]


def create_initial_state(
    task_id: str,
    tenant_id: str,
    user_id: str,
    audit_type: str,
    documents: List[Dict[str, Any]]
) -> AuditState:
    """
    创建初始状态
    
    Args:
        task_id: 任务 ID
        tenant_id: 租户 ID
        user_id: 用户 ID
        audit_type: 审查类型
        documents: 文档列表
        
    Returns:
        初始化的 AuditState
    """
    now = datetime.utcnow().isoformat()
    
    return AuditState(
        # 任务信息
        task_id=task_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type=audit_type,
        documents=documents,
        
        # 数据摄入
        parsed_docs=[],
        entities=[],
        relations=[],
        ocr_results=None,
        
        # 门卫阶段
        triage_results=[],
        triage_passed=False,
        triage_rejected_docs=[],
        
        # 审查结果
        finance_findings=[],
        tax_findings=[],
        legal_findings=[],
        
        # 反思
        conflicts=[],
        evidence_gaps=[],
        confidence_scores={},
        reflection_summary="",
        
        # 税务验证
        tax_validation={},
        tax_indicators=[],
        tax_errors=[],
        
        # RAG增强
        rag_contexts=[],
        rag_enhanced_findings=[],
        
        # 重做
        need_rework=False,
        rework_agents=[],
        rework_count=0,
        rework_reason="",
        
        # 企业记忆
        historical_risks=[],
        semantic_facts=[],
        
        # 人工介入
        needs_human_review=False,
        review_request_id=None,
        review_status=None,
        review_decision=None,
        review_feedback=None,
        review_trigger_reason=None,
        human_review_completed=False,
        
        # PII脱敏
        pii_mapping={},
        
        # 任务管理
        task_contexts={},
        agent_registries={},
        task_dependencies={},
        pending_tasks=[],
        completed_tasks=[],
        failed_tasks=[],
        
        # 最终输出
        final_report=None,
        
        # 元数据
        created_at=now,
        updated_at=now,
        status="pending",
        error_message=None
    )
