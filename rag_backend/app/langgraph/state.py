"""
LangGraph 状态定义

使用 Pydantic BaseModel 替代 TypedDict，提供运行时类型校验。
每个 state 写入操作（specialist_results、rag_context 等）在 LangGraph
的 reducer 合并时获得自动校验，非法数据在写入瞬间被拦截。
"""

from typing import Annotated, List, Dict, Any, Optional
import operator
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# =========================================================================
# 枚举
# =========================================================================

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


# =========================================================================
# 结构化数据模型（带运行时校验）
# =========================================================================

class AgentMessage(BaseModel):
    """Agent 消息"""
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpecialistResult(BaseModel):
    """专家结果"""
    specialist_type: SpecialistType
    query: str
    response: str
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
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
    skipped: bool = False  # 🆕 标记反思是否被跳过（异常/降级）


# =========================================================================
# 智能体状态（Pydantic BaseModel 替代 TypedDict）
# =========================================================================

class AgentState(BaseModel):
    """
    LangGraph 智能体状态 — Pydantic BaseModel 版

    关键变更：
    - TypedDict → BaseModel：所有字段在写入时获得类型校验
    - Annotated [+ operator.add]：LangGraph reducer 保持正常工作
    - field_validator：在边界拦截非法数据

    ⚠️ 与 TypedDict 的使用差异：
    - 读：state["field"] → state.field
    - 写：state["field"] = x → state.field = x
      （但通过 LangGraph 的 return {**state, ...} 方式仍然兼容）
    """

    # ── 会话信息 ──
    session_id: str = ""
    tenant_id: str = ""
    user_id: str = ""

    # ── 用户输入 ──
    user_query: str = Field(default="", max_length=10000)

    # ── 意图识别 ──
    intent: Optional[str] = None
    intent_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # ── 路由信息 ──
    routing_strategy: Optional[str] = None
    specialists_needed: List[str] = Field(default_factory=list)

    # ── RAG 检索结果 ──
    rag_context: Annotated[List[Dict[str, Any]], operator.add] = Field(default_factory=list)

    # ── 图谱路径检索结果 ──
    graph_path_context: Optional[Dict[str, Any]] = None

    # ── 专家结果列表 ──
    specialist_results: Annotated[List[Dict[str, Any]], operator.add] = Field(default_factory=list)

    # ── 反思结果 ──
    reflection_result: Optional[Dict[str, Any]] = None
    enable_reflection: bool = True

    # ── 聚合响应 ──
    aggregated_response: Optional[str] = None

    # ── 迭代控制 ──
    iteration: int = 0
    max_iterations: int = Field(default=10, ge=1, le=100)

    # ── 重试计数 ──
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0, le=20)

    # ── 追踪 ──
    trace_id: Optional[str] = None  # Agent Tracer 追踪 ID

    # ── 错误跟踪 ──
    error: Optional[str] = None
    error_history: List[str] = Field(default_factory=list)

    # ── 消息历史 ──
    messages: Annotated[List[Any], operator.add] = Field(default_factory=list)

    # ── 元数据 ──
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # ── 技能系统 ──
    activated_skills: Annotated[List[Dict[str, Any]], operator.add] = Field(default_factory=list)

    # ── 最终结果 ──
    final_answer: Optional[str] = None
    output: str = ""
    needs_human_review: bool = False

    # ── 追问状态 ──
    needs_clarification: bool = False
    clarification_request: Optional[Dict[str, Any]] = None

    # ── 复杂度路由（Adaptive RAG） ──
    # trivial: 闲聊/问候，跳过整条链路
    # factual: 单跳事实，走 RAG + 单专家
    # reasoning: 多跳推理，走完整链路
    # deep: 调研型，预留给 Orchestrator-Worker
    complexity: Optional[str] = None

    # ── 检索质量评分（CRAG 闭环） ──
    retrieval_quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    missing_aspects: List[str] = Field(default_factory=list)
    retrieval_iterations: int = Field(default=0, ge=0)
    max_retrieval_iterations: int = Field(default=2, ge=0, le=5)
    rewritten_query: Optional[str] = None

    # ── 忠实度检查（Hallucination Checker） ──
    faithfulness_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    unfaithful_sentences: List[str] = Field(default_factory=list)
    regenerate_count: int = Field(default=0, ge=0)
    max_regenerate_count: int = Field(default=1, ge=0, le=3)

    # ── 兼容 TypedDict 的 dict-style API ──

    def __getitem__(self, key):
        """支持 state['field'] 读取"""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        """支持 state['field'] = value 写入"""
        setattr(self, key, value)

    def __iter__(self):
        """支持 dict(state) 和 {**state} 解包（yield keys）"""
        return iter(self.model_dump().keys())

    def get(self, key, default=None):
        """支持 state.get('field', default)"""
        return getattr(self, key, default)

    def copy(self):
        """兼容 TypedDict 的 .copy() 方法"""
        return self.model_copy(deep=True)

    def setdefault(self, key, default=None):
        """兼容 TypedDict 的 .setdefault() 方法"""
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        # 属性不存在或为 None — 设置为默认值
        setattr(self, key, default)
        return default

    def keys(self):
        return self.model_dump().keys()

    def values(self):
        return self.model_dump().values()

    def items(self):
        return self.model_dump().items()

    # ── 校验 ──
    @field_validator("user_query")
    @classmethod
    def query_not_empty(cls, v):
        if v and not v.strip():
            raise ValueError("user_query cannot be only whitespace")
        return v

    model_config = {
        "extra": "forbid",  # 禁止写入未定义的字段
        "validate_assignment": True,  # 赋值时校验
        "use_enum_values": False,
        "arbitrary_types_allowed": False,
    }


# =========================================================================
# 辅助函数
# =========================================================================

def create_initial_state(
    session_id: str,
    tenant_id: str,
    user_id: str,
    user_query: str,
    max_iterations: int = 10,
    max_retries: int = 3,
    messages: Optional[List[Any]] = None,
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
        messages: 历史消息列表
        **metadata: 其他元数据（enable_reflection, entities, trace_id 等）

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
        enable_reflection=metadata.get("enable_reflection", True),
        aggregated_response=None,
        activated_skills=[],
        iteration=0,
        max_iterations=max_iterations,
        retry_count=0,
        max_retries=max_retries,
        trace_id=metadata.get("trace_id"),
        error=None,
        error_history=[],
        messages=messages or [],
        metadata=metadata,
        final_answer=None,
        output="",
        needs_human_review=False,
        needs_clarification=False,
        clarification_request=None
    )


def update_state(state: AgentState, **updates) -> AgentState:
    """创建新的 state 实例并应用更新"""
    new_state = state.model_copy(deep=True)
    for key, value in updates.items():
        if hasattr(new_state, key):
            setattr(new_state, key, value)
    return new_state


def increment_iteration(state: AgentState) -> AgentState:
    """增加迭代计数"""
    return update_state(state, iteration=state.iteration + 1)


def add_error(state: AgentState, error: str) -> AgentState:
    """添加错误到历史"""
    return update_state(
        state,
        error=error,
        error_history=state.error_history + [error]
    )


def add_specialist_result(state: AgentState, result: SpecialistResult) -> AgentState:
    """添加专家结果"""
    return update_state(
        state,
        specialist_results=state.specialist_results + [result.model_dump()]
    )
