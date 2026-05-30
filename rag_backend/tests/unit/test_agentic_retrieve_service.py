"""
测试 EnterpriseAgentService._agentic_retrieve 多轮自主检索循环。

通过 monkeypatch unified_retriever.retrieve 隔离真实检索/LLM，
验证：累积去重、top_k 截断、retrieval_history/evaluation 透传、
"足够即停"与"达到 max_iterations 即停"两条终止路径，
以及注入 LLM bridge 后的智能评估 + 查询改写。
"""

import pytest
from unittest.mock import AsyncMock

import app.services.agent_service as agent_service_module
from app.services.agent_service import EnterpriseAgentService


def _svc(monkeypatch, bridge=None):
    """构造一个未初始化的 service 实例，并默认把 LLM bridge 置空（走规则版）。"""
    svc = EnterpriseAgentService.__new__(EnterpriseAgentService)
    monkeypatch.setattr(
        EnterpriseAgentService, "_build_agentic_llm_bridge",
        AsyncMock(return_value=bridge),
    )
    return svc


async def _run_agentic(svc, **kwargs):
    """消费 _agentic_retrieve 异步生成器：收集 progress 事件，返回 (result_dict, progress_list)。"""
    result = None
    progress = []
    async for kind, payload in svc._agentic_retrieve(**kwargs):
        if kind == "progress":
            progress.append(payload)
        else:
            result = payload
    return result, progress


def _make_retrieve(results_per_round, captured_queries=None):
    """构造一个 AsyncMock，按调用次数返回不同轮次的结果。"""
    calls = {"n": 0}

    async def _retrieve(*args, **kwargs):
        if captured_queries is not None:
            captured_queries.append(kwargs.get("query"))
        idx = min(calls["n"], len(results_per_round) - 1)
        calls["n"] += 1
        rag = results_per_round[idx]
        return {
            "rag_results": rag,
            "combined_context": "\n".join(r["content"] for r in rag),
            "mode": "HYBRID",
        }

    return _retrieve, calls


@pytest.mark.asyncio
async def test_agentic_stops_when_sufficient(monkeypatch):
    """首轮结果充分 → 只检索一轮（规则评估）。"""
    round1 = [
        {"id": str(i), "content": "企业所得税 税率 优惠 内容", "rerank_score": 1.0 - i * 0.1}
        for i in range(5)
    ]
    retrieve_fn, calls = _make_retrieve([round1])
    monkeypatch.setattr(agent_service_module.unified_retriever, "retrieve", AsyncMock(side_effect=retrieve_fn))
    svc = _svc(monkeypatch)

    result, progress = await _run_agentic(
        svc,
        query="企业所得税 税率 优惠",
        kb_id="kb1", session_id="s1", user_id="u1", tenant_id="t1",
        max_iterations=3, top_k=10, enable_rerank=True, enable_graph=False,
    )

    assert calls["n"] == 1
    assert len(result["retrieval_history"]) == 1
    assert result["retrieval_history"][0]["result_count"] == 5
    assert result["evaluation"]["is_sufficient"] is True
    assert result["mode"] == "AGENTIC"
    assert result["combined_context"]
    # 进度事件：至少包含一轮的 retrieval/evaluate
    assert any(p.get("stage") == "retrieval" for p in progress)
    assert any(p.get("stage") == "evaluate" for p in progress)


@pytest.mark.asyncio
async def test_agentic_stops_at_max_iterations(monkeypatch):
    """结果"不充分但不算无用"（中等分）→ 跑满 max_iterations 即停（规则评估）。

    构造每轮返回相同的 3 条、其中 1 条命中查询关键词，规则评估综合分约 0.47：
    既低于充分性阈值 0.7（不会"足够即停"），又高于前置短路阈值 0.2（不会被短路），
    因此会一直检索到 max_iterations。
    """
    mid = [[
        {"id": "1", "content": "企业所得税 的相关说明"},
        {"id": "2", "content": "无关内容甲"},
        {"id": "3", "content": "无关内容乙"},
    ]]
    retrieve_fn, calls = _make_retrieve(mid)
    monkeypatch.setattr(agent_service_module.unified_retriever, "retrieve", AsyncMock(side_effect=retrieve_fn))
    svc = _svc(monkeypatch)

    result, _progress = await _run_agentic(
        svc,
        query="企业所得税 优惠 政策",
        kb_id="kb1", session_id="s1", user_id="u1", tenant_id="t1",
        max_iterations=2, top_k=10, enable_rerank=True, enable_graph=False,
    )

    assert calls["n"] == 2
    assert len(result["retrieval_history"]) == 2


