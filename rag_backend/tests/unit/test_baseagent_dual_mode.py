#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 BaseAgent 双模式功能

验证 BaseAgent 是否正确支持静态和动态模板两种模式
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent_framework.core.base_agent import BaseAgent


class MockLLMAdapter:
    """模拟 LLM 适配器"""
    async def generate(self, prompt, **kwargs):
        return f"Mock response for: {prompt[:50]}..."


class MockToolManager:
    """模拟工具管理器"""
    @property
    def tools(self):
        return []
    
    def get_all_tools(self):
        return []
    
    def get_tools_description(self):
        return ""


def test_static_mode():
    """测试静态模式"""
    print("\n" + "=" * 60)
    print("测试 1: 静态提示词模式")
    print("=" * 60)
    
    agent = BaseAgent(
        llm_adapter=MockLLMAdapter(),
        tool_manager=MockToolManager(),
        system_prompt="你是一个有帮助的助手。",
        max_iterations=1
    )
    
    print("\n✅ Agent 创建成功")
    print(f"   - 提示词模式: {'模板' if agent.use_template else '静态'}")
    print(f"   - 系统提示词: {agent.system_prompt[:50]}...")
    print(f"   - 模板名称: {agent.template_name}")
    
    # 测试渲染
    rendered = agent._render_system_prompt()
    print(f"\n✅ 渲染结果: {rendered[:100]}...")
    
    assert not agent.use_template, "静态模式应该 use_template=False"
    assert agent.system_prompt == rendered, "静态模式应该直接返回 system_prompt"
    
    print("\n✅ 静态模式测试通过！")
    return True


def test_template_mode():
    """测试动态模板模式"""
    print("\n" + "=" * 60)
    print("测试 2: 动态模板模式")
    print("=" * 60)
    
    agent = BaseAgent(
        llm_adapter=MockLLMAdapter(),
        tool_manager=MockToolManager(),
        template_name="reflection",
        max_iterations=1
    )
    
    print("\n✅ Agent 创建成功")
    print(f"   - 提示词模式: {'模板 [' + agent.template_name + ']' if agent.use_template else '静态'}")
    print(f"   - 系统提示词: {agent.system_prompt}")
    print(f"   - 模板名称: {agent.template_name}")
    
    # 测试渲染
    context = {
        "original_task": "测试任务",
        "current_answer": "测试答案",
        "reflection_round": 1,
        "max_reflections": 3,
        "previous_reflections": [],
        "tool_outputs": {}
    }
    
    rendered = agent._render_system_prompt(context)
    print("\n✅ 渲染结果 (前200字符):")
    print("-" * 60)
    print(rendered[:200])
    print("...")
    
    assert agent.use_template, "模板模式应该 use_template=True"
    assert "{original_task}" not in rendered, "变量应该被替换"
    assert "测试任务" in rendered, "渲染后应该包含上下文数据"
    
    print("\n✅ 动态模板模式测试通过！")
    return True


def test_mode_comparison():
    """对比两种模式"""
    print("\n" + "=" * 60)
    print("测试 3: 模式对比")
    print("=" * 60)
    
    static_agent = BaseAgent(
        llm_adapter=MockLLMAdapter(),
        tool_manager=MockToolManager(),
        system_prompt="静态提示词",
        max_iterations=1
    )
    
    template_agent = BaseAgent(
        llm_adapter=MockLLMAdapter(),
        tool_manager=MockToolManager(),
        template_name="reflection",
        max_iterations=1
    )
    
    print("\n📊 模式对比:")
    print("   静态模式:")
    print(f"      - use_template: {static_agent.use_template}")
    print(f"      - system_prompt: '{static_agent.system_prompt}'")
    print(f"      - template_name: {static_agent.template_name}")
    
    print("\n   模板模式:")
    print(f"      - use_template: {template_agent.use_template}")
    print(f"      - system_prompt: '{template_agent.system_prompt}'")
    print(f"      - template_name: '{template_agent.template_name}'")
    
    assert static_agent.use_template == False
    assert template_agent.use_template == True
    assert template_agent.system_prompt == ""
    
    print("\n✅ 模式对比测试通过！")
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 BaseAgent 双模式功能测试")
    print("=" * 60)
    
    results = []
    
    results.append(("静态模式", test_static_mode()))
    results.append(("动态模板模式", test_template_mode()))
    results.append(("模式对比", test_mode_comparison()))
    
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
        print("🎉 所有测试通过！BaseAgent 双模式功能正常。")
    else:
        print("⚠️ 部分测试失败，请检查。")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
