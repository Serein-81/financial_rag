"""
政策智能系统集成测试
测试政策采集、检索、通知的完整流程
"""

import pytest
from datetime import datetime
from uuid import uuid4

from app.services.policy_retrieval_service import PolicyRetrievalService
from app.services.policy_notification_service import PolicyNotificationService
from app.services.policy_scheduler import PolicyScheduler, SchedulerConfig, UpdateFrequency
from app.services.policy_collector import PolicySource
from app.models.policy import Policy, PolicyStatus, PolicyPriority


@pytest.mark.asyncio
async def test_policy_retrieval_service_initialization():
    """测试政策检索服务初始化"""
    service = PolicyRetrievalService()
    
    assert service.default_top_k == 10
    assert service.min_score_threshold == 0.5


@pytest.mark.asyncio
async def test_cosine_similarity_calculation():
    """测试余弦相似度计算"""
    service = PolicyRetrievalService()
    
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    similarity = service._cosine_similarity(vec1, vec2)
    assert similarity == 1.0
    
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0]
    similarity = service._cosine_similarity(vec1, vec2)
    assert similarity == 0.0
    
    vec1 = [1.0, 1.0, 0.0]
    vec2 = [1.0, 0.0, 1.0]
    similarity = service._cosine_similarity(vec1, vec2)
    assert similarity == pytest.approx(0.5, rel=0.01)


@pytest.mark.asyncio
async def test_match_score_calculation():
    """测试匹配分数计算"""
    service = PolicyNotificationService()
    
    policy_data = {
        "industries": ["制造业", "科技"],
        "regions": ["北京", "上海"],
        "tax_types": ["增值税", "企业所得税"],
        "scales": ["大型企业"],
        "priority": "high"
    }
    
    enterprise_profile = {
        "industry": "制造业",
        "region": "北京",
        "tax_types": ["增值税", "个人所得税"],
        "scale": "大型企业"
    }
    
    score = service._calculate_match_score(policy_data, enterprise_profile)
    
    assert score >= 0.6
    assert score <= 1.0


@pytest.mark.asyncio
async def test_match_reason_generation():
    """测试匹配原因生成"""
    service = PolicyNotificationService()
    
    policy_data = {
        "industries": ["制造业"],
        "regions": ["北京"],
        "tax_types": ["增值税"]
    }
    
    reasons = service._generate_match_reasons(policy_data, "test_enterprise")
    
    assert len(reasons) > 0
    assert any("制造业" in reason for reason in reasons)


@pytest.mark.asyncio
async def test_scheduler_config_creation():
    """测试调度器配置创建"""
    config = SchedulerConfig(
        frequency=UpdateFrequency.DAILY,
        keywords=["税务", "优惠政策"],
        enabled_sources=["国家税务总局"],
        time_of_day="03:00"
    )
    
    assert config.frequency == UpdateFrequency.DAILY
    assert config.keywords == ["税务", "优惠政策"]
    assert config.enabled_sources == ["国家税务总局"]
    assert config.time_of_day == "03:00"


@pytest.mark.asyncio
async def test_policy_source_creation():
    """测试政策来源创建"""
    source = PolicySource(
        name="国家税务总局",
        base_url="https://www.chinatax.gov.cn",
        enabled=True,
        priority=1,
        list_pattern="/api/policies",
        search_keywords=["税务", "税收"]
    )
    
    assert source.name == "国家税务总局"
    assert source.enabled is True
    assert source.priority == 1


@pytest.mark.asyncio
async def test_scheduler_initialization():
    """测试调度器初始化"""
    scheduler = PolicyScheduler()
    
    assert scheduler._running is False
    assert scheduler._task is None
    assert isinstance(scheduler._config, SchedulerConfig)


@pytest.mark.asyncio
async def test_enterprise_profile_extraction():
    """测试企业画像提取"""
    service = PolicyNotificationService()
    
    class MockTenant:
        industry = "制造业"
        region = "北京"
        scale = "大型企业"
        tax_types = ["增值税", "企业所得税"]
        meta_info = {"keywords": ["智能制造", "数字化"]}
    
    tenant = MockTenant()
    profile = service._get_enterprise_profile(tenant)
    
    assert profile["industry"] == "制造业"
    assert profile["region"] == "北京"
    assert profile["scale"] == "大型企业"
    assert profile["tax_types"] == ["增值税", "企业所得税"]
    assert profile["keywords"] == ["智能制造", "数字化"]


@pytest.mark.asyncio
async def test_build_match_query():
    """测试构建匹配查询"""
    service = PolicyRetrievalService()
    
    profile = {
        "industry": "制造业",
        "scale": "大型企业",
        "tax_types": ["增值税", "企业所得税"],
        "keywords": ["智能制造", "数字化转型", "工业4.0"]
    }
    
    query = service._build_match_query(profile)
    
    assert "制造业" in query
    assert "大型企业" in query
    assert "增值税" in query
    assert "企业所得税" in query


@pytest.mark.asyncio
async def test_explain_match():
    """测试匹配解释"""
    service = PolicyRetrievalService()
    
    policy = {
        "industries": ["制造业", "科技"],
        "regions": ["北京", "上海"],
        "tax_types": ["增值税"],
        "priority": "high"
    }
    
    profile = {
        "industry": "制造业",
        "region": "北京",
        "tax_types": ["增值税", "个人所得税"]
    }
    
    reasons = service._explain_match(policy, profile)
    
    assert len(reasons) >= 2
    assert any("制造业" in reason for reason in reasons)
    assert any("北京" in reason for reason in reasons)


def test_policy_model_creation():
    """测试政策模型创建"""
    policy = Policy(
        id=uuid4(),
        policy_id="POL-2024-001",
        title="关于完善增值税政策的公告",
        content="根据相关法律法规，现就完善增值税政策公告如下...",
        summary="完善增值税政策的公告",
        source_name="国家税务总局",
        source_url="https://www.chinatax.gov.cn/...",
        published_date=datetime.now(),
        effective_date=datetime.now(),
        priority=PolicyPriority.HIGH,
        status=PolicyStatus.ACTIVE,
        industries=["制造业", "服务业"],
        regions=["全国"],
        tax_types=["增值税"],
        scales=["所有规模"],
        tags=["增值税", "税务改革"],
        view_count=100,
        tenant_id="default"
    )
    
    assert policy.title == "关于完善增值税政策的公告"
    assert policy.priority == PolicyPriority.HIGH
    assert policy.status == PolicyStatus.ACTIVE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
