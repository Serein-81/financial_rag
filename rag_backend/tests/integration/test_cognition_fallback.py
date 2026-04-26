# -*- coding: utf-8 -*-
"""
测试认知层降级提取方案

验证从 Markdown 格式的 raw_analysis 中提取信息
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from app.services.invoice.cognition_service import InvoiceCognitionService


def test_markdown_parsing():
    """测试 Markdown 格式的 raw_analysis 解析"""
    print("\n=== 测试 Markdown 格式解析 ===")

    raw_analysis = """# 📋 税务分析报告

## 1. 税种识别
- **税种类型**: other
- **适用税率**: 6.0
- **税额估算**: 2025.0
- **税务期间**: 2025年10月

## 2. 合规性评估
- **合规状态**: review_required
- **置信度**: 95.00%
- **可扣除项目**: 无
- **免税项目**: 无

## 3. 风险点分析
1. 存在合规性问题

## 4. 风险评估
- **risk_level**: high
- **risk_factors**: ['存在合规性问题']
- **requires_professional_review**: True

## 5. 提取信息
- **税率**: 6.0%
- **金额**: 2025.0
- **税号**: 125916912310001
- **期间**: 2025年10月

## 6. 专业建议
1. 建议进行详细的合规性审查
2. 建议保留完整的税务档案
3. 如有大额税务事项，咨询专业税务顾问

## 7. 总结
⚠️ 需要进一步审查，建议咨询专业税务顾问。"""

    original_text = "这是一份税务申报表..."

    service = InvoiceCognitionService()
    extraction = service._fallback_extraction(original_text, raw_analysis)

    print(f"\n提取结果:")
    print(f"  - amount: {extraction.amount}")
    print(f"  - tax_amount: {extraction.tax_amount}")
    print(f"  - tax_rate: {extraction.tax_rate}")
    print(f"  - invoice_number: {extraction.invoice_number}")
    print(f"  - invoice_date: {extraction.invoice_date}")
    print(f"  - confidence: {extraction.confidence}")
    print(f"  - raw_analysis: {extraction.raw_analysis[:100]}...")

    # 验证提取结果
    assert extraction.amount is not None, "金额应该被提取"
    assert extraction.amount == 2025.0, f"金额应该是 2025.0，实际是 {extraction.amount}"

    assert extraction.tax_amount is not None, "税额应该被提取"
    assert extraction.tax_amount == 2025.0, f"税额应该是 2025.0，实际是 {extraction.tax_amount}"

    assert extraction.tax_rate is not None, "税率应该被提取"
    assert abs(extraction.tax_rate - 0.06) < 0.001, f"税率应该是 0.06，实际是 {extraction.tax_rate}"

    assert extraction.invoice_number is not None, "发票号码应该被提取"
    assert extraction.invoice_number == "125916912310001", f"发票号码应该是 125916912310001，实际是 {extraction.invoice_number}"

    assert extraction.invoice_date is not None, "发票日期应该被提取"
    assert "2025年10月" in extraction.invoice_date, f"发票日期应该包含 2025年10月，实际是 {extraction.invoice_date}"

    print("\n✅ 所有验证通过！Markdown 格式解析成功！")


def test_multiple_patterns():
    """测试多个正则表达式模式"""
    print("\n=== 测试多个正则表达式模式 ===")

    test_cases = [
        {
            "text": "**金额**: 100000.0\n**税率**: 13.0%\n**税号**: ABC123456789",
            "expected_amount": 100000.0,
            "expected_tax_rate": 0.13,
            "expected_invoice_number": "ABC123456789"
        },
        {
            "text": "金额：50000.0\n税率：6.0%\n发票号：XYZ987654321",
            "expected_amount": 50000.0,
            "expected_tax_rate": 0.06,
            "expected_invoice_number": "XYZ987654321"
        },
        {
            "text": "总额: 250000.0\n适用税率: 9.0\n税额估算: 22500.0",
            "expected_amount": 250000.0,
            "expected_tax_rate": 0.09,
            "expected_tax_amount": 22500.0
        }
    ]

    service = InvoiceCognitionService()

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")

        extraction = service._fallback_extraction(test_case["text"], "")

        print(f"  - 金额: {extraction.amount} (期望: {test_case['expected_amount']})")
        print(f"  - 税率: {extraction.tax_rate} (期望: {test_case['expected_tax_rate']})")

        if "expected_tax_amount" in test_case:
            print(f"  - 税额: {extraction.tax_amount} (期望: {test_case['expected_tax_amount']})")

        if "expected_invoice_number" in test_case:
            print(f"  - 发票号: {extraction.invoice_number} (期望: {test_case['expected_invoice_number']})")

        # 验证
        assert abs(extraction.amount - test_case["expected_amount"]) < 0.01, \
            f"金额不正确: {extraction.amount} vs {test_case['expected_amount']}"

        assert abs(extraction.tax_rate - test_case["expected_tax_rate"]) < 0.001, \
            f"税率不正确: {extraction.tax_rate} vs {test_case['expected_tax_rate']}"

        if "expected_tax_amount" in test_case:
            assert abs(extraction.tax_amount - test_case["expected_tax_amount"]) < 0.01, \
                f"税额不正确: {extraction.tax_amount} vs {test_case['expected_tax_amount']}"

        if "expected_invoice_number" in test_case:
            assert extraction.invoice_number == test_case["expected_invoice_number"], \
                f"发票号码不正确: {extraction.invoice_number} vs {test_case['expected_invoice_number']}"

        print(f"  ✅ 测试用例 {i} 通过！")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")

    service = InvoiceCognitionService()

    # 空文本
    extraction = service._fallback_extraction("", "")
    assert extraction.amount is None, "空文本应该返回 None"
    assert extraction.confidence == 0.3, "置信度应该是 0.3"
    print("✅ 空文本处理正确")

    # 只有数字
    extraction = service._fallback_extraction("金额：abc123", "")
    assert extraction.amount is None, "非数字应该返回 None"
    print("✅ 非数字处理正确")

    # 税率大于1
    extraction = service._fallback_extraction("税率：13.0", "")
    assert abs(extraction.tax_rate - 0.13) < 0.001, "13.0 应该被转换为 0.13"
    print("✅ 税率转换正确（13.0 -> 0.13）")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试认知层降级提取方案")
    print("=" * 60)

    try:
        test_markdown_parsing()
        test_multiple_patterns()
        test_edge_cases()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！Markdown 格式解析修复成功！")
        print("=" * 60)
        print("\n修复说明：")
        print("1. 扩展了正则表达式模式，支持 Markdown 格式（**bold**）")
        print("2. 添加了对 '适用税率' 和 '税额估算' 的支持")
        print("3. 支持从 original_text 和 raw_analysis 两个文本源提取信息")
        print("4. 改进了税率转换逻辑，自动处理大于1的值")
        print("5. 增加了错误处理，避免解析失败导致程序崩溃")
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
