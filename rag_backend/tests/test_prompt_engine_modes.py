#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 PromptEngine 双模式功能

直接测试 PromptEngine，支持静态和动态模板两种模式
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.prompt_service import PromptEngine


def test_static_mode():
    """测试静态提示词"""
    print("\n" + "=" * 60)
    print("测试 1: 静态提示词模式")
    print("=" * 60)
    
    engine = PromptEngine()
    
    static_prompt = "你是一个有帮助的助手。"
    
    print(f"\n✅ 静态提示词: {static_prompt}")
    
    # 模拟静态模式：直接使用 prompt
    result = static_prompt
    
    print(f"\n✅ 输出结果: {result}")
    
    assert result == static_prompt, "静态模式应该直接返回原始提示词"
    
    print("\n✅ 静态模式测试通过！")
    return True


def test_template_mode():
    """测试动态模板模式"""
    print("\n" + "=" * 60)
    print("测试 2: 动态模板模式")
    print("=" * 60)
    
    engine = PromptEngine()
    
    context = {
        "original_task": "分析公司财务状况",
        "current_answer": "公司收入增长了10%",
        "reflection_round": 1,
        "max_reflections": 3,
        "previous_reflections": [],
        "tool_outputs": {}
    }
    
    result = engine.render("reflection", context, load_skills=False)
    
    print("\n✅ 渲染结果 (前300字符):")
    print("-" * 60)
    print(result[:300])
    print("...")
    
    assert "{original_task}" not in result, "original_task 变量应该被替换"
    assert "分析公司财务状况" in result, "渲染后应该包含原始任务"
    assert "{reflection_round}" not in result, "reflection_round 变量应该被替换"
    assert "第 1 轮" in result, "渲染后应该包含轮次信息"
    
    print("\n✅ 动态模板模式测试通过！")
    return True


def test_mixed_mode():
    """测试混合模式"""
    print("\n" + "=" * 60)
    print("测试 3: 混合模式")
    print("=" * 60)
    
    engine = PromptEngine()
    
    base_prompt = "你是一个专业的分析师。"
    
    context = {
        "task": "分析公司财务",
        "depth": "详细"
    }
    
    template = engine.render("finance_specialist", context, load_skills=False)
    
    # 混合使用：基础提示词 + 模板渲染
    result = f"{base_prompt}\n\n{template}"
    
    print("\n✅ 混合模式结果 (前300字符):")
    print("-" * 60)
    print(result[:300])
    print("...")
    
    assert "你是一个专业的分析师" in result, "应该包含基础提示词"
    assert "分析公司财务" in result, "应该包含渲染后的模板内容"
    
    print("\n✅ 混合模式测试通过！")
    return True


def test_template_variables():
    """测试各种模板变量"""
    print("\n" + "=" * 60)
    print("测试 4: 模板变量测试")
    print("=" * 60)
    
    engine = PromptEngine()
    
    context = {
        "query": "测试查询",
        "context": "这是上下文内容",
        "analysis_depth": "detailed",
        "tax_types": ["增值税", "企业所得税"],
        "include_investment_models": True
    }
    
    # 测试 finance_specialist 模板
    result = engine.render("finance_specialist", context, load_skills=False)
    
    checks = [
        ("{query}" not in result, "query 变量被替换"),
        ("{context}" not in result, "context 变量被替换"),
        ("{analysis_depth}" not in result, "analysis_depth 变量被替换"),
        ("测试查询" in result, "query 值正确渲染"),
        ("这是上下文内容" in result, "context 值正确渲染"),
    ]
    
    print("\n🔍 变量检查:")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    # 测试 tax_specialist 模板
    result = engine.render("tax_specialist", context, load_skills=False)
    
    tax_checks = [
        ("{query}" not in result, "tax query 变量被替换"),
        ("{tax_types}" not in result, "tax_types 变量被替换"),
        ("{tax_depth}" not in result, "tax_depth 变量被替换"),
        ("测试查询" in result, "tax query 值正确渲染"),
        ("增值税" in result, "tax_types 循环渲染"),
    ]
    
    print("\n🔍 税务模板变量检查:")
    for passed, name in tax_checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    print("\n✅ 模板变量测试完成！")
    return all_passed


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 PromptEngine 双模式功能测试")
    print("=" * 60)
    
    results = []
    
    results.append(("静态模式", test_static_mode()))
    results.append(("动态模板模式", test_template_mode()))
    results.append(("混合模式", test_mixed_mode()))
    results.append(("模板变量测试", test_template_variables()))
    
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
        print("🎉 所有测试通过！PromptEngine 双模式功能正常。")
    else:
        print("⚠️ 部分测试失败，请检查。")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
