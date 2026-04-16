"""测试直接调用 A2AInitializer 初始化"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_initialize():
    """测试 A2AInitializer 初始化"""
    print("="*60)
    print("测试 A2AInitializer 初始化")
    print("="*60)

    try:
        from app.a2a_protocol.initializer import initialize_a2a_protocol
        from app.services.agent_registry import agent_discovery_registry

        print("\n调用 initialize_a2a_protocol()...")
        initializer, registry = await initialize_a2a_protocol()

        print("\n初始化完成！")
        print(f"  - Wrappers: {list(initializer.wrappers.keys())}")

        agents = agent_discovery_registry.list_agents(enabled_only=False)
        print(f"\n注册到 agent_discovery_registry 的 Agent 数量: {len(agents)}")

        for agent in agents:
            print(f"\n  Agent: {agent.agent_name} ({agent.agent_id})")
            print(f"    工具数量: {len(agent.tools)}")
            print(f"    工具分布: {agent.get_tool_count_summary()}")

        summary = agent_discovery_registry.get_summary()
        print(f"\n注册摘要:")
        print(f"  - 总 Agent 数: {summary['total_agents']}")
        print(f"  - 总工具数: {summary['total_tools']}")
        print(f"  - 工具分布: {summary['tool_breakdown']}")

    except Exception as e:
        print(f"\n❌ 初始化失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_initialize())
