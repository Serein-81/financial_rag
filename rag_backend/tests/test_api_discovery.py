"""测试 Agent Discovery API 端点"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_api_endpoints():
    """测试 API 端点"""
    from app.services.agent_registry import agent_discovery_registry

    print("="*60)
    print("测试 Agent Discovery Registry 状态")
    print("="*60)

    agents = agent_discovery_registry.list_agents(enabled_only=False)
    print(f"\n注册到 agent_discovery_registry 的 Agent 数量: {len(agents)}")

    for agent in agents:
        print(f"\n  Agent: {agent.agent_name} ({agent.agent_id})")
        print(f"    工具数量: {len(agent.tools)}")
        print(f"    工具分布: {agent.get_tool_count_summary()}")

        if agent.tools:
            print(f"    工具列表:")
            for tool in agent.tools[:5]:
                print(f"      - {tool.name} ({tool.location.value}, {tool.category})")
            if len(agent.tools) > 5:
                print(f"      ... 还有 {len(agent.tools) - 5} 个工具")

    summary = agent_discovery_registry.get_summary()
    print(f"\n注册摘要:")
    print(f"  - 总 Agent 数: {summary['total_agents']}")
    print(f"  - 总工具数: {summary['total_tools']}")
    print(f"  - 工具分布: {summary['tool_breakdown']}")

    all_tools = agent_discovery_registry.list_all_tools()
    print(f"\n所有工具: {len(all_tools)} 个")

    local_tools = agent_discovery_registry.list_all_tools(location='local')
    print(f"本地工具: {len(local_tools)} 个")

    mcp_tools = agent_discovery_registry.list_all_tools(location='mcp')
    print(f"MCP 工具: {len(mcp_tools)} 个")

if __name__ == "__main__":
    asyncio.run(test_api_endpoints())
