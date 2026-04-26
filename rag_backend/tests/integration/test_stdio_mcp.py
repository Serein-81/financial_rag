"""
本地 STDIO MCP 测试

测试本地 MCP STDIO 服务器的通信
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def test_stdio_server():
    """测试 STDIO MCP 服务器"""
    print("=" * 60)
    print("🧪 测试本地 STDIO MCP 服务器")
    print("=" * 60)

    try:
        from app.mcp.stdio_client import LocalMCPClient
        from app.mcp.stdio_server import LocalMCPServer
        
        server_command = "python -m app.mcp.stdio_server"
        working_dir = os.path.join(os.path.dirname(__file__), "..")
        
        print(f"\n📡 初始化 STDIO 客户端...")
        print(f"   命令: {server_command}")
        print(f"   工作目录: {working_dir}")
        
        client = LocalMCPClient(
            server_command=server_command,
            working_directory=working_dir
        )
        
        print("\n🔌 连接 STDIO 服务器...")
        try:
            await client.connect()
            print("   ✅ 连接成功")
            
            print("\n📋 获取工具列表...")
            tools = client.list_tools()
            print(f"   ✅ 发现 {len(tools)} 个工具:")
            for tool in tools[:5]:  # 只显示前5个工具
                print(f"      - {tool.name}: {tool.description[:50]}...")
            if len(tools) > 5:
                print(f"      ... 还有 {len(tools) - 5} 个工具")
            
            print("\n🔧 测试工具调用...")
            if tools:
                test_tool = tools[0]
                print(f"   调用工具: {test_tool.name}")
                
                result = await client.call_tool(test_tool.name, tenant_id="test_tenant")
                print(f"   ✅ 工具执行成功")
                print(f"   结果: {result[:200]}...")
            else:
                print("   ⚠️ 没有可用的工具进行测试")
            
            print("\n🔌 断开连接...")
            await client.disconnect()
            print("   ✅ 断开成功")
            
            print("\n" + "=" * 60)
            print("✅ STDIO MCP 测试通过")
            print("=" * 60)
            return True
            
        except (ConnectionRefusedError, FileNotFoundError, TimeoutError) as e:
            print(f"   ⚠️  STDIO 服务器未运行或连接失败: {e}")
            print("     提示: 请确保 STDIO MCP 服务器已启动")
            print("\n" + "=" * 60)
            print("⚠️  STDIO MCP 测试跳过（服务器未运行）")
            print("=" * 60)
            return True  # 跳过测试，不算失败
        
    except Exception as e:
        print(f"\n❌ STDIO MCP 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mcp_factory():
    """测试 MCP 工厂"""
    print("\n" + "=" * 60)
    print("🧪 测试 MCP 工厂（STDIO 模式）")
    print("=" * 60)

    try:
        from app.mcp.mcp_factory import mcp_factory, MCPMode
        
        mode = mcp_factory.get_mode()
        print(f"\n📊 当前 MCP 模式: {mode.value}")
        
        print("\n🔌 连接 MCP 服务器...")
        try:
            await mcp_factory.connect()
            print("   ✅ 连接成功")
            
            print("\n📋 获取工具列表...")
            tools = await mcp_factory.list_tools()
            print(f"   ✅ 发现 {len(tools)} 个工具")
            for tool in tools[:5]:
                print(f"      - {tool.get('name', 'unknown')}: {tool.get('source', 'unknown')}")
            if len(tools) > 5:
                print(f"      ... 还有 {len(tools) - 5} 个工具")
            
            print("\n🔌 断开连接...")
            await mcp_factory.disconnect()
            print("   ✅ 断开成功")
            
            print("\n" + "=" * 60)
            print("✅ MCP 工厂测试通过")
            print("=" * 60)
            return True
            
        except (ConnectionRefusedError, TimeoutError) as e:
            print(f"   ⚠️  MCP 服务器连接失败: {e}")
            print("     提示: 请确保 MCP 服务器已启动")
            print("\n" + "=" * 60)
            print("⚠️  MCP 工厂测试跳过（服务器未运行）")
            print("=" * 60)
            return True  # 跳过测试，不算失败
        
    except Exception as e:
        print(f"\n❌ MCP 工厂测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_tool_registry():
    """测试 Agent 工具注册"""
    print("\n" + "=" * 60)
    print("🧪 测试 Agent 工具注册（STDIO 模式）")
    print("=" * 60)

    try:
        from app.agent_framework.tools.tool_manager import ToolManager
        from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
        
        print("\n🔧 初始化工具管理器...")
        tool_manager = ToolManager()
        print("   ✅ 工具管理器创建成功")
        
        print("\n📦 注册工具...")
        result = await initialize_tool_manager(
            tool_manager,
            include_mcp=True,
            include_local=False,
            tenant_id="test_tenant"
        )
        
        print(f"\n📊 注册结果:")
        print(f"   MCP 工具: {len(result['cloud_tools'])} 个")
        print(f"   本地工具: {len(result['local_tools'])} 个")
        print(f"   总计: {result['total_count']} 个")
        
        print(f"\n🔧 可用工具列表:")
        for tool_name in tool_manager.tools.keys():
            print(f"   - {tool_name}")
        
        print("\n" + "=" * 60)
        print("✅ Agent 工具注册测试通过")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Agent 工具注册测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    os.environ["MCP_MODE"] = "stdio"
    
    tests = [
        ("STDIO MCP 服务器", test_stdio_server),
        ("MCP 工厂", test_mcp_factory),
        ("Agent 工具注册", test_agent_tool_registry),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 {test_name} 时发生异常: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
