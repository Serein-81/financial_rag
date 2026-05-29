"""
Unit tests for app/langgraph/quality_nodes.py

Covers:
- RetrievalGrader (rule + LLM mode)
- QueryRewriter (rule + LLM mode)
- FaithfulnessChecker (rule + LLM mode)
- Conditional routing (route_after_grader, route_after_faithfulness, route_by_complexity)
- Complexity inference helper
"""

from __future__ import annotations

import pytest

from app.langgraph.state import AgentState, create_initial_state
from app.langgraph.quality_nodes import (
    RetrievalGrader,
    QueryRewriter,
    FaithfulnessChecker,
)
from app.langgraph.conditional import (
    route_after_grader,
    route_after_faithfulness,
    route_by_complexity,
)
from app.langgraph.nodes import _infer_complexity, _build_aggregator_query_with_hint


# =========================================================================
# Fakes
# =========================================================================

class FakeLLM:
    """Records prompts and returns scripted responses."""

    def __init__(self, response: str = "{}"):
        self.response = response
        self.calls: list[str] = []

    async def generate(self, prompt: str, max_tokens: int = 300) -> str:
        self.calls.append(prompt)
        return self.response


def _make_state(query: str = "小型微利企业税率是多少？", **overrides) -> AgentState:
    state = create_initial_state(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        user_query=query,
    )
    for k, v in overrides.items():
        setattr(state, k, v)
    return state


def _chunk(content: str, **extra) -> dict:
    return {"content": content, **extra}


# =========================================================================
# RetrievalGrader
# =========================================================================

class TestRetrievalGrader:
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero_score(self):
        state = _make_state(rag_context=[])
        grader = RetrievalGrader()
        result = await grader.grade(state)
        assert result.retrieval_quality_score == 0.0
        assert result.missing_aspects == ["没有检索到任何文档"]

    @pytest.mark.asyncio
    async def test_rule_mode_high_keyword_overlap_passes(self):
        state = _make_state(
            query="小型微利企业税率",
            rag_context=[
                _chunk("小型微利企业的所得税税率为20%"),
                _chunk("小型微利企业认定标准包括年应纳税所得额"),
                _chunk("小型微利企业税率优惠政策"),
                _chunk("小型微利企业税收减免"),
                _chunk("小型微利企业适用税率"),
            ],
        )
        grader = RetrievalGrader()  # no LLM → rules
        result = await grader.grade(state)
        assert result.retrieval_quality_score >= 0.6

    @pytest.mark.asyncio
    async def test_rule_mode_low_overlap_fails(self):
        state = _make_state(
            query="区块链共识算法的拜占庭容错原理",
            rag_context=[_chunk("今天天气很好"), _chunk("猫吃鱼")],
        )
        grader = RetrievalGrader()
        result = await grader.grade(state)
        assert result.retrieval_quality_score < 0.6
        assert len(result.missing_aspects) >= 1

    @pytest.mark.asyncio
    async def test_llm_mode_uses_returned_json(self):
        state = _make_state(rag_context=[_chunk("税率20%")])
        llm = FakeLLM(
            response='{"score": 0.92, "is_sufficient": true, "missing_aspects": []}'
        )
        grader = RetrievalGrader(llm_service=llm)
        result = await grader.grade(state)
        assert result.retrieval_quality_score == pytest.approx(0.92)
        assert result.missing_aspects == []
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_llm_mode_falls_back_to_rules_on_bad_json(self):
        state = _make_state(
            query="税率",
            rag_context=[_chunk("税率为20%"), _chunk("税率说明")],
        )
        llm = FakeLLM(response="not json at all")
        grader = RetrievalGrader(llm_service=llm)
        result = await grader.grade(state)
        # 降级到规则后仍能给出一个评分，不是 None
        assert result.retrieval_quality_score is not None

    @pytest.mark.asyncio
    async def test_llm_response_with_extra_text_extracts_json(self):
        state = _make_state(rag_context=[_chunk("税率20%")])
        llm = FakeLLM(
            response='这是评估结果：{"score": 0.5, "missing_aspects": ["税收优惠条件"]}'
        )
        grader = RetrievalGrader(llm_service=llm)
        result = await grader.grade(state)
        assert result.retrieval_quality_score == pytest.approx(0.5)
        assert "税收优惠条件" in result.missing_aspects


# =========================================================================
# QueryRewriter
# =========================================================================

