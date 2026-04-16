"""
A2A Transport Layer 测试脚本

测试传输层的各种功能：
1. 本地传输（message_bus）
2. HTTP 传输
3. 传输管理器
"""

import asyncio
import sys
from datetime import datetime

sys.path.insert(0, "d:/Python/Codebase/My_rag/rag_backend")


async def test_local_transport():
    """测试本地传输"""
    print("\n" + "="*60)
    print("[TEST 1] 本地传输 (LocalAgentTransport)")
    print("="*60)
    
    from app.a2a_protocol.transports import LocalAgentTransport, TransportConfig
    from app.multi_agent_system.message_bus import MessageBus
    
    message_bus = MessageBus()
    
    config = TransportConfig(
        transport_type="local",
        timeout=30.0
    )
    
    transport = LocalAgentTransport(config, message_bus)
    await transport.connect()
    
    class DummyAgent:
        async def process_message(self, message):
            return {
                "status": "processed",
                "received": message,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    dummy = DummyAgent()
    transport.register_local_agent("test_agent", dummy)
    
    result = await transport.send_message(
        to_agent="test_agent",
        message={"content": "Hello from test!"},
        tenant_id="test_tenant"
    )
    
    print(f"[PASS] 本地传输测试通过")
    print(f"   Response: {result}")
    
    stats = transport.get_statistics()
    print(f"   Stats: {stats}")
    
    await transport.disconnect()
    
    return True


async def test_http_transport():
    """测试 HTTP 传输"""
    print("\n" + "="*60)
    print("[TEST 2] HTTP 传输 (HttpAgentTransport)")
    print("="*60)
    
    from app.a2a_protocol.transports import HttpAgentTransport, TransportConfig
    
    config = TransportConfig(
        transport_type="http",
        url="http://httpbin.org",
        timeout=10.0
    )
    
    transport = HttpAgentTransport(config)
    await transport.connect()
    
    health = await transport.health_check()
    print(f"   Health check: {health}")
    
    stats = transport.get_statistics()
    print(f"   Stats: {stats}")
    
    await transport.disconnect()
    
    return True


async def test_transport_manager():
    """测试传输管理器"""
    print("\n" + "="*60)
    print("[TEST 3] 传输管理器 (TransportManager)")
    print("="*60)
    
    from app.a2a_protocol.transports import get_transport_manager, shutdown_transport_manager
    
    transport = await get_transport_manager()
    
    class DummyAgent:
        async def process_message(self, message):
            return {
                "status": "processed",
                "received": message
            }
    
    transport.register_local_agent("assistant", DummyAgent())
    
    result = await transport.send_message(
        to_agent="assistant",
        message={"content": "Test message"},
        tenant_id="test_tenant"
    )
    
    print(f"[PASS] 传输管理器测试通过")
    print(f"   Response: {result}")
    
    stats = transport.get_statistics()
    print(f"   Stats: {stats}")
    
    await shutdown_transport_manager()
    
    return True


async def test_multitenant():
    """测试多租户穿透"""
    print("\n" + "="*60)
    print("[TEST 4] 多租户穿透")
    print("="*60)
    
    from app.a2a_protocol.transports import get_transport_manager, shutdown_transport_manager
    
    transport = await get_transport_manager()
    
    tenants = ["tenant_a", "tenant_b", "tenant_c"]
    
    for tenant_id in tenants:
        result = await transport.send_message(
            to_agent="assistant",
            message={
                "content": f"Hello from {tenant_id}",
                "tenant_id": tenant_id
            },
            tenant_id=tenant_id
        )
        print(f"   [PASS] {tenant_id}: {result}")
    
    await shutdown_transport_manager()
    
    return True


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("A2A Transport Layer 测试套件")
    print("="*60)
    
    tests = [
        ("本地传输", test_local_transport),
        ("HTTP 传输", test_http_transport),
        ("传输管理器", test_transport_manager),
        ("多租户穿透", test_multitenant),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"[FAIL] {name} 测试失败: {e}")
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, result, error in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} | {name}")
        if error:
            print(f"     Error: {error}")
    
    total = len(results)
    passed = sum(1 for _, result, _ in results if result)
    print(f"\nTotal: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
