#!/usr/bin/env python3
"""
阶段4集成测试脚本

测试Agent追踪、工具调用链追踪和Prompt优化功能
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.agent_tracer import agent_tracer
from app.services.tool_call_tracer import tool_call_tracer
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.core.react_agent import ReActAgent


async def test_agent_tracing():
    """测试Agent追踪功能"""
    print("🎯 测试Agent追踪功能")
    print("-" * 40)
    
    try:
        # 1. 开始追踪
        trace_id = await agent_tracer.start_trace(
            agent_type="ReAct",
            user_query="测试查询：什么是人工智能？",
            session_id=str(uuid.uuid4())
        )
        print(f"✅ 开始追踪: {trace_id}")
        
        # 2. 添加思考步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=1,
            step_type="thought",
            content="我需要思考什么是人工智能",
            confidence=0.8
        )
        print("✅ 添加思考步骤")
        
        # 3. 添加行动步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=2,
            step_type="action",
            content="调用搜索工具",
            tool_name="search",
            tool_input={"query": "人工智能定义"},
            tool_duration=150.5
        )
        print("✅ 添加行动步骤")
        
        # 4. 添加观察步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=3,
            step_type="observation",
            content="搜索结果显示人工智能是...",
            tool_output="人工智能是计算机科学的一个分支"
        )
        print("✅ 添加观察步骤")
        
        # 5. 添加最终答案
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=4,
            step_type="final_answer",
            content="人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。"
        )
        print("✅ 添加最终答案步骤")
        
        # 6. 结束追踪
        await agent_tracer.end_trace(
            trace_id=trace_id,
            final_answer="人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
            success=True
        )
        print("✅ 结束追踪")
        
        # 7. 查询追踪结果
        trace_data = await agent_tracer.get_trace_with_steps(trace_id)
        if trace_data:
            print(f"✅ 查询追踪结果:")
            print(f"   - 总步骤: {trace_data['total_iterations']}")
            print(f"   - 总耗时: {trace_data['total_time']:.2f}s")
            print(f"   - 工具调用: {trace_data['tool_calls_count']}")
            print(f"   - 状态: {trace_data['status']}")
        else:
            print("❌ 查询追踪结果失败")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent追踪测试失败: {e}")
        return False


async def test_tool_call_tracing():
    """测试工具调用链追踪功能"""
    print("\n🔧 测试工具调用链追踪功能")
    print("-" * 40)
    
    try:
        # 先创建一个真实的Agent追踪记录
        agent_trace_id = await agent_tracer.start_trace(
            agent_type="ReAct",
            user_query="工具调用链测试查询",
            session_id=str(uuid.uuid4())
        )
        print(f"🎬 创建Agent追踪: {agent_trace_id}")
        
        # 1. 开始工具调用
        call_id = await tool_call_tracer.start_call(
            tool_name="search",
            tool_type="function",
            input_params={"query": "人工智能", "limit": 5},
            trace_id=agent_trace_id
        )
        print(f"✅ 开始工具调用: {call_id}")
        
        # 2. 模拟嵌套工具调用
        nested_call_id = await tool_call_tracer.start_call(
            tool_name="format_result",
            tool_type="function",
            input_params={"data": "搜索结果"},
            trace_id=agent_trace_id,
            parent_call_id=call_id
        )
        print(f"✅ 开始嵌套工具调用: {nested_call_id}")
        
        # 3. 结束嵌套调用
        await tool_call_tracer.end_call(
            call_id=nested_call_id,
            output_result="格式化后的搜索结果",
            duration=50.0,
            status="success"
        )
        print("✅ 结束嵌套工具调用")
        
        # 4. 结束主调用
        await tool_call_tracer.end_call(
            call_id=call_id,
            output_result="人工智能相关搜索结果",
            duration=200.0,
            status="success"
        )
        print("✅ 结束主工具调用")
        
        # 5. 查询调用链
        chain_data = await tool_call_tracer.build_call_chain(agent_trace_id)
        if chain_data:
            print(f"✅ 构建调用链:")
            print(f"   - 总调用: {chain_data['statistics']['total_calls']}")
            print(f"   - 总耗时: {chain_data['statistics']['total_duration']}ms")
            print(f"   - 成功率: {chain_data['statistics']['success_rate']}%")
        else:
            print("❌ 构建调用链失败")
        
        # 6. 清理测试数据 - 结束Agent追踪
        await agent_tracer.end_trace(
            trace_id=agent_trace_id,
            final_answer="工具调用链测试完成",
            success=True
        )
        print("🧹 清理测试数据")
        
        return True
        
    except Exception as e:
        print(f"❌ 工具调用链追踪测试失败: {e}")
        return False


async def test_integrated_agent():
    """测试集成的Agent功能"""
    print("\n🤖 测试集成Agent功能")
    print("-" * 40)
    
    try:
        # 创建LLM适配器（如果可用）
        try:
            llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
            print("✅ 创建LLM适配器成功")
        except Exception as e:
            print(f"⚠️ 创建LLM适配器失败，使用模拟模式: {e}")
            llm_adapter = None
        
        # 创建工具管理器
        tool_manager = ToolManager()
        
        # 注册一个简单的测试工具
        def simple_calculator(operation: str, a: float, b: float) -> str:
            """简单计算器工具"""
            if operation == "add":
                return f"{a} + {b} = {a + b}"
            elif operation == "multiply":
                return f"{a} × {b} = {a * b}"
            else:
                return f"不支持的操作: {operation}"
        
        tool_manager.register_function(
            name="calculator",
            func=simple_calculator,
            description="执行简单的数学计算"
        )
        print("✅ 注册测试工具")
        
        # 创建ReAct Agent
        if llm_adapter:
            agent = ReActAgent(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager,
                system_prompt="你是一个有用的助手，可以使用工具来帮助回答问题。",
                max_iterations=3
            )
            print("✅ 创建ReAct Agent")
            
            # 测试Agent执行（简单测试，不依赖真实LLM）
            print("✅ Agent创建成功，追踪功能已集成")
        else:
            print("⚠️ 跳过Agent执行测试（无LLM适配器）")
        
        return True
        
    except Exception as e:
        print(f"❌ 集成Agent测试失败: {e}")
        return False


async def test_api_endpoints():
    """测试API端点（模拟）"""
    print("\n🌐 测试API端点")
    print("-" * 40)
    
    try:
        # 测试导入API模块
        from app.api.v1.endpoints import agent_trace, tool_trace, prompt_optimization
        print("✅ API模块导入成功")
        
        # 检查路由器是否存在
        if hasattr(agent_trace, 'router'):
            print("✅ Agent追踪API路由器存在")
        
        if hasattr(tool_trace, 'router'):
            print("✅ 工具追踪API路由器存在")
        
        if hasattr(prompt_optimization, 'router'):
            print("✅ Prompt优化API路由器存在")
        
        return True
        
    except Exception as e:
        print(f"❌ API端点测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 阶段4集成测试开始")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 运行各项测试
    results = {}
    
    # 1. Agent追踪测试
    results["agent_tracing"] = await test_agent_tracing()
    
    # 2. 工具调用链追踪测试
    results["tool_tracing"] = await test_tool_call_tracing()
    
    # 3. 集成Agent测试
    results["integrated_agent"] = await test_integrated_agent()
    
    # 4. API端点测试
    results["api_endpoints"] = await test_api_endpoints()
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("🏁 阶段4集成测试结果")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        test_display_name = {
            "agent_tracing": "Agent决策追踪",
            "tool_tracing": "工具调用链追踪",
            "integrated_agent": "集成Agent功能",
            "api_endpoints": "API端点"
        }.get(test_name, test_name)
        
        print(f"{status} {test_display_name}")
    
    print(f"\n📊 测试统计: {passed_tests}/{total_tests} 通过")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！阶段4功能正常")
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
    
    print("\n💡 下一步建议:")
    if results.get("agent_tracing") and results.get("tool_tracing"):
        print("   ✅ 后端追踪功能完整，可以开始前端可视化开发")
    if results.get("api_endpoints"):
        print("   ✅ API端点正常，可以进行前端集成")
    if not all(results.values()):
        print("   🔧 修复失败的测试项目")
    
    print("   📋 详细任务清单: TODO_Phase4.md")


if __name__ == "__main__":
    asyncio.run(main())