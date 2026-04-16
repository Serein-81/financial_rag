"""测试各专家注册顺序"""
import asyncio
import sys
sys.path.insert(0, '.')

import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

async def test():
    from app.a2a_protocol.initializer import A2AInitializer
    from app.services.agent_registry import agent_discovery_registry

    print("="*60)
    print("测试专家注册顺序")
    print("="*60)

    initializer = A2AInitializer(base_url="http://localhost:8080")

    print("\n开始注册税务专家...")
    try:
        await initializer._register_tax_specialist()
        print("税务专家注册完成")
    except Exception as e:
        print(f"税务专家注册失败: {e}")

    print("\n开始注册财务专家...")
    try:
        await initializer._register_finance_specialist()
        print("财务专家注册完成")
    except Exception as e:
        print(f"财务专家注册失败: {e}")

    print("\n开始注册法律专家...")
    try:
        await initializer._register_legal_specialist()
        print("法律专家注册完成")
    except Exception as e:
        print(f"法律专家注册失败: {e}")

    print("\n开始注册ReAct Agent...")
    try:
        await initializer._register_react_agent()
        print("ReAct Agent注册完成")
    except Exception as e:
        print(f"ReAct Agent注册失败: {e}")

    print("\n" + "="*60)
    print("注册结果")
    print("="*60)

    agents = agent_discovery_registry.list_agents(enabled_only=False)
    print(f"总共注册了 {len(agents)} 个 Agent")

    for agent in agents:
        print(f"\n【{agent.agent_name}】")
        print(f"  工具总数: {len(agent.tools)}")
        cloud_tools = [t.name for t in agent.tools if t.location.value == 'cloud']
        local_tools = [t.name for t in agent.tools if t.location.value == 'local']
        print(f"  云端工具 ({len(cloud_tools)}): {cloud_tools}")
        print(f"  本地工具 ({len(local_tools)}): {local_tools}")

asyncio.run(test())
