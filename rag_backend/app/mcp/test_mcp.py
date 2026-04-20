import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel
from typing import List

from app.mcp.client_manager import (
    MCPClientManager,
    MCPToolInfo,
    MCPTimeoutError,
    TIMEOUT_MAP,
)
from app.mcp.langchain_adapter import MCPToolAdapter


@pytest.fixture
def sample_tool_info():
    return MCPToolInfo(
        name="calculate_tax",
        description="计算个人所得税",
        input_schema={
            "type": "object",
            "properties": {
                "income": {
                    "type": "number",
                    "description": "年收入(万元)"
                },
                "region": {
                    "type": "string",
                    "description": "地区"
                },
                "is_married": {
                    "type": "boolean",
                    "description": "是否已婚"
                }
            },
            "required": ["income"]
        },
        timeout_type="quick"
    )


@pytest.fixture
def complex_tool_info():
    return MCPToolInfo(
        name="generate_financial_report",
        description="生成财务报表",
        input_schema={
            "type": "object",
            "properties": {
                "financial_records": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "year": {"type": "integer", "description": "年份"},
                            "revenue": {"type": "number", "description": "收入(万元)"},
                            "expenses": {
                                "type": "object",
                                "properties": {
                                    "operational": {"type": "number"},
                                    "marketing": {"type": "number"}
                                }
                            }
                        },
                        "required": ["year", "revenue"]
                    }
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["growth", "ratio", "forecast"]
                },
                "include_charts": {"type": "boolean", "description": "包含图表"}
            },
            "required": ["financial_records", "analysis_type"]
        },
        timeout_type="slow"
    )


class TestTimeoutMap:
    def test_timeout_map_values(self):
        assert TIMEOUT_MAP["quick"] == 10
        assert TIMEOUT_MAP["normal"] == 30
        assert TIMEOUT_MAP["slow"] == 60
        assert TIMEOUT_MAP["complex"] == 120

    def test_client_default_timeout(self):
        client = MCPClientManager(
            server_url="http://test.com/sse",
            api_key="test_key",
            timeout=60
        )
        assert client.default_timeout == 60
        assert client.dynamic_timeout is True

    def test_get_timeout_by_name(self):
        client = MCPClientManager(
            server_url="http://test.com/sse",
            api_key="test_key",
            dynamic_timeout=True
        )

        assert client._get_timeout("calculate_tax") == 10
        assert client._get_timeout("search_enterprise") == 30
        assert client._get_timeout("generate_report") == 60
        assert client._get_timeout("unknown_tool") == 120


class TestMCPToolInfo:
    def test_tool_info_creation(self, sample_tool_info):
        assert sample_tool_info.name == "calculate_tax"
        assert sample_tool_info.timeout_type == "quick"

    def test_tool_info_default_timeout(self):
        tool = MCPToolInfo(
            name="test",
            description="test",
            input_schema={}
        )
        assert tool.timeout_type == "normal"


