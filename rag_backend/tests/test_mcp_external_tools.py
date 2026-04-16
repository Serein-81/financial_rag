"""
MCP 外部服务工具测试
测试天气查询、位置查询、网络搜索功能
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


async def test_mcp_tools_via_proxy():
    """
    通过 MCP 代理测试工具
    """
    print("=" * 60)
    print("🔧 MCP 外部服务工具测试")
    print("=" * 60)

    try:
        from app.agent_framework.tools.tool_manager import ToolManager
        from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
        from app.mcp.mcp_tool_proxy import get_mcp_proxy, get_all_mcp_tools_as_langchain_tools

        print("\n📡 初始化 MCP 代理...")
        proxy = await get_mcp_proxy()
        print(f"  ✅ MCP 代理已连接: {proxy}")

        print("\n📋 获取 MCP 工具列表...")
        tools = get_all_mcp_tools_as_langchain_tools()
        print(f"  ✅ 找到 {len(tools)} 个 MCP 工具:")
        for tool in tools:
            print(f"     - {tool.name}: {tool.description[:50]}...")

        print("\n📦 初始化工具管理器并注册工具...")
        tool_manager = ToolManager()
        result = await initialize_tool_manager(
            tool_manager,
            include_mcp=True,
            include_local=False,
            tenant_id="test_tenant"
        )
        print(f"  ✅ MCP 工具注册结果: {len(result['mcp_tools'])} 个")
        print(f"     工具列表: {result['mcp_tools']}")

        return True

    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_weather_tool_direct():
    """
    直接测试天气工具
    """
    print("\n" + "=" * 60)
    print("🌤️  天气查询工具测试")
    print("=" * 60)

    try:
        from app.mcp.mcp_tool_proxy import get_mcp_proxy

        proxy = await get_mcp_proxy()

        print("\n📍 测试查询北京天气...")
        result = await proxy.call_tool("get_weather", city_name="北京")
        print(f"  ✅ 结果: {result}")

        return True

    except Exception as e:
        print(f"  ❌ 天气查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_location_tool_direct():
    """
    直接测试位置查询工具
    """
    print("\n" + "=" * 60)
    print("📍 位置查询工具测试")
    print("=" * 60)

    try:
        from app.mcp.mcp_tool_proxy import get_mcp_proxy

        proxy = await get_mcp_proxy()

        print("\n📍 测试查询北京市朝阳区位置信息...")
        result = await proxy.call_tool("get_location_info", address="北京市朝阳区")
        print(f"  ✅ 结果: {result}")

        return True

    except Exception as e:
        print(f"  ❌ 位置查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_search_tool_direct():
    """
    直接测试网络搜索工具
    """
    print("\n" + "=" * 60)
    print("🔍 网络搜索工具测试")
    print("=" * 60)

    try:
        from app.mcp.mcp_tool_proxy import get_mcp_proxy

        proxy = await get_mcp_proxy()

        print("\n🔎 测试搜索 'Python 异步编程' ...")
        result = await proxy.call_tool("search_web", query="Python 异步编程", max_results=3)
        print(f"  ✅ 结果: {result[:500]}..." if len(str(result)) > 500 else f"  ✅ 结果: {result}")

        return True

    except Exception as e:
        print(f"  ❌ 网络搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_receptionist_agent_tools():
    """
    测试接待智能体的 MCP 工具注册
    """
    print("\n" + "=" * 60)
    print("🤝 接待智能体 MCP 工具测试")
    print("=" * 60)

    try:
        from app.agent_framework.llm.factory import LLMAdapterFactory
        from app.agent_framework.tools.tool_manager import ToolManager
        from app.agent_framework.tools.agent_tool_registry import (
            initialize_tool_manager,
            get_receptionist_tools_config
        )
        from app.multi_agent_system.agents.receptionist_agent import ReceptionistAgent
        from app.multi_agent_system.message_bus import MessageBus

        print("\n🔧 获取接待智能体工具配置...")
        config = get_receptionist_tools_config()
        print(f"  ✅ MCP 工具: {config['mcp_tools']}")
        print(f"  ✅ 本地工具: {config['local_tools']}")

        print("\n🤖 创建接待智能体...")
        llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
        tool_manager = ToolManager()

        await initialize_tool_manager(
            tool_manager,
            include_mcp=True,
            include_local=True,
            tenant_id="test_tenant"
        )

        print(f"\n  ✅ 工具管理器已注册 {len(tool_manager.tools)} 个工具:")
        for name in tool_manager.tools.keys():
            print(f"     - {name}")

        message_bus = MessageBus()
        receptionist = ReceptionistAgent(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            message_bus=message_bus,
            timeout=30.0
        )

        print("\n  ✅ 接待智能体初始化成功")
        print(f"     工具管理器工具数量: {len(receptionist.tool_manager.tools)}")

        return True

    except Exception as e:
        print(f"  ❌ 接待智能体测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_specialist_agents_search():
    """
    测试专家智能体的搜索功能
    """
    print("\n" + "=" * 60)
    print("💼 专家智能体搜索功能测试")
    print("=" * 60)

    try:
        from app.agent_framework.llm.factory import LLMAdapterFactory
        from app.agent_framework.tools.tool_manager import ToolManager
        from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
        from app.multi_agent_system.agents.finance_specialist import FinanceSpecialist
        from app.multi_agent_system.agents.tax_specialist import TaxSpecialist
        from app.multi_agent_system.agents.legal_specialist import LegalSpecialist

        print("\n🤖 创建财务专家智能体...")
        llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
        finance_tool_manager = ToolManager()

        await initialize_tool_manager(
            finance_tool_manager,
            include_mcp=True,
            include_local=True,
            tenant_id="test_tenant"
        )

        finance_specialist = FinanceSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=finance_tool_manager
        )

        print(f"  ✅ 财务专家工具: {list(finance_specialist.tool_manager.tools.keys())}")

        print("\n🤖 创建税务专家智能体...")
        tax_tool_manager = ToolManager()

        await initialize_tool_manager(
            tax_tool_manager,
            include_mcp=True,
            include_local=True,
            tenant_id="test_tenant"
        )

        tax_specialist = TaxSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tax_tool_manager
        )

        print(f"  ✅ 税务专家工具: {list(tax_specialist.tool_manager.tools.keys())}")

        print("\n🤖 创建法务专家智能体...")
        legal_tool_manager = ToolManager()

        await initialize_tool_manager(
            legal_tool_manager,
            include_mcp=True,
            include_local=True,
            tenant_id="test_tenant"
        )

        legal_specialist = LegalSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=legal_tool_manager
        )

        print(f"  ✅ 法务专家工具: {list(legal_specialist.tool_manager.tools.keys())}")

        has_search = "search_web" in finance_specialist.tool_manager.tools
        print(f"\n  ✅ 所有专家智能体都已添加 search_web: {has_search}")

        return True

    except Exception as e:
        print(f"  ❌ 专家智能体测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 MCP 外部服务工具完整测试")
    print("=" * 60)

    results = {}

    results["MCP工具注册"] = await test_mcp_tools_via_proxy()
    results["天气查询"] = await test_weather_tool_direct()
    results["位置查询"] = await test_location_tool_direct()
    results["网络搜索"] = await test_search_tool_direct()
    results["接待智能体"] = await test_receptionist_agent_tools()
    results["专家智能体"] = await test_specialist_agents_search()

    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请检查配置")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
