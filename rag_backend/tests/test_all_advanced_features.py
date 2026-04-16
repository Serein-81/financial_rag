# test_all_advanced_features.py

"""
测试所有高级特性的综合测试脚本

包括：
1. Agent 决策可视化
2. 工具调用链追踪  
3. 自动 Prompt 优化
"""

import asyncio
import sys
import os
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import AsyncSessionLocal
from app.services.agent_tracer import agent_tracer
from app.services.tool_call_tracer import tool_call_tracer
from app.services.prompt_optimizer import get_prompt_optimizer
from app.services.prompt_ab_test import get_ab_test_manager


async def test_agent_tracing():
    """测试 Agent 追踪功能"""
    print("\n🎯 测试 Agent 决策可视化...")
    
    try:
        # 1. 开始追踪
        trace_id = await agent_tracer.start_trace(
            agent_type="ReAct",
            user_query="什么是人工智能？",
            session_id=str(uuid4()),
            message_id=str(uuid4())
        )
        print(f"✅ 创建追踪: {trace_id}")
        
        # 2. 添加思考步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=1,
            step_type="thought",
            content="我需要思考如何回答关于人工智能的问题"
        )
        print("✅ 添加思考步骤")
        
        # 3. 添加行动步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=2,
            step_type="action",
            content="搜索人工智能的定义",
            tool_name="search",
            tool_input={"query": "人工智能定义"},
            tool_output="人工智能是计算机科学的一个分支...",
            tool_duration=150.5
        )
        print("✅ 添加行动步骤")
        
        # 4. 添加观察步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=3,
            step_type="observation",
            content="搜索结果提供了人工智能的基本定义"
        )
        print("✅ 添加观察步骤")
        
        # 5. 结束追踪
        await agent_tracer.end_trace(
            trace_id=trace_id,
            final_answer="人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
            success=True,
            total_iterations=3,
            tool_calls_count=1
        )
        print("✅ 结束追踪")
        
        # 6. 查询追踪结果
        trace_data = await agent_tracer.get_trace_with_steps(trace_id)
        print(f"✅ 查询追踪结果:")
        print(f"   - 总步骤: {trace_data['total_iterations']}")
        print(f"   - 工具调用: {trace_data['tool_calls_count']}")
        print(f"   - 总耗时: {trace_data['total_time']:.2f}s")
        print(f"   - 步骤数量: {len(trace_data['steps'])}")
        
        return trace_id
        
    except Exception as e:
        print(f"❌ Agent 追踪测试失败: {e}")
        return None


async def test_tool_tracing(trace_id):
    """测试工具调用追踪功能"""
    print("\n🔧 测试工具调用链追踪...")
    
    try:
        # 1. 开始主工具调用
        call_id_1 = await tool_call_tracer.start_call(
            trace_id=trace_id,
            tool_name="search",
            tool_type="function",
            input_params={"query": "人工智能"}
        )
        print(f"✅ 开始主工具调用: {call_id_1}")
        
        # 2. 开始嵌套工具调用
        call_id_2 = await tool_call_tracer.start_call(
            trace_id=trace_id,
            parent_call_id=call_id_1,
            tool_name="web_search",
            tool_type="api",
            input_params={"url": "https://example.com", "query": "AI"}
        )
        print(f"✅ 开始嵌套工具调用: {call_id_2}")
        
        # 3. 结束嵌套调用
        await tool_call_tracer.end_call(
            call_id=call_id_2,
            output_result="找到了关于AI的详细信息",
            duration=200.0,
            status="success"
        )
        print("✅ 结束嵌套调用")
        
        # 4. 结束主调用
        await tool_call_tracer.end_call(
            call_id=call_id_1,
            output_result="搜索完成，获得AI相关信息",
            duration=350.0,
            status="success"
        )
        print("✅ 结束主调用")
        
        # 5. 查询调用链
        chain_data = await tool_call_tracer.build_call_chain(trace_id)
        print(f"✅ 查询调用链:")
        print(f"   - 总调用: {chain_data['statistics']['total_calls']}")
        print(f"   - 总耗时: {chain_data['statistics']['total_duration']}ms")
        print(f"   - 成功率: {chain_data['statistics']['success_rate']}%")
        print(f"   - 调用链层级: {len(chain_data['call_chain'])}")
        
        # 6. 查询工具统计
        stats = await tool_call_tracer.get_tool_statistics(days=1)
        print(f"✅ 工具统计:")
        print(f"   - 统计的工具数: {len(stats['tool_stats'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ 工具追踪测试失败: {e}")
        return False


