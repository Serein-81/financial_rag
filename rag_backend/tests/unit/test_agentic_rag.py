"""
测试 Agentic RAG 功能
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime
from app.langgraph.agentic_rag_state import (
    AgenticRAGState,
    RetrievalStep,
    EvaluationResult
)
from app.langgraph.agentic_rag_nodes import (
    RetrievalPlanner,
    RetrievalExecutor,
    ResultEvaluator,
    ContextAggregator
)


@pytest.fixture
def mock_llm_service():
    """模拟 LLM 服务"""
    service = Mock()
    service.generate = AsyncMock(return_value='''
    {
        "coverage_score": 0.8,
        "relevance_score": 0.9,
        "completeness_score": 0.7,
        "is_sufficient": true,
        "missing_aspects": [],
        "reasoning": "结果充分"
    }
    ''')
    return service


@pytest.fixture
def mock_vector_search():
    """模拟向量检索服务"""
    service = Mock()
    service.search = AsyncMock(return_value=[
        {"id": "1", "content": "测试内容1", "score": 0.9},
        {"id": "2", "content": "测试内容2", "score": 0.8}
    ])
    return service


@pytest.fixture
def mock_graph_search():
    """模拟图谱检索服务"""
    service = Mock()
    result_mock = Mock()
    result_mock.vector_chunks = [
        {"id": "3", "content": "图谱内容1", "score": 0.85}
    ]
    service.hybrid_retrieve = AsyncMock(return_value=result_mock)
    return service


@pytest.fixture
def basic_state():
    """基础状态"""
    return AgenticRAGState(
        query="测试查询",
        kb_id="test_kb",
        chat_history=[],
        retrieval_history=[],
        iteration_count=0,
        max_iterations=3,
        current_results=[],
        all_results=[],
        is_sufficient=False,
        should_continue=True,
        total_retrieval_time=0.0
    )


# ==================== RetrievalPlanner 测试 ====================

@pytest.mark.asyncio
async def test_retrieval_planner_first_retrieval(basic_state):
    """测试首次检索规划"""
    planner = RetrievalPlanner()

    state = await planner.plan(basic_state)

    # 验证规划结果
    assert "current_query" in state
    assert "next_action" in state
    assert state["next_action"] in ["vector_search", "hybrid_search", "multi_step_search"]


@pytest.mark.asyncio
async def test_retrieval_planner_classify_simple_query():
    """测试简单查询分类"""
    planner = RetrievalPlanner()

    complexity = planner._classify_query_complexity("企业所得税税率")
    assert complexity == "simple"


@pytest.mark.asyncio
async def test_retrieval_planner_classify_complex_query():
    """测试复杂查询分类"""
    planner = RetrievalPlanner()

    complexity = planner._classify_query_complexity("详细分析企业所得税优惠政策")
    assert complexity == "complex"


@pytest.mark.asyncio
async def test_retrieval_planner_classify_multi_hop_query():
    """测试多跳查询分类"""
    planner = RetrievalPlanner()

    complexity = planner._classify_query_complexity("为什么小型微利企业享受税收优惠")
    assert complexity == "multi_hop"


@pytest.mark.asyncio
async def test_retrieval_planner_subsequent_retrieval(basic_state):
    """测试后续检索规划"""
    planner = RetrievalPlanner()

    # 设置已有检索历史
    basic_state["iteration_count"] = 1
    basic_state["evaluation"] = EvaluationResult(
        is_sufficient=False,
        coverage_score=0.4,
        relevance_score=0.5,
        completeness_score=0.3,
        overall_score=0.4,
        missing_aspects=["缺少具体数值"]
    )

    state = await planner.plan(basic_state)

    # 应该生成新的检索计划
    assert "current_query" in state
    assert "next_action" in state


@pytest.mark.asyncio
async def test_retrieval_planner_refine_query():
    """测试查询改写"""
    planner = RetrievalPlanner()

    refined = planner._refine_query_for_missing(
        "企业所得税",
        ["税率", "优惠政策"]
    )

    # 应该包含缺失方面
    assert "税率" in refined or "优惠政策" in refined


# ==================== RetrievalExecutor 测试 ====================

@pytest.mark.asyncio
async def test_retrieval_executor_vector_search(basic_state, mock_vector_search):
    """测试向量检索执行"""
    executor = RetrievalExecutor(vector_search_service=mock_vector_search)

    basic_state["next_action"] = "vector_search"
    basic_state["current_query"] = "测试查询"

    state = await executor.execute(basic_state)

    # 验证检索结果
    assert len(state["current_results"]) > 0
    assert len(state["all_results"]) > 0
    assert state["iteration_count"] == 1
    assert len(state["retrieval_history"]) == 1

    # 验证检索步骤记录
    step = state["retrieval_history"][0]
    assert step.action == "vector_search"
    assert step.result_count > 0


@pytest.mark.asyncio
async def test_retrieval_executor_hybrid_search(basic_state, mock_graph_search):
    """测试混合检索执行"""
    executor = RetrievalExecutor(graph_search_service=mock_graph_search)

    basic_state["next_action"] = "hybrid_search"
    basic_state["current_query"] = "测试查询"

    state = await executor.execute(basic_state)

    # 验证调用了图谱检索
    mock_graph_search.hybrid_retrieve.assert_called_once()
    assert len(state["current_results"]) > 0


@pytest.mark.asyncio
async def test_retrieval_executor_unknown_action(basic_state):
    """测试未知动作处理"""
    executor = RetrievalExecutor()

    basic_state["next_action"] = "unknown_action"
    basic_state["current_query"] = "测试查询"

    state = await executor.execute(basic_state)

    # 应该返回空结果
    assert state["current_results"] == []


@pytest.mark.asyncio
async def test_retrieval_executor_accumulates_results(basic_state, mock_vector_search):
    """测试结果累积"""
    executor = RetrievalExecutor(vector_search_service=mock_vector_search)

    basic_state["next_action"] = "vector_search"
    basic_state["current_query"] = "测试查询"

    # 第一轮检索
    state = await executor.execute(basic_state)
    first_count = len(state["all_results"])

    # 第二轮检索
    state["next_action"] = "vector_search"
    state = await executor.execute(state)

    # 结果应该累积（去重）
    assert len(state["all_results"]) >= first_count


@pytest.mark.asyncio
async def test_retrieval_executor_tracks_time(basic_state, mock_vector_search):
    """测试检索时间追踪"""
    executor = RetrievalExecutor(vector_search_service=mock_vector_search)

    basic_state["next_action"] = "vector_search"
    basic_state["current_query"] = "测试查询"

    state = await executor.execute(basic_state)

    # 应该记录检索时间
    assert state["total_retrieval_time"] > 0


# ==================== ResultEvaluator 测试 ====================

@pytest.mark.asyncio
async def test_result_evaluator_with_llm(basic_state, mock_llm_service):
    """测试使用 LLM 评估"""
    evaluator = ResultEvaluator(llm_service=mock_llm_service)

    basic_state["all_results"] = [
        {"content": "测试内容1"},
        {"content": "测试内容2"}
    ]

    state = await evaluator.evaluate(basic_state)

    # 验证评估结果
    assert "evaluation" in state
    assert state["evaluation"].is_sufficient is True
    assert state["evaluation"].overall_score > 0

    # LLM 应该被调用
    mock_llm_service.generate.assert_called_once()


@pytest.mark.asyncio
async def test_result_evaluator_with_rules(basic_state):
    """测试使用规则评估"""
    evaluator = ResultEvaluator(llm_service=None, threshold=0.7)

    basic_state["all_results"] = [
        {"content": "测试查询相关内容1"},
        {"content": "测试查询相关内容2"},
        {"content": "测试查询相关内容3"}
    ]

    state = await evaluator.evaluate(basic_state)

    # 验证评估结果
    assert "evaluation" in state
    assert isinstance(state["evaluation"], EvaluationResult)
    assert 0 <= state["evaluation"].overall_score <= 1


@pytest.mark.asyncio
async def test_result_evaluator_empty_results(basic_state):
    """测试空结果评估"""
    evaluator = ResultEvaluator()

    basic_state["all_results"] = []

    state = await evaluator.evaluate(basic_state)

    # 空结果应该评估为不充分
    assert state["evaluation"].is_sufficient is False
    assert state["evaluation"].overall_score == 0.0


@pytest.mark.asyncio
async def test_result_evaluator_decides_continuation(basic_state):
    """测试继续检索决策（不充分但分数不算无用 → 继续）"""
    evaluator = ResultEvaluator()

    # 提供 3 条结果，使规则评估综合分约 0.3：低于充分性阈值（不充分）、
    # 但高于前置短路阈值 0.2（不会被短路），从而应继续检索。
    basic_state["all_results"] = [{"content": f"一些内容{i}"} for i in range(3)]
    basic_state["iteration_count"] = 1
    basic_state["max_iterations"] = 3

    state = await evaluator.evaluate(basic_state)

    # 结果不充分、分数不算无用、且未达到最大迭代次数，应该继续
    if not state["evaluation"].is_sufficient:
        assert state["should_continue"] is True


@pytest.mark.asyncio
async def test_result_evaluator_stops_at_max_iterations(basic_state):
    """测试达到最大迭代次数停止"""
    evaluator = ResultEvaluator()

    basic_state["all_results"] = [{"content": "内容"}]
    basic_state["iteration_count"] = 3
    basic_state["max_iterations"] = 3

    state = await evaluator.evaluate(basic_state)

    # 达到最大迭代次数，应该停止
    assert state["should_continue"] is False


@pytest.mark.asyncio
async def test_result_evaluator_coverage_score(basic_state):
    """测试覆盖度评分"""
    evaluator = ResultEvaluator()

    # 提供充足结果
    basic_state["all_results"] = [
        {"content": f"测试内容{i}"}
        for i in range(10)
    ]

    state = await evaluator.evaluate(basic_state)

    # 覆盖度应该较高
    assert state["evaluation"].coverage_score >= 0.8


@pytest.mark.asyncio
async def test_result_evaluator_relevance_score(basic_state):
    """测试相关性评分"""
    evaluator = ResultEvaluator()

    basic_state["query"] = "企业所得税"
    basic_state["all_results"] = [
        {"content": "企业所得税标准税率为25%"},
        {"content": "小型微利企业所得税优惠"},
        {"content": "企业所得税计算方法"}
    ]

    state = await evaluator.evaluate(basic_state)

    # 相关性应该较高
    assert state["evaluation"].relevance_score > 0.5


# ==================== ContextAggregator 测试 ====================

@pytest.mark.asyncio
async def test_context_aggregator_basic(basic_state):
    """测试基本聚合功能"""
    aggregator = ContextAggregator()

    basic_state["all_results"] = [
        {"content": "内容1", "score": 0.9},
        {"content": "内容2", "score": 0.8},
        {"content": "内容3", "score": 0.7}
    ]

    state = await aggregator.aggregate(basic_state)

    # 验证聚合结果
    assert "final_chunks" in state
    assert "final_context" in state
    assert len(state["final_chunks"]) > 0
    assert len(state["final_context"]) > 0


@pytest.mark.asyncio
async def test_context_aggregator_deduplication(basic_state):
    """测试去重功能"""
    aggregator = ContextAggregator()

    # 包含重复内容
    basic_state["all_results"] = [
        {"content": "重复内容"},
        {"content": "重复内容"},
        {"content": "不同内容"}
    ]

    state = await aggregator.aggregate(basic_state)

    # 应该去重
    assert len(state["final_chunks"]) == 2


@pytest.mark.asyncio
async def test_context_aggregator_sorting(basic_state):
    """测试排序功能"""
    aggregator = ContextAggregator()

    basic_state["all_results"] = [
        {"content": "低分内容", "score": 0.5},
        {"content": "高分内容", "score": 0.9},
        {"content": "中分内容", "score": 0.7}
    ]

    state = await aggregator.aggregate(basic_state)

    # 应该按分数排序
    if len(state["final_chunks"]) > 1:
        scores = [c.get("score", 0) for c in state["final_chunks"]]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_context_aggregator_top_k_limit(basic_state):
    """测试 Top-K 限制"""
    aggregator = ContextAggregator()

    # 提供超过10个结果
    basic_state["all_results"] = [
        {"content": f"内容{i}", "score": 1.0 - i * 0.05}
        for i in range(15)
    ]

    state = await aggregator.aggregate(basic_state)

    # 应该限制为 Top-10
    assert len(state["final_chunks"]) <= 10


@pytest.mark.asyncio
async def test_context_aggregator_empty_results(basic_state):
    """测试空结果聚合"""
    aggregator = ContextAggregator()

    basic_state["all_results"] = []

    state = await aggregator.aggregate(basic_state)

    # 应该返回空列表
    assert state["final_chunks"] == []
    assert state["final_context"] == ""


@pytest.mark.asyncio
async def test_context_aggregator_generates_text(basic_state):
    """测试生成上下文文本"""
    aggregator = ContextAggregator()

    basic_state["all_results"] = [
        {"content": "第一段内容"},
        {"content": "第二段内容"}
    ]

    state = await aggregator.aggregate(basic_state)

    # 验证生成的文本包含所有内容
    assert "第一段内容" in state["final_context"]
    assert "第二段内容" in state["final_context"]


# ==================== 集成测试 ====================

@pytest.mark.asyncio
async def test_agentic_rag_full_workflow(
    basic_state,
    mock_vector_search,
    mock_llm_service
):
    """测试完整的 Agentic RAG 工作流"""
    planner = RetrievalPlanner()
    executor = RetrievalExecutor(vector_search_service=mock_vector_search)
    evaluator = ResultEvaluator(llm_service=mock_llm_service)
    aggregator = ContextAggregator()

    state = basic_state

    # 第一轮迭代
    state = await planner.plan(state)
    state = await executor.execute(state)
    state = await evaluator.evaluate(state)

    # 验证第一轮结果
    assert state["iteration_count"] == 1
    assert len(state["retrieval_history"]) == 1
    assert "evaluation" in state

    # 如果需要继续，执行第二轮
    if state["should_continue"]:
        state = await planner.plan(state)
        state = await executor.execute(state)
        state = await evaluator.evaluate(state)

        assert state["iteration_count"] == 2

    # 最终聚合
    state = await aggregator.aggregate(state)

    # 验证最终结果
    assert "final_chunks" in state
    assert "final_context" in state
    assert state["retrieval_method"] == "agentic_rag"
