"""
测试用户反馈系统

包括反馈模型、API、失败案例分析器的测试。
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4
import json

from app.models.feedback import (
    UserFeedback,
    FailureCase,
    ImprovementRecord,
    FeedbackType,
    FailureType,
    FailureStatus,
    ImprovementType
)
from app.services.failure_analyzer import FailureAnalyzer


# ==================== Fixtures ====================

@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.delete = Mock()
    session.rollback = Mock()
    session.execute = Mock()
    return session


@pytest.fixture
def mock_llm_service():
    """模拟 LLM 服务"""
    service = Mock()
    service.generate = AsyncMock(return_value=json.dumps({
        "root_causes": ["检索未找到相关文档", "知识库缺少对应内容"],
        "missing_info": ["税率具体数值"],
        "context_issues": ["上下文不足"],
        "recommendations": ["使用 GraphRAG 增强检索", "补充知识库"],
        "confidence_score": 85
    }))
    return service


@pytest.fixture
def sample_feedback():
    """示例反馈"""
    return UserFeedback(
        id=uuid4(),
        session_id="test_session_123",
        message_id=uuid4(),
        user_id=uuid4(),
        tenant_id="test_tenant",
        query="小型微利企业税率是多少？",
        response="小型微利企业享受税收优惠。",
        feedback_type=FeedbackType.NEGATIVE,
        rating=2,
        comment="答案不完整，没有说明具体税率",
        retrieval_method="simple",
        chunks_used=[{"id": "chunk_1", "content": "小型微利企业优惠政策..."}],
        kb_id="tax_kb",
        retrieval_time=1000,
        generation_time=2000,
        total_time=3000,
        token_count=500,
        created_at=datetime.now()
    )


@pytest.fixture
def sample_failure_case(sample_feedback):
    """示例失败案例"""
    return FailureCase(
        id=uuid4(),
        feedback_id=sample_feedback.id,
        failure_type=FailureType.INCOMPLETE,
        analysis={
            "root_causes": ["信息不完整"],
            "missing_info": ["具体税率"],
            "recommendations": ["增加检索轮次"]
        },
        fix_suggestions=["使用 Agentic RAG", "补充检索"],
        status=FailureStatus.PENDING,
        auto_analyzed=True,
        confidence_score=80,
        created_at=datetime.now()
    )


# ==================== UserFeedback 模型测试 ====================

def test_user_feedback_creation(sample_feedback):
    """测试反馈创建"""
    assert sample_feedback.session_id == "test_session_123"
    assert sample_feedback.feedback_type == FeedbackType.NEGATIVE
    assert sample_feedback.rating == 2
    assert sample_feedback.query == "小型微利企业税率是多少？"


def test_user_feedback_to_dict(sample_feedback):
    """测试反馈转字典"""
    feedback_dict = sample_feedback.to_dict()

    assert feedback_dict["session_id"] == "test_session_123"
    assert feedback_dict["feedback_type"] == "negative"
    assert feedback_dict["rating"] == 2
    assert feedback_dict["query"] == "小型微利企业税率是多少？"
    assert feedback_dict["retrieval_method"] == "simple"


def test_feedback_type_enum():
    """测试反馈类型枚举"""
    assert FeedbackType.POSITIVE.value == "positive"
    assert FeedbackType.NEGATIVE.value == "negative"
    assert FeedbackType.NEUTRAL.value == "neutral"


# ==================== FailureCase 模型测试 ====================

def test_failure_case_creation(sample_failure_case):
    """测试失败案例创建"""
    assert sample_failure_case.failure_type == FailureType.INCOMPLETE
    assert sample_failure_case.status == FailureStatus.PENDING
    assert sample_failure_case.auto_analyzed is True
    assert sample_failure_case.confidence_score == 80


def test_failure_case_to_dict(sample_failure_case):
    """测试失败案例转字典"""
    case_dict = sample_failure_case.to_dict()

    assert case_dict["failure_type"] == "incomplete"
    assert case_dict["status"] == "pending"
    assert case_dict["auto_analyzed"] is True
    assert case_dict["confidence_score"] == 80
    assert "analysis" in case_dict
    assert "fix_suggestions" in case_dict


def test_failure_type_enum():
    """测试失败类型枚举"""
    assert FailureType.RETRIEVAL.value == "retrieval"
    assert FailureType.GENERATION.value == "generation"
    assert FailureType.HALLUCINATION.value == "hallucination"
    assert FailureType.INCOMPLETE.value == "incomplete"
    assert FailureType.IRRELEVANT.value == "irrelevant"


# ==================== ImprovementRecord 模型测试 ====================

def test_improvement_record_creation():
    """测试改进记录创建"""
    record = ImprovementRecord(
        id=uuid4(),
        failure_case_id=uuid4(),
        improvement_type=ImprovementType.PROMPT,
        before_config={"strict_mode": False},
        after_config={"strict_mode": True},
        deployed=False,
        description="优化 Prompt 以减少幻觉"
    )

    assert record.improvement_type == ImprovementType.PROMPT
    assert record.deployed is False
    assert record.before_config["strict_mode"] is False
    assert record.after_config["strict_mode"] is True


def test_improvement_record_to_dict():
    """测试改进记录转字典"""
    record = ImprovementRecord(
        id=uuid4(),
        failure_case_id=uuid4(),
        improvement_type=ImprovementType.RETRIEVAL,
        before_config={"method": "simple"},
        after_config={"method": "graphrag"},
        deployed=True,
        success_rate_before=70,
        success_rate_after=85
    )

    record_dict = record.to_dict()

    assert record_dict["improvement_type"] == "retrieval"
    assert record_dict["deployed"] is True
    assert record_dict["success_rate_before"] == 70
    assert record_dict["success_rate_after"] == 85


# ==================== FailureAnalyzer 测试 ====================

@pytest.mark.asyncio
async def test_analyzer_classify_retrieval_failure():
    """测试分类检索失败"""
    analyzer = FailureAnalyzer()

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="企业所得税优惠",
        response="抱歉，未找到相关信息。",
        feedback_type=FeedbackType.NEGATIVE,
        rating=1,
        comment="没找到任何文档",
        retrieval_method="simple",
        chunks_used=[],
        created_at=datetime.now()
    )

    failure_type = analyzer._classify_failure_type(feedback)

    assert failure_type == FailureType.RETRIEVAL


@pytest.mark.asyncio
async def test_analyzer_classify_incomplete_failure():
    """测试分类不完整失败"""
    analyzer = FailureAnalyzer()

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="小型微利企业税率",
        response="小型微利企业享受优惠。",
        feedback_type=FeedbackType.NEGATIVE,
        rating=2,
        comment="信息不完整，缺少具体税率",
        retrieval_method="simple",
        chunks_used=[{"content": "优惠政策"}],
        created_at=datetime.now()
    )

    failure_type = analyzer._classify_failure_type(feedback)

    assert failure_type == FailureType.INCOMPLETE


@pytest.mark.asyncio
async def test_analyzer_classify_hallucination_failure():
    """测试分类幻觉失败"""
    analyzer = FailureAnalyzer()

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="企业所得税税率",
        response="企业所得税税率是30%。",
        feedback_type=FeedbackType.NEGATIVE,
        rating=1,
        comment="编造信息，税率不对",
        retrieval_method="simple",
        chunks_used=[{"content": "企业所得税标准税率为25%"}],
        created_at=datetime.now()
    )

    failure_type = analyzer._classify_failure_type(feedback)

    assert failure_type == FailureType.HALLUCINATION


@pytest.mark.asyncio
async def test_analyzer_classify_irrelevant_failure():
    """测试分类不相关失败"""
    analyzer = FailureAnalyzer()

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="企业所得税计算",
        response="个人所得税的计算方法是...",
        feedback_type=FeedbackType.NEGATIVE,
        rating=2,
        comment="答非所问，回答了个税而不是企业所得税",
        retrieval_method="simple",
        chunks_used=[{"content": "个人所得税"}],
        created_at=datetime.now()
    )

    failure_type = analyzer._classify_failure_type(feedback)

    assert failure_type == FailureType.IRRELEVANT


@pytest.mark.asyncio
async def test_analyzer_analyze_with_rules(sample_feedback):
    """测试基于规则的分析"""
    analyzer = FailureAnalyzer()

    failure_type = FailureType.INCOMPLETE
    analysis = analyzer._analyze_with_rules(sample_feedback, failure_type)

    assert analysis["failure_type"] == "incomplete"
    assert "root_causes" in analysis
    assert "recommendations" in analysis
    assert "missing_info" in analysis
    assert len(analysis["root_causes"]) > 0


@pytest.mark.asyncio
async def test_analyzer_analyze_retrieval_failure():
    """测试分析检索失败"""
    analyzer = FailureAnalyzer()

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="政策查询",
        response="未找到相关内容",
        feedback_type=FeedbackType.NEGATIVE,
        rating=1,
        retrieval_method="simple",
        chunks_used=[],
        created_at=datetime.now()
    )

    failure_type = FailureType.RETRIEVAL
    analysis = analyzer._analyze_with_rules(feedback, failure_type)

    assert "检索未找到相关文档" in analysis["root_causes"]
    assert any("GraphRAG" in r for r in analysis["recommendations"])


@pytest.mark.asyncio
async def test_analyzer_analyze_with_llm(sample_feedback, mock_llm_service):
    """测试使用 LLM 分析"""
    analyzer = FailureAnalyzer(llm_service=mock_llm_service)

    failure_type = FailureType.INCOMPLETE
    analysis = await analyzer._analyze_with_llm(sample_feedback, failure_type)

    assert analysis["failure_type"] == "incomplete"
    assert "root_causes" in analysis
    assert "recommendations" in analysis
    assert analysis["confidence_score"] == 85

    # 验证 LLM 被调用
    mock_llm_service.generate.assert_called_once()


@pytest.mark.asyncio
async def test_analyzer_generate_fix_suggestions():
    """测试生成修复建议"""
    analyzer = FailureAnalyzer()

    failure_type = FailureType.INCOMPLETE
    analysis = {
        "recommendations": ["增加检索轮次", "使用 Agentic RAG"]
    }

    suggestions = analyzer._generate_fix_suggestions(failure_type, analysis)

    assert len(suggestions) > 0
    assert "增加检索轮次" in suggestions or "启用多轮检索补充信息" in suggestions


@pytest.mark.asyncio
async def test_analyzer_full_workflow(sample_feedback, mock_db_session):
    """测试完整分析工作流"""
    analyzer = FailureAnalyzer(db_session=mock_db_session)

    failure_case = await analyzer.analyze_feedback(sample_feedback, use_llm=False)

    assert failure_case.failure_type in FailureType
    assert failure_case.auto_analyzed is True
    assert failure_case.analysis is not None
    assert len(failure_case.fix_suggestions) > 0

    # 验证数据库操作
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_analyzer_suggest_improvements(sample_failure_case, mock_db_session):
    """测试生成改进建议"""
    analyzer = FailureAnalyzer(db_session=mock_db_session)

    improvement = await analyzer.suggest_improvements(sample_failure_case)

    assert improvement.failure_case_id == sample_failure_case.id
    assert improvement.improvement_type in ImprovementType
    assert improvement.before_config is not None
    assert improvement.after_config is not None
    assert improvement.description is not None

    # 验证数据库操作
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_analyzer_generate_config_changes_for_retrieval():
    """测试为检索失败生成配置变更"""
    analyzer = FailureAnalyzer()

    failure_case = FailureCase(
        id=uuid4(),
        feedback_id=uuid4(),
        failure_type=FailureType.RETRIEVAL,
        status=FailureStatus.PENDING
    )

    before_config, after_config = analyzer._generate_config_changes(failure_case)

    assert before_config["retrieval_method"] == "simple"
    assert after_config["retrieval_method"] == "graphrag"
    assert after_config["top_k"] > before_config["top_k"]


@pytest.mark.asyncio
async def test_analyzer_generate_config_changes_for_incomplete():
    """测试为不完整失败生成配置变更"""
    analyzer = FailureAnalyzer()

    failure_case = FailureCase(
        id=uuid4(),
        feedback_id=uuid4(),
        failure_type=FailureType.INCOMPLETE,
        status=FailureStatus.PENDING
    )

    before_config, after_config = analyzer._generate_config_changes(failure_case)

    assert before_config["max_iterations"] == 1
    assert after_config["retrieval_method"] == "agentic"
    assert after_config["max_iterations"] == 3


@pytest.mark.asyncio
async def test_analyzer_generate_config_changes_for_hallucination():
    """测试为幻觉失败生成配置变更"""
    analyzer = FailureAnalyzer()

    failure_case = FailureCase(
        id=uuid4(),
        feedback_id=uuid4(),
        failure_type=FailureType.HALLUCINATION,
        status=FailureStatus.PENDING
    )

    before_config, after_config = analyzer._generate_config_changes(failure_case)

    assert after_config.get("strict_context_mode") is True
    assert after_config.get("enable_citation") is True


@pytest.mark.asyncio
async def test_analyzer_generate_improvement_description(sample_failure_case):
    """测试生成改进描述"""
    analyzer = FailureAnalyzer()

    description = analyzer._generate_improvement_description(sample_failure_case)

    assert "incomplete" in description
    assert len(description) > 0
    assert "根本原因" in description or "改进措施" in description


@pytest.mark.asyncio
async def test_analyzer_llm_fallback_to_rules(sample_feedback):
    """测试 LLM 失败时降级到规则分析"""
    mock_llm = Mock()
    mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

    analyzer = FailureAnalyzer(llm_service=mock_llm)

    failure_type = FailureType.INCOMPLETE
    analysis = await analyzer._analyze_with_llm(sample_feedback, failure_type)

    # 应该降级到规则分析
    assert "failure_type" in analysis
    assert "root_causes" in analysis


# ==================== API 端点测试（模拟） ====================

def test_feedback_create_request_validation():
    """测试反馈创建请求验证"""
    from app.api.v1.endpoints.feedback import FeedbackCreate

    feedback_data = FeedbackCreate(
        session_id="test_session",
        query="测试查询",
        response="测试响应",
        feedback_type=FeedbackType.POSITIVE,
        rating=5
    )

    assert feedback_data.session_id == "test_session"
    assert feedback_data.rating == 5


def test_feedback_create_rating_validation():
    """测试评分验证"""
    from app.api.v1.endpoints.feedback import FeedbackCreate
    from pydantic import ValidationError

    # 测试无效评分
    with pytest.raises(ValidationError):
        FeedbackCreate(
            session_id="test",
            query="query",
            response="response",
            feedback_type=FeedbackType.POSITIVE,
            rating=6  # 超出范围
        )


def test_failure_case_create_request():
    """测试失败案例创建请求"""
    from app.api.v1.endpoints.feedback import FailureCaseCreate

    case_data = FailureCaseCreate(
        feedback_id=uuid4(),
        failure_type=FailureType.RETRIEVAL,
        analysis={"root": "cause"},
        fix_suggestions=["suggestion1", "suggestion2"]
    )

    assert case_data.failure_type == FailureType.RETRIEVAL
    assert len(case_data.fix_suggestions) == 2


def test_improvement_record_create_request():
    """测试改进记录创建请求"""
    from app.api.v1.endpoints.feedback import ImprovementRecordCreate

    record_data = ImprovementRecordCreate(
        failure_case_id=uuid4(),
        improvement_type=ImprovementType.PROMPT,
        before_config={"old": "config"},
        after_config={"new": "config"},
        description="测试改进"
    )

    assert record_data.improvement_type == ImprovementType.PROMPT
    assert record_data.description == "测试改进"


# ==================== 性能测试 ====================

@pytest.mark.asyncio
async def test_analyzer_performance_with_many_feedbacks():
    """测试批量分析性能"""
    analyzer = FailureAnalyzer()

    # 创建 100 个反馈
    feedbacks = []
    for i in range(100):
        feedback = UserFeedback(
            id=uuid4(),
            session_id=f"session_{i}",
            query=f"查询 {i}",
            response=f"响应 {i}",
            feedback_type=FeedbackType.NEGATIVE,
            rating=2,
            comment="不满意",
            retrieval_method="simple",
            chunks_used=[],
            created_at=datetime.now()
        )
        feedbacks.append(feedback)

    # 测试分类性能
    import time
    start = time.time()

    for feedback in feedbacks:
        analyzer._classify_failure_type(feedback)

    elapsed = time.time() - start

    # 应该在 1 秒内完成
    assert elapsed < 1.0


# ==================== 边界情况测试 ====================

def test_feedback_with_no_comment(sample_feedback):
    """测试没有评论的反馈"""
    sample_feedback.comment = None

    feedback_dict = sample_feedback.to_dict()

    assert feedback_dict["comment"] is None


def test_feedback_with_no_chunks(sample_feedback):
    """测试没有文档块的反馈"""
    sample_feedback.chunks_used = []

    assert len(sample_feedback.chunks_used) == 0


@pytest.mark.asyncio
async def test_analyzer_with_empty_feedback():
    """测试空反馈分析"""
    analyzer = FailureAnalyzer()

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="",
        response="",
        feedback_type=FeedbackType.NEUTRAL,
        rating=3,
        retrieval_method="simple",
        chunks_used=[],
        created_at=datetime.now()
    )

    failure_type = analyzer._classify_failure_type(feedback)

    # 应该有一个默认分类
    assert failure_type in FailureType


# ==================== 集成测试 ====================

@pytest.mark.asyncio
async def test_full_feedback_lifecycle(mock_db_session, mock_llm_service):
    """测试完整的反馈生命周期"""
    # 1. 创建反馈
    feedback = UserFeedback(
        id=uuid4(),
        session_id="integration_test",
        query="企业所得税优惠",
        response="小型微利企业享受优惠。",
        feedback_type=FeedbackType.NEGATIVE,
        rating=2,
        comment="答案不完整",
        retrieval_method="simple",
        chunks_used=[],
        created_at=datetime.now()
    )

    # 2. 分析失败案例
    analyzer = FailureAnalyzer(
        llm_service=mock_llm_service,
        db_session=mock_db_session
    )
    failure_case = await analyzer.analyze_feedback(feedback, use_llm=True)

    assert failure_case is not None
    assert failure_case.failure_type in FailureType

    # 3. 生成改进建议
    improvement = await analyzer.suggest_improvements(failure_case)

    assert improvement is not None
    assert improvement.failure_case_id == failure_case.id
    assert improvement.improvement_type in ImprovementType

    # 验证整个流程的数据库操作
    assert mock_db_session.add.call_count >= 2
    assert mock_db_session.commit.call_count >= 2


# ==================== 错误处理测试 ====================

@pytest.mark.asyncio
async def test_analyzer_handles_invalid_feedback():
    """测试处理无效反馈"""
    analyzer = FailureAnalyzer()

    # 创建一个基本有效但数据缺失的反馈
    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="test",
        response="test",
        feedback_type=FeedbackType.NEGATIVE,
        retrieval_method=None,  # 缺失
        chunks_used=None,  # 缺失
        created_at=datetime.now()
    )

    # 应该能处理而不崩溃
    failure_type = analyzer._classify_failure_type(feedback)
    assert failure_type in FailureType

    analysis = analyzer._analyze_with_rules(feedback, failure_type)
    assert "failure_type" in analysis


@pytest.mark.asyncio
async def test_analyzer_handles_database_error(mock_db_session):
    """测试处理数据库错误"""
    mock_db_session.commit.side_effect = Exception("Database Error")

    analyzer = FailureAnalyzer(db_session=mock_db_session)

    feedback = UserFeedback(
        id=uuid4(),
        session_id="test",
        query="test",
        response="test",
        feedback_type=FeedbackType.NEGATIVE,
        created_at=datetime.now()
    )

    # 应该抛出异常
    with pytest.raises(Exception):
        await analyzer.analyze_feedback(feedback)
