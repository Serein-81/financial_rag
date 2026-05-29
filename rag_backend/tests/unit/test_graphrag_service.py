"""
测试 GraphRAG 服务
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from app.services.graphrag_service import GraphRAGService, GraphRAGContext


@pytest.fixture
def mock_vector_search():
    """模拟向量检索服务"""
    service = Mock()
    service.search = AsyncMock(return_value=[
        {
            "content": "企业所得税标准税率为25%",
            "metadata": {"entity_mentions": ["企业所得税"]},
            "score": 0.95
        },
        {
            "content": "小型微利企业享受20%的优惠税率",
            "metadata": {"entity_mentions": ["小型微利企业", "优惠税率"]},
            "score": 0.88
        }
    ])
    return service


@pytest.fixture
def mock_neo4j():
    """模拟 Neo4j 管理器"""
    manager = Mock()

    # 模拟 session
    session_mock = MagicMock()
    result_mock = MagicMock()
    record_mock = {
        "start_nodes": [
            {"id": 1, "name": "企业所得税", "type": "Tax"}
        ],
        "connected_nodes": [
            {"id": 2, "name": "小型微利企业", "type": "Enterprise"},
            {"id": 3, "name": "税率优惠", "type": "Policy"}
        ],
        "relations": [
            {"source": "企业所得税", "target": "小型微利企业", "type": "APPLIES_TO"},
            {"source": "小型微利企业", "target": "税率优惠", "type": "ENJOYS"}
        ]
    }

    result_mock.single.return_value = record_mock
    session_mock.run.return_value = result_mock

    # 配置 driver
    manager.driver.session.return_value.__enter__.return_value = session_mock

    return manager


@pytest.fixture
def mock_rerank():
    """模拟 Rerank 服务"""
    service = Mock()
    service.rerank = AsyncMock(return_value=[
        {"index": 0, "score": 0.95},
        {"index": 1, "score": 0.88}
    ])
    return service


@pytest.fixture
def graphrag_service(mock_vector_search, mock_neo4j, mock_rerank):
    """创建 GraphRAG 服务实例"""
    return GraphRAGService(
        vector_search_service=mock_vector_search,
        neo4j_manager=mock_neo4j,
        rerank_service=mock_rerank
    )


@pytest.mark.asyncio
async def test_hybrid_retrieve(graphrag_service):
    """测试混合检索"""
    result = await graphrag_service.hybrid_retrieve(
        query="小型微利企业所得税率",
        kb_id="test_kb",
        top_k=5
    )

    # 验证返回类型
    assert isinstance(result, GraphRAGContext)

    # 验证检索方法
    assert result.retrieval_method == "hybrid"

    # 验证向量检索结果
    assert result.total_chunks > 0
    assert len(result.vector_chunks) > 0

    # 验证图谱结果
    assert result.total_entities > 0
    assert result.total_relations > 0

    # 验证合并上下文
    assert result.merged_context
    assert "企业所得税" in result.merged_context


@pytest.mark.asyncio
async def test_vector_retrieve(graphrag_service, mock_vector_search):
    """测试向量检索"""
    chunks = await graphrag_service._vector_retrieve(
        query="测试查询",
        kb_id="test_kb",
        top_k=10
    )

    assert len(chunks) == 2
    assert chunks[0]["content"] == "企业所得税标准税率为25%"

    # 验证调用了向量检索服务
    mock_vector_search.search.assert_called_once()


@pytest.mark.asyncio
async def test_vector_retrieve_without_service():
    """测试没有向量检索服务时的情况"""
    service = GraphRAGService(
        vector_search_service=None,
        neo4j_manager=None,
        rerank_service=None
    )

    chunks = await service._vector_retrieve("query", "kb_id")
    assert chunks == []


def test_extract_entities_from_chunks(graphrag_service):
    """测试从文档块提取实体"""
    chunks = [
        {
            "content": "测试内容1",
            "metadata": {"entity_mentions": ["实体A", "实体B"]}
        },
        {
            "content": "测试内容2",
            "metadata": {"entity_mentions": ["实体C"]}
        },
        {
            "content": "测试内容3",
            "entities": ["实体D", "实体E"]
        }
    ]

    entities = graphrag_service._extract_entities_from_chunks(chunks)

    assert len(entities) >= 3
    assert "实体A" in entities
    assert "实体B" in entities
    assert "实体C" in entities


def test_extract_entities_empty_chunks(graphrag_service):
    """测试从空文档块提取实体"""
    entities = graphrag_service._extract_entities_from_chunks([])
    assert entities == []


def test_extract_entities_no_metadata(graphrag_service):
    """测试从没有元数据的文档块提取实体"""
    chunks = [
        {"content": "测试内容，没有元数据"}
    ]

    entities = graphrag_service._extract_entities_from_chunks(chunks)
    assert entities == []


@pytest.mark.asyncio
async def test_traverse_graph(graphrag_service):
    """测试图谱遍历"""
    result = await graphrag_service._traverse_graph(
        entry_entities=["企业所得税"],
        depth=2,
        max_nodes=20
    )

    # 验证返回结构
    assert "entities" in result
    assert "relations" in result

    # 验证实体
    assert len(result["entities"]) > 0

    # 验证关系
    assert len(result["relations"]) > 0


@pytest.mark.asyncio
async def test_traverse_graph_empty_entities(graphrag_service):
    """测试空实体列表的图谱遍历"""
    result = await graphrag_service._traverse_graph(
        entry_entities=[],
        depth=2,
        max_nodes=20
    )

    assert result["entities"] == []
    assert result["relations"] == []


@pytest.mark.asyncio
async def test_traverse_graph_without_neo4j():
    """测试没有 Neo4j 时的图谱遍历"""
    service = GraphRAGService(
        vector_search_service=None,
        neo4j_manager=None,
        rerank_service=None
    )

    result = await service._traverse_graph(["实体A"])

    assert result["entities"] == []
    assert result["relations"] == []


def test_merge_contexts(graphrag_service):
    """测试合并上下文"""
    vector_chunks = [
        {"content": "文档片段1"},
        {"content": "文档片段2"}
    ]

    graph_context = {
        "entities": [
            {"name": "实体A", "type": "TypeA"},
            {"name": "实体B", "type": "TypeB"}
        ],
        "relations": [
            {"source": "实体A", "target": "实体B", "type": "RELATED_TO"}
        ]
    }

    merged = graphrag_service._merge_contexts(vector_chunks, graph_context)

    # 验证合并结果包含所有信息
    assert "文档片段1" in merged
    assert "文档片段2" in merged
    assert "实体A" in merged
    assert "实体B" in merged
    assert "RELATED_TO" in merged


def test_merge_contexts_empty():
    """测试空上下文合并"""
    service = GraphRAGService()

    merged = service._merge_contexts([], {"entities": [], "relations": []})
    assert merged == ""


@pytest.mark.asyncio
async def test_rerank_results(graphrag_service, mock_rerank):
    """测试 Rerank"""
    chunks = [
        {"content": "文档1"},
        {"content": "文档2"}
    ]

    reranked = await graphrag_service._rerank_results("查询", chunks)

    # 验证调用了 Rerank 服务
    mock_rerank.rerank.assert_called_once()

    # 验证返回结果
    assert len(reranked) == 2
    assert "rerank_score" in reranked[0]


@pytest.mark.asyncio
async def test_rerank_results_without_service():
    """测试没有 Rerank 服务时"""
    service = GraphRAGService(
        vector_search_service=None,
        neo4j_manager=None,
        rerank_service=None
    )

    chunks = [{"content": "文档1"}]
    result = await service._rerank_results("查询", chunks)

    # 应该返回原样
    assert result == chunks


@pytest.mark.asyncio
async def test_vector_only_retrieve(graphrag_service):
    """测试纯向量检索"""
    result = await graphrag_service.vector_only_retrieve(
        query="测试查询",
        kb_id="test_kb",
        top_k=5
    )

    # 验证检索方法
    assert result.retrieval_method == "vector_only"

    # 验证没有图谱结果
    assert result.total_entities == 0
    assert result.total_relations == 0

    # 验证有向量结果
    assert result.total_chunks > 0


def test_classify_query_complexity_simple(graphrag_service):
    """测试简单查询分类"""
    queries = [
        "企业所得税税率",
        "什么是增值税",
        "查询政策文件"
    ]

    for query in queries:
        result = graphrag_service.classify_query_complexity(query)
        assert result == "simple"


def test_classify_query_complexity_complex(graphrag_service):
    """测试复杂查询分类"""
    queries = [
        "详细分析企业所得税优惠政策",
        "解释税收筹划的原理",
        "说明财务报表的编制方法"
    ]

    for query in queries:
        result = graphrag_service.classify_query_complexity(query)
        assert result == "complex"


def test_classify_query_complexity_multi_hop(graphrag_service):
    """测试多跳推理查询分类"""
    queries = [
        "为什么小型微利企业享受税收优惠",
        "如何计算企业所得税",
        "比较一般纳税人和小规模纳税人的区别"
    ]

    for query in queries:
        result = graphrag_service.classify_query_complexity(query)
        assert result == "multi_hop"


def test_chunks_to_text(graphrag_service):
    """测试文档块转文本"""
    chunks = [
        {"content": "内容1"},
        {"content": "内容2"},
        {"content": "内容3"}
    ]

    text = graphrag_service._chunks_to_text(chunks)

    assert "1. 内容1" in text
    assert "2. 内容2" in text
    assert "3. 内容3" in text


def test_chunks_to_text_empty(graphrag_service):
    """测试空文档块转文本"""
    text = graphrag_service._chunks_to_text([])
    assert text == ""


@pytest.mark.asyncio
async def test_hybrid_retrieve_with_disabled_rerank(graphrag_service):
    """测试禁用 Rerank 的混合检索"""
    result = await graphrag_service.hybrid_retrieve(
        query="测试查询",
        kb_id="test_kb",
        top_k=5,
        enable_rerank=False
    )

    assert isinstance(result, GraphRAGContext)
    # Rerank 服务不应该被调用
    graphrag_service.rerank.rerank.assert_not_called()


@pytest.mark.asyncio
async def test_hybrid_retrieve_custom_params(graphrag_service):
    """测试自定义参数的混合检索"""
    result = await graphrag_service.hybrid_retrieve(
        query="测试查询",
        kb_id="test_kb",
        top_k=3,
        graph_depth=1,
        max_graph_nodes=10
    )

    # 验证 top_k 限制
    assert len(result.vector_chunks) <= 3
