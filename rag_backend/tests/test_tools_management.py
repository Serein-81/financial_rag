#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具管理测试脚本

演示如何使用集中式工具管理
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.tools import (
    get_all_tools,
    get_tool_names,
    get_tools_info,
    print_tools_summary
)


def test_get_all_tools():
    """测试获取所有工具"""
    print("=" * 80)
    print("测试 1: 获取所有工具对象")
    print("=" * 80)
    
    tools = get_all_tools()
    print(f"✅ 成功获取 {len(tools)} 个工具")
    
    for tool in tools:
        print(f"   - {tool.name} ({type(tool).__name__})")
    
    print()


def test_get_tool_names():
    """测试获取工具名称列表"""
    print("=" * 80)
    print("测试 2: 获取工具名称列表")
    print("=" * 80)
    
    names = get_tool_names()
    print(f"✅ 工具名称列表 ({len(names)} 个):")
    
    for name in names:
        print(f"   - {name}")
    
    print()


def test_get_tools_info():
    """测试获取工具信息（用于提示词）"""
    print("=" * 80)
    print("测试 3: 获取工具信息（用于提示词渲染）")
    print("=" * 80)
    
    tools_info = get_tools_info()
    print(f"✅ 工具信息列表 ({len(tools_info)} 个):")
    
    for info in tools_info:
        print(f"\n   工具名: {info['name']}")
        print(f"   描述: {info['description'][:80]}...")
    
    print()


def test_print_summary():
    """测试打印工具摘要"""
    print("=" * 80)
    print("测试 4: 打印工具摘要")
    print("=" * 80)
    
    print_tools_summary()
    print()


def test_integration_with_prompt():
    """测试与提示词引擎集成"""
    print("=" * 80)
    print("测试 5: 与提示词引擎集成")
    print("=" * 80)
    
    # 模拟提示词渲染所需的数据
    tools_info = get_tools_info()
    
    print("📝 提示词渲染所需的工具数据:")
    print(f"   context = {{")
    print(f"       'tools': {tools_info}")
    print(f"   }}")
    
    print("\n✅ 这些数据可以直接传递给 prompt_engine.render()")
    print()


def main():
    """主函数"""
    print("\n")
    print("🚀 工具管理测试开始")
    print("\n")
    
    # 运行所有测试
    test_get_all_tools()
    test_get_tool_names()
    test_get_tools_info()
    test_print_summary()
    test_integration_with_prompt()
    
    print("=" * 80)
    print("✅ 所有测试完成")
    print("=" * 80)
    
    print("\n💡 添加新工具的步骤:")
    print("   1. 在 app/tools/agent_tools.py 中定义新工具函数")
    print("   2. 在 get_all_tools() 函数中添加新工具到返回列表")
    print("   3. 在 app/prompts/skills/ 目录创建对应的 skill 文件")
    print("   4. 重启服务，新工具自动生效")
    print()


if __name__ == "__main__":
    main()
