"""简化的初始化测试"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test():
    from app.services.agent_registry import agent_discovery_registry

    print("="*60)
    print("测试单一专家注册")
    print("="*60)

    from app.a2a_protocol.initializer import A2AInitializer

    initializer = A2AInitializer(base_url="http://localhost:8080")

    print("\n注册税务专家...")
    await initializer._register_tax_specialist()

    print("\n注册财务专家...")
    await initializer._register_finance_specialist()

    print("\n注册法律专家...")
    await initializer._register_legal_specialist()

    print("\n注册ReAct...")
    await initializer._register_react_agent()

    print("\n" + "="*60)
    print("检查注册结果")
    print("="*60)

    agents = agent_discovery_registry.list_agents(enabled_only=False)
    print(f"总共 {len(agents)} 个 Agent:")

    for agent in agents:
        cloud_count = len([t for t in agent.tools if t.location.value == 'cloud'])
        local_count = len([t for t in agent.tools if t.location.value == 'local'])
        print(f"  - {agent.agent_name}: {len(agent.tools)} 个工具 (云端: {cloud_count}, 本地: {local_count})")

    for agent in agents:
        if agent.agent_id == 'tax_specialist':
            print(f"\n税务专家 云端工具: {[t.name for t in agent.tools if t.location.value == 'cloud']}")
        elif agent.agent_id == 'finance_specialist':
            print(f"\n财务专家 云端工具: {[t.name for t in agent.tools if t.location.value == 'cloud']}")
        elif agent.agent_id == 'legal_specialist':
            print(f"\n法律专家 云端工具: {[t.name for t in agent.tools if t.location.value == 'cloud']}")

asyncio.run(test())
