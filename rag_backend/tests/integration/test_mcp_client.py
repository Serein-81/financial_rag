"""
MCP 服务器 HTTP 客户端测试
使用简单的 HTTP API 调用
"""

import httpx
import asyncio
from typing import Any, Dict

MCP_SERVER_URL = "http://8.148.226.49:8080"
MCP_API_KEY = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"


class HTTPClient:
    """简单的 HTTP 客户端，使用 API Key 认证"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def get_tools(self) -> Dict[str, Any]:
        """获取工具列表"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/tools",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用指定工具"""
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


async def test_connection():
    """测试连接"""
    print("\n📡 测试健康检查...")
    client = HTTPClient(MCP_SERVER_URL, MCP_API_KEY)

    if await client.health_check():
        print("  ✅ 服务器连接正常")
    else:
        print("  ❌ 服务器连接失败")
        return False

    print("\n📋 获取工具列表...")
    try:
        tools_data = await client.get_tools()
        print(f"  ✅ 获取到 {tools_data.get('total', 0)} 个工具:")
        for tool in tools_data.get("tools", []):
            print(f"     - {tool.get('name', 'unknown')}")
        return True
    except Exception as e:
        print(f"  ❌ 获取工具列表失败: {e}")
        return False


async def test_tax_tools():
    """测试税务工具"""
    print("\n🧪 测试税务工具...")
    client = HTTPClient(MCP_SERVER_URL, MCP_API_KEY)

    print("\n  1️⃣ 增值税计算 (calculate_tax_vat)...")
    result = await client.call_tool("calculate_tax_vat", {
        "taxable_amount": 100000,
        "tax_rate": 0.13
    })
    print(f"  结果: {result}")

    print("\n  2️⃣ 企业所得税计算 (calculate_corporate_tax)...")
    result = await client.call_tool("calculate_corporate_tax", {
        "revenue": 1000000,
        "costs": 600000,
        "tax_rate": 0.25
    })
    print(f"  结果: {result}")


async def test_legal_tools():
    """测试法律工具"""
    print("\n⚖️ 测试法律工具...")
    client = HTTPClient(MCP_SERVER_URL, MCP_API_KEY)

    print("\n  1️⃣ 合同要素检查 (check_contract_essentials)...")
    result = await client.call_tool("check_contract_essentials", {
        "contract_type": "销售合同",
        "party_a": "甲方公司",
        "party_b": "乙方公司",
        "subject_matter": "货物买卖"
    })
    print(f"  结果: {result}")


async def test_financial_tools():
    """测试财务工具"""
    print("\n💰 测试财务工具...")
    client = HTTPClient(MCP_SERVER_URL, MCP_API_KEY)

    print("\n  1️⃣ 资产负债率 (calculate_asset_liability_ratio)...")
    result = await client.call_tool("calculate_asset_liability_ratio", {
        "total_assets": 1000000,
        "total_liabilities": 400000
    })
    print(f"  结果: {result}")

    print("\n  2️⃣ 流动比率 (calculate_current_ratio)...")
    result = await client.call_tool("calculate_current_ratio", {
        "current_assets": 500000,
        "current_liabilities": 250000
    })
    print(f"  结果: {result}")

    print("\n  3️⃣ 速动比率 (calculate_quick_ratio)...")
    result = await client.call_tool("calculate_quick_ratio", {
        "current_assets": 500000,
        "inventory": 100000,
        "current_liabilities": 250000
    })
    print(f"  结果: {result}")


async def test_enterprise_tools():
    """测试企业信息工具"""
    print("\n🏢 测试企业信息工具...")
    client = HTTPClient(MCP_SERVER_URL, MCP_API_KEY)

    print("\n  1️⃣ 企业信息搜索 (search_enterprise_info)...")
    result = await client.call_tool("search_enterprise_info", {
        "company_name": "腾讯"
    })
    print(f"  结果: {result}")


async def main():
    print("=" * 60)
    print("🚀 MCP 服务器 HTTP 测试")
    print("=" * 60)

    print(f"\n📡 连接到: {MCP_SERVER_URL}")

    if not await test_connection():
        print("\n❌ 连接失败，退出测试")
        return

    await test_tax_tools()
    await test_legal_tools()
    await test_financial_tools()
    await test_enterprise_tools()

    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
