"""
测试模板渲染功能

验证 BaseAgent 的动态提示词模板系统
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.prompt_service import PromptEngine


def test_reflection_template():
    """测试反思模板渲染"""
    print("\n" + "=" * 60)
    print("测试 1: 反思模板渲染")
    print("=" * 60)
    
    engine = PromptEngine()
    
    context = {
        "original_task": "分析公司2024年的财务状况",
        "current_answer": "公司2024年收入增长10%，净利润增长5%。",
        "reflection_round": 1,
        "max_reflections": 3,
        "previous_reflections": [],
        "tool_outputs": {
            "财务分析": "数据已提取",
            "比率计算": "完成"
        }
    }
    
    result = engine.render("reflection", context, load_skills=False)
    
    print("\n📋 模板渲染结果：")
    print("-" * 60)
    print(f"✅ 渲染成功，长度: {len(result)} 字符")
    
    # 验证关键变量是否被替换
    checks = [
        ("{original_task}" not in result, "original_task"),
        ("{current_answer}" not in result, "current_answer"),
        ("{reflection_round}" not in result, "reflection_round"),
        ("{max_reflections}" not in result, "max_reflections"),
        ("分析公司2024年的财务状况" in result, "原始任务内容"),
        ("公司2024年收入增长10%" in result, "当前答案内容"),
        ("第 1 轮" in result or "1" in result, "反思轮次"),
    ]
    
    print("\n🔍 变量替换检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_finance_template():
    """测试财务专家模板渲染"""
    print("\n" + "=" * 60)
    print("测试 2: 财务专家模板渲染")
    print("=" * 60)
    
    engine = PromptEngine()
    
    context = {
        "query": "我们公司今年的利润率如何？",
        "context": "2024年上半年营收500万，成本300万，毛利200万。",
        "history": "用户: 请分析财务状况\n助手: 好的，请问具体是哪方面？",
        "financial_data": "暂无",
        "analysis_depth": "detailed",
        "include_investment_models": True
    }
    
    result = engine.render("finance_specialist", context, load_skills=False)
    
    print("\n📋 模板渲染结果：")
    print("-" * 60)
    print(f"✅ 渲染成功，长度: {len(result)} 字符")
    
    # 验证关键变量
    checks = [
        ("{query}" not in result, "query"),
        ("{context}" not in result, "context"),
        ("{history}" not in result, "history"),
        ("我们公司今年的利润率如何？" in result, "用户问题"),
        ("2024年上半年营收500万" in result, "上下文内容"),
        ("流动比率" in result, "详细分析内容"),
    ]
    
    print("\n🔍 变量替换检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_tax_template():
    """测试税务专家模板渲染"""
    print("\n" + "=" * 60)
    print("测试 3: 税务专家模板渲染")
    print("=" * 60)
    
    engine = PromptEngine()
    
    context = {
        "query": "小规模纳税人如何享受增值税优惠？",
        "context": "小规模纳税人增值税征收率为3%。",
        "history": "",
        "tax_data": "企业类型：小规模纳税人",
        "tax_types": ["增值税", "企业所得税"],
        "tax_depth": "detailed"
    }
    
    result = engine.render("tax_specialist", context, load_skills=False)
    
    print("\n📋 模板渲染结果：")
    print("-" * 60)
    print(f"✅ 渲染成功，长度: {len(result)} 字符")
    
    # 验证关键变量
    checks = [
        ("{query}" not in result, "query"),
        ("{tax_types}" not in result, "tax_types"),
        ("{tax_depth}" not in result, "tax_depth"),
        ("小规模纳税人如何享受增值税优惠？" in result, "用户问题"),
        ("增值税" in result, "涉及税种"),
        ("小规模纳税人征收率" in result, "详细税种说明"),
    ]
    
    print("\n🔍 变量替换检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_conditional_rendering():
    """测试条件渲染"""
    print("\n" + "=" * 60)
    print("测试 4: 条件渲染")
    print("=" * 60)
    
    engine = PromptEngine()
    
    # 测试当 context 为空时
    context_empty = {
        "query": "测试查询"
    }
    result_empty = engine.render("finance_specialist", context_empty, load_skills=False)
    
    # 测试当 context 有值时
    context_with_data = {
        "query": "测试查询",
        "context": "这是上下文内容"
    }
    result_with_data = engine.render("finance_specialist", context_with_data, load_skills=False)
    
    print(f"\n📋 空上下文渲染: {len(result_empty)} 字符")
    print(f"📋 有数据渲染: {len(result_with_data)} 字符")
    
    # 验证条件渲染
    checks = [
        ("未检索到相关文档" in result_empty, "空上下文时显示提示"),
        ("这是上下文内容" in result_with_data, "有数据时显示内容"),
    ]
    
    print("\n🔍 条件渲染检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_loop_rendering():
    """测试循环渲染"""
    print("\n" + "=" * 60)
    print("测试 5: 循环渲染")
    print("=" * 60)
    
    engine = PromptEngine()
    
    context = {
        "query": "测试",
        "tax_types": ["增值税", "企业所得税", "个人所得税"],
        "reflection": {
            "round": 1,
            "issues": "问题1",
            "suggestions": "建议1",
            "improved": "是"
        }
    }
    
    result = engine.render("tax_specialist", context, load_skills=False)
    
    # 验证循环渲染
    tax_count = result.count("增值税") + result.count("企业所得税") + result.count("个人所得税")
    
    checks = [
        (tax_count >= 3, "税种循环渲染"),
        ("第 1 轮" in result or "1" in result, "反思轮次"),
    ]
    
    print(f"\n🔍 循环渲染检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 模板渲染功能测试")
    print("=" * 60)
    
    results = []
    
    results.append(("反思模板", test_reflection_template()))
    results.append(("财务专家模板", test_finance_template()))
    results.append(("税务专家模板", test_tax_template()))
    results.append(("条件渲染", test_conditional_rendering()))
    results.append(("循环渲染", test_loop_rendering()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status}: {name}")
        all_passed = all_passed and passed
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查。")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
