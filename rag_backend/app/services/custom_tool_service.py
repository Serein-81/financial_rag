from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_framework.tools.tool_manager import ToolManager
from app.mcp.decorators import local_tool
from app.models.custom_tool import CustomTool, CustomToolKind, CustomToolStatus
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
            self.register_tool_sugar(tool)
            self.register_agent_discovery(tool)
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
    ) -> CustomTool:
        tool = await self.get_tool(db, tenant_id, tool_id)
        if tool.kind == CustomToolKind.PYTHON_CODE.value:
            raise CustomToolServiceError("python_code tools require an external sandbox approval flow before publishing")

        tool.status = CustomToolStatus.PUBLISHED.value
        tool.enabled = True
        if agent_id:
            tool.agent_id = agent_id
        await db.commit()
        await db.refresh(tool)
        self.register_tool_sugar(tool)
        self.register_agent_discovery(tool)
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
        self._published_callables[tool.name] = dynamic_custom_tool
        return dynamic_custom_tool

    def register_to_tool_manager(self, tool_manager: ToolManager, tool: CustomTool) -> None:
        tool_manager.register_langchain_tool(self.register_tool_sugar(tool))

    def register_agent_discovery(self, tool: CustomTool) -> None:
        if not tool.agent_id:
            return
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
            ),
        )

    def _validate_spec(self, spec: CustomToolSpec) -> None:
        if not self.SAFE_NAME_RE.match(spec.name):
            raise CustomToolServiceError("Tool name must be a valid Python-style identifier")
        if spec.kind == CustomToolKind.HTTP.value:
            if not (spec.runtime_config or {}).get("url"):
                raise CustomToolServiceError("HTTP tools require runtime_config.url")

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
        return policy

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
  "runtime_config": {{}},
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
            runtime_config={},
            safety_policy={"allow_private_network": False, "allowed_domains": [], "code_execution": False},
            agent_id=request.agent_id,
        )


custom_tool_service = CustomToolService()


def get_published_custom_tool_callables() -> List[Any]:
    return list(custom_tool_service._published_callables.values())
