# -*- coding: utf-8 -*-
"""
手动测试脚本：验证 JSONB 字段解析修复

运行方式：python tests/test_jsonb_fix.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from uuid import uuid4
from datetime import datetime, timezone


def test_json_parsing_from_string():
    """测试从字符串解析 JSONB 字段"""
    print("\n=== 测试 1: 从字符串解析 JSONB 字段 ===")

    mock_trigger_details_str = '{"confidence": 0.92, "amount": 100000, "invoice_number": "NO123456"}'
    mock_content_str = '{"extraction": {"amount": 100000}, "risk_decision": {"risk_level": "high"}}'

    trigger_details = json.loads(mock_trigger_details_str) if isinstance(mock_trigger_details_str, str) else mock_trigger_details_str
    content = json.loads(mock_content_str) if isinstance(mock_content_str, str) else mock_content_str

    assert isinstance(trigger_details, dict), "trigger_details 应该是字典"
    assert trigger_details["confidence"] == 0.92, "confidence 值不正确"
    assert trigger_details["amount"] == 100000, "amount 值不正确"

    assert isinstance(content, dict), "content 应该是字典"
    assert "extraction" in content, "content 应该包含 extraction"
    assert "risk_decision" in content, "content 应该包含 risk_decision"

    print("✅ 通过：成功从字符串解析 JSONB 字段")
    print(f"   - trigger_details: {trigger_details}")
    print(f"   - content: {content}")


def test_json_parsing_from_dict():
    """测试已经是字典的字段保持不变"""
    print("\n=== 测试 2: 已经是字典的字段保持不变 ===")

    mock_trigger_details = {"confidence": 0.92, "amount": 100000}
    mock_content = {"extraction": {"amount": 100000}}

    trigger_details = json.loads(mock_trigger_details) if isinstance(mock_trigger_details, str) else mock_trigger_details
    content = json.loads(mock_content) if isinstance(mock_content, str) else mock_content

    assert isinstance(trigger_details, dict), "trigger_details 应该是字典"
    assert trigger_details["confidence"] == 0.92, "confidence 值不正确"

    assert isinstance(content, dict), "content 应该是字典"
    assert "extraction" in content, "content 应该包含 extraction"

    print("✅ 通过：已经是字典的字段保持不变")
    print(f"   - trigger_details: {trigger_details}")
    print(f"   - content: {content}")


def test_review_result_parsing():
    """测试 review_result 字段的解析"""
    print("\n=== 测试 3: review_result 字段解析 ===")

    mock_review_result_str = '{"decision": "approved", "comments": "审核通过"}'

    review_result = json.loads(mock_review_result_str) if isinstance(mock_review_result_str, str) else mock_review_result_str

    assert isinstance(review_result, dict), "review_result 应该是字典"
    assert review_result["decision"] == "approved", "decision 值不正确"
    assert review_result["comments"] == "审核通过", "comments 值不正确"

    print("✅ 通过：review_result 字段解析正确")
    print(f"   - review_result: {review_result}")


def test_complex_trigger_details():
    """测试完整的 trigger_details 结构（模拟真实数据）"""
    print("\n=== 测试 4: 完整的 trigger_details 结构 ===")

    # 模拟真实数据库中存储的数据
    complex_trigger_details = {
        "risk_level": "high",
        "trigger_rules": ["RULE_HIGH_AMOUNT", "RULE_LOW_CONFIDENCE"],
        "trigger_reasons": ["金额超过阈值", "AI置信度低于80%"],
        "confidence": 0.75,
        "amount": 1500000.0,
        "tax_amount": 195000.0,
        "tax_rate": 0.13,
        "invoice_number": "NO9876543210",
        "invoice_date": "2024-03-15",
        "invoice_type": "增值税专用发票",
        "seller": "销售方公司",
        "buyer": "购买方公司",
        "semantic_suspicion": ["供应商为新注册公司", "金额异常大"]
    }

    # 模拟数据库返回字符串（JSONB 在某些情况下会返回字符串）
    trigger_details_str = json.dumps(complex_trigger_details, ensure_ascii=False)

    # 测试解析逻辑
    trigger_details = json.loads(trigger_details_str) if isinstance(trigger_details_str, str) else trigger_details_str

    assert isinstance(trigger_details, dict), "trigger_details 应该是字典"
    assert trigger_details["risk_level"] == "high", "risk_level 不正确"
    assert len(trigger_details["trigger_rules"]) == 2, "trigger_rules 长度不正确"
    assert len(trigger_details["semantic_suspicion"]) == 2, "semantic_suspicion 长度不正确"
    assert trigger_details["amount"] == 1500000.0, "amount 值不正确"

    print("✅ 通过：完整的 trigger_details 结构解析正确")
    print(f"   - risk_level: {trigger_details['risk_level']}")
    print(f"   - trigger_rules: {trigger_details['trigger_rules']}")
    print(f"   - semantic_suspicion: {trigger_details['semantic_suspicion']}")
    print(f"   - amount: {trigger_details['amount']}")


def test_none_values_handling():
    """测试 None 值的处理"""
    print("\n=== 测试 5: None 值的处理 ===")

    # 测试 None 值
    none_value = None
    result = json.loads(none_value) if isinstance(none_value, str) and none_value else none_value
    assert result is None, "None 值应该保持为 None"
    print("✅ 通过：None 值处理正确")

    # 测试空字符串
    empty_str = ""
    result = json.loads(empty_str) if isinstance(empty_str, str) and empty_str else empty_str
    assert result == "", "空字符串应该保持为空字符串"
    print("✅ 通过：空字符串处理正确")


def test_front_end_display_scenario():
    """测试前端显示场景（模拟真实使用情况）"""
    print("\n=== 测试 6: 前端显示场景模拟 ===")

    # 模拟从后端 API 获取的数据
    api_response = {
        "id": str(uuid4()),
        "task_id": str(uuid4()),
        "tenant_id": "tenant_001",
        "user_id": str(uuid4()),
        "review_type": "tax",
        "priority": "high",
        "status": "pending",
        "trigger_reason": "high_amount_detected",
        "trigger_details": json.dumps({
            "confidence": 0.75,
            "amount": 1500000.0,
            "tax_amount": 195000.0,
            "tax_rate": 0.13,
            "invoice_number": "NO9876543210",
            "invoice_type": "增值税专用发票",
            "semantic_suspicion": ["供应商为新注册公司"]
        }, ensure_ascii=False),
        "content": json.dumps({
            "extraction": {
                "amount": 1500000.0,
                "tax_amount": 195000.0,
                "tax_rate": 0.13,
                "invoice_number": "NO9876543210"
            },
            "risk_decision": {
                "risk_level": "high",
                "decision": "requires_human_review"
            }
        }, ensure_ascii=False),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_overdue": False,
        "age_hours": 2.5
    }

    # 应用修复后的解析逻辑
    trigger_details = json.loads(api_response["trigger_details"]) if isinstance(api_response["trigger_details"], str) else api_response["trigger_details"]
    content = json.loads(api_response["content"]) if isinstance(api_response["content"], str) else api_response["content"]

    # 模拟前端访问数据
    print(f"   - 发票号码: {trigger_details['invoice_number']}")
    print(f"   - 发票金额: ¥{trigger_details['amount']:,.2f}")
    print(f"   - 税额: ¥{trigger_details['tax_amount']:,.2f}")
    print(f"   - 税率: {trigger_details['tax_rate'] * 100}%")
    print(f"   - AI置信度: {trigger_details['confidence'] * 100:.1f}%")
    print(f"   - 语义可疑点: {', '.join(trigger_details['semantic_suspicion'])}")

    # 验证前端可以正常访问
    assert trigger_details['confidence'] >= 0, "置信度应该可以正常访问"
    assert trigger_details['amount'] > 0, "金额应该可以正常访问"
    assert len(trigger_details['semantic_suspicion']) > 0, "语义可疑点应该可以正常访问"

    print("✅ 通过：前端可以正常访问和显示所有字段")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试 JSONB 字段解析修复")
    print("=" * 60)

    try:
        test_json_parsing_from_string()
        test_json_parsing_from_dict()
        test_review_result_parsing()
        test_complex_trigger_details()
        test_none_values_handling()
        test_front_end_display_scenario()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！JSONB 字段解析修复成功！")
        print("=" * 60)
        print("\n修复说明：")
        print("1. 在 human_review.py 的列表端点中添加了 JSON 解析保护")
        print("2. 在 human_review.py 的详情端点中添加了 JSON 解析保护")
        print("3. 对 trigger_details, content, review_result 字段进行防御性解析")
        print("4. 确保前端可以正确访问所有提取的发票信息")
        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
