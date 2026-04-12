"""
A2A Transport Layer 轻量级测试
直接测试传输层组件，不触发完整应用初始化
"""

import asyncio
import sys
from datetime import datetime

sys.path.insert(0, "d:/Python/Codebase/My_rag/rag_backend")


async def test_transport_base():
    """测试传输基类"""
    print("\n" + "="*60)
    print("[TEST 1] 传输层基础测试")
    print("="*60)
    
    from app.a2a_protocol.transports.base import TransportConfig, TransportType, AgentTransport, TransportError
    
    config = TransportConfig(
        transport_type=TransportType.LOCAL,
        url="http://localhost:8000",
        timeout=30.0
    )
    
    print(f"[PASS] TransportConfig created: {config.transport_type}")
    print(f"   Config: url={config.url}, timeout={config.timeout}")
    
    class TestTransport(AgentTransport):
        async def connect(self): self._connected = True
        async def disconnect(self): self._connected = False
        async def send_message(self, to_agent, message, tenant_id=None): return {"status": "ok"}
        async def send_notification(self, to_agent, message, tenant_id=None): pass
        async def subscribe(self, agent, event_types, callback, tenant_id=None): return "sub_1"
        async def unsubscribe(self, subscription_id): pass
        async def stream_events(self, task_id, tenant_id=None):
            yield {"event": "test"}
    
    transport = TestTransport(config)
    print(f"[PASS] AgentTransport subclass created")
    print(f"   Metadata: {transport.get_metadata()}")
    
    return True


async def test_local_transport():
    """测试本地传输（使用 mock message_bus）"""
    print("\n" + "="*60)
    print("[TEST 2] 本地传输测试")
    print("="*60)
    
    from app.a2a_protocol.transports.base import TransportConfig, TransportType
    from app.a2a_protocol.transports.local_transport import LocalAgentTransport
    
    class MockMessageBus:
        def __init__(self):
            self.subscribers = {}
            self.message_queues = {}
            self.lock = asyncio.Lock()
        
        async def send_request(self, from_agent, to_agent, request_content, timeout=30.0, tenant_id=None):
            return None
        
        def subscribe(self, agent_name, callback):
            if agent_name not in self.subscribers:
                self.subscribers[agent_name] = []
            self.subscribers[agent_name].append(callback)
        
        def unsubscribe(self, agent_name, callback=None):
            if agent_name in self.subscribers:
                if callback:
                    if callback in self.subscribers[agent_name]:
                        self.subscribers[agent_name].remove(callback)
                else:
                    del self.subscribers[agent_name]
        
        async def get_messages(self, agent_name, limit=10, clear_queue=True):
            return []
    
    mock_bus = MockMessageBus()
    config = TransportConfig(transport_type=TransportType.LOCAL)
    transport = LocalAgentTransport(config, message_bus=mock_bus)
    
    class DummyAgent:
        async def process_message(self, message):
            return {"status": "processed", "received": message}
    
    transport.register_local_agent("test_agent", DummyAgent())
    await transport.connect()
    
    result = await transport.send_message(
        to_agent="test_agent",
        message={"content": "Hello from test!"},
        tenant_id="test_tenant"
    )
    
    print(f"[PASS] 本地传输测试通过")
    print(f"   Response: {result}")
    print(f"   Stats: {transport.get_statistics()}")
    print(f"   Local agents: {transport.get_local_agents()}")
    
    await transport.disconnect()
    return True


async def test_http_transport():
    """测试 HTTP 传输"""
    print("\n" + "="*60)
    print("[TEST 3] HTTP 传输测试")
    print("="*60)
    
    from app.a2a_protocol.transports.base import TransportConfig, TransportType
    from app.a2a_protocol.transports.http_transport import HttpAgentTransport
    
    config = TransportConfig(
        transport_type=TransportType.HTTP,
        url="https://httpbin.org",
        timeout=10.0
    )
    
    transport = HttpAgentTransport(config)
    await transport.connect()
    
    print(f"[PASS] HTTP 传输连接成功")
    print(f"   Connected: {transport.is_connected}")
    print(f"   Stats: {transport.get_statistics()}")
    
    await transport.disconnect()
    return True


async def test_transport_manager():
    """测试传输管理器"""
    print("\n" + "="*60)
    print("[TEST 4] 传输管理器测试")
    print("="*60)
    
    from app.a2a_protocol.transports.manager import TransportManager
    
    class MockMessageBus:
        def __init__(self):
            self.subscribers = {}
            self.message_queues = {}
            self.lock = asyncio.Lock()
        
        async def send_request(self, from_agent, to_agent, request_content, timeout=30.0, tenant_id=None):
            return None
        
        def subscribe(self, agent_name, callback):
            if agent_name not in self.subscribers:
                self.subscribers[agent_name] = []
            self.subscribers[agent_name].append(callback)
        
        def unsubscribe(self, agent_name, callback=None):
            pass
        
        async def get_messages(self, agent_name, limit=10, clear_queue=True):
            return []
    
    mock_bus = MockMessageBus()
    manager = TransportManager()
    await manager.initialize(message_bus=mock_bus)
    
    class DummyAgent:
        async def process_message(self, message):
            return {"status": "processed", "received": message}
    
    manager.register_local_agent("assistant", DummyAgent())
    manager.register_remote_agent("cloud", "http://localhost:8001")
    
    result = await manager.send_message(
        to_agent="assistant",
        message={"content": "Test"},
        tenant_id="test"
    )
    
    print(f"[PASS] 传输管理器测试通过")
    print(f"   Response: {result}")
    print(f"   Stats: {manager.get_statistics()}")
    print(f"   Agent location: {manager.get_agent_location('assistant')}")
    
    await manager.shutdown()
    return True


async def test_multitenant():
    """测试多租户"""
    print("\n" + "="*60)
    print("[TEST 5] 多租户安全穿透测试")
    print("="*60)
    
    from app.a2a_protocol.transports.manager import TransportManager
    
    class MockMessageBus:
        def __init__(self):
            self.subscribers = {}
            self.message_queues = {}
            self.lock = asyncio.Lock()
        
        async def send_request(self, from_agent, to_agent, request_content, timeout=30.0, tenant_id=None):
            return None
        
        def subscribe(self, agent_name, callback):
            pass
        
        def unsubscribe(self, agent_name, callback=None):
            pass
        
        async def get_messages(self, agent_name, limit=10, clear_queue=True):
            return []
    
    mock_bus = MockMessageBus()
    manager = TransportManager()
    await manager.initialize(message_bus=mock_bus)
    
    class DummyAgent:
        async def process_message(self, message):
            return {"status": "processed", "tenant": message.get("tenant_id")}
    
    manager.register_local_agent("tenant_agent", DummyAgent())
    
    tenants = ["tenant_a", "tenant_b", "tenant_c"]
    results = []
    
    for tenant_id in tenants:
        result = await manager.send_message(
            to_agent="tenant_agent",
            message={"content": f"Hello", "tenant_id": tenant_id},
            tenant_id=tenant_id
        )
        results.append((tenant_id, result))
        print(f"   [PASS] {tenant_id}: {result}")
    
    await manager.shutdown()
    
    return all(r[1].get("tenant") == r[0] for r in results)


async def main():
    """运行所有测试"""
    print("="*60)
    print("A2A Transport Layer 轻量级测试套件")
    print("="*60)
    
    tests = [
        ("传输层基础", test_transport_base),
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
            import traceback
            results.append((name, False, str(e)))
            print(f"[FAIL] {name} 测试失败: {e}")
            traceback.print_exc()
    
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