class TestQueryRewriter:
    @pytest.mark.asyncio
    async def test_rule_mode_appends_missing_aspect(self):
        state = _make_state(
            query="小型微利企业",
            missing_aspects=["具体税率数值"],
            retrieval_iterations=0,
            rag_context=[_chunk("a"), _chunk("b")],
        )
        rewriter = QueryRewriter()
        result = await rewriter.rewrite(state)
        assert result.rewritten_query is not None
        assert "具体税率数值" in result.rewritten_query
        assert result.retrieval_iterations == 1
        # 必须清空旧 context，让下一轮 rag_retrieval 重检
        assert result.rag_context == []
        assert result.retrieval_quality_score is None

    @pytest.mark.asyncio
    async def test_rule_mode_with_no_missing_aspects(self):
        state = _make_state(query="测试", missing_aspects=[])
        rewriter = QueryRewriter()
        result = await rewriter.rewrite(state)
        assert result.rewritten_query is not None
        assert "测试" in result.rewritten_query

    @pytest.mark.asyncio
    async def test_llm_mode_uses_returned_text(self):
        state = _make_state(missing_aspects=["税率"])
        llm = FakeLLM(response="  小型微利企业的具体所得税税率   ")
        rewriter = QueryRewriter(llm_service=llm)
        result = await rewriter.rewrite(state)
        assert result.rewritten_query == "小型微利企业的具体所得税税率"

    @pytest.mark.asyncio
    async def test_iteration_counter_increments(self):
        state = _make_state(
            missing_aspects=["x"],
            retrieval_iterations=1,
        )
        rewriter = QueryRewriter()
        result = await rewriter.rewrite(state)
        assert result.retrieval_iterations == 2


# =========================================================================
# FaithfulnessChecker
# =========================================================================

class TestFaithfulnessChecker:
    @pytest.mark.asyncio
    async def test_skips_when_no_answer(self):
        state = _make_state(aggregated_response=None, rag_context=[_chunk("x")])
        checker = FaithfulnessChecker()
        result = await checker.check(state)
        assert result.faithfulness_score == 1.0
        assert result.unfaithful_sentences == []

    @pytest.mark.asyncio
    async def test_skips_when_no_context(self):
        state = _make_state(
            aggregated_response="一些答案",
            rag_context=[],
        )
        checker = FaithfulnessChecker()
        result = await checker.check(state)
        assert result.faithfulness_score == 1.0

    @pytest.mark.asyncio
    async def test_rule_mode_detects_unsupported_sentence(self):
        state = _make_state(
            aggregated_response="小型微利企业税率20%。火星上有外星人。",
            rag_context=[_chunk("小型微利企业税率为20%，享受税收优惠政策。")],
        )
        checker = FaithfulnessChecker()
        result = await checker.check(state)
        assert result.faithfulness_score < 1.0
        # 火星那句应被标记
        assert any("火星" in s for s in result.unfaithful_sentences)

    @pytest.mark.asyncio
    async def test_rule_mode_fully_supported_answer(self):
        state = _make_state(
            aggregated_response="小型微利企业税率为20%。",
            rag_context=[
                _chunk("小型微利企业适用所得税税率为20%，是国家税收优惠政策。")
            ],
        )
        checker = FaithfulnessChecker()
        result = await checker.check(state)
        assert result.faithfulness_score == 1.0
        assert result.unfaithful_sentences == []

    @pytest.mark.asyncio
    async def test_llm_mode_uses_returned_json(self):
        state = _make_state(
            aggregated_response="答案A。答案B。",
            rag_context=[_chunk("context")],
        )
        llm = FakeLLM(
            response='{"score": 0.55, "unfaithful_sentences": ["答案B。"]}'
        )
        checker = FaithfulnessChecker(llm_service=llm)
        result = await checker.check(state)
        assert result.faithfulness_score == pytest.approx(0.55)
        assert "答案B。" in result.unfaithful_sentences


# =========================================================================
# Conditional routing
# =========================================================================