async def test_prompt_optimization():
    """测试 Prompt 优化功能"""
    print("\n🤖 测试 Prompt 优化...")
    
    async with AsyncSessionLocal() as db:
        try:
            optimizer = get_prompt_optimizer(db)
            ab_manager = get_ab_test_manager(db)
            
            # 1. 创建 Prompt 模板
            template_a = await optimizer.create_template(
                name="react_agent_v1",
                version="1.0",
                template_text="你是一个智能助手，请按照以下步骤思考：\n1. 分析问题\n2. 选择工具\n3. 执行行动\n4. 观察结果\n5. 给出答案",
                agent_type="react",
                use_case="general",
                description="ReAct Agent 基础版本",
                is_baseline=True
            )
            print(f"✅ 创建模板 A: {template_a.id}")
            
            template_b = await optimizer.create_template(
                name="react_agent_v2",
                version="2.0", 
                template_text="你是一个高效的智能助手。请遵循 ReAct 框架：\n\nThought: 分析当前情况和需要采取的行动\nAction: 选择并执行最合适的工具\nObservation: 仔细观察工具执行结果\n\n重复上述过程直到能够给出完整答案。",
                agent_type="react",
                use_case="general",
                description="ReAct Agent 优化版本"
            )
            print(f"✅ 创建模板 B: {template_b.id}")
            
            # 2. 创建 A/B 测试
            ab_test = await ab_manager.create_test(
                test_name="react_general_test",
                template_a_id=template_a.id,
                template_b_id=template_b.id,
                traffic_split=0.5,
                description="ReAct Agent 通用场景 A/B 测试"
            )
            print(f"✅ 创建 A/B 测试: {ab_test.id}")
            
            # 3. 模拟执行记录
            for i in range(10):
                # 随机选择模板
                selected_template_id = await ab_manager.select_template("react_general_test")
                
                # 记录执行结果
                await optimizer.record_execution(
                    template_id=selected_template_id,
                    user_query=f"测试问题 {i+1}",
                    final_answer=f"测试答案 {i+1}",
                    execution_time=2.5 + i * 0.1,
                    iterations_count=3 + (i % 2),
                    tool_calls_count=1 + (i % 3),
                    success=True,
                    auto_score=0.8 + (i % 3) * 0.05
                )
                
                # 增加测试执行计数
                await ab_manager.increment_execution_count(ab_test.id)
            
            print("✅ 模拟 10 次执行记录")
            
            # 4. 分析模板性能
            perf_a = await optimizer.analyze_template_performance(template_a.id, days=1)
            perf_b = await optimizer.analyze_template_performance(template_b.id, days=1)
            
            print(f"✅ 模板 A 性能:")
            print(f"   - 执行次数: {perf_a['total_executions']}")
            print(f"   - 成功率: {perf_a['success_rate']:.1%}")
            print(f"   - 平均评分: {perf_a['avg_score']:.2f}")
            
            print(f"✅ 模板 B 性能:")
            print(f"   - 执行次数: {perf_b['total_executions']}")
            print(f"   - 成功率: {perf_b['success_rate']:.1%}")
            print(f"   - 平均评分: {perf_b['avg_score']:.2f}")
            
            # 5. 比较模板
            comparison = await optimizer.compare_templates(template_a.id, template_b.id, days=1)
            print(f"✅ 模板比较结果:")
            print(f"   - 获胜者: {comparison['winner']}")
            print(f"   - 评分差异: {comparison['comparison']['score_diff']:.1f}%")
            
            # 6. 获取优化建议
            suggestions_a = await optimizer.get_optimization_suggestions(template_a.id, days=1)
            print(f"✅ 模板 A 优化建议: {len(suggestions_a)} 条")
            for suggestion in suggestions_a:
                print(f"   - {suggestion['type']}: {suggestion['message']}")
            
            # 7. 分析 A/B 测试结果
            test_results = await ab_manager.analyze_test_results(ab_test.id)
            print(f"✅ A/B 测试结果:")
            print(f"   - 总执行: {test_results['total_executions']}")
            print(f"   - 获胜者: {test_results['winner']}")
            print(f"   - 置信度: {test_results['confidence']:.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Prompt 优化测试失败: {e}")
            return False


