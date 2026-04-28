from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_framework.tools.tool_manager import ACTIVE_TOOL_MANAGERS, ToolManager
from app.mcp.decorators import local_tool
from app.models.custom_tool import CustomTool, CustomToolKind, CustomToolStatus
from app.models.user import User
from app.schemas.custom_tool import CustomToolSpec, GenerateToolRequest
from app.services.agent_registry import ToolInfo, ToolLocation, agent_discovery_registry
from app.services.custom_tool_runtime import custom_tool_runtime


class CustomToolServiceError(ValueError):
    pass


class CustomToolService:
    SAFE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

    def __init__(self) -> None:
        self._published_callables: Dict[str, Any] = {}

    async def generate_spec(self, request: GenerateToolRequest) -> CustomToolSpec:
        preferred_kind = request.preferred_kind or "echo"
        if preferred_kind not in {kind.value for kind in CustomToolKind}:
            preferred_kind = "echo"

        prompt = self._build_generation_prompt(request, preferred_kind)
        try:
            from app.services.llm_service import llm_service

            content = await llm_service.get_answer(prompt, [], [], add_truncation_notification=False)
            parsed = self._extract_json(content)
            return CustomToolSpec(**parsed)
        except Exception:
            return self._fallback_spec(request, preferred_kind)

    async def generate_code_draft(self, spec: CustomToolSpec, instruction: Optional[str] = None) -> CustomToolSpec:
        prompt = self._build_code_generation_prompt(spec, instruction)
        try:
            from app.services.llm_service import llm_service

            content = await llm_service.get_answer(prompt, [], [], add_truncation_notification=False)
            code = self._extract_code(content)
        except Exception:
            code = self._fallback_code(spec)

        data = spec.model_dump()
        data["kind"] = CustomToolKind.PYTHON_CODE.value
        data["generated_code"] = code
        data["safety_policy"] = {
            **(data.get("safety_policy") or {}),
            "code_execution": False,
            "requires_sandbox_review": True,
        }
        return CustomToolSpec(**data)

    async def create_tool(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        spec: CustomToolSpec,
    ) -> CustomTool:
        self._validate_spec(spec)
        status = CustomToolStatus.REVIEWING.value if spec.kind == CustomToolKind.PYTHON_CODE.value else CustomToolStatus.DRAFT.value
        tool = CustomTool(
            tenant_id=tenant_id,
            created_by=user_id,
            name=spec.name,
            display_name=spec.display_name,
            description=spec.description,
            purpose=spec.purpose,
            kind=spec.kind,
            status=status,
            version=spec.version,
            input_schema={key: value.model_dump() for key, value in spec.input_schema.items()},
            output_schema={key: value.model_dump() for key, value in spec.output_schema.items()},
            runtime_config=spec.runtime_config,
            safety_policy=self._default_safety_policy(spec),
            generated_code=spec.generated_code,
            agent_id=spec.agent_id,
            enabled=False,
        )
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        return tool

    async def list_tools(self, db: AsyncSession, tenant_id: str, include_unpublished: bool = False) -> List[CustomTool]:
        query = select(CustomTool).where(CustomTool.tenant_id == tenant_id)
        if not include_unpublished:
            query = query.where(
                CustomTool.status == CustomToolStatus.PUBLISHED.value,
                CustomTool.enabled.is_(True),
            )
        result = await db.execute(query.order_by(CustomTool.created_at.desc()))
        return list(result.scalars().all())

    async def load_published_tools(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(CustomTool).where(
                CustomTool.status == CustomToolStatus.PUBLISHED.value,
                CustomTool.enabled.is_(True),
                CustomTool.kind != CustomToolKind.PYTHON_CODE.value,
            )
        )
        tools = list(result.scalars().all())
        for tool in tools:
            publisher_name = await self._get_user_display_name(db, tool.approved_by or tool.created_by)
            creator_name = await self._get_user_display_name(db, tool.created_by)
            self.register_tool_sugar(tool)
            self.register_agent_discovery(tool, publisher_name=publisher_name, creator_name=creator_name)
        return len(tools)

    async def get_tool(self, db: AsyncSession, tenant_id: str, tool_id: str) -> CustomTool:
        result = await db.execute(
            select(CustomTool).where(CustomTool.tenant_id == tenant_id, CustomTool.id == tool_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise CustomToolServiceError("Custom tool not found")
        return tool

    async def execute_tool(
        self,
        db: AsyncSession,
        tenant_id: str,
        tool_id: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool = await self.get_tool(db, tenant_id, tool_id)
        if not (tool.enabled and tool.status == CustomToolStatus.PUBLISHED.value):
            raise CustomToolServiceError("Custom tool is not published")
        result = await custom_tool_runtime.execute(tool, arguments)
        output_schema = tool.output_schema or {}
        result.setdefault("arguments", arguments)
        result.setdefault("output_schema", output_schema)
        result.setdefault("output", self._format_output(output_schema, result))
        return result

    async def publish_tool(
        self,
        db: AsyncSession,
        tenant_id: str,
        tool_id: str,
        agent_id: Optional[str] = None,
        published_by: Optional[str] = None,
        published_by_name: Optional[str] = None,
    ) -> CustomTool:
        tool = await self.get_tool(db, tenant_id, tool_id)
        if tool.kind == CustomToolKind.PYTHON_CODE.value:
            raise CustomToolServiceError("python_code tools require an external sandbox approval flow before publishing")

        tool.status = CustomToolStatus.PUBLISHED.value
        tool.enabled = True
        if agent_id:
            tool.agent_id = agent_id
        if published_by:
            tool.approved_by = published_by
        await db.commit()
        await db.refresh(tool)
        creator_name = await self._get_user_display_name(db, tool.created_by)
        self.register_tool_sugar(tool)
        self.register_agent_discovery(tool, publisher_name=published_by_name, creator_name=creator_name)
        self.register_active_tool_managers(tool)
        return tool

    def register_tool_sugar(self, tool: CustomTool) -> Any:
        """Create an @local_tool compatible callable for current-process ToolManager registration."""

        @local_tool(
            name=tool.name,
            description=tool.description,
            tags=["custom", tool.kind],
            timeout=int((tool.runtime_config or {}).get("timeout") or 30),
        )
        async def dynamic_custom_tool(**kwargs):
            return await custom_tool_runtime.execute(tool, kwargs)

        dynamic_custom_tool._custom_input_schema = tool.input_schema or {}
        dynamic_custom_tool._custom_output_schema = tool.output_schema or {}
        dynamic_custom_tool._custom_metadata = self._tool_metadata(tool)
        self._published_callables[tool.name] = dynamic_custom_tool
        return dynamic_custom_tool

    def register_to_tool_manager(self, tool_manager: ToolManager, tool: CustomTool) -> None:
        tool_manager.register_langchain_tool(self.register_tool_sugar(tool))

    def register_active_tool_managers(self, tool: CustomTool) -> int:
        registered = 0
        for tool_manager in list(ACTIVE_TOOL_MANAGERS):
            try:
                self.register_to_tool_manager(tool_manager, tool)
                registered += 1
            except Exception:
                continue
        return registered

    def register_agent_discovery(
        self,
        tool: CustomTool,
        publisher_name: Optional[str] = None,
        creator_name: Optional[str] = None,
    ) -> None:
        if not tool.agent_id:
            return
        existing_agent = agent_discovery_registry.get_agent(tool.agent_id)
        if existing_agent:
            existing_agent.tools = [t for t in existing_agent.tools if t.name != tool.name]
        agent_discovery_registry.add_tool_to_agent(
            tool.agent_id,
            ToolInfo(
                name=tool.name,
                description=tool.description,
                location=ToolLocation.LOCAL,
                parameters=tool.input_schema or {},
                tags=["custom", tool.kind],
                category="custom",
                is_async=True,
                enabled=tool.enabled,
                metadata={
                    **self._tool_metadata(tool),
                    "published_by_name": publisher_name,
                    "created_by_name": creator_name,
                },
            ),
        )

    def _validate_spec(self, spec: CustomToolSpec) -> None:
        if not self.SAFE_NAME_RE.match(spec.name):
            raise CustomToolServiceError("Tool name must be a valid Python-style identifier")
        if spec.kind == CustomToolKind.HTTP.value:
            if not (spec.runtime_config or {}).get("url"):
                raise CustomToolServiceError("HTTP tools require runtime_config.url")
            api_key = (spec.runtime_config or {}).get("api_key") or {}
            if api_key.get("enabled"):
                if api_key.get("placement") not in {"header", "query"}:
                    raise CustomToolServiceError("HTTP api_key.placement must be header or query")
                if not api_key.get("name"):
                    raise CustomToolServiceError("HTTP api_key.name is required when API key is enabled")
                if not api_key.get("value"):
                    raise CustomToolServiceError("HTTP api_key.value is required when API key is enabled")
        for schema_name, schema in (("input_schema", spec.input_schema), ("output_schema", spec.output_schema)):
            for field_name, field in (schema or {}).items():
                if not self.SAFE_NAME_RE.match(field_name):
                    raise CustomToolServiceError(f"{schema_name} field name is invalid: {field_name}")
                if field.type not in {"string", "number", "integer", "boolean", "array", "object"}:
                    raise CustomToolServiceError(f"{schema_name}.{field_name} has unsupported type: {field.type}")

    def _format_output(self, output_schema: Dict[str, Any], result: Dict[str, Any]) -> Any:
        data = result.get("data", result)
        if not output_schema:
            return data
        schema_keys = list(output_schema.keys())
        if schema_keys == ["data"]:
            return {"data": data}
        if isinstance(data, dict):
            return {key: data.get(key) for key in schema_keys}
        return {schema_keys[0]: data}

    def _default_safety_policy(self, spec: CustomToolSpec) -> Dict[str, Any]:
        policy = dict(spec.safety_policy or {})
        policy.setdefault("allow_private_network", False)
        policy.setdefault("allowed_domains", [])
        policy.setdefault("code_execution", False)
        policy["code_execution"] = False
        return policy

    def _tool_metadata(self, tool: CustomTool) -> Dict[str, Any]:
        return {
            "custom_tool_id": str(tool.id),
            "is_custom_tool": True,
            "published_by": tool.approved_by,
            "created_by": tool.created_by,
            "has_api_key": bool(((tool.runtime_config or {}).get("api_key") or {}).get("enabled")),
            "input_schema": tool.input_schema or {},
            "output_schema": tool.output_schema or {},
        }

    async def _get_user_display_name(self, db: AsyncSession, user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return None
        try:
            result = await db.execute(select(User).where(User.id == uuid.UUID(str(user_id))))
            user = result.scalar_one_or_none()
            if not user:
                return user_id
            return user.full_name or user.nickname or user.username or user.email or user_id
        except Exception:
            return user_id

    def _build_generation_prompt(self, request: GenerateToolRequest, preferred_kind: str) -> str:
        return f"""
Generate one JSON object for a custom agent tool. Return JSON only.
Allowed kind: echo, http, rag_query, python_code. Prefer: {preferred_kind}.
Use safe snake_case name. For python_code, put code in generated_code but it will not run.

User request: {request.natural_language}
Purpose: {request.purpose or ""}
Inputs: {request.inputs or ""}
Outputs: {request.outputs or ""}
Agent id: {request.agent_id or ""}

Schema:
{{
  "name": "tool_name",
  "display_name": "Human name",
  "description": "What it does",
  "purpose": "When to use it",
  "kind": "{preferred_kind}",
  "version": "1.0.0",
  "input_schema": {{"query": {{"type": "string", "description": "", "required": true}}}},
  "output_schema": {{"data": {{"type": "object", "description": "", "required": true}}}},
  "runtime_config": {{
    "url": "",
    "method": "GET",
    "api_key": {{"enabled": false, "placement": "header", "name": "Authorization", "prefix": "Bearer", "value": ""}}
  }},
  "safety_policy": {{"allow_private_network": false, "allowed_domains": [], "code_execution": false}},
  "generated_code": null,
  "agent_id": {json.dumps(request.agent_id)}
}}
"""

    def _build_code_generation_prompt(self, spec: CustomToolSpec, instruction: Optional[str]) -> str:
        return f"""
Generate a safe Python async function draft for this custom agent tool.
Return only one Python code block or plain Python code. Do not include filesystem, subprocess, eval, exec, network, database, or import side effects.
The code is for human review only and will not be executed by the runtime.

Tool spec JSON:
{json.dumps(spec.model_dump(), ensure_ascii=False, indent=2)}

Additional instruction:
{instruction or ""}

Requirements:
- Define: async def run(**kwargs) -> dict
- Validate required inputs from kwargs.
- Return a JSON-serializable dict with keys: status, data.
- Use only Python standard control flow and simple calculations.
"""

    def _extract_json(self, content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= start:
            text = text[start : end + 1]
        return json.loads(text)

    def _extract_code(self, content: str) -> str:
        text = content.strip()
        match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def _fallback_code(self, spec: CustomToolSpec) -> str:
        required_fields = [
            name
            for name, field in (spec.input_schema or {}).items()
            if getattr(field, "required", True)
        ]
        checks = "\n".join([
            f"    if {field!r} not in kwargs:\n        raise ValueError('Missing required argument: {field}')"
            for field in required_fields
        ])
        return f"""async def run(**kwargs) -> dict:
{checks or "    # No required arguments declared."}
    return {{
        "status": "success",
        "data": {{
            "tool": {spec.name!r},
            "inputs": kwargs,
        }},
    }}
"""

    def _fallback_spec(self, request: GenerateToolRequest, preferred_kind: str) -> CustomToolSpec:
        raw = request.natural_language.strip().lower()
        name = re.sub(r"[^a-z0-9_]+", "_", raw)[:40].strip("_") or "custom_tool"
        if not name[0].isalpha():
            name = f"custom_{name}"
        return CustomToolSpec(
            name=name,
            display_name=request.purpose or "自定义工具",
            description=request.natural_language,
            purpose=request.purpose,
            kind=preferred_kind,
            input_schema={
                "query": {"type": "string", "description": request.inputs or "用户输入", "required": True}
            },
            output_schema={
                "data": {"type": "object", "description": request.outputs or "工具输出", "required": True}
            },
            runtime_config={
                "api_key": {
                    "enabled": False,
                    "placement": "header",
                    "name": "Authorization",
                    "prefix": "Bearer",
                    "value": "",
                }
            },
            safety_policy={"allow_private_network": False, "allowed_domains": [], "code_execution": False},
            agent_id=request.agent_id,
        )


custom_tool_service = CustomToolService()


def get_published_custom_tool_callables() -> List[Any]:
    return list(custom_tool_service._published_callables.values())