class TestRouting:
    def test_route_after_grader_proceeds_on_high_score(self):
        state = _make_state(
            retrieval_quality_score=0.85,
            retrieval_iterations=0,
            max_retrieval_iterations=2,
        )
        assert route_after_grader(state) == "proceed"

    def test_route_after_grader_rewrites_on_low_score(self):
        state = _make_state(
            retrieval_quality_score=0.3,
            retrieval_iterations=0,
            max_retrieval_iterations=2,
        )
        assert route_after_grader(state) == "rewrite"

    def test_route_after_grader_proceeds_when_at_iteration_limit(self):
        state = _make_state(
            retrieval_quality_score=0.3,
            retrieval_iterations=2,
            max_retrieval_iterations=2,
        )
        assert route_after_grader(state) == "proceed"

    def test_route_after_grader_handles_none_score(self):
        state = _make_state(retrieval_quality_score=None, retrieval_iterations=0)
        # None → 0.0 → rewrite
        assert route_after_grader(state) == "rewrite"

    def test_route_after_faithfulness_proceeds_on_high_score(self):
        state = _make_state(
            faithfulness_score=0.9,
            regenerate_count=0,
            max_regenerate_count=1,
        )
        assert route_after_faithfulness(state) == "proceed"

    def test_route_after_faithfulness_regenerates_on_low_score(self):
        state = _make_state(
            faithfulness_score=0.4,
            regenerate_count=0,
            max_regenerate_count=1,
        )
        assert route_after_faithfulness(state) == "regenerate"

    def test_route_after_faithfulness_caps_regenerate(self):
        state = _make_state(
            faithfulness_score=0.4,
            regenerate_count=1,
            max_regenerate_count=1,
        )
        assert route_after_faithfulness(state) == "proceed"

    def test_route_by_complexity_trivial_short_circuits(self):
        state = _make_state(complexity="trivial")
        assert route_by_complexity(state) == "direct_answer"

    def test_route_by_complexity_factual_does_not_short_circuit(self):
        state = _make_state(complexity="factual")
        assert route_by_complexity(state) is None

    def test_route_by_complexity_none_does_not_short_circuit(self):
        state = _make_state(complexity=None)
        assert route_by_complexity(state) is None


# =========================================================================
# Complexity inference
# =========================================================================

class TestComplexityInference:
    @pytest.mark.parametrize("q", ["你好", "hello", "嗨", "  ", "谢谢", "hi!"])
    def test_greeting_is_trivial(self, q):
        assert _infer_complexity(q) == "trivial"

    def test_short_query_is_trivial(self):
        assert _infer_complexity("ok") == "trivial"

    def test_reasoning_keyword_is_reasoning(self):
        assert _infer_complexity("为什么小型微利企业有税率优惠？") == "reasoning"

    def test_long_factual_query(self):
        assert (
            _infer_complexity("小型微利企业的所得税税率是多少") == "factual"
        )

    def test_agent_complexity_high_maps_to_reasoning(self):
        class FakeComplexity:
            value = "high"

        assert _infer_complexity("一个普通问题", FakeComplexity()) == "reasoning"

    def test_agent_complexity_very_high_maps_to_deep(self):
        class FakeComplexity:
            value = "very_high"

        assert _infer_complexity("一个深度调研问题", FakeComplexity()) == "deep"


# =========================================================================
# Aggregator regenerate hint (closes the faithfulness loop)
# =========================================================================

class TestAggregatorRegenerateHint:
    def test_first_pass_query_unchanged(self):
        state = _make_state(
            query="小型微利企业税率",
            regenerate_count=0,
            unfaithful_sentences=[],
        )
        result = _build_aggregator_query_with_hint(state)
        assert result == "小型微利企业税率"

    def test_first_pass_with_unfaithful_but_zero_regen_unchanged(self):
        # 边界：regen=0 即使有 unfaithful 也不应注入（这是第一次生成，没有上一轮）
        state = _make_state(
            query="问题",
            regenerate_count=0,
            unfaithful_sentences=["某句"],
        )
        result = _build_aggregator_query_with_hint(state)
        assert result == "问题"

    def test_regenerate_injects_hint_into_query(self):
        state = _make_state(
            query="小型微利企业税率",
            regenerate_count=1,
            unfaithful_sentences=["火星上有外星人。", "GDP是负数。"],
        )
        result = _build_aggregator_query_with_hint(state)
        assert "小型微利企业税率" in result
        assert "忠实度修正第 1 次" in result
        assert "火星上有外星人。" in result
        assert "GDP是负数。" in result
        assert "严格基于检索到的资料" in result

    def test_regenerate_with_empty_unfaithful_unchanged(self):
        # regen>0 但 unfaithful 为空时，不注入（异常情况兜底）
        state = _make_state(
            query="问题",
            regenerate_count=1,
            unfaithful_sentences=[],
        )
        result = _build_aggregator_query_with_hint(state)
        assert result == "问题"

    def test_regenerate_caps_at_five_unfaithful_sentences(self):
        # 超过 5 句的 unfaithful 只取前 5 句（防止 prompt 爆炸）
        state = _make_state(
            query="问题",
            regenerate_count=1,
            unfaithful_sentences=[f"句{i}" for i in range(10)],
        )
        result = _build_aggregator_query_with_hint(state)
        for i in range(5):
            assert f"句{i}" in result
        # 第 5 句之后不应出现
        assert "句9" not in result
