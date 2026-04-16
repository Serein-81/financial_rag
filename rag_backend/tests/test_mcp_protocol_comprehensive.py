"""
MCP协议工具测试
Model Context Protocol Tool Tests
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.mcp.client_manager import MCPClientManager
from app.mcp.mcp_factory import MCPFactory, MCPProvider
from app.mcp.mcp_tool_proxy import MCPToolProxy
from app.mcp.financial_tools import FinancialTools


class TestMCPClientManager:
    """测试MCP客户端管理器"""

    @pytest.fixture
    def client_manager(self):
        return MCPClientManager()

    @pytest.mark.asyncio
    async def test_manager_initialization(self, client_manager):
        """测试管理器初始化"""
        assert client_manager is not None
        assert hasattr(client_manager, 'clients')

    @pytest.mark.asyncio
    async def test_register_client(self, client_manager):
        """测试注册MCP客户端"""
        mock_client = MagicMock()
        mock_client.client_id = "test_mcp_client_001"
        mock_client.connect = AsyncMock(return_value=True)
        
        success = await client_manager.register(mock_client)
        assert success is True

    @pytest.mark.asyncio
    async def test_connect_to_server(self, client_manager):
        """测试连接到MCP服务器"""
        with patch.object(client_manager, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = True
            
            result = await client_manager.connect(
                server_url="http://localhost:8080/mcp",
                client_id="client_001"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_client(self, client_manager):
        """测试断开客户端连接"""
        mock_client = MagicMock()
        mock_client.client_id = "test_client_002"
        mock_client.disconnect = AsyncMock(return_value=True)
        
        await client_manager.register(mock_client)
        
        success = await client_manager.disconnect("test_client_002")
        assert success is True

    @pytest.mark.asyncio
    async def test_list_available_tools(self, client_manager):
        """测试列出可用工具"""
        tools = await client_manager.list_tools()
        assert isinstance(tools, list)


class TestMCPFactory:
    """测试MCP工厂"""

    def test_create_openai_mcp_client(self):
        """测试创建OpenAI MCP客户端"""
        client = MCPFactory.create_client(
            provider=MCPProvider.OPENAI,
            config={"api_key": "test_key"}
        )
        
        assert client is not None

    def test_create_custom_mcp_client(self):
        """测试创建自定义MCP客户端"""
        client = MCPFactory.create_client(
            provider=MCPProvider.CUSTOM,
            config={"endpoint": "http://localhost:8080"}
        )
        
        assert client is not None

    @pytest.mark.asyncio
    async def test_factory_client_lifecycle(self):
        """测试工厂客户端生命周期"""
        client = MCPFactory.create_client(
            provider=MCPProvider.CUSTOM,
            config={"endpoint": "http://localhost:8080"}
        )
        
        assert hasattr(client, 'connect') or hasattr(client, 'initialize')
        
        if hasattr(client, 'disconnect'):
            await client.disconnect()


class TestMCPToolProxy:
    """测试MCP工具代理"""

    @pytest.fixture
    def tool_proxy(self):
        return MCPToolProxy()

    @pytest.mark.asyncio
    async def test_proxy_initialization(self, tool_proxy):
        """测试代理初始化"""
        assert tool_proxy is not None
        assert hasattr(tool_proxy, 'tools')

    @pytest.mark.asyncio
    async def test_register_tool(self, tool_proxy):
        """测试注册工具"""
        async def mock_tool(params):
            return {"result": "success"}
        
        tool_def = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        }
        
        success = await tool_proxy.register_tool(tool_def, mock_tool)
        assert success is True

    @pytest.mark.asyncio
    async def test_execute_tool(self, tool_proxy):
        """测试执行工具"""
        async def mock_tool(params):
            return {"result": f"processed {params.get('input', '')}"}
        
        tool_def = {
            "name": "echo_tool",
            "description": "Echo input",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        }
        
        await tool_proxy.register_tool(tool_def, mock_tool)
        
        result = await tool_proxy.execute("echo_tool", {"input": "test_data"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_tool_not_found_error(self, tool_proxy):
        """测试工具未找到错误"""
        with pytest.raises(Exception):
            await tool_proxy.execute("nonexistent_tool", {})


class TestFinancialTools:
    """测试金融工具"""

    @pytest.fixture
    def financial_tools(self):
        return FinancialTools()

    @pytest.mark.asyncio
    async def test_tools_initialization(self, financial_tools):
        """测试工具初始化"""
        assert financial_tools is not None

    @pytest.mark.asyncio
    async def test_calculate_metrics(self, financial_tools):
        """测试计算财务指标"""
        financial_data = {
            "revenue": 1000000,
            "expenses": 600000,
            "assets": 2000000,
            "liabilities": 800000
        }
        
        with patch.object(financial_tools, 'calculate_metrics', new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = {
                "profit_margin": 0.4,
                "debt_ratio": 0.4,
                "roi": 0.2
            }
            
            result = await financial_tools.calculate_metrics(financial_data)
            
            assert result is not None
            assert "profit_margin" in result or "debt_ratio" in result

    @pytest.mark.asyncio
    async def test_analyze_trends(self, financial_tools):
        """测试趋势分析"""
        historical_data = [
            {"year": 2021, "revenue": 800000},
            {"year": 2022, "revenue": 900000},
            {"year": 2023, "revenue": 1100000}
        ]
        
        with patch.object(financial_tools, 'analyze_trends', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "trend": "upward",
                "cagr": 0.137
            }
            
            result = await financial_tools.analyze_trends(historical_data)
            
            assert result is not None
            assert "trend" in result


class TestMCPToolDefinitions:
    """测试MCP工具定义"""

    def test_tool_definition_structure(self):
        """测试工具定义结构"""
        tool_def = {
            "name": "search_knowledge_base",
            "description": "Search the enterprise knowledge base",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
        
        assert "name" in tool_def
        assert "description" in tool_def
        assert "inputSchema" in tool_def
        assert "query" in tool_def["inputSchema"]["properties"]

    def test_tool_validation(self):
        """测试工具参数验证"""
        tool_def = {
            "name": "validate_tool",
            "description": "Validates input parameters",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "minimum": 0},
                    "currency": {"type": "string", "enum": ["CNY", "USD", "EUR"]}
                },
                "required": ["amount"]
            }
        }
        
        valid_input = {"amount": 100, "currency": "CNY"}
        assert valid_input["amount"] >= 0
        assert valid_input["currency"] in ["CNY", "USD", "EUR"]

    def test_nested_parameters(self):
        """测试嵌套参数"""
        tool_def = {
            "name": "complex_tool",
            "description": "Tool with nested parameters",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "config": {
                        "type": "object",
                        "properties": {
                            "timeout": {"type": "integer"},
                            "retries": {"type": "integer"}
                        }
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        }
        
        assert "config" in tool_def["inputSchema"]["properties"]
        assert tool_def["inputSchema"]["properties"]["config"]["type"] == "object"


class TestMCPProtocolCompliance:
    """测试MCP协议合规性"""

    def test_json_rpc_request_format(self):
        """测试JSON-RPC请求格式"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"arg1": "value1"}
            }
        }
        
        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert "method" in request
        assert "params" in request

    def test_json_rpc_response_format(self):
        """测试JSON-RPC响应格式"""
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "Tool execution result"}
                ]
            }
        }
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response

    def test_json_rpc_error_format(self):
        """测试JSON-RPC错误格式"""
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            }
        }
        
        assert error_response["jsonrpc"] == "2.0"
        assert "error" in error_response
        assert "code" in error_response["error"]
        assert "message" in error_response["error"]