async def test_integration():
    """测试功能集成"""
    print("\n🔗 测试功能集成...")
    
    try:
        # 模拟完整的 Agent 执行流程
        print("模拟完整 Agent 执行流程...")
        
        # 1. 开始 Agent 追踪
        trace_id = await agent_tracer.start_trace(
            agent_type="ReAct",
            user_query="集成测试：查询天气信息"
        )
        
        # 2. 开始工具调用
        call_id = await tool_call_tracer.start_call(
            trace_id=trace_id,
            tool_name="weather_api",
            input_params={"city": "北京"}
        )
        
        # 3. 添加 Agent 步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=1,
            step_type="thought",
            content="用户想查询天气，我需要调用天气API"
        )
        
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=2,
            step_type="action",
            content="调用天气API查询北京天气",
            tool_name="weather_api",
            tool_input={"city": "北京"}
        )
        
        # 4. 结束工具调用
        await tool_call_tracer.end_call(
            call_id=call_id,
            output_result="北京今天晴天，温度25°C",
            duration=120.0,
            status="success"
        )
        
        # 5. 添加观察和答案步骤
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=3,
            step_type="observation",
            content="成功获取北京天气信息",
            tool_output="北京今天晴天，温度25°C",
            tool_duration=120.0
        )
        
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=4,
            step_type="final_answer",
            content="根据查询结果，北京今天是晴天，温度为25°C。"
        )
        
        # 6. 结束 Agent 追踪
        await agent_tracer.end_trace(
            trace_id=trace_id,
            final_answer="根据查询结果，北京今天是晴天，温度为25°C。",
            success=True,
            total_iterations=4,
            tool_calls_count=1
        )
        
        # 7. 记录 Prompt 执行（如果有模板）
        async with AsyncSessionLocal() as db:
            optimizer = get_prompt_optimizer(db)
            templates = await optimizer.list_templates(agent_type="react", is_active=True)
            
            if templates:
                template = templates[0]
                await optimizer.record_execution(
                    template_id=template.id,
                    user_query="集成测试：查询天气信息",
                    final_answer="根据查询结果，北京今天是晴天，温度为25°C。",
                    execution_time=3.2,
                    iterations_count=4,
                    tool_calls_count=1,
                    success=True,
                    auto_score=0.95
                )
                print(f"✅ 记录到模板: {template.name}")
        
        print("✅ 集成测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始测试所有高级特性...")
    
    results = {
        "agent_tracing": False,
        "tool_tracing": False, 
        "prompt_optimization": False,
        "integration": False
    }
    
    # 1. 测试 Agent 追踪
    trace_id = await test_agent_tracing()
    results["agent_tracing"] = trace_id is not None
    
    # 2. 测试工具追踪
    if trace_id:
        results["tool_tracing"] = await test_tool_tracing(trace_id)
    
    # 3. 测试 Prompt 优化
    results["prompt_optimization"] = await test_prompt_optimization()
    
    # 4. 测试功能集成
    results["integration"] = await test_integration()
    
    # 输出测试结果
    print("\n" + "="*50)
    print("📊 测试结果汇总:")
    print("="*50)
    
    for feature, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        feature_name = {
            "agent_tracing": "Agent 决策可视化",
            "tool_tracing": "工具调用链追踪",
            "prompt_optimization": "自动 Prompt 优化",
            "integration": "功能集成测试"
        }[feature]
        print(f"{feature_name}: {status}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\n总体结果: {total_passed}/{total_tests} 通过")
    
    if total_passed == total_tests:
        print("\n🎉 所有测试通过！三大高级特性运行正常！")
    else:
        print(f"\n⚠️ 有 {total_tests - total_passed} 个测试失败，请检查相关功能")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)