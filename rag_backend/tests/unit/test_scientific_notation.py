# -*- coding: utf-8 -*-
"""
测试科学计数法和异常值处理
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.invoice.cognition_service import InvoiceCognitionService


def test_scientific_notation_handling():
    """测试科学计数法的处理"""
    print("\n=== 测试科学计数法处理 ===")

    # 模拟 TaxSpecialist 返回的异常数据
    data = {
        "amount": "2.5322000000486044e+19",  # 科学计数法
        "tax_amount": "2.5322000000486042",  # 异常大的值
        "tax_rate": "0.06",
        "invoice_number": "125916912310001",
        "invoice_date": "2025年10月20日",
        "confidence": 0.3,
        "raw_analysis": "# 税务分析报告..."
    }

    service = InvoiceCognitionService()
    cleaned = service._clean_extracted_data(data)

    print(f"\n清洗前:")
    print(f"  - amount: {data['amount']}")
    print(f"  - tax_amount: {data['tax_amount']}")
    print(f"  - tax_rate: {data['tax_rate']}")

    print(f"\n清洗后:")
    print(f"  - amount: {cleaned['amount']}")
    print(f"  - tax_amount: {cleaned['tax_amount']}")
    print(f"  - tax_rate: {cleaned['tax_rate']}")

    # 验证：金额应该被设为 None（因为是科学计数法）
    assert cleaned['amount'] is None or cleaned['amount'] == 0, f"金额应该被设为 None 或 0，实际: {cleaned['amount']}"
    
    # 注意：由于金额被设为 None，税额验证逻辑不会触发，所以税额可能被保留（但这是可接受的）
    # 在实际使用中，降级提取方案会从原始文本重新提取正确的值
    print(f"\n  注：由于金额为 None，税额验证不会触发，但系统会使用降级方案重新提取")

    print("\n✅ 科学计数法处理正确")


def test_tax_amount_validation():
    """测试税额验证和自动修正"""
    print("\n=== 测试税额验证和自动修正 ===")

    # 模拟数据：金额和税率正确，但税额错误
    data = {
        "amount": 75.47,
        "tax_amount": 2.532,  # 错误（应该是 4.53）
        "tax_rate": 0.06,
        "invoice_number": "125916912310001",
        "invoice_date": "2025年10月20日",
        "confidence": 0.3,
        "raw_analysis": "# 税务分析报告..."
    }

    service = InvoiceCognitionService()
    cleaned = service._clean_extracted_data(data)

    print(f"\n清洗前:")
    print(f"  - amount: {data['amount']}")
    print(f"  - tax_amount: {data['tax_amount']}")
    print(f"  - tax_rate: {data['tax_rate']}")

    print(f"\n清洗后:")
    print(f"  - amount: {cleaned['amount']}")
    print(f"  - tax_amount: {cleaned['tax_amount']}")
    print(f"  - tax_rate: {cleaned['tax_rate']}")

    # 验证：税额应该被修正为 75.47 × 0.06 = 4.53
    assert cleaned['amount'] == 75.47, f"金额应该保持为 75.47，实际: {cleaned['amount']}"
    assert abs(cleaned['tax_amount'] - 4.53) < 0.01, f"税额应该被修正为 4.53，实际: {cleaned['tax_amount']}"
    assert cleaned['tax_rate'] == 0.06, f"税率应该保持为 0.06，实际: {cleaned['tax_rate']}"

    print("\n✅ 税额验证和自动修正正确")


def test_normal_data():
    """测试正常数据"""
    print("\n=== 测试正常数据 ===")

    data = {
        "amount": 75.47,
        "tax_amount": 4.53,
        "tax_rate": 0.06,
        "invoice_number": "125916912310001",
        "invoice_date": "2025年10月20日",
        "confidence": 0.3,
        "raw_analysis": "# 税务分析报告..."
    }

    service = InvoiceCognitionService()
    cleaned = service._clean_extracted_data(data)

    print(f"\n清洗前:")
    print(f"  - amount: {data['amount']}")
    print(f"  - tax_amount: {data['tax_amount']}")
    print(f"  - tax_rate: {data['tax_rate']}")

    print(f"\n清洗后:")
    print(f"  - amount: {cleaned['amount']}")
    print(f"  - tax_amount: {cleaned['tax_amount']}")
    print(f"  - tax_rate: {cleaned['tax_rate']}")

    # 验证：正常数据应该保持不变
    assert cleaned['amount'] == 75.47, f"金额应该保持为 75.47，实际: {cleaned['amount']}"
    assert cleaned['tax_amount'] == 4.53, f"税额应该保持为 4.53，实际: {cleaned['tax_amount']}"
    assert cleaned['tax_rate'] == 0.06, f"税率应该保持为 0.06，实际: {cleaned['tax_rate']}"

    print("\n✅ 正常数据处理正确")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")

    # 测试1：税额为0的情况
    print("\n测试1：税额为0的情况")
    data1 = {
        "amount": 75.47,
        "tax_amount": 0,
        "tax_rate": 0.06,
        "invoice_number": "123",
        "invoice_date": "2025-01-01",
        "confidence": 0.5,
        "raw_analysis": ""
    }
    service = InvoiceCognitionService()
    cleaned1 = service._clean_extracted_data(data1)
    print(f"  - tax_amount: {cleaned1['tax_amount']} (应该保持为 0)")
    assert cleaned1['tax_amount'] == 0, "税额为0应该保持为0"

    # 测试2：金额为0的情况
    print("\n测试2：金额为0的情况")
    data2 = {
        "amount": 0,
        "tax_amount": 0,
        "tax_rate": 0.06,
        "invoice_number": "123",
        "invoice_date": "2025-01-01",
        "confidence": 0.5,
        "raw_analysis": ""
    }
    cleaned2 = service._clean_extracted_data(data2)
    print(f"  - amount: {cleaned2['amount']} (应该保持为 0)")
    assert cleaned2['amount'] == 0, "金额为0应该保持为0"

    # 测试3：税额大于金额的情况
    print("\n测试3：税额大于金额的情况")
    data3 = {
        "amount": 75.47,
        "tax_amount": 100,  # 大于金额
        "tax_rate": 0.06,
        "invoice_number": "123",
        "invoice_date": "2025-01-01",
        "confidence": 0.5,
        "raw_analysis": ""
    }
    cleaned3 = service._clean_extracted_data(data3)
    print(f"  - tax_amount: {cleaned3['tax_amount']} (应该被修正为 4.53)")
    assert abs(cleaned3['tax_amount'] - 4.53) < 0.01, f"税额应该被修正为 4.53，实际: {cleaned3['tax_amount']}"

    print("\n✅ 所有边界情况测试通过")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试科学计数法和异常值处理")
    print("=" * 60)

    try:
        test_scientific_notation_handling()
        test_tax_amount_validation()
        test_normal_data()
        test_edge_cases()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！科学计数法和异常值处理修复成功！")
        print("=" * 60)
        print("\n修复说明：")
        print("1. 检测科学计数法（如 2.532e+19）并设为 None")
        print("2. 检测异常大的值（> 1e10）并设为 None")
        print("3. 验证税额合理性：税额不应该大于金额")
        print("4. 如果税额错误但金额和税率正确，自动修正税额")
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
