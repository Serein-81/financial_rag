"""
统一状态定义

这是整个系统的核心状态定义，融合了：
- LangGraph 的 AgentState
- Multi-Agent System 的 AuditState
- TaskBlackboard 的 TaskContext

关键设计原则：
1. 只存储引用（ID），不存储大数据
2. 明确的类型注解
3. 完整的文档字符串
4. 向后兼容现有状态定义
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    """
    意图分类枚举
    
    定义用户查询的可能意图类型
    """
    RAG_RETRIEVAL = "rag_retrieval"  # RAG 检索
    SINGLE_SPECIALIST = "single_specialist"  # 单专家查询
    MULTI_SPECIALIST = "multi_specialist"  # 多专家协作
    DIRECT_ANSWER = "direct_answer"  # 直接回答
    HUMAN_REVIEW = "human_review"  # 需要人工审核
    EXPERT_CONSULTATION = "expert_consultation"  # 专家会诊（新增）
    UNKNOWN = "unknown"  # 未知意图


class SpecialistType(str, Enum):
    """
    专家类型枚举
    
    定义系统中可用的专家类型
    """
    FINANCE = "finance"  # 财务专家
    TAX = "tax"  # 税务专家
    LEGAL = "legal"  # 法律专家
    REPORT = "report"  # 报告生成专家
    REFLECTION = "reflection"  # 反思专家
    COORDINATOR = "coordinator"  # 协调者


class QualityLevel(str, Enum):
    """
    质量等级枚举
    
    定义输出质量等级
    """
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"  # 良好
    ACCEPTABLE = "acceptable"  # 可接受
    POOR = "poor"  # 较差
    UNACCEPTABLE = "unacceptable"  # 不可接受


class OrchestrationMode(str, Enum):
    """
    编排模式枚举
    
    定义多智能体的编排模式
    """
    LANGGRAPH = "langgraph"  # 顶层 LangGraph 编排
    MESSAGE_BUS = "message_bus"  # Message Bus 黑板模式
    HYBRID = "hybrid"  # 混合模式


class ExecutionStatus(str, Enum):
    """
    执行状态枚举
    
    定义任务执行状态
    """
    PENDING = "pending"  # 待处理
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 取消
    WAITING_DEPENDENCY = "waiting_dependency"  # 等待依赖


class TaskPriority(int, Enum):
    """
    任务优先级枚举
    
    定义任务优先级（数值越小优先级越高）
    """
    CRITICAL = 1  # 最高优先级
    HIGH = 2  # 高优先级
    NORMAL = 3  # 普通优先级
    LOW = 4  # 低优先级
    BACKGROUND = 5  # 后台任务


class AgentMessage(BaseModel):
    """
    Agent 消息模型
    
    用于记录对话历史中的单条消息
    """
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class SpecialistResult(BaseModel):
    """
    专家结果模型
    
    记录单个专家的执行结果
    """
    specialist_type: SpecialistType
    specialist_id: str
    query: str
    response: str
    confidence: float = Field(ge=0.0, le=1.0)
    tools_used: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {
        "json_encoders": {
            SpecialistType: lambda v: v.value
        }
    }


class ReflectionResult(BaseModel):
    """
    反思结果模型
    
    记录反思 Agent 的质量评估结果
    """
    quality_level: QualityLevel
    overall_score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    needs_human_review: bool = False
    revised_response: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnifiedState(TypedDict, total=False):
    """
    统一状态定义
    
    这是整个多智能体系统的核心状态结构。
    使用 TypedDict 确保类型安全，同时保持灵活性。
    
    关键设计决策：
    1. **只存储引用**：不直接存储大型数据（如文档内容、嵌入向量）
       只存储 ID 或元数据引用，由专门的存储层负责实际数据
    2. **明确的分区**：将状态分为核心信息、流程控制、结果存储等区域
    3. **可追溯性**：每个状态都包含创建时间和更新时间戳
    4. **可扩展性**：使用 metadata 字段存储自定义数据
    
    Attributes:
        核心会话信息:
            session_id: 会话 ID，用于标识一次用户会话
            tenant_id: 租户 ID，用于多租户数据隔离
            user_id: 用户 ID，标识发起请求的用户
            request_id: 请求 ID，用于请求级别的追踪
        
        用户输入:
            user_query: 用户的原始查询
            query_timestamp: 查询时间戳
        
        意图识别:
            intent: 识别的用户意图
            intent_confidence: 意图识别的置信度
            routing_strategy: 路由策略
            target_specialists: 目标专家列表
        
        编排模式:
            orchestration_mode: 当前编排模式
            current_phase: 当前执行阶段
        
        RAG 检索:
            rag_context_ids: RAG 上下文的文档 ID 列表
            rag_context_metadata: RAG 上下文元数据
        
        Message Bus 上下文:
            message_bus_summary: 压缩后的共识摘要
            message_bus_disagreements: 未解决的分歧点
            message_bus_key_decisions: 关键决策列表
        
        专家结果:
            specialist_result_ids: 专家结果的 ID 列表
            specialist_results_metadata: 专家结果元数据
        
        反思结果:
            reflection_result_id: 反思结果的 ID
            reflection_metadata: 反思元数据
        
        聚合响应:
            aggregated_response: 聚合后的响应
        
        迭代控制:
            iteration: 当前迭代次数
            max_iterations: 最大迭代次数
            retry_count: 当前重试次数
            max_retries: 最大重试次数
        
        错误跟踪:
            error: 当前错误信息
            error_history: 错误历史
            warnings: 警告信息
        
        消息历史:
            messages: 对话消息历史
        
        元数据:
            metadata: 自定义元数据
            created_at: 状态创建时间
            updated_at: 状态更新时间
        
        追踪信息:
            trace_id: OpenTelemetry trace ID
            span_id: OpenTelemetry span ID
        
        最终结果:
            final_answer: 最终答案
            needs_human_review: 是否需要人工审核
            human_review_id: 人工审核 ID
    """
    
    # ========== 核心会话信息 ==========
    session_id: str
    tenant_id: str
    user_id: str
    request_id: str
    
    # ========== 用户输入 ==========
    user_query: str
    query_timestamp: datetime
    
    # ========== 意图识别 ==========
    intent: Optional[IntentCategory]
    intent_confidence: float
    routing_strategy: Optional[str]
    target_specialists: List[SpecialistType]
    
    # ========== 编排模式 ==========
    orchestration_mode: OrchestrationMode
    current_phase: str
    
    # ========== RAG 检索（只存储引用） ==========
    rag_context_ids: List[str]
    rag_context_metadata: Dict[str, Any]
    
    # ========== Message Bus 上下文（压缩后） ==========
    message_bus_summary: Optional[str]
    message_bus_disagreements: List[str]
    message_bus_key_decisions: List[str]
    
    # ========== 专家结果（只存储引用） ==========
    specialist_result_ids: List[str]
    specialist_results_metadata: List[Dict[str, Any]]
    
    # ========== 反思结果 ==========
    reflection_result_id: Optional[str]
    reflection_metadata: Optional[Dict[str, Any]]
    
    # ========== 聚合响应 ==========
    aggregated_response: Optional[str]
    
    # ========== 迭代控制 ==========
    iteration: int
    max_iterations: int
    retry_count: int
    max_retries: int
    
    # ========== 错误跟踪 ==========
    error: Optional[str]
    error_history: List[str]
    warnings: List[str]
    
    # ========== 消息历史 ==========
    messages: List[Dict[str, Any]]
    
    # ========== 元数据 ==========
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    # ========== 追踪信息（用于 OpenTelemetry） ==========
    trace_id: Optional[str]
    span_id: Optional[str]
    
    # ========== 最终结果 ==========
    final_answer: Optional[str]
    needs_human_review: bool
    human_review_id: Optional[str]
