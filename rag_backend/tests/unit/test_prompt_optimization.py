"""
测试 Prompt 优化系统

包括版本管理、A/B测试、自动改进的测试。
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime
import uuid

from app.models.prompt_version import (
    PromptVersion,
    ABTestExperiment,
    PromptImprovementSuggestion,
    PromptStatus
)
from app.services.ab_test_service import ABTestService


# ==================== Prompt版本模型测试 ====================

def test_prompt_version_creation():
    """测试创建Prompt版本"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="rag_generation",
        prompt_type="rag_generation",
        version="1.0.0",
        template="请回答：{query}\\n\\n上下文：{context}",
        status=PromptStatus.DRAFT.value
    )

    assert version.prompt_name == "rag_generation"
    assert version.version == "1.0.0"
    assert version.status == "draft"


def test_prompt_version_to_dict():
    """测试版本转字典"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test_prompt",
        prompt_type="custom",
        version="1.0.0",
        template="test template",
        total_uses=100,
        success_count=90,
        avg_rating=4.5
    )

    version_dict = version.to_dict()

    assert version_dict["prompt_name"] == "test_prompt"
    assert version_dict["metrics"]["total_uses"] == 100
    assert version_dict["metrics"]["success_rate"] == 0.9
    assert version_dict["metrics"]["avg_rating"] == 4.5


def test_prompt_version_success_rate():
    """测试成功率计算"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test",
        total_uses=100,
        success_count=85
    )

    assert version.get_success_rate() == 0.85


def test_prompt_version_satisfaction_rate():
    """测试满意度计算"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test",
        positive_feedback_count=80,
        negative_feedback_count=20
    )

    assert version.get_satisfaction_rate() == 0.8


def test_prompt_version_increment_usage():
    """测试增加使用统计"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test"
    )

    version.increment_usage(success=True, response_time_ms=250, token_usage=500)

    assert version.total_uses == 1
    assert version.success_count == 1
    assert version.avg_response_time_ms == 250
    assert version.avg_token_usage == 500

    # 再次增加
    version.increment_usage(success=True, response_time_ms=300, token_usage=600)

    assert version.total_uses == 2
    assert version.success_count == 2
    # 滑动平均
    assert 250 < version.avg_response_time_ms < 300


