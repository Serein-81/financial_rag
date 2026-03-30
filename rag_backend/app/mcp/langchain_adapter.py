import asyncio
import logging
from typing import Any, Dict, List, Optional, get_type_hints, get_origin, get_args

from langchain_core.tools import BaseTool, tool
from langchain_core.callbacks import CallbackManagerForToolRun

from pydantic import BaseModel, Field, create_model

from app.mcp.client_manager import MCPClientManager, MCPToolInfo, TIMEOUT_MAP

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    def __init__(self, mcp_client: MCPClientManager):
        self.mcp_client = mcp_client
        self._tool_cache: Dict[str, BaseTool] = {}
        self._nested_models: List[type[BaseModel]] = []

    def _infer_pydantic_type(self, schema: Dict[str, Any]) -> Any:
        json_type = schema.get("type")

        TYPE_MAP = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }

        if json_type in TYPE_MAP:
            return TYPE_MAP[json_type]

        if json_type == "array":
            items_schema = schema.get("items", {})
            item_type = self._infer_pydantic_type(items_schema)
            return List[item_type]

        if json_type == "object" or "properties" in schema:
            properties = schema.get("properties", {})
            required_fields = schema.get("required", [])

            field_definitions = {}
            for field_name, field_schema in properties.items():
                field_type = self._infer_pydantic_type(field_schema)

                if field_name not in required_fields:
                    field_type = Optional[field_type]
                    field_definitions[field_name] = (field_type, Field(default=None))
                else:
                    field_definitions[field_name] = (field_type, ...)

            model_name = f"DynamicObject_{len(self._nested_models)}"
            nested_model = create_model(model_name, **field_definitions)
            self._nested_models.append(nested_model)
            return nested_model

        return str

    def _generate_args_schema(self, tool_info: MCPToolInfo) -> type[BaseModel]:
        self._nested_models = []

        properties = tool_info.input_schema.get("properties", {})
        required_fields = tool_info.input_schema.get("required", [])

        field_definitions = {}

        for param_name, param_schema in properties.items():
            description = param_schema.get("description", "")
            param_type = self._infer_pydantic_type(param_schema)

            if param_name in required_fields:
                field_definitions[param_name] = (param_type, Field(description=description))
            else:
                field_definitions[param_name] = (
                    Optional[param_type],
                    Field(default=None, description=description)
                )

        schema_name = f"{tool_info.name.title().replace('_', '')}Args"

        return create_model(schema_name, **field_definitions)

    def create_async_tool(self, tool_info: MCPToolInfo) -> BaseTool:
        tool_name = tool_info.name
        tool_description = tool_info.description

        timeout = TIMEOUT_MAP.get(tool_info.timeout_type, 60)

        args_schema = self._generate_args_schema(tool_info)

        @tool(tool_name, description=tool_description, args_schema=args_schema)
        async def wrapped_tool(
            run_manager: Optional[CallbackManagerForToolRun] = None,
            **kwargs: Any
        ) -> str:
            try:
                result = await self.mcp_client.call_tool(tool_name, arguments=kwargs)
                return str(result)

            except asyncio.TimeoutError:
                return f"工具 {tool_name} 执行超时 ({timeout}s)"
            except Exception as e:
                logger.error(f"工具 {tool_name} 执行失败: {e}")
                return f"工具 {tool_name} 执行失败: {str(e)}"

        return wrapped_tool

    async def get_all_tools(self) -> List[BaseTool]:
        if not self._tool_cache:
            tools = self.mcp_client.tools
            for tool_info in tools:
                langchain_tool = self.create_async_tool(tool_info)
                self._tool_cache[tool_info.name] = langchain_tool

        return list(self._tool_cache.values())

    async def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        if tool_name in self._tool_cache:
            return self._tool_cache[tool_name]

        for tool_info in self.mcp_client.tools:
            if tool_info.name == tool_name:
                langchain_tool = self.create_async_tool(tool_info)
                self._tool_cache[tool_name] = langchain_tool
                return langchain_tool

        return None


class LangGraphMCPIntegration:
    def __init__(self, mcp_client: MCPClientManager):
        self.mcp_client = mcp_client
        self.adapter = MCPToolAdapter(mcp_client)

    async def get_tools_for_agent(self) -> List[BaseTool]:
        return await self.adapter.get_all_tools()

    async def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        return await self.adapter.get_tool(tool_name)

    async def refresh_tools(self) -> None:
        self.adapter._tool_cache.clear()
        await self.get_tools_for_agent()
