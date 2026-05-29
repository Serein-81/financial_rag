"""
测试 Harness 评估框架

包括数据集、评估器、运行器的测试。
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
import json

from tests.harness.dataset import (
    TestCase,
    TestDataset,
    DatasetBuilder,
    DifficultyLevel,
    QuestionCategory,
    create_sample_dataset
)
from tests.harness.evaluators.retrieval_evaluator import (
    RetrievalEvaluator,
    RetrievalMetrics
)
from tests.harness.evaluators.generation_evaluator import (
    GenerationEvaluator,
    GenerationMetrics
)


# ==================== 数据集测试 ====================

def test_test_case_creation():
    """测试创建测试用例"""
    test_case = TestCase(
        id="test_001",
        query="测试查询",
        expected_answer="测试答案",
        ground_truth_chunks=["doc_1", "doc_2"],
        difficulty=DifficultyLevel.EASY,
        category=QuestionCategory.FACTUAL
    )

    assert test_case.id == "test_001"
    assert test_case.query == "测试查询"
    assert len(test_case.ground_truth_chunks) == 2


def test_test_case_to_dict():
    """测试用例转字典"""
    test_case = TestCase(
        id="test_001",
        query="测试查询",
        expected_answer="测试答案",
        ground_truth_chunks=["doc_1"],
        difficulty=DifficultyLevel.EASY,
        category=QuestionCategory.FACTUAL
    )

    case_dict = test_case.to_dict()

    assert case_dict["id"] == "test_001"
    assert case_dict["difficulty"] == "easy"
    assert case_dict["category"] == "factual"


def test_test_case_from_dict():
    """测试从字典创建用例"""
    data = {
        "id": "test_001",
        "query": "测试查询",
        "expected_answer": "测试答案",
        "ground_truth_chunks": ["doc_1"],
        "difficulty": "medium",
        "category": "reasoning"
    }

    test_case = TestCase.from_dict(data)

    assert test_case.id == "test_001"
    assert test_case.difficulty == DifficultyLevel.MEDIUM
    assert test_case.category == QuestionCategory.REASONING


def test_test_dataset_creation():
    """测试创建数据集"""
    test_cases = [
        TestCase(
            id="test_001",
            query="查询1",
            expected_answer="答案1",
            ground_truth_chunks=["doc_1"],
            difficulty=DifficultyLevel.EASY,
            category=QuestionCategory.FACTUAL
        ),
        TestCase(
            id="test_002",
            query="查询2",
            expected_answer="答案2",
            ground_truth_chunks=["doc_2"],
            difficulty=DifficultyLevel.HARD,
            category=QuestionCategory.MULTI_HOP
        )
    ]

    dataset = TestDataset(
        name="test_dataset",
        version="1.0",
        description="测试数据集",
        test_cases=test_cases
    )

    assert len(dataset) == 2
    assert dataset[0].id == "test_001"


def test_dataset_filter_by_difficulty():
    """测试按难度过滤"""
    dataset = create_sample_dataset()

    easy_cases = dataset.filter_by_difficulty(DifficultyLevel.EASY)

    assert len(easy_cases) >= 1
    assert all(c.difficulty == DifficultyLevel.EASY for c in easy_cases)


def test_dataset_filter_by_category():
    """测试按类别过滤"""
    dataset = create_sample_dataset()

    factual_cases = dataset.filter_by_category(QuestionCategory.FACTUAL)

    assert len(factual_cases) >= 1
    assert all(c.category == QuestionCategory.FACTUAL for c in factual_cases)


def test_dataset_statistics():
    """测试数据集统计"""
    dataset = create_sample_dataset()

    stats = dataset.get_statistics()

    assert stats["total_cases"] == len(dataset)
    assert "by_difficulty" in stats
    assert "by_category" in stats
    assert stats["avg_query_length"] > 0


def test_dataset_builder():
    """测试数据集构建器"""
    builder = DatasetBuilder(
        name="test_dataset",
        version="1.0",
        description="测试"
    )

    builder.add_case(
        case_id="test_001",
        query="查询",
        expected_answer="答案",
        ground_truth_chunks=["doc_1"],
        difficulty=DifficultyLevel.EASY,
        category=QuestionCategory.FACTUAL
    )

    dataset = builder.build()

    assert len(dataset) == 1
    assert dataset.name == "test_dataset"


# ==================== 检索评估器测试 ====================

def test_retrieval_evaluator_recall_at_k():
    """测试 Recall@K 计算"""
    evaluator = RetrievalEvaluator(k_values=[1, 3, 5])

    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4", "doc_5"]
    ground_truth = ["doc_1", "doc_3", "doc_6", "doc_7"]

    metrics = evaluator.evaluate(retrieved, ground_truth)

    # Recall@5 = |{doc_1, doc_3}| / |{doc_1, doc_3, doc_6, doc_7}| = 2/4 = 0.5
    assert metrics.recall_at_k[5] == 0.5


def test_retrieval_evaluator_precision_at_k():
    """测试 Precision@K 计算"""
    evaluator = RetrievalEvaluator(k_values=[5])

    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4", "doc_5"]
    ground_truth = ["doc_1", "doc_3"]

    metrics = evaluator.evaluate(retrieved, ground_truth)

    # Precision@5 = 2 / 5 = 0.4
    assert metrics.precision_at_k[5] == 0.4


def test_retrieval_evaluator_mrr():
    """测试 MRR 计算"""
    evaluator = RetrievalEvaluator()

    # 第一个相关文档在位置 2
    retrieved = ["doc_x", "doc_1", "doc_y", "doc_z"]
    ground_truth = ["doc_1", "doc_2"]

    metrics = evaluator.evaluate(retrieved, ground_truth)

    # MRR = 1 / 2 = 0.5
    assert metrics.mrr == 0.5


def test_retrieval_evaluator_perfect_match():
    """测试完美匹配"""
    evaluator = RetrievalEvaluator(k_values=[5])

    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4", "doc_5"]
    ground_truth = ["doc_1", "doc_2", "doc_3"]

    metrics = evaluator.evaluate(retrieved, ground_truth)

    # Recall@5 = 3/3 = 1.0
    assert metrics.recall_at_k[5] == 1.0
    # Precision@5 = 3/5 = 0.6
    assert metrics.precision_at_k[5] == 0.6
    # MRR = 1/1 = 1.0
    assert metrics.mrr == 1.0


def test_retrieval_evaluator_no_match():
    """测试无匹配"""
    evaluator = RetrievalEvaluator(k_values=[5])

    retrieved = ["doc_1", "doc_2", "doc_3"]
    ground_truth = ["doc_x", "doc_y", "doc_z"]

    metrics = evaluator.evaluate(retrieved, ground_truth)

    assert metrics.recall_at_k[5] == 0.0
    assert metrics.precision_at_k[5] == 0.0
    assert metrics.mrr == 0.0


def test_retrieval_evaluator_batch():
    """测试批量评估"""
    evaluator = RetrievalEvaluator(k_values=[5])

    batch = [
        (["doc_1", "doc_2"], ["doc_1"]),
        (["doc_3", "doc_4"], ["doc_3"]),
    ]

    metrics = evaluator.evaluate_batch(batch)

    # 两个都是 Recall@5 = 1.0, 平均 = 1.0
    assert metrics.recall_at_k[5] == 1.0


# ==================== 生成评估器测试 ====================

@pytest.mark.asyncio
async def test_generation_evaluator_with_rules():
    """测试基于规则的生成评估"""
    evaluator = GenerationEvaluator(llm_service=None)

    metrics = await evaluator.evaluate(
        query="企业所得税税率是多少？",
        generated_answer="企业所得税的标准税率为25%。",
        expected_answer="企业所得税标准税率为25%。"
    )

    assert metrics.overall_score > 0
    assert 0 <= metrics.relevance_score <= 5
    assert 0 <= metrics.completeness_score <= 5


@pytest.mark.asyncio
async def test_generation_evaluator_with_llm():
    """测试基于 LLM 的生成评估"""
    mock_llm = Mock()
    mock_llm.generate = AsyncMock(return_value=json.dumps({
        "accuracy_score": 5,
        "completeness_score": 4,
        "relevance_score": 5,
        "fluency_score": 5,
        "overall_score": 4.75,
        "has_hallucination": False,
        "reasoning": "答案准确完整"
    }))

    evaluator = GenerationEvaluator(llm_service=mock_llm)

    metrics = await evaluator.evaluate(
        query="测试查询",
        generated_answer="生成答案",
        expected_answer="期望答案"
    )

    assert metrics.accuracy_score == 5
    assert metrics.overall_score == 4.75
    assert metrics.has_hallucination is False


@pytest.mark.asyncio
async def test_generation_evaluator_llm_fallback():
    """测试 LLM 失败时降级"""
    mock_llm = Mock()
    mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

    evaluator = GenerationEvaluator(llm_service=mock_llm)

    metrics = await evaluator.evaluate(
        query="测试查询",
        generated_answer="生成答案",
        expected_answer="期望答案"
    )

    # 应该降级到规则评估，返回有效结果
    assert isinstance(metrics, GenerationMetrics)
    assert metrics.overall_score >= 0


@pytest.mark.asyncio
async def test_generation_evaluator_average_metrics():
    """测试计算平均指标"""
    evaluator = GenerationEvaluator()

    metrics_list = [
        GenerationMetrics(
            accuracy_score=5,
            completeness_score=4,
            relevance_score=5,
            fluency_score=5,
            overall_score=4.75
        ),
        GenerationMetrics(
            accuracy_score=3,
            completeness_score=3,
            relevance_score=4,
            fluency_score=4,
            overall_score=3.5
        )
    ]

    avg_metrics = evaluator.calculate_average_metrics(metrics_list)

    assert avg_metrics.accuracy_score == 4.0
    assert avg_metrics.overall_score == 4.125


# ==================== 边界情况测试 ====================

def test_empty_retrieved_docs():
    """测试空检索结果"""
    evaluator = RetrievalEvaluator(k_values=[5])

    retrieved = []
    ground_truth = ["doc_1", "doc_2"]

    metrics = evaluator.evaluate(retrieved, ground_truth)

    assert metrics.recall_at_k[5] == 0.0
    assert metrics.precision_at_k[5] == 0.0


def test_empty_ground_truth():
    """测试空标准答案"""
    evaluator = RetrievalEvaluator(k_values=[5])

    retrieved = ["doc_1", "doc_2"]
    ground_truth = []

    metrics = evaluator.evaluate(retrieved, ground_truth)

    assert metrics.recall_at_k[5] == 0.0


@pytest.mark.asyncio
async def test_empty_generated_answer():
    """测试空生成答案"""
    evaluator = GenerationEvaluator()

    metrics = await evaluator.evaluate(
        query="查询",
        generated_answer="",
        expected_answer="期望答案"
    )

    assert isinstance(metrics, GenerationMetrics)


# ==================== 性能测试 ====================

def test_retrieval_evaluator_performance():
    """测试检索评估器性能"""
    import time

    evaluator = RetrievalEvaluator(k_values=[1, 3, 5, 10])

    # 评估 100 次
    start = time.time()

    for _ in range(100):
        retrieved = [f"doc_{i}" for i in range(10)]
        ground_truth = [f"doc_{i}" for i in range(0, 10, 2)]
        evaluator.evaluate(retrieved, ground_truth)

    elapsed = time.time() - start

    # 应该在 0.1 秒内完成
    assert elapsed < 0.1


# ==================== 集成测试 ====================

def test_sample_dataset_creation():
    """测试示例数据集创建"""
    dataset = create_sample_dataset()

    assert len(dataset) >= 3
    assert dataset.name == "tax_qa_sample"
    assert dataset.version == "1.0"


def test_dataset_to_dict_and_from_dict():
    """测试数据集序列化和反序列化"""
    original = create_sample_dataset()

    # 转为字典
    data = original.to_dict()

    # 从字典创建
    restored = TestDataset.from_dict(data)

    assert restored.name == original.name
    assert len(restored) == len(original)
    assert restored[0].id == original[0].id
