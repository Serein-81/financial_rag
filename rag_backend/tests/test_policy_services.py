"""
政策智能系统功能测试
测试政策采集、检索、通知的完整流程
"""

import pytest
from datetime import datetime
from uuid import uuid4

pytest.importorskip("pgvector", reason="pgvector required for model imports")

from app.services.policy_retrieval_service import PolicyRetrievalService
from app.services.policy_notification_service import PolicyNotificationService
from app.services.policy_scheduler import PolicyScheduler, SchedulerConfig, UpdateFrequency
from app.services.policy_collector import PolicyCollector, PolicySource, CollectedPolicy
from app.services.policy_collector.robots_checker import RobotsChecker
from app.services.policy_collector.rate_limiter import RateLimiter, RateLimitConfig
from app.models.policy import Policy, PolicyStatus, PolicyPriority
from app.models.enterprise_policy_match import EnterprisePolicyMatch, NotificationStatus, MatchStatus


class TestPolicyRetrievalService:
    """测试政策检索服务"""
    
    def test_initialization(self):
        """测试服务初始化"""
        service = PolicyRetrievalService()
        assert service.default_top_k == 10
        assert service.min_score_threshold == 0.5
    
    def test_cosine_similarity_same_vector(self):
        """测试相同向量的相似度"""
        service = PolicyRetrievalService()
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = service._cosine_similarity(vec1, vec2)
        assert similarity == 1.0
    
    def test_cosine_similarity_orthogonal_vectors(self):
        """测试正交向量的相似度"""
        service = PolicyRetrievalService()
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = service._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
    
    def test_cosine_similarity_partial(self):
        """测试部分相似的向量"""
        service = PolicyRetrievalService()
        vec1 = [1.0, 1.0, 0.0]
        vec2 = [1.0, 0.0, 1.0]
        similarity = service._cosine_similarity(vec1, vec2)
        assert 0.4 < similarity < 0.6
    
    def test_cosine_similarity_empty_vector(self):
        """测试空向量的处理"""
        service = PolicyRetrievalService()
        similarity = service._cosine_similarity([], [])
        assert similarity == 0.0
    
    def test_build_match_query_with_industry(self):
        """测试构建包含行业的查询"""
        service = PolicyRetrievalService()
        profile = {"industry": "制造业", "scale": "大型企业"}
        query = service._build_match_query(profile)
        assert "制造业" in query
        assert "大型企业" in query
    
    def test_build_match_query_with_tax_types(self):
        """测试构建包含税种的查询"""
        service = PolicyRetrievalService()
        profile = {
            "tax_types": ["增值税", "企业所得税"]
        }
        query = service._build_match_query(profile)
        assert "增值税" in query
        assert "企业所得税" in query
    
    def test_build_match_query_empty_profile(self):
        """测试空画像的默认查询"""
        service = PolicyRetrievalService()
        query = service._build_match_query({})
        assert "税务政策" in query
    
    def test_explain_match_industry(self):
        """测试行业匹配解释"""
        service = PolicyRetrievalService()
        policy = {"industries": ["制造业"], "regions": []}
        profile = {"industry": "制造业"}
        reasons = service._explain_match(policy, profile)
        assert any("制造业" in r for r in reasons)
    
    def test_explain_match_region(self):
        """测试地区匹配解释"""
        service = PolicyRetrievalService()
        policy = {"industries": [], "regions": ["北京"]}
        profile = {"industry": "", "region": "北京"}
        reasons = service._explain_match(policy, profile)
        assert any("北京" in r for r in reasons)
    
    def test_explain_match_priority(self):
        """测试优先级匹配解释"""
        service = PolicyRetrievalService()
        policy = {"industries": [], "regions": [], "priority": "high"}
        profile = {}
        reasons = service._explain_match(policy, profile)
        assert any("高优先级" in r for r in reasons)


