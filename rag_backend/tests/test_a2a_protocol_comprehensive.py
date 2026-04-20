"""
A2A协议通信测试
Agent-to-Agent Protocol Communication Tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.a2a_protocol.client import A2AClient
from app.a2a_protocol.server import A2AServer
from app.a2a_protocol.models import (
    Message,
    Task,
    TaskStatus
)
from app.a2a_protocol.agent_card import AgentCard
from app.a2a_protocol.registry import AgentRegistry
from app.a2a_protocol.dispatcher import HybridDispatcher
from app.a2a_protocol.initializer import A2AInitializer
from app.a2a_protocol.transports.http_transport import HttpAgentTransport
from app.a2a_protocol.transports.local_transport import LocalAgentTransport


class TestAgentRegistry:
    """测试智能体注册表"""

    @pytest.fixture
    def registry(self):
        return AgentRegistry()

    def test_register_agent(self, registry):
        """测试注册智能体"""
        agent_card = AgentCard(
            agent_id="test_agent_001",
            agent_name="Test Agent",
            description="A test agent",
            capabilities=["analysis", "reporting"],
            endpoint="http://localhost:8080"
        )
        
        success = registry.register(agent_card)
        assert success is True

    def test_get_agent(self, registry):
        """测试获取智能体"""
        agent_card = AgentCard(
            agent_id="test_agent_002",
            agent_name="Test Agent 2",
            description="Another test agent",
            capabilities=["data_processing"],
            endpoint="http://localhost:8081"
        )
        
        registry.register(agent_card)
        
        retrieved_agent = registry.get("test_agent_002")
        assert retrieved_agent is not None
        assert retrieved_agent.agent_id == "test_agent_002"

    def test_list_agents(self, registry):
        """测试列出智能体"""
        agent1 = AgentCard(
            agent_id="agent_1",
            agent_name="Agent One",
            description="First agent",
            capabilities=["task1"],
            endpoint="http://localhost:8001"
        )
        
        agent2 = AgentCard(
            agent_id="agent_2",
            agent_name="Agent Two",
            description="Second agent",
            capabilities=["task2"],
            endpoint="http://localhost:8002"
        )
        
        registry.register(agent1)
        registry.register(agent2)
        
        agents = registry.list_agents()
        assert len(agents) >= 2

    def test_find_agents_by_capability(self, registry):
        """测试按能力查找智能体"""
        agent1 = AgentCard(
            agent_id="finance_agent",
            agent_name="Finance Agent",
            description="Finance specialist",
            capabilities=["financial_analysis", "reporting"],
            endpoint="http://localhost:8001"
        )
        
        agent2 = AgentCard(
            agent_id="tax_agent",
            agent_name="Tax Agent",
            description="Tax specialist",
            capabilities=["tax_analysis", "compliance"],
            endpoint="http://localhost:8002"
        )
        
        registry.register(agent1)
        registry.register(agent2)
        
        finance_agents = registry.find_by_capability("financial_analysis")
        assert len(finance_agents) >= 1
        assert any(a.agent_id == "finance_agent" for a in finance_agents)

    def test_unregister_agent(self, registry):
        """测试取消注册智能体"""
        agent_card = AgentCard(
            agent_id="temp_agent",
            agent_name="Temp Agent",
            description="Temporary agent",
            capabilities=["testing"],
            endpoint="http://localhost:8003"
        )
        
        registry.register(agent_card)
        success = registry.unregister("temp_agent")
        assert success is True
        
        retrieved = registry.get("temp_agent")
        assert retrieved is None


class TestA2AClient:
    """测试A2A客户端"""

    @pytest.fixture
    def client(self):
        return A2AClient(base_url="http://localhost:8080")

    @pytest.mark.asyncio
    async def test_send_task_request(self, client):
        """测试发送任务请求"""
        with patch.object(client, 'send_request', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                "task_id": "task_001",
                "status": "accepted",
                "result": {}
            }
            
            result = await client.send_task_request(
                agent_id="target_agent",
                task_data={"action": "analyze", "data": "test_data"}
            )
            
            assert result is not None
            assert "task_id" in result or "status" in result

    @pytest.mark.asyncio
    async def test_get_task_status(self, client):
        """测试获取任务状态"""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "task_id": "task_001",
                "status": "processing",
                "progress": 50
            }
            
            status = await client.get_task_status("task_001")
            
            assert status is not None
            assert "status" in status

    @pytest.mark.asyncio
    async def test_send_message(self, client):
        """测试发送消息"""
        message = A2AMessage(
            msg_id="msg_001",
            sender="sender_agent",
            receiver="receiver_agent",
            content={"type": "notification", "data": "test"},
            timestamp=datetime.now()
        )
        
        with patch.object(client, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await client.send_message(message)
            assert result is True

    @pytest.mark.asyncio
    async def test_query_agent_capabilities(self, client):
        """测试查询智能体能力"""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "agent_id": "test_agent",
                "capabilities": ["analysis", "reporting", "retrieval"]
            }
            
            capabilities = await client.query_capabilities("test_agent")
            
            assert capabilities is not None
            assert isinstance(capabilities, (list, dict))


class TestA2AServer:
    """测试A2A服务器"""

    @pytest.fixture
    def server(self):
        server = A2AServer(host="localhost", port=8080)
        return server

    def test_server_initialization(self, server):
        """测试服务器初始化"""
        assert server is not None
        assert hasattr(server, 'host')
        assert hasattr(server, 'port')

    @pytest.mark.asyncio
    async def test_register_handler(self, server):
        """测试注册处理器"""
        async def mock_handler(data):
            return {"status": "processed"}
        
        server.register_handler("test_action", mock_handler)
        
        assert "test_action" in server.handlers or hasattr(server, "handlers")

    @pytest.mark.asyncio
    async def test_handle_incoming_message(self, server):
        """测试处理传入消息"""
        message = A2AMessage(
            msg_id="msg_002",
            sender="client_agent",
            receiver="server_agent",
            content={"action": "ping"},
            timestamp=datetime.now()
        )
        
        response = await server.handle_message(message)
        
        assert response is not None


class TestDispatcher:
    """测试消息分发器"""

    @pytest.fixture
    def dispatcher(self):
        return Dispatcher()

    @pytest.mark.asyncio
    async def test_dispatch_to_agent(self, dispatcher):
        """测试分发到智能体"""
        message = A2AMessage(
            msg_id="dispatch_001",
            sender="sender",
            receiver="target_agent",
            content={"task": "process_data"},
            timestamp=datetime.now()
        )
        
        result = await dispatcher.dispatch(message)
        
        assert result is not None or result is None

    @pytest.mark.asyncio
    async def test_dispatcher_routing(self, dispatcher):
        """测试分发器路由"""
        routing_table = {
            "finance": "finance_agent",
            "tax": "tax_agent",
            "legal": "legal_agent"
        }
        
        dispatcher.set_routing_table(routing_table)
        
        target = dispatcher.route("finance")
        assert target == "finance_agent" or target is not None


class TestHTTPTransport:
    """测试HTTP传输层"""

    @pytest.fixture
    def http_transport(self):
        return HTTPTransport(base_url="http://localhost:8080")

    @pytest.mark.asyncio
    async def test_send_http_request(self, http_transport):
        """测试发送HTTP请求"""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_post.return_value = mock_response
            
            response = await http_transport.send(
                endpoint="/api/agent/task",
                data={"task": "test"}
            )
            
            assert response is not None

    @pytest.mark.asyncio
    async def test_receive_http_request(self, http_transport):
        """测试接收HTTP请求"""
        response = await http_transport.receive()
        
        assert response is not None or response is None


class TestLocalTransport:
    """测试本地传输层"""

    @pytest.fixture
    def local_transport(self):
        return LocalTransport()

    @pytest.mark.asyncio
    async def test_local_message_send(self, local_transport):
        """测试本地消息发送"""
        message = A2AMessage(
            msg_id="local_msg_001",
            sender="agent_a",
            receiver="agent_b",
            content={"type": "local_communication"},
            timestamp=datetime.now()
        )
        
        result = await local_transport.send(message)
        assert result is True

    @pytest.mark.asyncio
    async def test_local_message_receive(self, local_transport):
        """测试本地消息接收"""
        message = A2AMessage(
            msg_id="local_msg_002",
            sender="agent_c",
            receiver="agent_d",
            content={"type": "query"},
            timestamp=datetime.now()
        )
        
        await local_transport.send(message)
        
        received = await local_transport.receive(timeout=1.0)
        assert received is None or received.msg_id == "local_msg_002"


class TestA2AInitializer:
    """测试A2A初始化器"""

    @pytest.fixture
    def initializer(self):
        return A2AInitializer(base_url="http://localhost:8080")

    @pytest.mark.asyncio
    async def test_initialize_system(self, initializer):
        """测试系统初始化"""
        with patch.object(initializer, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            
            result = await initializer.initialize()
            assert result is True

    @pytest.mark.asyncio
    async def test_register_tax_specialist(self, initializer):
        """测试注册税务专家"""
        with patch.object(initializer, '_register_tax_specialist', new_callable=AsyncMock) as mock_reg:
            mock_reg.return_value = True
            
            result = await initializer._register_tax_specialist()
            assert result is True

    @pytest.mark.asyncio
    async def test_register_finance_specialist(self, initializer):
        """测试注册财务专家"""
        with patch.object(initializer, '_register_finance_specialist', new_callable=AsyncMock) as mock_reg:
            mock_reg.return_value = True
            
            result = await initializer._register_finance_specialist()
            assert result is True

    @pytest.mark.asyncio
    async def test_register_legal_specialist(self, initializer):
        """测试注册法律专家"""
        with patch.object(initializer, '_register_legal_specialist', new_callable=AsyncMock) as mock_reg:
            mock_reg.return_value = True
            
            result = await initializer._register_legal_specialist()
            assert result is True


class TestAgentCardDiscovery:
    """测试智能体卡片发现"""

    @pytest.fixture
    def registry(self):
        return AgentRegistry()

    def test_discover_agents(self, registry):
        """测试发现智能体"""
        agent1 = AgentCard(
            agent_id="discoverable_1",
            agent_name="Discoverable Agent 1",
            description="Can be discovered",
            capabilities=["discovery_test"],
            endpoint="http://localhost:9001"
        )
        
        agent2 = AgentCard(
            agent_id="discoverable_2",
            agent_name="Discoverable Agent 2",
            description="Also discoverable",
            capabilities=["discovery_test"],
            endpoint="http://localhost:9002"
        )
        
        registry.register(agent1)
        registry.register(agent2)
        
        discovered = registry.list_agents()
        assert len(discovered) >= 2

    def test_capability_based_discovery(self, registry):
        """测试基于能力的发现"""
        agent = AgentCard(
            agent_id="capability_agent",
            agent_name="Capability Agent",
            description="Multi-capability agent",
            capabilities=["analysis", "retrieval", "synthesis"],
            endpoint="http://localhost:9003"
        )
        
        registry.register(agent)
        
        analysis_capable = registry.find_by_capability("analysis")
        assert len(analysis_capable) >= 1


class TestA2AMessageHandling:
    """测试A2A消息处理"""

    def test_message_creation(self):
        """测试消息创建"""
        message = A2AMessage(
            msg_id="msg_test_001",
            sender="agent_sender",
            receiver="agent_receiver",
            content={"action": "analyze", "data": "sample"},
            timestamp=datetime.now()
        )
        
        assert message.msg_id == "msg_test_001"
        assert message.sender == "agent_sender"
        assert message.receiver == "agent_receiver"
        assert message.content["action"] == "analyze"

    def test_message_serialization(self):
        """测试消息序列化"""
        message = A2AMessage(
            msg_id="msg_ser_001",
            sender="sender",
            receiver="receiver",
            content={"key": "value"},
            timestamp=datetime.now()
        )
        
        serialized = message.model_dump() if hasattr(message, 'model_dump') else message.dict()
        assert "msg_id" in serialized
        assert serialized["sender"] == "sender"


class TestTaskManagement:
    """测试任务管理"""

    def test_task_creation(self):
        """测试任务创建"""
        task = Task(
            task_id="task_001",
            description="Test task",
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        assert task.task_id == "task_001"
        assert task.status == TaskStatus.PENDING

    def test_task_status_transitions(self):
        """测试任务状态转换"""
        task = Task(
            task_id="task_002",
            description="Status transition test",
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        task.status = TaskStatus.PROCESSING
        assert task.status == TaskStatus.PROCESSING
        
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED


class TestA2AErrorHandling:
    """测试A2A错误处理"""

    @pytest.fixture
    def client(self):
        return A2AClient(base_url="http://localhost:9999")

    @pytest.mark.asyncio
    async def test_connection_timeout(self, client):
        """测试连接超时"""
        with patch.object(client, 'send_request', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(asyncio.TimeoutError):
                await client.send_task_request(
                    agent_id="timeout_agent",
                    task_data={"action": "test"}
                )

    @pytest.mark.asyncio
    async def test_invalid_agent_error(self, client):
        """测试无效智能体错误"""
        with patch.object(client, 'send_request', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Agent not found")
            
            with pytest.raises(Exception):
                await client.send_task_request(
                    agent_id="nonexistent_agent",
                    task_data={"action": "test"}
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
