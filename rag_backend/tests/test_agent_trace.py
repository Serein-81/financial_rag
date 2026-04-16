# test_agent_trace.py

"""
Agent 追踪功能测试

测试 Agent 决策可视化的完整功能
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent_framework.core.agent_factory import AgentFactory
from app.agent_framework.llm.factory import LLMFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.services.agent_tracer import agent_tracer


async def test_basic_trace():
    """测试基础追踪功能"""
    print("\n" + "="*60)
    print("测试 1: 基础追踪功能")
    print("="*60)
    
    # 1. 开始追踪
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
    
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=2,
        step_type="action",
        content="调用搜索工具",
        tool_name="search_kb",
        tool_input={"query": "人工智能"},
        tool_duration=150.5
    )
    
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=3,
        step_type="observation",
        content="找到了相关信息...",
        tool_output="人工智能是计算机科学的一个分支..."
    )
    
    await agent_tracer.add_step(
        trace_id=trace_id,
        step_number=4,
        step_type="final_answer",
        content="人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
        confidence=1.0
    )
    
    # 3. 结束追踪
    await agent_tracer.end_trace(
        trace_id=trace_id,
        final_answer="人工智能是计算机科学的一个分支...",
        success=True
    )
    
    print("✅ 追踪已结束")
    
    # 4. 查询追踪
    trace_data = await agent_tracer.get_trace_with_steps(trace_id)
    
    print("\n📊 追踪摘要:")
    print(f"   - 总步骤: {trace_data['total_iterations']}")
    print(f"   - 工具调用: {trace_data['tool_calls_count']}")
    print(f"   - 总耗时: {trace_data['total_time']:.2f}s")
    print(f"   - 状态: {trace_data['status']}")
    
    print("\n📝 步骤详情:")
    for step in trace_data['steps']:
        icon = {"thought": "💭", "action": "🔧", "observation": "👁️", "final_answer": "✅"}.get(step['step_type'], "📝")
        print(f"   {icon} Step {step['step_number']} ({step['step_type']}): {step['content'][:50]}...")
    
    return trace_id


async def test_agent_with_trace():
    """测试 Agent 集成追踪"""
    print("\n" + "="*60)
    print("测试 2: Agent 集成追踪")
    print("="*60)
    
    try:
        # 1. 创建 LLM 适配器
        llm = LLMFactory.create_llm(
            provider="zhipu",
            model="glm-4-flash"
        )
        
        # 2. 创建工具管理器
        tool_manager = ToolManager()
        
        # 添加一个简单的测试工具
        def simple_search(query: str) -> str:
            return f"搜索结果：关于'{query}'的信息..."
        
        tool_manager.register_function(
            name="simple_search",
            func=simple_search,
            description="简单的搜索工具"
        )
        
        # 3. 创建 Agent
        agent = AgentFactory.create_agent(
            agent_type="react",
            llm_adapter=llm,
            tool_manager=tool_manager
        )
        
        # 4. 执行 Agent（会自动追踪）
        print("\n🤖 执行 Agent...")
        result = await agent.run(
            user_input="什么是机器学习？",
            session_id="test-session-123"
        )
        
        print(f"\n✅ Agent 回答: {result[:100]}...")
        
        # 5. 查询追踪记录
        if agent.current_trace_id:
            print(f"\n📊 查询追踪记录: {agent.current_trace_id}")
            trace_data = await agent_tracer.get_trace_with_steps(agent.current_trace_id)
            
            if trace_data:
                print(f"   - Agent 类型: {trace_data['agent_type']}")
                print(f"   - 总步骤: {trace_data['total_iterations']}")
                print(f"   - 工具调用: {trace_data['tool_calls_count']}")
                print(f"   - 状态: {trace_data['status']}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_session_traces():
    """测试会话追踪查询"""
    print("\n" + "="*60)
    print("测试 3: 会话追踪查询")
    print("="*60)
    
    session_id = "test-session-456"
    
    # 创建多个追踪
    for i in range(3):
        trace_id = await agent_tracer.start_trace(
            agent_type="ReAct",
            user_query=f"测试查询 {i+1}",
            session_id=session_id
        )
        
        await agent_tracer.add_step(
            trace_id=trace_id,
            step_number=1,
            step_type="thought",
            content=f"思考问题 {i+1}"
        )
        
        await agent_tracer.end_trace(
            trace_id=trace_id,
            final_answer=f"答案 {i+1}",
            success=True
        )
    
    # 查询会话的所有追踪
    traces = await agent_tracer.get_session_traces(session_id)
    
    print(f"\n📊 会话 {session_id} 的追踪记录:")
    print(f"   总数: {len(traces)}")
    
    for i, trace in enumerate(traces, 1):
        print(f"\n   {i}. {trace['trace_id']}")
        print(f"      查询: {trace['user_query']}")
        print(f"      状态: {trace['status']}")
        print(f"      步骤: {trace['total_iterations']}")


async def main():
    """主测试函数"""
    print("\n🧪 开始 Agent 追踪功能测试")
    print("="*60)
    
    try:
        # 测试 1: 基础追踪
        await test_basic_trace()
        
        # 测试 2: Agent 集成（需要配置 LLM）
        # await test_agent_with_trace()
        
        # 测试 3: 会话追踪查询
        await test_session_traces()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