class TestPolicyNotificationService:
    """测试政策通知服务"""
    
    def test_initialization(self):
        """测试服务初始化"""
        service = PolicyNotificationService()
        assert service.match_threshold == 0.6
        assert service.batch_size == 100
    
    def test_calculate_match_score_full_match(self):
        """测试完全匹配"""
        service = PolicyNotificationService()
        policy = {
            "industries": ["制造业"],
            "regions": ["北京"],
            "tax_types": ["增值税"],
            "scales": ["大型企业"]
        }
        profile = {
            "industry": "制造业",
            "region": "北京",
            "tax_types": ["增值税"],
            "scale": "大型企业"
        }
        score = service._calculate_match_score(policy, profile)
        assert score >= 0.9
    
    def test_calculate_match_score_partial_match(self):
        """测试部分匹配"""
        service = PolicyNotificationService()
        policy = {
            "industries": ["制造业"],
            "regions": ["上海"],
            "tax_types": ["增值税"],
            "scales": []
        }
        profile = {
            "industry": "制造业",
            "region": "北京",
            "tax_types": ["增值税"],
            "scale": ""
        }
        score = service._calculate_match_score(policy, profile)
        assert 0.3 < score < 0.8
    
    def test_calculate_match_score_no_match(self):
        """测试无匹配"""
        service = PolicyNotificationService()
        policy = {
            "industries": ["农业"],
            "regions": ["农村"],
            "tax_types": ["农业税"],
            "scales": []
        }
        profile = {
            "industry": "制造业",
            "region": "北京",
            "tax_types": ["增值税"],
            "scale": ""
        }
        score = service._calculate_match_score(policy, profile)
        assert score < 0.3
    
    def test_generate_match_reasons(self):
        """测试生成匹配原因"""
        service = PolicyNotificationService()
        policy = {
            "industries": ["制造业", "科技"],
            "regions": ["北京", "上海"],
            "tax_types": ["增值税"]
        }
        reasons = service._generate_match_reasons(policy, "test")
        assert len(reasons) > 0
        assert any("制造业" in r or "科技" in r for r in reasons)
    
    def test_get_enterprise_profile(self):
        """测试企业画像提取"""
        service = PolicyNotificationService()
        
        class MockTenant:
            industry = "制造业"
            region = "北京"
            scale = "大型企业"
            tax_types = ["增值税"]
            meta_info = {"keywords": ["智能制造"]}
        
        profile = service._get_enterprise_profile(MockTenant())
        assert profile["industry"] == "制造业"
        assert profile["region"] == "北京"
        assert profile["keywords"] == ["智能制造"]


class TestPolicyScheduler:
    """测试政策调度器"""
    
    def test_initialization(self):
        """测试调度器初始化"""
        scheduler = PolicyScheduler()
        assert scheduler._running is False
        assert scheduler._task is None
        assert isinstance(scheduler._config, SchedulerConfig)
    
    def test_scheduler_config(self):
        """测试调度器配置"""
        config = SchedulerConfig(
            frequency=UpdateFrequency.DAILY,
            keywords=["税务"],
            time_of_day="03:00"
        )
        assert config.frequency == UpdateFrequency.DAILY
        assert config.keywords == ["税务"]
        assert config.time_of_day == "03:00"
    
    def test_update_frequency_enum(self):
        """测试更新频率枚举"""
        assert UpdateFrequency.HOURLY.value == "hourly"
        assert UpdateFrequency.DAILY.value == "daily"
        assert UpdateFrequency.WEEKLY.value == "weekly"
        assert UpdateFrequency.MONTHLY.value == "monthly"


class TestPolicyCollector:
    """测试政策采集器"""
    
    def test_initialization(self):
        """测试采集器初始化"""
        collector = PolicyCollector()
        assert len(collector.sources) > 0
        assert collector._http_client is None  # 初始化时为 None
    
    def test_policy_source(self):
        """测试政策来源配置"""
        source = PolicySource(
            name="测试来源",
            base_url="https://test.gov.cn",
            search_url="https://test.gov.cn/search",
            list_url="https://test.gov.cn/list",
            enabled=True,
            priority=1
        )
        assert source.name == "测试来源"
        assert source.enabled is True
        assert source.priority == 1
    
    def test_collected_policy(self):
        """测试采集的政策数据"""
        policy = CollectedPolicy(
            source_name="测试来源",
            source_url="https://test.gov.cn/policy/1",
            title="测试政策",
            content="政策内容",
            published_date=datetime.now()
        )
        assert policy.title == "测试政策"
        assert policy.source_name == "测试来源"


class TestRobotsChecker:
    """测试 robots.txt 检查器"""
    
    def test_initialization(self):
        """测试检查器初始化"""
        checker = RobotsChecker()
        assert checker.user_agent == "PolicyCollector/1.0"
        assert len(checker._robots_cache) == 0
    
    def test_initialization_custom_user_agent(self):
        """测试自定义 User-Agent"""
        checker = RobotsChecker(user_agent="CustomBot/1.0")
        assert checker.user_agent == "CustomBot/1.0"


class TestRateLimiter:
    """测试速率限制器"""
    
    def test_initialization(self):
        """测试限流器初始化"""
        limiter = RateLimiter()
        assert limiter.default_config is not None
    
    def test_rate_limit_config(self):
        """测试限流配置"""
        config = RateLimitConfig(
            requests_per_second=1.0,
            requests_per_minute=60,
            requests_per_hour=3600,
            burst_size=5
        )
        assert config.requests_per_second == 1.0
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 3600
    
    def test_default_config_values(self):
        """测试默认配置值"""
        config = RateLimitConfig()
        assert config.requests_per_second == 1.0
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_size == 5
        assert config.min_delay == 0.5


