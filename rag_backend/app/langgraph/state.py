"""
LangGraph 状态定义

定义多智能体工作流的状态结构和类型
"""

from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional, Literal
import operator
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    """意图分类"""
    RAG_RETRIEVAL = "rag_retrieval"
    SINGLE_SPECIALIST = "single_specialist"
    MULTI_SPECIALIST = "multi_specialist"
    DIRECT_ANSWER = "direct_answer"
    HUMAN_REVIEW = "human_review"
    UNKNOWN = "unknown"


class SpecialistType(str, Enum):
    """专家类型"""
    FINANCE = "finance"
    TAX = "tax"
    LEGAL = "legal"
    REPORT = "report"
    REFLECTION = "reflection"


class QualityLevel(str, Enum):
    """质量等级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


class AgentMessage(BaseModel):
    """Agent 消息"""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpecialistResult(BaseModel):
    """专家结果"""
    specialist_type: SpecialistType
    query: str
    response: str
    confidence: float = Field(ge=0.0, le=1.0)
    tools_used: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class ReflectionResult(BaseModel):
    """反思结果"""
    quality_level: QualityLevel
    overall_score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    needs_human_review: bool = False
    revised_response: Optional[str] = None


class AgentState(TypedDict):
    """
    LangGraph 智能体状态
    
    这是整个多智能体工作流的核心状态定义。
    
    ⚠️ 关键设计：使用 Annotated[..., operator.add] 支持并行节点结果合并。
    当多个专家并行执行时，operator.add 会将结果合并而不是覆盖。
    """
    # 会话信息
    session_id: str
    tenant_id: str
    user_id: str
    
    # 用户输入
    user_query: str
    
    # 意图识别
    intent: Optional[str]
    intent_confidence: float
    
    # 路由信息
    routing_strategy: Optional[str]
    specialists_needed: Annotated[List[str], operator.add]
    
    # RAG 检索结果（使用 operator.add 并行合并）
    rag_context: Annotated[List[Dict[str, Any]], operator.add]
    
    # 专家结果列表（使用 operator.add 并行合并）
    # 多个专家并行执行时，每个专家的输出会被追加到列表中
    specialist_results: Annotated[List[Dict[str, Any]], operator.add]
    
    # 反思结果
    reflection_result: Optional[Dict[str, Any]]
    
    # 聚合响应
    aggregated_response: Optional[str]
    
    # 迭代控制
    iteration: int
    max_iterations: int
    
    # 重试计数
    retry_count: int
    max_retries: int
    
    # 错误跟踪
    error: Optional[str]
    error_history: List[str]
    
    # 消息历史（使用 operator.add 并行合并）
    messages: Annotated[List[Any], operator.add]
    
    # 元数据
    metadata: Dict[str, Any]
    
    # 最终结果
    final_answer: Optional[str]
    output: str  # 用于存放最终报告输出
    needs_human_review: bool
    
    # 追问状态（用于模糊输入处理）
    needs_clarification: bool
    clarification_request: Optional[Dict[str, Any]]


def create_initial_state(
    session_id: str,
    tenant_id: str,
    user_id: str,
    user_query: str,
    max_iterations: int = 10,
    max_retries: int = 3,
    **metadata
) -> AgentState:
    """
    创建初始状态
    
    Args:
        session_id: 会话ID
        tenant_id: 租户ID
        user_id: 用户ID
        user_query: 用户查询
        max_iterations: 最大迭代次数
        max_retries: 最大重试次数
        **metadata: 其他元数据
        
    Returns:
        AgentState: 初始状态
    """
    return AgentState(
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        user_query=user_query,
        intent=None,
        intent_confidence=0.0,
        routing_strategy=None,
        specialists_needed=[],
        rag_context=[],
        specialist_results=[],
        reflection_result=None,
        aggregated_response=None,
        iteration=0,
        max_iterations=max_iterations,
        retry_count=0,
        max_retries=max_retries,
        error=None,
        error_history=[],
        messages=[],
        metadata=metadata,
        final_answer=None,
        output="",
        needs_human_review=False,
        needs_clarification=False,
        clarification_request=None
    )


def update_state(state: AgentState, **updates) -> AgentState:
    """
    更新状态
    
    Args:
        state: 当前状态
        **updates: 要更新的字段
        
    Returns:
        AgentState: 更新后的状态
    """
    new_state = state.copy()
    for key, value in updates.items():
        if key in new_state:
            new_state[key] = value
    return new_state


def increment_iteration(state: AgentState) -> AgentState:
    """增加迭代计数"""
    return update_state(state, iteration=state["iteration"] + 1)


def add_error(state: AgentState, error: str) -> AgentState:
    """添加错误到历史"""
    return update_state(
        state,
        error=error,
        error_history=state["error_history"] + [error]
    )


def add_specialist_result(state: AgentState, result: SpecialistResult) -> AgentState:
    """添加专家结果"""
    return update_state(
        state,
        specialist_results=state["specialist_results"] + [result]
    )
