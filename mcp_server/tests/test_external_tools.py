"""
MCP 服务器外部服务工具测试
直接通过 HTTP API 调用 MCP 服务器
"""

import asyncio
import httpx


MCP_SERVER_URL = "http://8.148.226.49:8080"
MCP_API_KEY = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"


class MCPClient:
    """MCP HTTP 客户端"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def get_tools(self) -> dict:
        """获取工具列表"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/tools",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用工具"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/mcp/call",
                headers=self.headers,
                json={"tool_name": tool_name, "arguments": arguments}
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


async def test_mcp_server_connection():
    """测试 MCP 服务器连接"""
    print("=" * 60)
    print("🔗 MCP 服务器连接测试")
    print("=" * 60)

    client = MCPClient(MCP_SERVER_URL, MCP_API_KEY)

    print("\n📡 测试服务器连接...")
    if await client.health_check():
        print("  ✅ 服务器连接正常")
        return True, client
    else:
        print("  ❌ 服务器连接失败")
        return False, None


async def test_tools_list(client: MCPClient):
    """测试获取工具列表"""
    print("\n" + "=" * 60)
    print("📋 获取工具列表")
    print("=" * 60)

    try:
        tools_data = await client.get_tools()
        total = tools_data.get("total", 0)
        tools = tools_data.get("tools", [])
        
        print(f"  ✅ 获取到 {total} 个工具:")
        
        external_tools = []
        for tool in tools:
            name = tool.get("name", "unknown")
            category = tool.get("category", "unknown")
            print(f"     - {name} ({category})")
            
            if name in ["get_weather", "get_location_info", "search_web"]:
                external_tools.append(name)
        
        return True, external_tools

    except Exception as e:
        print(f"  ❌ 获取工具列表失败: {e}")
        return False, []


async def test_weather_tool(client: MCPClient):
    """测试天气查询工具"""
    print("\n" + "=" * 60)
    print("🌤️  天气查询工具测试")
    print("=" * 60)

    try:
        print("\n📍 测试查询北京天气...")
        result = await client.call_tool("get_weather", {"city_name": "北京"})
        print(f"  ✅ 工具调用成功")
        print(f"  结果: {result}")
        return True

    except Exception as e:
        print(f"  ❌ 天气查询失败: {e}")
        return False


async def test_location_tool(client: MCPClient):
    """测试位置查询工具"""
    print("\n" + "=" * 60)
    print("📍 位置查询工具测试")
    print("=" * 60)

    try:
        print("\n📍 测试查询北京市朝阳区位置信息...")
        result = await client.call_tool("get_location_info", {"address": "北京市朝阳区"})
        print(f"  ✅ 工具调用成功")
        print(f"  结果: {result}")
        return True

    except Exception as e:
        print(f"  ❌ 位置查询失败: {e}")
        return False


async def test_search_tool(client: MCPClient):
    """测试网络搜索工具"""
    print("\n" + "=" * 60)
    print("🔍 网络搜索工具测试")
    print("=" * 60)

    try:
        print("\n🔎 测试搜索 'Python 异步编程' ...")
        result = await client.call_tool("search_web", {
            "query": "Python 异步编程",
            "max_results": 3
        })
        print(f"  ✅ 工具调用成功")
        
        result_str = str(result)
        if len(result_str) > 300:
            print(f"  结果 (前300字符): {result_str[:300]}...")
        else:
            print(f"  结果: {result}")
        return True

    except Exception as e:
        print(f"  ❌ 网络搜索失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 MCP 服务器外部服务工具测试")
    print("=" * 60)
    print(f"\n服务器地址: {MCP_SERVER_URL}")

    results = {}

    success, client = await test_mcp_server_connection()
    results["服务器连接"] = success

    if success:
        results["工具列表"], external_tools = await test_tools_list(client)
        
        if "get_weather" in external_tools:
            results["天气查询"] = await test_weather_tool(client)
        else:
            print("\n⚠️  get_weather 工具未在服务器上注册，跳过测试")
            results["天气查询"] = None

        if "get_location_info" in external_tools:
            results["位置查询"] = await test_location_tool(client)
        else:
            print("\n⚠️  get_location_info 工具未在服务器上注册，跳过测试")
            results["位置查询"] = None

        if "search_web" in external_tools:
            results["网络搜索"] = await test_search_tool(client)
        else:
            print("\n⚠️  search_web 工具未在服务器上注册，跳过测试")
            results["网络搜索"] = None
    else:
        results["工具列表"] = False
        results["天气查询"] = False
        results["位置查询"] = False
        results["网络搜索"] = False

    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        if passed is None:
            status = "⏭️ 跳过"
        elif passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"  {test_name}: {status}")

    all_passed = all(r for r in results.values() if r is not None)
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请检查 MCP 服务器状态")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
