"""测试各专家工具过滤逻辑"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test():
    from app.agent_framework.tools.agent_tool_registry import get_specialist_tools_config

    print("="*60)
    print("测试各专家的工具配置")
    print("="*60)

    test_cases = [
        ("税务专家", "税务"),
        ("财务专家", "财务"),
        ("法律专家", "法律"),
        ("ReAct通用智能体", "通用"),
    ]

    for name, specialty in test_cases:
        config = get_specialist_tools_config(specialty.lower())
        print(f"\n【{name}】(specialty={specialty})")
        print(f"  MCP工具: {config.get('mcp_tools', [])}")
        print(f"  本地工具: {config.get('local_tools', [])}")
        print(f"  MCP工具数量: {len(config.get('mcp_tools', []))}")
        print(f"  本地工具数量: {len(config.get('local_tools', []))}")
        print(f"  总计: {len(config.get('mcp_tools', [])) + len(config.get('local_tools', []))}")

asyncio.run(test())