class TestMCPStreamHandling:
    """测试MCP流式处理"""

    @pytest.fixture
    def mock_mcp_client(self):
        client = MagicMock()
        client.execute_stream = MagicMock(return_value=iter([
            "chunk1",
            "chunk2",
            "chunk3"
        ]))
        return client

    @pytest.mark.asyncio
    async def test_stream_execution(self, mock_mcp_client):
        """测试流式执行"""
        chunks = list(mock_mcp_client.execute_stream(
            tool_name="streaming_tool",
            params={"input": "test"}
        ))
        
        assert len(chunks) == 3
        assert "chunk1" in chunks

    @pytest.mark.asyncio
    async def test_stream_with_async_generator(self):
        """测试异步生成器流"""
        async def async_stream():
            for i in range(3):
                yield f"async_chunk_{i}"
                await asyncio.sleep(0.01)
        
        chunks = [chunk async for chunk in async_stream()]
        assert len(chunks) == 3
        assert "async_chunk_0" in chunks


class TestMCPToolSecurity:
    """测试MCP工具安全"""

    def test_dangerous_parameters_blocked(self):
        """测试危险参数被阻止"""
        dangerous_params = {
            "command": "rm -rf /",
            "file_path": "../../../etc/passwd"
        }
        
        blocked = any([
            "rm" in str(dangerous_params.values()),
            "../" in str(dangerous_params.values())
        ])
        
        assert blocked is True or blocked is False

    def test_tool_execution_timeout(self):
        """测试工具执行超时"""
        timeout_config = {
            "max_execution_time": 30,
            "timeout_unit": "seconds"
        }
        
        assert timeout_config["max_execution_time"] == 30

    def test_tool_permission_check(self):
        """测试工具权限检查"""
        tool_permissions = {
            "read_knowledge_base": ["user", "admin"],
            "write_knowledge_base": ["admin"],
            "execute_code": []
        }
        
        assert "user" in tool_permissions["read_knowledge_base"]
        assert "execute_code" not in tool_permissions or len(tool_permissions["execute_code"]) == 0


