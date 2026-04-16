"""测试工具过滤逻辑"""
import asyncio
import sys
import logging
sys.path.insert(0, '.')

logging.basicConfig(level=logging.DEBUG, format='%(message)s')
logger = logging.getLogger('app.a2a_protocol.initializer')
logger.setLevel(logging.DEBUG)

async def test():
    from app.a2a_protocol.initializer import initialize_a2a_protocol
    from app.services.agent_registry import agent_discovery_registry

    print("="*60)
    print("测试工具过滤逻辑")
    print("="*60)

    initializer, registry = await initialize_a2a_protocol()

    print("\n" + "="*60)
    print("注册结果")
    print("="*60)

    agents = agent_discovery_registry.list_agents(enabled_only=False)
    for agent in agents:
        print(f"\n【{agent.agent_name}】")
        print(f"  工具总数: {len(agent.tools)}")
        print(f"  云端工具 ({len([t for t in agent.tools if t.location.value == 'cloud'])}): {[t.name for t in agent.tools if t.location.value == 'cloud']}")
        print(f"  本地工具 ({len([t for t in agent.tools if t.location.value == 'local'])}): {[t.name for t in agent.tools if t.location.value == 'local']}")

asyncio.run(test())
