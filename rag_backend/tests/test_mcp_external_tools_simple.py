"""
MCP 外部服务工具简单测试
直接测试 MCP 工具功能，不依赖完整 Agent 框架
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def test_mcp_proxy():
    """
    测试 MCP 代理和工具
    """
    print("=" * 60)
    print("🔧 MCP 外部服务工具测试")
    print("=" * 60)

    try:
        from app.mcp.mcp_tool_proxy import get_mcp_proxy, TOOL_ROUTING_CONFIG
        from app.agent_framework.tools.tool_router import get_mcp_tools

        print("\n📋 MCP 工具路由配置检查...")
        mcp_tools = get_mcp_tools()
        print(f"  ✅ 找到 {len(mcp_tools)} 个 MCP 工具:")
        for tool_name in mcp_tools:
            config = TOOL_ROUTING_CONFIG.get(tool_name, {})
            print(f"     - {tool_name}")
            print(f"       描述: {config.get('description', 'N/A')[:60]}...")

        print("\n📡 初始化 MCP 代理...")
        proxy = await get_mcp_proxy()
        print(f"  ✅ MCP 代理已连接")
        print(f"     服务器地址: {proxy.base_url}")

        return True, mcp_tools, proxy

    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False, [], None


async def test_weather_tool(proxy):
    """
    测试天气工具
    """
    print("\n" + "=" * 60)
    print("🌤️  天气查询工具测试")
    print("=" * 60)

    if not proxy:
        print("  ⚠️ MCP 代理未初始化，跳过测试")
        return False

    try:
        print("\n📍 测试查询北京天气...")
        result = await proxy.call_tool("get_weather", city_name="北京")
        print(f"  ✅ 结果: {result}")
        return True

    except Exception as e:
        print(f"  ❌ 天气查询失败: {e}")
        return False


async def test_location_tool(proxy):
    """
    测试位置查询工具
    """
    print("\n" + "=" * 60)
    print("📍 位置查询工具测试")
    print("=" * 60)

    if not proxy:
        print("  ⚠️ MCP 代理未初始化，跳过测试")
        return False

    try:
        print("\n📍 测试查询北京市朝阳区位置信息...")
        result = await proxy.call_tool("get_location_info", address="北京市朝阳区")
        print(f"  ✅ 结果: {result}")
        return True

    except Exception as e:
        print(f"  ❌ 位置查询失败: {e}")
        return False


async def test_search_tool(proxy):
    """
    测试网络搜索工具
    """
    print("\n" + "=" * 60)
    print("🔍 网络搜索工具测试")
    print("=" * 60)

    if not proxy:
        print("  ⚠️ MCP 代理未初始化，跳过测试")
        return False

    try:
        print("\n🔎 测试搜索 'Python 异步编程' ...")
        result = await proxy.call_tool("search_web", query="Python 异步编程", max_results=3)
        
        if isinstance(result, str) and len(result) > 200:
            print(f"  ✅ 结果 (前200字符): {result[:200]}...")
        else:
            print(f"  ✅ 结果: {result}")
        return True

    except Exception as e:
        print(f"  ❌ 网络搜索失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 MCP 外部服务工具完整测试")
    print("=" * 60)

    results = {}

    success, mcp_tools, proxy = await test_mcp_proxy()
    results["MCP工具配置"] = success

    if success:
        results["天气查询"] = await test_weather_tool(proxy)
        results["位置查询"] = await test_location_tool(proxy)
        results["网络搜索"] = await test_search_tool(proxy)
    else:
        results["天气查询"] = False
        results["位置查询"] = False
        results["网络搜索"] = False

    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")

    print("\n📋 MCP 工具列表:")
    for tool in mcp_tools:
        print(f"     - {tool}")

    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请检查 MCP 服务器状态和配置")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