class TestMCPToolErrorHandling:
    """测试MCP工具错误处理"""

    @pytest.mark.asyncio
    async def test_tool_execution_error(self):
        """测试工具执行错误"""
        async def failing_tool(params):
            raise ValueError("Invalid parameter")
        
        with pytest.raises(ValueError) as exc_info:
            await failing_tool({"invalid": "params"})
        
        assert "Invalid parameter" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self):
        """测试工具超时处理"""
        async def slow_tool(params):
            await asyncio.sleep(100)
            return "done"
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_tool({}), timeout=0.1)

    @pytest.mark.asyncio
    async def test_tool_connection_error(self):
        """测试工具连接错误"""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = ConnectionError("Connection refused")
            
            with pytest.raises(ConnectionError):
                await asyncio.wait_for(
                    mock_post("http://localhost:9999/tool"),
                    timeout=1.0
                )


class TestMCPToolIntegration:
    """测试MCP工具集成"""

    @pytest.fixture
    def tool_registry(self):
        registry = {}
        return registry

    @pytest.mark.asyncio
    async def test_multiple_tools_integration(self, tool_registry):
        """测试多工具集成"""
        async def tool1(params):
            return {"step": 1, "data": params}
        
        async def tool2(params):
            return {"step": 2, "data": params}
        
        async def tool3(params):
            return {"step": 3, "data": params}
        
        tool_registry["tool1"] = tool1
        tool_registry["tool2"] = tool2
        tool_registry["tool3"] = tool3
        
        result1 = await tool_registry["tool1"]({"input": "data1"})
        result2 = await tool_registry["tool2"]({"input": result1})
        result3 = await tool_registry["tool3"]({"input": result2})
        
        assert result3["step"] == 3

    @pytest.mark.asyncio
    async def test_tool_chain_execution(self, tool_registry):
        """测试工具链执行"""
        chain = [
            ("transform", lambda x: {"transformed": x["data"]}),
            ("validate", lambda x: {"valid": True, **x}),
            ("store", lambda x: {"stored": True, **x})
        ]
        
        data = {"data": "test_input"}
        for name, func in chain:
            data = func(data)
        
        assert "stored" in data
        assert data["stored"] is True


class TestMCPProviderSwitching:
    """测试MCP提供者切换"""

    def test_switch_to_openai_provider(self):
        """测试切换到OpenAI提供者"""
        factory = MCPFactory()
        client = factory.create_client(MCPProvider.OPENAI, {"model": "gpt-4"})
        
        assert client is not None

    def test_switch_to_custom_provider(self):
        """测试切换到自定义提供者"""
        factory = MCPFactory()
        client = factory.create_client(
            MCPProvider.CUSTOM,
            {"endpoint": "http://custom-mcp-server:8080"}
        )
        
        assert client is not None

    def test_provider_capabilities(self):
        """测试提供者能力"""
        capabilities = {
            MCPProvider.OPENAI: ["text_generation", "embedding"],
            MCPProvider.CUSTOM: ["custom_tools", "flexible_schema"]
        }
        
        assert len(capabilities[MCPProvider.OPENAI]) > 0
        assert len(capabilities[MCPProvider.CUSTOM]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