@pytest.mark.asyncio
async def test_agentic_short_circuits_on_hopeless_score(monkeypatch):
    """前置短路：首轮整体分极低（知识库基本无相关内容）→ 不再续检索，1 轮即停。"""
    poor = [[{"id": "x", "content": "完全无关的内容"}]]
    retrieve_fn, calls = _make_retrieve(poor)
    monkeypatch.setattr(agent_service_module.unified_retriever, "retrieve", AsyncMock(side_effect=retrieve_fn))
    svc = _svc(monkeypatch)

    result, _progress = await _run_agentic(
        svc,
        query="支付宝和移动支付什么关系",
        kb_id="kb1", session_id="s1", user_id="u1", tenant_id="t1",
        max_iterations=3, top_k=10, enable_rerank=True, enable_graph=False,
    )

    # 低分短路：只跑了 1 轮（而非 max_iterations=3）
    assert calls["n"] == 1
    assert len(result["retrieval_history"]) == 1


@pytest.mark.asyncio
async def test_agentic_dedup_and_top_k(monkeypatch):
    """跨轮累积去重，最终按 top_k 截断。"""
    round1 = [{"id": str(i), "content": f"片段{i}", "rerank_score": 0.5} for i in range(4)]
    round2 = [{"id": str(i), "content": f"片段{i}", "rerank_score": 0.9} for i in range(2, 8)]
    retrieve_fn, calls = _make_retrieve([round1, round2])
    monkeypatch.setattr(agent_service_module.unified_retriever, "retrieve", AsyncMock(side_effect=retrieve_fn))
    svc = _svc(monkeypatch)

    result, _progress = await _run_agentic(
        svc,
        query="zzz",
        kb_id="kb1", session_id="s1", user_id="u1", tenant_id="t1",
        max_iterations=2, top_k=3, enable_rerank=True, enable_graph=False,
    )

    assert len(result["rag_results"]) == 3
    assert all(c["rerank_score"] == 0.9 for c in result["rag_results"])


class _FakeBridge:
    """记录调用的假 LLM bridge：评估返回 JSON，改写返回新查询。"""

    def __init__(self):
        self.eval_calls = 0
        self.rewrite_calls = 0

    async def generate(self, prompt: str, max_tokens: int = 300) -> str:
        if "检索查询改写助手" in prompt:
            self.rewrite_calls += 1
            return "企业所得税优惠政策的具体适用条件"
        self.eval_calls += 1
        if self.eval_calls == 1:
            return ('```json\n{"coverage_score":0.3,"relevance_score":0.3,'
                    '"completeness_score":0.3,"is_sufficient":false,'
                    '"missing_aspects":["适用条件"],"reasoning":"信息不足"}\n```')
        return ('{"coverage_score":0.9,"relevance_score":0.9,'
                '"completeness_score":0.9,"is_sufficient":true,'
                '"missing_aspects":[],"reasoning":"信息充分"}')


@pytest.mark.asyncio
async def test_agentic_uses_llm_eval_and_rewrite(monkeypatch):
    """注入 LLM bridge：首轮 LLM 判定不足 → LLM 改写查询 → 次轮判定充分即停。"""
    rounds = [
        [{"id": "a", "content": "企业所得税概述"}],
        [{"id": "b", "content": "企业所得税优惠政策适用条件明细"}],
    ]
    captured = []
    retrieve_fn, calls = _make_retrieve(rounds, captured_queries=captured)
    monkeypatch.setattr(agent_service_module.unified_retriever, "retrieve", AsyncMock(side_effect=retrieve_fn))

    bridge = _FakeBridge()
    svc = _svc(monkeypatch, bridge=bridge)

    result, _progress = await _run_agentic(
        svc,
        query="企业所得税优惠",
        kb_id="kb1", session_id="s1", user_id="u1", tenant_id="t1",
        max_iterations=3, top_k=10, enable_rerank=True, enable_graph=True,
    )

    # 两轮：LLM 评估调用 2 次，改写 1 次
    assert calls["n"] == 2
    assert bridge.eval_calls == 2
    assert bridge.rewrite_calls == 1
    # 第二轮使用了 LLM 改写后的查询（带 ```json 围栏也能正确解析评估）
    assert captured[1] == "企业所得税优惠政策的具体适用条件"
    assert result["evaluation"]["is_sufficient"] is True
    assert result["evaluation"]["reasoning"] == "信息充分"