class TestPolicyModel:
    """测试政策数据模型"""
    
    def test_policy_status_enum(self):
        """测试政策状态枚举"""
        assert PolicyStatus.ACTIVE.value == "active"
        assert PolicyStatus.ARCHIVED.value == "archived"
        assert PolicyStatus.DRAFT.value == "draft"
        assert PolicyStatus.EXPIRED.value == "expired"
    
    def test_policy_priority_enum(self):
        """测试政策优先级枚举"""
        assert PolicyPriority.CRITICAL.value == "critical"
        assert PolicyPriority.HIGH.value == "high"
        assert PolicyPriority.MEDIUM.value == "medium"
        assert PolicyPriority.LOW.value == "low"
    
    def test_policy_model_creation(self):
        """测试政策模型创建"""
        now = datetime.now()
        
        policy = Policy(
            policy_id="POL-2024-001",
            title="关于完善增值税政策的公告",
            content="根据相关法律法规...",
            summary="完善增值税政策",
            source_name="国家税务总局",
            source_url="https://chinatax.gov.cn/policy/1",
            published_date=now,
            effective_date=now,
            priority=PolicyPriority.HIGH,
            status=PolicyStatus.ACTIVE,
            industries=["制造业"],
            regions=["全国"],
            tax_types=["增值税"],
            scales=["所有规模"],
            tags=["税务改革"]
        )
        
        assert policy.title == "关于完善增值税政策的公告"
        assert policy.priority == PolicyPriority.HIGH
        assert policy.status == PolicyStatus.ACTIVE
        assert "制造业" in policy.industries
        assert "增值税" in policy.tax_types


class TestEnterprisePolicyMatch:
    """测试企业政策匹配模型"""
    
    def test_notification_status_enum(self):
        """测试通知状态枚举"""
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.SENT.value == "sent"
        assert NotificationStatus.FAILED.value == "failed"
        assert NotificationStatus.ACKNOWLEDGED.value == "acknowledged"
        assert NotificationStatus.DISMISSED.value == "dismissed"
    
    def test_match_status_enum(self):
        """测试匹配状态枚举"""
        assert MatchStatus.ACTIVE.value == "active"
        assert MatchStatus.INACTIVE.value == "inactive"
        assert MatchStatus.EXPIRED.value == "expired"
    
    def test_enterprise_policy_match_creation(self):
        """测试企业政策匹配创建"""
        policy_id = uuid4()
        
        match = EnterprisePolicyMatch(
            enterprise_id="enterprise-001",
            policy_id=policy_id,
            match_score=0.85,
            match_status=MatchStatus.ACTIVE,
            notification_status=NotificationStatus.SENT,
            match_reasons=["适用于制造业行业", "涉及增值税"]
        )
        
        assert match.enterprise_id == "enterprise-001"
        assert match.match_score == 0.85
        assert match.match_status == MatchStatus.ACTIVE
        assert match.notification_status == NotificationStatus.SENT


class TestIntegration:
    """集成测试"""
    
    def test_end_to_end_match_flow(self):
        """测试端到端匹配流程"""
        notification_service = PolicyNotificationService()
        
        policy = {
            "industries": ["制造业"],
            "regions": ["北京"],
            "tax_types": ["增值税", "企业所得税"],
            "priority": "high"
        }
        
        enterprise = {
            "industry": "制造业",
            "region": "北京",
            "tax_types": ["增值税"],
            "scale": "大型企业"
        }
        
        score = notification_service._calculate_match_score(policy, enterprise)
        assert score >= notification_service.match_threshold
        
        reasons = notification_service._generate_match_reasons(policy, enterprise)
        assert len(reasons) > 0
    
    def test_retrieval_and_match_integration(self):
        """测试检索和匹配集成"""
        retrieval_service = PolicyRetrievalService()
        notification_service = PolicyNotificationService()
        
        policy = {
            "industries": ["科技"],
            "regions": ["上海"],
            "tax_types": ["企业所得税"],
            "priority": "medium"
        }
        
        enterprise = {
            "industry": "科技",
            "region": "上海",
            "tax_types": ["企业所得税"],
            "scale": "中小企业"
        }
        
        score = notification_service._calculate_match_score(policy, enterprise)
        reasons = notification_service._generate_match_reasons(policy, enterprise)
        
        assert len(reasons) > 0
        assert score > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
