"""
回归测试：UnifiedRetriever._mmr_rerank 的性能与正确性。

旧实现在双重循环里逐个 get_embedding，对 ~20 候选会发起上百次串行 embedding
网络请求，单轮检索阻塞 ~40s。本测试锁定：
1. 无论候选多少，embedding 网络请求只发 2 次（1 次 query + 1 次批量 candidates）；
2. MMR 多样性用"已选文档"向量比较（修复旧代码误用 query 向量的 bug）；
3. 返回数量受 top_k 约束。
"""

import pytest
from unittest.mock import AsyncMock

import app.services.unified_retriever as ur_module
from app.services.unified_retriever import UnifiedRetriever


def _cand(i, text):
    return {"content": text, "rerank_score": 1.0 - i * 0.01}


@pytest.mark.asyncio
async def test_mmr_batches_embeddings(monkeypatch):
    retriever = UnifiedRetriever()

    # 构造 20 个候选（超过 top_k，触发 MMR 循环）
    cands = [_cand(i, f"候选文档内容 {i} " * 5) for i in range(20)]

    get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    # 批量返回与输入等长的向量；用不同向量让多样性有意义
    get_embeddings = AsyncMock(
        side_effect=lambda texts: [[float(i % 3), float((i + 1) % 3), 1.0] for i in range(len(texts))]
    )
    monkeypatch.setattr(ur_module.embedding_service, "get_embedding", get_embedding)
    monkeypatch.setattr(ur_module.embedding_service, "get_embeddings", get_embeddings)

    result = await retriever._mmr_rerank(query="测试查询", candidates=cands, top_k=10)

    # 1. 只发 2 次 embedding 请求（1 query + 1 批量），与候选数无关
    assert get_embedding.await_count == 1
    assert get_embeddings.await_count == 1
    # 批量调用一次性传入了全部候选
    assert len(get_embeddings.await_args.args[0]) == 20
    # 3. 返回数量受 top_k 约束
    assert len(result) == 10
    # 返回项都来自原候选
    assert all(r in cands for r in result)


@pytest.mark.asyncio
async def test_mmr_short_circuit_when_few_candidates(monkeypatch):
    """候选数 <= top_k 时直接返回，不触发任何 embedding 请求。"""
    retriever = UnifiedRetriever()
    cands = [_cand(i, f"doc {i}") for i in range(5)]

    get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    get_embeddings = AsyncMock(return_value=[])
    monkeypatch.setattr(ur_module.embedding_service, "get_embedding", get_embedding)
    monkeypatch.setattr(ur_module.embedding_service, "get_embeddings", get_embeddings)

    result = await retriever._mmr_rerank(query="q", candidates=cands, top_k=10)

    assert len(result) == 5
    assert get_embedding.await_count == 0
    assert get_embeddings.await_count == 0
