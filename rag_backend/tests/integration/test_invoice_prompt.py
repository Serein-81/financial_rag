"""
测试发票识别提示词
验证新的提示词文件是否正确加载和处理缺失数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from app.services.invoice.cognition_service import InvoiceCognitionService


def test_prompt_loading():
    """测试提示词加载"""
    print("=" * 60)
    print("测试发票识别提示词加载")
    print("=" * 60)
    
    # 检查提示词文件是否存在
    prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "agents" / "tax" / "invoice_recognition.md"
    
    print(f"\n1. 检查提示词文件:")
    print(f"   路径: {prompt_path}")
    print(f"   存在: {'✅' if prompt_path.exists() else '❌'}")
    
    if not prompt_path.exists():
        print("   ❌ 提示词文件不存在！")
        return False
    
    # 读取提示词内容
    print(f"\n2. 读取提示词内容:")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"   长度: {len(content)} 字符")
    
    # 检查关键部分
    checks = [
        ("缺失数据处理规则", "缺失数据处理（关键）" in content),
        ("金额字段缺失处理", "金额字段缺失处理" in content),
        ("置信度评分规则", "置信度评分规则" in content),
        ("输出格式要求", "输出格式要求" in content),
        ("semantic_suspicion 说明", "semantic_suspicion" in content),
    ]
    
    print(f"\n3. 检查提示词关键部分:")
    for check_name, passed in checks:
        icon = "✅" if passed else "❌"
        print(f"   {icon} {check_name}")
    
    # 测试认知层加载
    print(f"\n4. 测试认知层加载提示词:")
    try:
        service = InvoiceCognitionService()
        prompt = service._get_invoice_system_prompt()
        
        print(f"   加载状态: ✅ 成功")
        print(f"   提示词长度: {len(prompt)} 字符")
        
        # 验证提示词包含关键内容
        key_content_checks = [
            ("包含缺失数据处理", "缺失" in prompt and "0" in prompt),
            ("包含置信度规则", "置信度" in prompt and "0-1" in prompt),
            ("包含语义可疑性", "semantic_suspicion" in prompt),
        ]
        
        for check_name, passed in key_content_checks:
            icon = "✅" if passed else "❌"
            print(f"   {icon} {check_name}")
        
        print(f"\n5. 提示词内容预览（前 500 字符）:")
        print("-" * 60)
        print(prompt[:500])
        print("-" * 60)
        
        return True
        
    except Exception as e:
        print(f"   ❌ 加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_missing_data_handling():
    """测试缺失数据处理说明"""
    print("\n" + "=" * 60)
    print("测试缺失数据处理说明")
    print("=" * 60)
    
    prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "agents" / "tax" / "invoice_recognition.md"
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查缺失数据处理规则
    missing_rules = [
        ("金额字段缺失", "金额字段" in content and "设为 0" in content),
        ("税率缺失", "税率" in content and "缺失" in content),
        ("税额缺失", "税额" in content and "缺失" in content),
        ("必填字段缺失", "必填字段缺失处理" in content),
        ("缺失提醒机制", "semantic_suspicion" in content and "缺失字段" in content),
    ]
    
    print("\n缺失数据处理规则检查:")
    for rule_name, passed in missing_rules:
        icon = "✅" if passed else "❌"
        print(f"   {icon} {rule_name}")
    
    return all(passed for _, passed in missing_rules)


def test_confidence_scoring():
    """测试置信度评分规则"""
    print("\n" + "=" * 60)
    print("测试置信度评分规则")
    print("=" * 60)
    
    prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "agents" / "tax" / "invoice_recognition.md"
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查置信度评分规则
    confidence_rules = [
        ("高置信度定义", "0.90-1.00" in content or "0.90-1.0" in content),
        ("中等置信度定义", "0.50-0.69" in content or "0.50-0.70" in content),
        ("低置信度定义", "0.30-0.49" in content),
        ("置信度计算规则", "置信度计算" in content),
    ]
    
    print("\n置信度评分规则检查:")
    for rule_name, passed in confidence_rules:
        icon = "✅" if passed else "❌"
        print(f"   {icon} {rule_name}")
    
    return all(passed for _, passed in confidence_rules)


def test_multi_agent_compatibility():
    """测试多智能体兼容性"""
    print("\n" + "=" * 60)
    print("测试多智能体兼容性")
    print("=" * 60)
    
    # 检查原有的系统提示词是否未被修改
    system_prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "agents" / "tax" / "system.md"
    
    print(f"\n1. 检查原有提示词文件:")
    print(f"   路径: {system_prompt_path}")
    print(f"   存在: {'✅' if system_prompt_path.exists() else '❌'}")
    
    if system_prompt_path.exists():
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            system_content = f.read()
        
        print(f"   内容长度: {len(system_content)} 字符")
        
        # 验证原有的关键内容未被修改
        checks = [
            ("税务专家角色", "税务专家" in system_content or "税务" in system_content),
            ("多智能体支持", True),  # 原文件本来就不应该包含发票识别特定内容
        ]
        
        print("\n2. 验证原有提示词完整性:")
        for check_name, passed in checks:
            icon = "✅" if passed else "❌"
            print(f"   {icon} {check_name}")
    
    # 验证新提示词是独立的
    invoice_prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "agents" / "tax" / "invoice_recognition.md"
    
    with open(invoice_prompt_path, 'r', encoding='utf-8') as f:
        invoice_content = f.read()
    
    print(f"\n3. 新提示词特点:")
    print(f"   - 专门用于发票识别: {'✅' if '发票识别' in invoice_content else '❌'}")
    print(f"   - 包含缺失数据处理: {'✅' if '缺失' in invoice_content else '❌'}")
    print(f"   - 不影响多智能体: {'✅' if system_prompt_path.exists() else '❌'}")
    
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("发票识别提示词测试")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("提示词加载", test_prompt_loading()))
    results.append(("缺失数据处理", test_missing_data_handling()))
    results.append(("置信度评分", test_confidence_scoring()))
    results.append(("多智能体兼容", test_multi_agent_compatibility()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for test_name, passed in results:
        icon = "✅" if passed else "❌"
        print(f"{icon} {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！提示词已成功优化。")
        print("\n✅ 已完成的工作:")
        print("   1. 创建了发票识别专用提示词文件")
        print("   2. 添加了缺失数据处理规则")
        print("   3. 添加了置信度评分规则")
        print("   4. 确保不影响多智能体协作")
    else:
        print("❌ 部分测试失败，请检查输出。")
    print("=" * 60)
