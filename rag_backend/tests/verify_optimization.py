#!/usr/bin/env python3
"""
快速验证优化后的 policy_agent.py 代码

验证点：
1. 导入成功
2. 辅助函数工作正常
3. Pydantic 模型验证通过
4. 业务常量定义正确
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """测试导入"""
    try:
        from app.api.v1.endpoints.policy_agent import (
            _create_enterprise_profile,
            _policy_input_to_dict,
            MAX_POLICIES_PER_REQUEST,
            MAX_POLICY_CONTENT_LENGTH,
            PolicyInput,
            EnterpriseProfileInput,
        )
        print("✓ 所有导入成功")
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_constants():
    """测试常量定义"""
    try:
        assert MAX_POLICIES_PER_REQUEST == 100
        assert MAX_POLICY_CONTENT_LENGTH == 50000
        print("✓ 常量定义正确")
        return True
    except Exception as e:
        print(f"✗ 常量测试失败: {e}")
        return False


def test_helper_functions():
    """测试辅助函数"""
    try:
        from app.api.v1.endpoints.policy_agent import (
            _create_enterprise_profile,
            _policy_input_to_dict,
            EnterpriseProfileInput,
            PolicyInput,
        )

        enterprise_input = EnterpriseProfileInput(
            enterprise_id="ent_123",
            enterprise_name="测试企业",
            industry="科技",
            region="深圳",
            scale="中型",
            tax_types=["增值税"],
            qualifications=["高新"]
        )

        profile = _create_enterprise_profile(enterprise_input)
        assert profile.enterprise_id == "ent_123"
        assert profile.industry == "科技"

        policy_input = PolicyInput(
            policy_id="pol_789",
            title="税收优惠",
            content="详细内容",
            priority="high"
        )

        policy_dict = _policy_input_to_dict(policy_input)
        assert policy_dict["policy_id"] == "pol_789"
        assert policy_dict["priority"] == "high"

        print("✓ 辅助函数工作正常")
        return True
    except Exception as e:
        print(f"✗ 辅助函数测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pydantic_models():
    """测试 Pydantic 模型"""
    try:
        from app.api.v1.endpoints.policy_agent import (
            PolicyInput,
            EnterpriseProfileInput,
        )

        policy = PolicyInput(
            policy_id="test_001",
            title="测试",
            content="内容",
            priority="medium"
        )
        assert policy.source == "manual"  # 默认值

        enterprise = EnterpriseProfileInput(
            enterprise_id="ent_001",
            enterprise_name="企业",
            industry="制造",
            region="上海",
            scale="小型"
        )
        assert enterprise.tax_types == []
        assert enterprise.qualifications == []

        print("✓ Pydantic 模型验证通过")
        return True
    except Exception as e:
        print(f"✗ Pydantic 模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("验证 policy_agent.py 优化结果")
    print("=" * 60)

    results = []

    print("\n1. 测试导入...")
    results.append(test_imports())

    print("\n2. 测试常量定义...")
    results.append(test_constants())

    print("\n3. 测试辅助函数...")
    results.append(test_helper_functions())

    print("\n4. 测试 Pydantic 模型...")
    results.append(test_pydantic_models())

    print("\n" + "=" * 60)
    if all(results):
        print("✓ 所有测试通过！优化成功实施。")
        print("=" * 60)
        return 0
    else:
        print("✗ 部分测试失败。请检查错误信息。")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
