"""
Agentic RAG 状态定义

定义自主检索 Agent 的状态结构，支持多轮迭代检索。
"""

from typing import List, Dict, Any, Optional, TypedDict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RetrievalStep:
    """单次检索步骤"""
    step_number: int
    action: str  # "vector_search" | "graph_traverse" | "refine_query" | "web_search"
    query: str
    parameters: Dict[str, Any]
    results: List[Dict[str, Any]] = field(default_factory=list)
    result_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvaluationResult:
    """检索结果评估"""
    is_sufficient: bool  # 是否足够回答问题
    coverage_score: float  # 覆盖度 0-1
    relevance_score: float  # 相关性 0-1
    completeness_score: float  # 完整性 0-1
    overall_score: float  # 综合评分 0-1
    missing_aspects: List[str] = field(default_factory=list)  # 缺失的方面
    reasoning: str = ""  # 评估理由


class AgenticRAGState(TypedDict, total=False):
    """
    Agentic RAG 状态

    支持多轮迭代检索的状态管理。
    """
    # 输入
    query: str  # 用户查询
    kb_id: str  # 知识库 ID
    chat_history: List[Dict[str, str]]  # 对话历史

    # 检索历史
    retrieval_history: List[RetrievalStep]  # 检索步骤历史
    iteration_count: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数

    # 当前状态
    current_query: str  # 当前检索查询（可能经过改写）
    current_results: List[Dict[str, Any]]  # 当前检索结果
    all_results: List[Dict[str, Any]]  # 所有检索结果（累积）

    # 评估结果
    evaluation: Optional[EvaluationResult]  # 最新评估结果
    is_sufficient: bool  # 是否已足够

    # 决策
    next_action: Optional[str]  # 下一步动作
    should_continue: bool  # 是否继续检索

    # 输出
    final_context: str  # 最终上下文
    final_chunks: List[Dict[str, Any]]  # 最终文档块

    # 元数据
    total_retrieval_time: float  # 总检索时间（秒）
    retrieval_method: str  # 检索方法标识