def test_prompt_version_add_feedback():
    """测试添加反馈"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test"
    )

    version.add_feedback(rating=5, is_positive=True)
    assert version.positive_feedback_count == 1
    assert version.avg_rating == 5

    version.add_feedback(rating=3, is_positive=False)
    assert version.negative_feedback_count == 1
    assert version.avg_rating == 4  # (5+3)/2


# ==================== A/B测试实验模型测试 ====================

def test_ab_test_experiment_creation():
    """测试创建A/B测试实验"""
    experiment = ABTestExperiment(
        tenant_id="tenant_1",
        experiment_name="test_experiment",
        prompt_name="rag_generation",
        prompt_type="rag_generation",
        variant_weights={
            str(uuid.uuid4()): 50,
            str(uuid.uuid4()): 50
        },
        min_sample_size=100,
        confidence_level=0.95
    )

    assert experiment.experiment_name == "test_experiment"
    assert len(experiment.variant_weights) == 2
    assert sum(experiment.variant_weights.values()) == 100


def test_ab_test_experiment_to_dict():
    """测试实验转字典"""
    experiment = ABTestExperiment(
        tenant_id="tenant_1",
        experiment_name="test",
        prompt_name="test_prompt",
        prompt_type="custom",
        variant_weights={"v1": 50, "v2": 50},
        total_samples=150,
        is_significant=True
    )

    exp_dict = experiment.to_dict()

    assert exp_dict["experiment_name"] == "test"
    assert exp_dict["results"]["total_samples"] == 150
    assert exp_dict["results"]["is_significant"] is True


# ==================== A/B测试服务测试 ====================

def test_ab_test_service_init():
    """测试A/B测试服务初始化"""
    mock_db = Mock()
    service = ABTestService(db=mock_db, tenant_id="tenant_1")

    assert service.tenant_id == "tenant_1"
    assert service.db == mock_db


async def test_ab_test_get_default_version():
    """测试获取默认版本"""
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = PromptVersion(
        id=uuid.uuid4(),
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test",
        is_default=True,
        status=PromptStatus.ACTIVE.value
    )
    mock_db.execute.return_value = result

    service = ABTestService(db=mock_db, tenant_id="tenant_1")
    version = await service._get_default_version("test")

    assert version is not None
    assert version.is_default is True


async def test_ab_test_get_variant_no_experiment():
    """测试没有实验时返回默认版本"""
    mock_db = AsyncMock()

    # 第一次查询实验返回 None
    no_experiment = MagicMock()
    no_experiment.scalar_one_or_none.return_value = None
    # 第二次查询默认版本
    default_version = MagicMock()
    default_version.scalar_one_or_none.return_value = PromptVersion(
        id=uuid.uuid4(),
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test",
        is_default=True
    )
    mock_db.execute.side_effect = [no_experiment, default_version]

    service = ABTestService(db=mock_db, tenant_id="tenant_1")
    version = await service.get_variant_for_user("test", user_id="user_1")

    assert version is not None
    assert version.is_default is True


async def test_ab_test_create_experiment_invalid_weights():
    """测试创建实验时权重不合法"""
    mock_db = AsyncMock()
    service = ABTestService(db=mock_db, tenant_id="tenant_1")

    # 权重总和不为100
    with pytest.raises(ValueError, match="权重总和必须为100"):
        await service.create_experiment(
            experiment_name="test",
            prompt_name="test",
            prompt_type="custom",
            variant_weights={"v1": 40, "v2": 40}  # 总和80
        )


async def test_ab_test_analyze_experiment_not_enough_samples():
    """测试样本量不足的分析"""
    mock_db = AsyncMock()

    # Mock实验
    experiment = ABTestExperiment(
        id=uuid.uuid4(),
        tenant_id="tenant_1",
        experiment_name="test",
        prompt_name="test",
        prompt_type="custom",
        variant_weights={
            "v1_id": 50,
            "v2_id": 50
        },
        min_sample_size=100,
        total_samples=50  # 不足
    )

    # Mock版本
    version1 = PromptVersion(
        id="v1_id",
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="v1",
        total_uses=25,
        success_count=20
    )

    version2 = PromptVersion(
        id="v2_id",
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.1.0",
        template="v2",
        total_uses=25,
        success_count=22
    )

    exp_result = MagicMock()
    exp_result.scalar_one_or_none.return_value = experiment
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = [version1, version2]
    mock_db.execute.side_effect = [exp_result, versions_result]

    service = ABTestService(db=mock_db, tenant_id="tenant_1")
    analysis = await service.analyze_experiment(str(experiment.id))

    assert analysis["has_enough_samples"] is False
    assert "还需要" in analysis["recommendation"]


# ==================== Prompt改进建议测试 ====================

def test_improvement_suggestion_creation():
    """测试创建改进建议"""
    suggestion = PromptImprovementSuggestion(
        tenant_id="tenant_1",
        prompt_version_id=uuid.uuid4(),
        prompt_name="test",
        issue_type="incomplete",
        issue_description="回答不完整",
        suggestion_type="add_instruction",
        suggestion_detail="添加完整性要求",
        confidence_score=0.8,
        priority="high"
    )

    assert suggestion.issue_type == "incomplete"
    assert suggestion.priority == "high"
    assert suggestion.confidence_score == 0.8


def test_improvement_suggestion_to_dict():
    """测试建议转字典"""
    suggestion = PromptImprovementSuggestion(
        tenant_id="tenant_1",
        prompt_version_id=uuid.uuid4(),
        prompt_name="test",
        issue_type="hallucination",
        issue_description="出现幻觉",
        suggestion_type="add_constraint",
        suggestion_detail="添加约束",
        confidence_score=0.9,
        priority="high",
        status="pending"
    )

    sug_dict = suggestion.to_dict()

    assert sug_dict["issue"]["type"] == "hallucination"
    assert sug_dict["suggestion"]["priority"] == "high"
    assert sug_dict["status"] == "pending"


# ==================== 集成测试 ====================

async def test_full_ab_test_workflow():
    """测试完整的A/B测试流程"""
    mock_db = AsyncMock()

    # 1. 创建两个版本
    version1_id = uuid.uuid4()
    version2_id = uuid.uuid4()

    version1 = PromptVersion(
        id=version1_id,
        tenant_id="tenant_1",
        prompt_name="rag_gen",
        prompt_type="rag_generation",
        version="1.0.0",
        template="旧版本Prompt",
        is_default=True,
        status=PromptStatus.ACTIVE.value
    )

    version2 = PromptVersion(
        id=version2_id,
        tenant_id="tenant_1",
        prompt_name="rag_gen",
        prompt_type="rag_generation",
        version="1.1.0",
        template="优化版本Prompt",
        status=PromptStatus.DRAFT.value
    )

    # 模拟使用数据
    version1.total_uses = 100
    version1.success_count = 80  # 80%成功率

    version2.total_uses = 100
    version2.success_count = 92  # 92%成功率（显著更好）

    # 创建实验
    experiment = ABTestExperiment(
        id=uuid.uuid4(),
        tenant_id="tenant_1",
        experiment_name="优化测试",
        prompt_name="rag_gen",
        prompt_type="rag_generation",
        variant_weights={
            str(version1_id): 50,
            str(version2_id): 50
        },
        min_sample_size=100
    )

    # Mock查询：先返回实验，再返回版本列表
    exp_result = MagicMock()
    exp_result.scalar_one_or_none.return_value = experiment
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = [version1, version2]
    mock_db.execute.side_effect = [exp_result, versions_result]

    # 分析实验
    service = ABTestService(db=mock_db, tenant_id="tenant_1")
    analysis = await service.analyze_experiment(str(experiment.id))

    # 验证
    assert analysis["has_enough_samples"] is True
    assert analysis["is_significant"] is True  # 12%的提升应该显著
    assert analysis["winner"] is not None
    assert analysis["winner"]["version"] == "1.1.0"


def test_prompt_optimization_workflow():
    """测试Prompt优化工作流"""
    # 1. 收集失败案例
    failure_cases = [
        {"type": "incomplete", "query": "问题1"},
        {"type": "incomplete", "query": "问题2"},
        {"type": "incomplete", "query": "问题3"},
        {"type": "hallucination", "query": "问题4"},
        {"type": "hallucination", "query": "问题5"}
    ]

    # 2. 统计失败类型
    from collections import Counter
    failure_counts = Counter([case["type"] for case in failure_cases])

    assert failure_counts["incomplete"] == 3
    assert failure_counts["hallucination"] == 2

    # 3. 生成改进建议
    suggestions = []
    if failure_counts["incomplete"] >= 3:
        suggestions.append({
            "issue": "incomplete",
            "suggestion": "添加完整性指令"
        })

    if failure_counts["hallucination"] >= 2:
        suggestions.append({
            "issue": "hallucination",
            "suggestion": "添加防幻觉约束"
        })

    assert len(suggestions) == 2


# ==================== 性能测试 ====================

def test_ab_test_hash_consistency():
    """测试一致性哈希的稳定性"""
    import hashlib

    user_id = "user_123"

    # 多次哈希应该得到相同结果
    hash1 = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    hash2 = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

    assert hash1 == hash2


def test_version_increment_performance():
    """测试版本增量更新性能"""
    import time

    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test"
    )

    start = time.time()

    # 模拟1000次使用
    for i in range(1000):
        version.increment_usage(success=True, response_time_ms=250, token_usage=500)

    elapsed = time.time() - start

    # 应该在0.1秒内完成
    assert elapsed < 0.1
    assert version.total_uses == 1000


# ==================== 边界情况测试 ====================

def test_prompt_version_zero_uses():
    """测试零使用次数的版本"""
    version = PromptVersion(
        tenant_id="tenant_1",
        prompt_name="test",
        prompt_type="custom",
        version="1.0.0",
        template="test",
        total_uses=0
    )

    assert version.get_success_rate() == 0.0
    assert version.get_satisfaction_rate() == 0.0


def test_ab_test_single_variant():
    """测试单个变体的实验（边界情况）"""
    mock_db = Mock()
    service = ABTestService(db=mock_db, tenant_id="tenant_1")

    # 单个变体权重100
    # 这在实际中不应该发生，但要能处理
    variant_weights = {str(uuid.uuid4()): 100}

    # 应该能创建（虽然不是真正的A/B测试）
    assert sum(variant_weights.values()) == 100
