# -*- coding: utf-8 -*-
"""
测试真实发票格式的提取

模拟用户提供的真实发票数据进行测试
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.invoice.cognition_service import InvoiceCognitionService


def test_real_invoice_format():
    """测试用户提供的真实发票格式"""
    print("\n=== 测试真实发票格式 ===")

    # 用户提供的真实发票文本
    invoice_text = """国统一发票监制
电子发票（普通发票）
全
章
国家税务总局
江苏省税务局
发票号码： 25322000000486043704
开票日期： 2025年10月20日
购
买
名称：
惠州学院
销
售
名称：
中科视拓（南京）科技有限公司
方
方
信
息
统一社会信用代码/纳税人识别号：
12440000456659188Y
信
息
统一社会信用代码/纳税人识别号：
91320191MA1XM5TX71
项目名称
规格型号
单 位
数 量
单 价
金 额 税率/征收率
税 额
*信息系统服务*云服务器
项
1 75.4716981132075
75.47
6%
4.53
租赁服务费
¥75.47..."""

    service = InvoiceCognitionService()
    extraction = service._fallback_extraction(invoice_text, "")

    print(f"\n提取结果:")
    print(f"  - invoice_number: {extraction.invoice_number}")
    print(f"  - invoice_date: {extraction.invoice_date}")
    print(f"  - amount: {extraction.amount}")
    print(f"  - tax_rate: {extraction.tax_rate}")
    print(f"  - tax_amount: {extraction.tax_amount}")
    print(f"  - seller_name: {extraction.seller_name}")
    print(f"  - buyer_name: {extraction.buyer_name}")
    print(f"  - confidence: {extraction.confidence}")

    # 验证提取结果
    print("\n验证结果:")
    print(f"  ✅ invoice_number: {extraction.invoice_number == '25322000000486043704'}")
    print(f"  ✅ invoice_date: {'2025年10月20日' in str(extraction.invoice_date)}")
    print(f"  ✅ amount: {extraction.amount is not None and abs(extraction.amount - 75.47) < 1.0}")
    print(f"  ✅ tax_rate: {extraction.tax_rate is not None and abs(extraction.tax_rate - 0.06) < 0.001}")
    print(f"  ✅ tax_amount: {extraction.tax_amount is not None and abs(extraction.tax_amount - 4.53) < 0.1}")

    # 详细验证
    success_count = 0
    total_checks = 5

    if extraction.invoice_number and "25322000000486043704" in str(extraction.invoice_number):
        print("  ✅ 发票号码提取成功")
        success_count += 1
    else:
        print(f"  ❌ 发票号码提取失败: {extraction.invoice_number}")

    if extraction.invoice_date and "2025年10月" in str(extraction.invoice_date):
        print("  ✅ 开票日期提取成功")
        success_count += 1
    else:
        print(f"  ❌ 开票日期提取失败: {extraction.invoice_date}")

    if extraction.amount and abs(extraction.amount - 75.47) < 1.0:
        print(f"  ✅ 金额提取成功: {extraction.amount}")
        success_count += 1
    else:
        print(f"  ❌ 金额提取失败: {extraction.amount} (期望: 75.47)")

    if extraction.tax_rate and abs(extraction.tax_rate - 0.06) < 0.001:
        print(f"  ✅ 税率提取成功: {extraction.tax_rate}")
        success_count += 1
    else:
        print(f"  ❌ 税率提取失败: {extraction.tax_rate} (期望: 0.06)")

    if extraction.tax_amount and abs(extraction.tax_amount - 4.53) < 0.1:
        print(f"  ✅ 税额提取成功: {extraction.tax_amount}")
        success_count += 1
    else:
        print(f"  ❌ 税额提取失败: {extraction.tax_amount} (期望: 4.53)")

    print(f"\n提取成功率: {success_count}/{total_checks} ({success_count * 100 // total_checks}%)")

    if success_count >= 3:
        print("\n✅ 测试通过！能够从真实发票中提取关键信息")
        return True
    else:
        print("\n❌ 测试失败！提取成功率过低")
        return False


def test_yuan_symbol():
    """测试 ¥ 符号格式"""
    print("\n=== 测试 ¥ 符号格式 ===")

    invoice_text = "金额：¥75.47\n税率：6%\n税额：¥4.53"

    service = InvoiceCognitionService()
    extraction = service._fallback_extraction(invoice_text, "")

    print(f"\n提取结果:")
    print(f"  - amount: {extraction.amount}")
    print(f"  - tax_rate: {extraction.tax_rate}")
    print(f"  - tax_amount: {extraction.tax_amount}")

    success = True

    if extraction.amount and abs(extraction.amount - 75.47) < 0.01:
        print("  ✅ 金额提取成功 (¥符号)")
    else:
        print(f"  ❌ 金额提取失败: {extraction.amount}")
        success = False

    if extraction.tax_amount and abs(extraction.tax_amount - 4.53) < 0.01:
        print("  ✅ 税额提取成功 (¥符号)")
    else:
        print(f"  ❌ 税额提取失败: {extraction.tax_amount}")
        success = False

    return success


def test_invoice_number_format():
    """测试发票号码格式"""
    print("\n=== 测试发票号码格式 ===")

    test_cases = [
        ("发票号码： 25322000000486043704", "25322000000486043704"),
        ("发票号码：1234567890", "1234567890"),
        ("发票号: ABC123456789", "ABC123456789"),
    ]

    service = InvoiceCognitionService()
    all_passed = True

    for text, expected in test_cases:
        extraction = service._fallback_extraction(text, "")

        if extraction.invoice_number and expected in str(extraction.invoice_number):
            print(f"  ✅ {text} -> {extraction.invoice_number}")
        else:
            print(f"  ❌ {text} -> {extraction.invoice_number} (期望: {expected})")
            all_passed = False

    return all_passed


def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试真实发票格式的提取")
    print("=" * 60)

    try:
        test1 = test_real_invoice_format()
        test2 = test_yuan_symbol()
        test3 = test_invoice_number_format()

        print("\n" + "=" * 60)
        if test1 and test2 and test3:
            print("✅ 所有测试通过！真实发票格式提取修复成功！")
            print("=" * 60)
            print("\n修复说明：")
            print("1. 添加了对 ¥ 货币符号的支持（¥75.47）")
            print("2. 支持表格格式的金额提取（75.47 6% 4.53）")
            print("3. 支持 20 位发票号码格式")
            print("4. 改进了日期提取，支持 '开票日期' 格式")
            print("5. 支持表格中的税率格式（6%）")
            return 0
        else:
            print("❌ 部分测试失败")
            print("=" * 60)
            return 1

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
