#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 多模式测试脚本

测试 ReAct、Plan、Reflect 三种模式的效果
"""

import asyncio
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agent_framework.core import create_agent, AgentFactory
from app.agent_framework.llm import create_llm_adapter
from app.agent_framework.tools.tool_manager import ToolManager


async def test_react_mode():
    """测试 ReAct 模式"""
    print("="*60)
    print("1️⃣ 测试 ReAct 模式（推理-行动）")
    print("="*60)
    print("特点：快速响应，适合简单任务\n")
    
    # 创建 Agent
    agent = create_agent(mode="react")
    
    # 测试任务
    task = "北京今天天气怎么样？"
    print(f"任务: {task}\n")
    
    start_time = time.time()
    result = await agent.run(task)
    elapsed = time.time() - start_time
    
    print(f"\n结果: {result}")
    print(f"耗时: {elapsed:.2f}秒\n")


async def test_plan_mode():
    """测试 Plan 模式"""
    print("="*60)
    print("2️⃣ 测试 Plan 模式（计划-执行）")
    print("="*60)
    print("特点：先规划后执行，适合复杂任务\n")
    
    # 创建 Agent
    agent = create_agent(mode="plan")
    
    # 测试任务
    task = "帮我查询北京的天气，并根据天气给出出行建议"
    print(f"任务: {task}\n")
    
    start_time = time.time()
    result = await agent.run(task)
    elapsed = time.time() - start_time
    
    print(f"\n结果: {result}")
    print(f"耗时: {elapsed:.2f}秒\n")


async def test_reflect_mode():
    """测试 Reflect 模式"""
    print("="*60)
    print("3️⃣ 测试 Reflect 模式（反思-改进）")
    print("="*60)
    print("特点：自我反思和改进，适合高质量要求\n")
    
    # 创建 Agent
    agent = create_agent(mode="reflect")
    
    # 测试任务
    task = "分析一下北京今天的天气情况，给出详细的分析报告"
    print(f"任务: {task}\n")
    
    start_time = time.time()
    result = await agent.run(task)
    elapsed = time.time() - start_time
    
    print(f"\n结果: {result}")
    print(f"耗时: {elapsed:.2f}秒\n")


async def test_mode_comparison():
    """对比三种模式"""
    print("="*60)
    print("4️⃣ 模式对比测试")
    print("="*60)
    
    task = "什么是人工智能？"
    print(f"相同任务: {task}\n")
    
    modes = ["react", "plan", "reflect"]
    results = {}
    
    for mode in modes:
        print(f"\n--- {mode.upper()} 模式 ---")
        agent = create_agent(mode=mode)
        
        start_time = time.time()
        result = await agent.run(task)
        elapsed = time.time() - start_time
        
        results[mode] = {
            "result": result,
            "time": elapsed
        }
        
        print(f"耗时: {elapsed:.2f}秒")
        print(f"结果长度: {len(result)} 字符")
    
    print("\n" + "="*60)
    print("对比总结")
    print("="*60)
    for mode, data in results.items():
        print(f"{mode.upper()}: {data['time']:.2f}秒, {len(data['result'])}字符")


async def test_factory_info():
    """测试工厂信息"""
    print("="*60)
    print("5️⃣ Agent 工厂信息")
    print("="*60)
    
    # 支持的模式
    modes = AgentFactory.get_supported_modes()
    print(f"\n支持的模式: {', '.join(modes)}")
    
    # 当前模式
    current = AgentFactory.get_current_mode()
    print(f"当前默认模式: {current}")
    
    # 模式描述
    print("\n模式说明:")
    for mode in modes:
        desc = AgentFactory.get_mode_description(mode)
        print(f"  - {mode}: {desc}")
    
    print()


async def main():
    """主函数"""
    print("\n🚀 开始测试 Agent 多模式...")
    print()
    
    try:
        # 测试工厂信息
        await test_factory_info()
        
        # 测试 ReAct 模式
        await test_react_mode()
        
        # 测试 Plan 模式
        await test_plan_mode()
        
        # 测试 Reflect 模式
        await test_reflect_mode()
        
        # 对比测试
        await test_mode_comparison()
        
        print("="*60)
        print("✅ 所有测试完成！")
        print("="*60)
        print()
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
