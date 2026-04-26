"""
A2A Strategy Pattern 测试

验证传输模式切换和状态黑板功能
"""

import asyncio
from app.a2a_protocol import (
    TransportMode,
    TransportStrategy,
    TransportStrategyFactory,
    LangGraphTransport,
    StateBlackboard,
    build_prompt_with_agent_cards,
    A2ATaskBus,
    FinancialAgentState,
    create_initial_state,
    submit_a2a_task,
    complete_a2a_task,
    AgentRegistry
)
from app.a2a_protocol.agent_card import AgentCardBuilder


async def test_transport_mode_switching():
    """测试传输模式切换"""
    print("\n=== 测试 1: 传输模式切换 ===")

    factory = TransportStrategyFactory.get_instance()

    strategy1 = factory.create_strategy(mode="graph_state")
    print(f"当前模式: {factory.current_mode.value}")
    assert factory.current_mode == TransportMode.GRAPH_STATE

    strategy2 = factory.create_strategy(mode="local")
    print(f"切换后模式: {factory.current_mode.value}")

    print("✅ 传输模式切换测试通过")


async def test_langgraph_transport():
    """测试 LangGraph 状态传输"""
    print("\n=== 测试 2: LangGraph 状态传输 ===")

    blackboard = StateBlackboard()
    transport = LangGraphTransport(state_blackboard=blackboard)

    await transport.connect()
    assert transport.is_connected

    message = {
        "content": "测试消息",
        "parts": [],
        "metadata": {"source": "test"}
    }

    result = await transport.send_message(
        to_agent="tax_specialist",
        message=message,
        tenant_id="test_tenant"
    )

    print(f"发送结果: {result}")
    assert "task_id" in result
    assert result["status"] == "queued"

    print(f"黑板队列深度: {blackboard.get_pending_count()}")
    assert blackboard.get_pending_count() == 1

    print("✅ LangGraph 状态传输测试通过")


async def test_agent_card_prompt_builder():
    """测试 AgentCard Prompt 生成器"""
    print("\n=== 测试 3: AgentCard Prompt 生成器 ===")

    cards = [
        AgentCardBuilder(
            name="tax_specialist",
            description="税务专家",
            url="http://localhost:8000"
        ).with_skill("tax_calc", "税务计算", "计算各类税费").build(),

        AgentCardBuilder(
            name="finance_specialist",
            description="财务专家",
            url="http://localhost:8000"
        ).with_skill("finance_analysis", "财务分析", "分析财务报表").build(),
    ]

    prompt = build_prompt_with_agent_cards(cards)
    print(f"生成的 Prompt:\n{prompt}")

    assert "tax_specialist" in prompt
    assert "finance_specialist" in prompt
    assert "税务计算" in prompt

    print("✅ AgentCard Prompt 生成器测试通过")


async def test_a2a_task_bus():
    """测试 A2A 任务总线"""
    print("\n=== 测试 4: A2A 任务总线 ===")

    state = create_initial_state("测试查询")
    print(f"初始状态 keys: {list(state.keys())}")

    state = submit_a2a_task(state, "tax_specialist", "计算增值税")
    print(f"提交任务后 a2a_task_bus 长度: {len(state['a2a_task_bus'])}")

    assert len(state["a2a_task_bus"]) == 1

    task_id = state["a2a_task_bus"][0]["task_id"]
    state = complete_a2a_task(state, task_id, {"result": "税额: 1000元"})

    assert state["agent_results"].get("tax_specialist") is not None

    print("✅ A2A 任务总线测试通过")


async def test_registry_integration():
    """测试 Registry 集成"""
    print("\n=== 测试 5: Registry 集成 ===")

    registry = AgentRegistry.get_instance()

    all_agents = registry.list_all_agents()
    print(f"注册的 Agent 数量: {len(all_agents)}")

    best_agent = registry.find_best_agent("税务计算")
    print(f"最佳匹配 Agent: {best_agent.name if best_agent else 'None'}")

    print("✅ Registry 集成测试通过")


async def main():
    """运行所有测试"""
    print("=" * 50)
    print("A2A Strategy Pattern 测试")
    print("=" * 50)

    await test_transport_mode_switching()
    await test_langgraph_transport()
    await test_agent_card_prompt_builder()
    await test_a2a_task_bus()
    await test_registry_integration()

    print("\n" + "=" * 50)
    print("所有测试通过! ✅")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())