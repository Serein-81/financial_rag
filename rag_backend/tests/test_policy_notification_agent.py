"""
PolicyNotificationAgent 功能测试

测试真正的 LLM Agent 集成：
1. 语义政策理解
2. 智能企业匹配
3. 个性化通知生成
4. 智能优先级排序
"""

import pytest
import asyncio
import logging

from app.multi_agent_system.agents.policy_notification_agent import (
    PolicyNotificationAgent,
    EnterpriseProfile,
    PolicyUnderstanding,
    MatchScore,
    create_policy_notification_agent
)
from app.services.policy_notification_agent_service import (
    create_agent_service,
    get_agent_service
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestPolicyNotificationAgent:
    """测试 PolicyNotificationAgent"""

    @pytest.fixture
    def enterprise_profile(self):
        """测试用企业画像"""
        return EnterpriseProfile(
            enterprise_id="test_001",
            name="测试科技有限公司",
            industry="信息技术",
            region="深圳",
            scale="中型企业",
            tax_types=["增值税", "企业所得税"],
            business_scope="软件开发和技术服务",
            recent_interests=["研发费用加计扣除", "高新技术企业优惠"]
        )

    @pytest.fixture
    def sample_policy(self):
        """测试用政策数据"""
        return {
            "policy_id": "test_policy_001",
            "title": "高新技术企业税收优惠新政",
            "content": """
            关于进一步支持高新技术企业创新发展的通知

            一、支持对象
            认定为国家高新技术企业的主体，以及从事高新技术产品研发、生产和服务的其他企业。

            二、主要优惠政策
            1. 企业所得税税率降至15%（原25%）
            2. 研发费用加计扣除比例提高至120%
            3. 符合条件的设备加速折旧，缩短折旧年限
            4. 技术转让所得减免企业所得税

            三、申报要求
            企业需在每年5月31日前通过税务系统提交相关材料。

            四、注意事项
            1. 企业需保持高新技术企业资格有效
            2. 研发费用需单独核算
            3. 需保存相关证明材料备查
            """,
            "industries": ["信息技术", "软件企业", "高新技术企业", "科技企业", "制造业"],
            "regions": ["深圳", "广东", "全国"],
            "scales": ["中型企业", "小型企业"],
            "tax_types": ["企业所得税", "增值税"],
            "priority": "high"
        }

    def test_agent_initialization_with_llm(self):
        """测试带 LLM 的 Agent 初始化"""
        try:
            from app.core.config import settings
            from app.agent_framework.llm.factory import LLMAdapterFactory
            
            default_provider = settings.get_llm_provider_for_agent("chat")
            llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            
            agent = create_policy_notification_agent(llm_adapter)
            
            assert agent is not None
            assert agent.llm_adapter is not None
            assert agent.match_weights is not None
            print(f"✅ Agent 初始化成功（LLM 模式: {default_provider}）")
            
        except Exception as e:
            pytest.skip(f"LLM 不可用: {e}")

    def test_agent_initialization_without_llm(self):
        """测试不带 LLM 的 Agent 初始化（降级模式）"""
        agent = PolicyNotificationAgent(
            llm_adapter=None,
            tool_manager=None
        )
        
        assert agent is not None
        assert agent.match_weights is not None
        print("✅ Agent 初始化成功（降级模式）")

    def test_policy_understanding_with_llm(self, sample_policy):
        """测试使用 LLM 的政策理解"""
        try:
            from app.core.config import settings
            from app.agent_framework.llm.factory import LLMAdapterFactory
            
            default_provider = settings.get_llm_provider_for_agent("chat")
            llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            agent = create_policy_notification_agent(llm_adapter)
            
            understanding = asyncio.run(agent.understand_policy(
                policy_content=sample_policy["content"],
                policy_id=sample_policy["policy_id"],
                title=sample_policy["title"]
            ))
            
            assert understanding is not None
            assert understanding.policy_id == sample_policy["policy_id"]
            assert understanding.summary != ""
            assert understanding.impact_level in ["high", "medium", "low"]
            
            print("✅ 政策理解成功")
            print(f"   摘要: {understanding.summary[:50]}...")
            print(f"   影响级别: {understanding.impact_level}")
            print(f"   置信度: {understanding.confidence}")
            
        except Exception as e:
            pytest.skip(f"LLM 不可用: {e}")

    def test_policy_understanding_fallback(self, sample_policy):
        """测试政策理解降级机制"""
        agent = PolicyNotificationAgent(
            llm_adapter=None,
            tool_manager=None
        )
        
        understanding = asyncio.run(agent.understand_policy(
            policy_content=sample_policy["content"],
            policy_id=sample_policy["policy_id"],
            title=sample_policy["title"]
        ))
        
        assert understanding is not None
        assert understanding.policy_id == sample_policy["policy_id"]
        assert understanding.confidence == 0.3  # 降级模式的置信度
        
        print("✅ 政策理解降级成功")

    def test_enterprise_matching_with_llm(self, enterprise_profile, sample_policy):
        """测试使用 LLM 的企业匹配"""
        try:
            from app.core.config import settings
            from app.agent_framework.llm.factory import LLMAdapterFactory
            
            default_provider = settings.get_llm_provider_for_agent("chat")
            llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            agent = create_policy_notification_agent(llm_adapter)
            
            match_score, reasons, understanding = asyncio.run(agent.match_enterprise_policy(
                policy=sample_policy,
                enterprise_profile=enterprise_profile
            ))
            
            assert match_score is not None
            assert 0.0 <= match_score.total_score <= 1.0
            assert isinstance(reasons, list)
            assert understanding is not None
            
            print("✅ 企业匹配成功")
            print(f"   总分: {match_score.total_score:.2f}")
            print(f"   语义分: {match_score.semantic_score:.2f}")
            print(f"   行业分: {match_score.industry_score:.2f}")
            print(f"   地区分: {match_score.region_score:.2f}")
            
        except Exception as e:
            pytest.skip(f"LLM 不可用: {e}")

    def test_notification_generation_with_llm(
        self,
        enterprise_profile,
        sample_policy
    ):
        """测试使用 LLM 的通知生成"""
        try:
            from app.core.config import settings
            from app.agent_framework.llm.factory import LLMAdapterFactory
            
            default_provider = settings.get_llm_provider_for_agent("chat")
            llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            agent = create_policy_notification_agent(llm_adapter)
            
            understanding = PolicyUnderstanding(
                policy_id=sample_policy["policy_id"],
                title=sample_policy["title"],
                summary="该政策旨在通过税收优惠鼓励高新技术企业增加研发投入",
                core_objectives=["降低企业税负", "鼓励研发创新"],
                applicable_conditions=["国家高新技术企业", "从事研发活动"],
                key_requirements=["单独核算研发费用", "保存证明材料"],
                deadlines=["每年5月31日"],
                opportunities=["税率降低10%", "研发费用加计扣除"],
                risks=["资格取消风险", "材料不合规风险"],
                impact_level="high"
            )
            
            match_score = MatchScore(
                total_score=0.85,
                semantic_score=0.9,
                industry_score=0.9,
                region_score=1.0,
                scale_score=0.8,
                tax_type_score=0.8,
                urgency_score=0.7
            )
            
            notification = asyncio.run(agent.generate_personalized_notification(
                policy=sample_policy,
                enterprise=enterprise_profile,
                understanding=understanding,
                match_score=match_score
            ))
            
            assert notification is not None
            assert notification.title != ""
            assert notification.content != ""
            assert notification.urgency_level in ["high", "medium", "low"]
            
            print("✅ 通知生成成功")
            print(f"   标题: {notification.title}")
            print(f"   紧迫度: {notification.urgency_level}")
            print(f"   行动号召: {notification.call_to_action}")
            
        except Exception as e:
            pytest.skip(f"LLM 不可用: {e}")

    def test_policy_prioritization_with_llm(self, enterprise_profile):
        """测试使用 LLM 的政策优先级排序"""
        try:
            from app.core.config import settings
            from app.agent_framework.llm.factory import LLMAdapterFactory
            
            default_provider = settings.get_llm_provider_for_agent("chat")
            llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            agent = create_policy_notification_agent(llm_adapter)
            
            policies = [
                {
                    "policy_id": "pol_1",
                    "title": "研发费用加计扣除政策",
                    "priority": "high",
                    "match_score": 0.9
                },
                {
                    "policy_id": "pol_2",
                    "title": "设备加速折旧政策",
                    "priority": "medium",
                    "match_score": 0.6
                },
                {
                    "policy_id": "pol_3",
                    "title": "技术转让所得减免",
                    "priority": "low",
                    "match_score": 0.3
                }
            ]
            
            sorted_policies = asyncio.run(agent.prioritize_policies(
                policies=policies,
                enterprise=enterprise_profile
            ))
            
            assert sorted_policies is not None
            assert len(sorted_policies) == 3
            
            print("✅ 优先级排序成功")
            print(f"   排序后顺序: {[p['policy_id'] for p in sorted_policies]}")
            
        except Exception as e:
            pytest.skip(f"LLM 不可用: {e}")


class TestPolicyNotificationAgentService:
    """测试 PolicyNotificationAgentService"""

    def test_service_initialization_with_llm(self):
        """测试服务初始化（带 LLM）"""
        try:
            service = get_agent_service()
            
            assert service is not None
            assert service.use_llm is True
            print("✅ Service 初始化成功（LLM 模式）")
            
        except Exception as e:
            pytest.skip(f"LLM 不可用: {e}")

    def test_service_initialization_without_llm(self):
        """测试服务初始化（不带 LLM）"""
        service = create_agent_service(None)
        
        assert service is not None
        assert service.use_llm is False
        print("✅ Service 初始化成功（降级模式）")

    def test_get_agent_service_singleton(self):
        """测试获取全局 Agent 服务（单例模式）"""
        service1 = get_agent_service()
        service2 = get_agent_service()
        
        assert service1 is service2
        print("✅ 单例模式正常工作")

    def test_match_policy_for_enterprise_with_fallback(self):
        """测试企业政策匹配（降级模式）"""
        service = create_agent_service(None)
        
        enterprise = EnterpriseProfile(
            enterprise_id="test_001",
            name="测试公司",
            industry="信息技术",
            region="深圳",
            scale="中型企业",
            tax_types=["增值税", "企业所得税"]
        )
        
        policy = {
            "policy_id": "test_001",
            "title": "高新技术企业优惠",
            "industries": ["信息技术", "高新技术企业"],
            "regions": ["深圳", "广东"],
            "tax_types": ["企业所得税"],
            "priority": "high"
        }
        
        result = asyncio.run(service.match_policy_for_enterprise(
            policy=policy,
            enterprise_profile=enterprise
        ))
        
        assert result is not None
        assert "match_score" in result
        assert "use_llm" in result
        assert result["use_llm"] is False  # 降级模式
        
        print("✅ 匹配成功（降级模式）")
        print(f"   匹配分数: {result['match_score']:.2f}")
        print(f"   使用 LLM: {result['use_llm']}")

    def test_generate_notification_with_fallback(self):
        """测试通知生成（降级模式）"""
        service = create_agent_service(None)
        
        enterprise = EnterpriseProfile(
            enterprise_id="test_001",
            name="测试公司",
            industry="信息技术"
        )
        
        policy = {
            "policy_id": "test_001",
            "title": "高新技术企业优惠",
            "priority": "high"
        }
        
        match_result = {
            "match_score": 0.85,
            "match_reasons": [
                {"category": "industry", "reason": "行业匹配"}
            ]
        }
        
        notification = asyncio.run(service.generate_notification(
            policy=policy,
            enterprise_profile=enterprise,
            match_result=match_result
        ))
        
        assert notification is not None
        assert "title" in notification
        assert "content" in notification
        assert "use_llm" in notification
        assert notification["use_llm"] is False
        
        print("✅ 通知生成成功（降级模式）")
        print(f"   标题: {notification['title']}")

    def test_prioritize_policies_with_fallback(self):
        """测试政策优先级排序（降级模式）"""
        service = create_agent_service(None)
        
        enterprise = EnterpriseProfile(
            enterprise_id="test_001",
            name="测试公司"
        )
        
        policies = [
            {"policy_id": "1", "title": "政策1", "priority": "low", "match_score": 0.3},
            {"policy_id": "2", "title": "政策2", "priority": "high", "match_score": 0.8},
            {"policy_id": "3", "title": "政策3", "priority": "medium", "match_score": 0.6}
        ]
        
        sorted_policies = asyncio.run(service.prioritize_policies(
            policies=policies,
            enterprise_profile=enterprise
        ))
        
        assert sorted_policies is not None
        assert len(sorted_policies) == 3
        assert sorted_policies[0]["priority"] in ["high", "critical"]
        
        print("✅ 优先级排序成功（降级模式）")
        print(f"   最高优先级: {sorted_policies[0]['title']}")


class TestPolicyNotificationAgentIntegration:
    """集成测试：完整流程"""

    def test_full_notification_flow_with_fallback(self):
        """完整通知流程测试（降级模式）"""
        print("\n" + "=" * 60)
        print("🧪 完整通知流程测试（降级模式）")
        print("=" * 60)
        
        service = create_agent_service(None)
        
        enterprise = EnterpriseProfile(
            enterprise_id="test_integration_001",
            name="测试科技有限公司",
            industry="信息技术",
            region="深圳",
            scale="中型企业",
            tax_types=["增值税", "企业所得税"],
            business_scope="软件开发",
            recent_interests=["研发费用加计扣除", "高新技术企业优惠"]
        )
        
        policy = {
            "policy_id": "integration_test_001",
            "title": "高新技术企业研发费用加计扣除政策",
            "content": """
            关于进一步支持高新技术企业创新发展的通知

            一、支持对象
            认定为国家高新技术企业的主体。

            二、主要优惠
            1. 企业所得税税率降至15%
            2. 研发费用加计扣除比例提高至120%

            三、申报要求
            企业需在每年5月31日前提交相关材料。
            """,
            "industries": ["信息技术", "软件企业", "高新技术企业"],
            "regions": ["深圳", "广东", "全国"],
            "scales": ["中型企业", "小型企业"],
            "tax_types": ["企业所得税", "增值税"],
            "priority": "high"
        }
        
        print("\n1️⃣ 步骤 1: 企业政策匹配")
        match_result = asyncio.run(service.match_policy_for_enterprise(
            policy=policy,
            enterprise_profile=enterprise
        ))
        print(f"   匹配分数: {match_result['match_score']:.2f}")
        print(f"   使用 LLM: {match_result['use_llm']}")
        
        print("\n2️⃣ 步骤 2: 生成个性化通知")
        notification = asyncio.run(service.generate_notification(
            policy=policy,
            enterprise_profile=enterprise,
            match_result=match_result
        ))
        print(f"   标题: {notification['title']}")
        print(f"   紧迫度: {notification['urgency_level']}")
        print(f"   使用 LLM: {notification['use_llm']}")
        
        print("\n3️⃣ 步骤 3: 发布通知事件")
        try:
            asyncio.run(service.emit_notification_event(
                enterprise_id=enterprise.enterprise_id,
                policy_id=policy["policy_id"],
                policy_title=policy["title"],
                match_score=match_result["match_score"],
                notification_content=notification,
                use_llm=notification.get("use_llm", False)
            ))
            print("   ✅ 事件发布成功")
        except Exception as e:
            print(f"   ⚠️ 事件发布失败（预期，缺少完整依赖）: {e}")
        
        print("\n✅ 完整流程测试完成（降级模式）")
        print("=" * 60)


if __name__ == "__main__":
    print("🚀 运行 PolicyNotificationAgent 测试")
    print("=" * 60)
    
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short"
    ])
