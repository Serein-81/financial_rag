"""
MCP 客户端模式切换测试

测试本地/云端模式切换功能
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()


async def test_current_mode():
    """测试当前配置的 MCP 模式"""
    from app.mcp import mcp_factory, MCPMode

    mode = mcp_factory.get_mode()
    mcp_factory.print_mode_info()

    print("\n" + "=" * 60)
    print(f"🔍 测试 {mode.value.upper()} 模式")
    print("=" * 60)

    try:
        await mcp_factory.connect()

        print("\n📋 可用工具列表:")
        tools = await mcp_factory.list_tools()
        for i, tool in enumerate(tools, 1):
            print(f"   {i}. {tool.get('name', 'unknown')}")

        print("\n🧪 测试工具调用:")
        result = await mcp_factory.call_tool("calculate_tax_vat", taxable_amount=100000, tax_rate=0.13)

        print("\n   调用结果:")
        print(f"   - 成功: {result.success}")
        if result.success:
            print(f"   - 数据: {result.data}")
        else:
            print(f"   - 错误: {result.error}")

        await mcp_factory.disconnect()

        print("\n" + "=" * 60)
        print("✅ 测试成功！")
        print("=" * 60)

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ 测试失败！")
        print(f"错误: {e}")
        print("=" * 60)

        print("\n💡 故障排除:")
        if mode == MCPMode.LOCAL:
            print("   1. 确保本地 MCP 服务器已启动:")
            print("      cd mcp_server && python -m uvicorn app.main:app --port 8001")
        else:
            print("   1. 检查云端服务器是否运行")
            print("   2. 检查网络连接")
            print("   3. 确认 API Key 正确")

        return False


def switch_mode(new_mode: str):
    """切换 MCP 模式"""
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        print("❌ .env 文件不存在")
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    replaced = False

    for line in lines:
        if line.startswith("MCP_MODE="):
            new_lines.append(f"MCP_MODE={new_mode}\n")
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        new_lines.append(f"\nMCP_MODE={new_mode}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"✅ 已切换到 {new_mode.upper()} 模式")
    print("   请重启程序以应用更改")

    return True


def print_usage():
    """打印使用说明"""
    print("\n" + "=" * 60)
    print("🔧 MCP 客户端模式切换工具")
    print("=" * 60)
    print("\n用法:")
    print("  python test_mcp_switch.py              # 测试当前模式")
    print("  python test_mcp_switch.py local       # 切换到本地模式")
    print("  python test_mcp_switch.py cloud        # 切换到云端模式")
    print("  python test_mcp_switch.py switch <mode>  # 切换模式")
    print("\n配置:")
    print("  MCP_MODE=local  # 本地模式（连接 127.0.0.1:8001）")
    print("  MCP_MODE=cloud  # 云端模式（连接远程服务器）")
    print("=" * 60)


async def main():
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "local":
            switch_mode("local")
            return
        elif command == "cloud":
            switch_mode("cloud")
            return
        elif command == "switch" and len(sys.argv) > 2:
            switch_mode(sys.argv[2].lower())
            return
        elif command in ["help", "-h", "--help"]:
            print_usage()
            return
        else:
            print(f"❌ 未知命令: {command}")
            print_usage()
            return

    print_usage()
    await test_current_mode()


if __name__ == "__main__":
    asyncio.run(main())
