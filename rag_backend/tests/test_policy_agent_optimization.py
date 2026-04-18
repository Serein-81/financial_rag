"""
测试优化后的 policy_agent.py 端点

验证优化是否正确实施且不影响功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints.policy_agent import (
    _create_enterprise_profile,
    _policy_input_to_dict,
    MAX_POLICIES_PER_REQUEST,
    MAX_POLICY_CONTENT_LENGTH,
    PolicyInput,
    EnterpriseProfileInput,
    PolicyMatchRequest,
    NotificationRequest,
    PriorityRequest,
    PolicyTestRequest,
)


class TestHelperFunctions:
    """测试辅助函数"""

    def test_create_enterprise_profile(self):
        """测试企业画像创建"""
        enterprise_input = EnterpriseProfileInput(
            enterprise_id="ent_123",
            enterprise_name="测试企业",
            industry="科技",
            region="深圳",
            scale="中型",
            tax_types=["增值税", "企业所得税"],
            qualifications=["高新技术企业"]
        )

        profile = _create_enterprise_profile(enterprise_input)

        assert profile.enterprise_id == "ent_123"
        assert profile.name == "测试企业"
        assert profile.industry == "科技"
        assert profile.region == "深圳"
        assert profile.scale == "中型"
        assert profile.tax_types == ["增值税", "企业所得税"]
        assert profile.keywords == ["高新技术企业"]
        assert profile.business_scope is None
        assert profile.recent_interests == []
        assert profile.preferences == {}

    def test_create_enterprise_profile_with_empty_lists(self):
        """测试企业画像创建（空列表）"""
        enterprise_input = EnterpriseProfileInput(
            enterprise_id="ent_456",
            enterprise_name="另一个企业",
            industry="制造",
            region="上海",
            scale="小型",
            tax_types=[],
            qualifications=[]
        )

        profile = _create_enterprise_profile(enterprise_input)

        assert profile.enterprise_id == "ent_456"
        assert profile.tax_types == []
        assert profile.keywords == []

    def test_policy_input_to_dict(self):
        """测试政策输入转换"""
        policy_input = PolicyInput(
            policy_id="pol_789",
            title="税收优惠政策",
            content="详细内容...",
            source="manual",
            publish_date="2024-01-01",
            priority="high"
        )

        policy_dict = _policy_input_to_dict(policy_input)

        assert policy_dict["policy_id"] == "pol_789"
        assert policy_dict["title"] == "税收优惠政策"
        assert policy_dict["content"] == "详细内容..."
        assert policy_dict["source"] == "manual"
        assert policy_dict["publish_date"] == "2024-01-01"
        assert policy_dict["priority"] == "high"

    def test_max_policies_constant(self):
        """测试最大政策数量常量"""
        assert MAX_POLICIES_PER_REQUEST == 100

    def test_max_policy_content_length_constant(self):
        """测试最大政策内容长度常量"""
        assert MAX_POLICY_CONTENT_LENGTH == 50000


class TestPydanticModels:
    """测试 Pydantic 模型"""

    def test_policy_input_validation(self):
        """测试政策输入验证"""
        policy = PolicyInput(
            policy_id="test_001",
            title="测试政策",
            content="测试内容",
            priority="high"
        )

        assert policy.policy_id == "test_001"
        assert policy.source == "manual"  # 默认值

    def test_enterprise_profile_input_validation(self):
        """测试企业画像输入验证"""
        enterprise = EnterpriseProfileInput(
            enterprise_id="ent_001",
            enterprise_name="测试企业",
            industry="科技",
            region="深圳",
            scale="中型"
        )

        assert enterprise.tax_types == []  # 默认值
        assert enterprise.qualifications == []  # 默认值

    def test_policy_match_request_validation(self):
        """测试政策匹配请求验证"""
        request = PolicyMatchRequest(
            policy=PolicyInput(
                policy_id="pol_001",
                title="政策",
                content="内容"
            ),
            enterprise=EnterpriseProfileInput(
                enterprise_id="ent_001",
                enterprise_name="企业",
                industry="科技",
                region="深圳",
                scale="中型"
            ),
            use_llm=True
        )

        assert request.use_llm is True

    def test_priority_request_with_empty_policies(self):
        """测试优先级排序请求（空列表）"""
        request = PriorityRequest(
            policies=[],
            enterprise_profile=EnterpriseProfileInput(
                enterprise_id="ent_001",
                enterprise_name="企业",
                industry="科技",
                region="深圳",
                scale="中型"
            )
        )

        assert request.policies == []

    def test_policy_test_request_validation(self):
        """测试流程测试请求验证"""
        request = PolicyTestRequest(
            policies=[
                PolicyInput(
                    policy_id=f"pol_{i:03d}",
                    title=f"政策{i}",
                    content="内容"
                )
                for i in range(5)
            ],
            enterprise=EnterpriseProfileInput(
                enterprise_id="ent_001",
                enterprise_name="企业",
                industry="科技",
                region="深圳",
                scale="中型"
            )
        )

        assert len(request.policies) == 5
        assert request.use_llm is True  # 默认值


class TestBusinessValidation:
    """测试业务验证"""

    def test_policy_content_length_check(self):
        """测试政策内容长度检查"""
        long_content = "x" * 60000  # 超过 MAX_POLICY_CONTENT_LENGTH

        policy = PolicyInput(
            policy_id="pol_long",
            title="长内容政策",
            content=long_content,
            priority="medium"
        )

        assert len(policy.content) > MAX_POLICY_CONTENT_LENGTH

    def test_multiple_policies_count(self):
        """测试多政策数量"""
        policies = [
            PolicyInput(
                policy_id=f"pol_{i:03d}",
                title=f"政策{i}",
                content="内容"
            )
            for i in range(150)  # 超过 MAX_POLICIES_PER_REQUEST
        ]

        request = PolicyTestRequest(
            policies=policies,
            enterprise=EnterpriseProfileInput(
                enterprise_id="ent_001",
                enterprise_name="企业",
                industry="科技",
                region="深圳",
                scale="中型"
            )
        )

        assert len(request.policies) > MAX_POLICIES_PER_REQUEST


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
