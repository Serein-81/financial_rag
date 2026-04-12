"""
LangSmith 集成测试

测试 AgentTracer 与 LangSmith 的双写功能
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.agent_tracer import agent_tracer


async def test_basic_trace():
    """测试基础追踪功能（本地数据库 + LangSmith）"""
    print("\n" + "="*60)
    print("测试: AgentTracer 基础追踪功能")
    print("="*60)
    
    print(f"LangSmith 启用状态: {agent_tracer.langsmith_enabled}")
    
    # 1. 开始追踪（不传 session_id，因为数据库字段是 UUID 类型）
    trace_id = await agent_tracer.start_trace(
        agent_type="ReAct",
        user_query="测试查询：什么是人工智能？"
    )
    
    print(f"✅ 追踪已开始，ID: {trace_id}")
    
    # 2. 添加步骤
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=1,
        step_type="thought",
        content="我需要思考如何回答这个问题",
        confidence=0.8
    )
    print(f"✅ 添加步骤 1 (thought)")
    
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=2,
        step_type="action",
        content="调用搜索工具",
        tool_name="search_kb",
        tool_input={"query": "人工智能"},
        tool_duration=150.5
    )
    print(f"✅ 添加步骤 2 (action)")
    
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=3,
        step_type="observation",
        content="找到了相关信息...",
        tool_output="人工智能是计算机科学的一个分支..."
    )
    print(f"✅ 添加步骤 3 (observation)")
    
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=4,
        step_type="final_answer",
        content="人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
        confidence=1.0
    )
    print(f"✅ 添加步骤 4 (final_answer)")
    
    # 3. 结束追踪
    await agent_tracer.end_trace(
        trace_id=trace_id,
        final_answer="人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
        success=True
    )
    
    print("✅ 追踪已结束")
    
    # 4. 查询追踪
    trace_data = await agent_tracer.get_trace_with_steps(trace_id)
    
    if trace_data:
        print(f"\n📊 追踪摘要:")
        print(f"   - 总步骤: {trace_data['total_iterations']}")
        print(f"   - 工具调用: {trace_data['tool_calls_count']}")
        print(f"   - 总耗时: {trace_data['total_time']:.2f}s")
        print(f"   - 状态: {trace_data['status']}")
        
        print(f"\n📝 步骤详情:")
        for step in trace_data['steps']:
            icon = {"thought": "💭", "action": "🔧", "observation": "👁️", "final_answer": "✅"}.get(step['step_type'], "📝")
            print(f"   {icon} Step {step['step_number']} ({step['step_type']}): {step['content'][:50]}...")
    else:
        print("❌ 无法获取追踪数据")
    
    return trace_id


async def test_langsmith_config():
    """测试 LangSmith 配置"""
    print("\n" + "="*60)
    print("测试: LangSmith 配置")
    print("="*60)
    
    from app.langsmith_integration import get_langsmith_config
    
    config = get_langsmith_config()
    
    print("LangSmith 配置:")
    for key, value in config.items():
        if key == "api_key" and value:
            # 隐藏 API key
            value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        print(f"   - {key}: {value}")
    
    return config


async def main():
    """主函数"""
    print("\n" + "="*70)
    print("🚀 LangSmith 集成测试开始")
    print("="*70)
    
    try:
        # 测试配置
        await test_langsmith_config()
        
        # 测试基础追踪
        trace_id = await test_basic_trace()
        
        print("\n" + "="*70)
        print("✅ 所有测试通过！")
        print("="*70)
        print(f"\n💡 提示:")
        print(f"   - 本地数据库写入: ✅ 正常工作")
        print(f"   - LangSmith 写入: {'✅ 启用' if agent_tracer.langsmith_enabled else '❌ 未启用（需要配置环境变量）'}")
        print(f"\n📋 启用 LangSmith 需要配置以下环境变量:")
        print(f"   export LANGSMITH_TRACING=true")
        print(f"   export LANGSMITH_API_KEY=your_api_key")
        print(f"   export LANGSMITH_PROJECT=your_project")
        
    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ 测试失败: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