class TestMCPToolAdapter:
    def test_infer_basic_types(self, sample_tool_info):
        client = MCPClientManager("http://test.com", "key")
        adapter = MCPToolAdapter(client)

        assert adapter._infer_pydantic_type({"type": "string"}) is str
        assert adapter._infer_pydantic_type({"type": "number"}) is float
        assert adapter._infer_pydantic_type({"type": "integer"}) is int
        assert adapter._infer_pydantic_type({"type": "boolean"}) is bool

    def test_infer_array_type(self, sample_tool_info):
        client = MCPClientManager("http://test.com", "key")
        adapter = MCPToolAdapter(client)

        array_schema = {
            "type": "array",
            "items": {"type": "string"}
        }
        result = adapter._infer_pydantic_type(array_schema)
        assert result == List[str]

    def test_infer_nested_object(self, complex_tool_info):
        client = MCPClientManager("http://test.com", "key")
        adapter = MCPToolAdapter(client)

        nested_schema = {
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "revenue": {"type": "number"}
            },
            "required": ["year", "revenue"]
        }
        result = adapter._infer_pydantic_type(nested_schema)
        assert issubclass(result, BaseModel)

    def test_generate_args_schema_simple(self, sample_tool_info):
        client = MCPClientManager("http://test.com", "key")
        adapter = MCPToolAdapter(client)

        schema = adapter._generate_args_schema(sample_tool_info)

        assert issubclass(schema, BaseModel)
        assert "income" in schema.model_fields
        assert "region" in schema.model_fields
        assert "is_married" in schema.model_fields

        assert schema.model_fields["income"].is_required()
        assert not schema.model_fields["region"].is_required()

    def test_generate_args_schema_complex(self, complex_tool_info):
        client = MCPClientManager("http://test.com", "key")
        adapter = MCPToolAdapter(client)

        schema = adapter._generate_args_schema(complex_tool_info)

        assert issubclass(schema, BaseModel)
        assert "financial_records" in schema.model_fields
        assert "analysis_type" in schema.model_fields
        assert "include_charts" in schema.model_fields

    @pytest.mark.asyncio
    async def test_create_async_tool(self, sample_tool_info):
        mock_client = AsyncMock(spec=MCPClientManager)
        mock_client.tools = [sample_tool_info]
        mock_client.call_tool = AsyncMock(return_value="test result")

        adapter = MCPToolAdapter(mock_client)
        langchain_tool = adapter.create_async_tool(sample_tool_info)

        assert langchain_tool.name == "calculate_tax"
        assert langchain_tool.description == "计算个人所得税"


class TestMCPClientManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        client = MCPClientManager("http://test.com", "key")

        with patch.object(client, "connect", new_callable=AsyncMock):
            with patch.object(client, "disconnect", new_callable=AsyncMock):
                async with client as c:
                    assert c is client

                client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_auto_reconnect(self):
        client = MCPClientManager("http://test.com", "key")
        client._is_initialized = True
        client._session = AsyncMock()

        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="success")]
        client._session.call_tool = AsyncMock(return_value=mock_result)

        result = await client.call_tool("test_tool", {"arg": "value"})

        assert result == "success"
        client._session.call_tool.assert_called_once_with("test_tool", {"arg": "value"})

    @pytest.mark.asyncio
    async def test_call_tool_timeout(self):
        client = MCPClientManager("http://test.com", "key", timeout=1)
        client._is_initialized = True
        client._session = AsyncMock()

        client._session.call_tool = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with pytest.raises(MCPTimeoutError) as exc_info:
            await client.call_tool("test_tool", {})

        assert "超时" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool_connection_error_with_reconnect(self):
        client = MCPClientManager("http://test.com", "key")
        client._is_initialized = True
        client._session = AsyncMock()

        call_count = 0

        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionResetError("Connection reset")
            return MagicMock(content=[MagicMock(text="success after reconnect")])

        client._session.call_tool = mock_call

        with patch.object(client, "connect", new_callable=AsyncMock):
            with patch.object(client, "disconnect", new_callable=AsyncMock):
                result = await client.call_tool("test_tool", {}, auto_reconnect=True, max_retries=2)

                assert result == "success after reconnect"
                assert call_count == 2

    def test_convert_tools(self):
        client = MCPClientManager("http://test.com", "key")

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            }
        }

        tools = client._convert_tools([mock_tool])

        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        assert tools[0].timeout_type == "normal"

    def test_tools_property(self):
        client = MCPClientManager("http://test.com", "key")
        client._tools = [MCPToolInfo("t1", "d1", {}), MCPToolInfo("t2", "d2", {})]

        assert len(client.tools) == 2
        assert client.tools[0].name == "t1"

    def test_is_connected_property(self):
        client = MCPClientManager("http://test.com", "key")

        assert client.is_connected is False

        client._is_initialized = True
        client._session = MagicMock()

        assert client.is_connected is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
