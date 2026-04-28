from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from app.models.custom_tool import CustomTool, CustomToolKind


class CustomToolRuntimeError(RuntimeError):
    pass


class CustomToolRuntime:
    """Executes tenant custom tools without evaluating user supplied code."""

    DEFAULT_TIMEOUT = 15.0
    MAX_RESPONSE_BYTES = 512 * 1024

    async def execute(self, tool: CustomTool, arguments: Dict[str, Any]) -> Dict[str, Any]:
        arguments = self._validate_payload(tool.input_schema or {}, arguments, "argument")

        if tool.kind == CustomToolKind.ECHO.value:
            result = {
                "status": "success",
                "tool": tool.name,
                "data": arguments,
            }
            return self._validate_output(tool, result)

        if tool.kind == CustomToolKind.HTTP.value:
            return self._validate_output(tool, await self._execute_http(tool, arguments))

        if tool.kind == CustomToolKind.RAG_QUERY.value:
            return self._validate_output(tool, await self._execute_rag_query(tool, arguments))

        if tool.kind == CustomToolKind.PYTHON_CODE.value:
            raise CustomToolRuntimeError(
                "python_code tools are stored for review only and are not executable in this runtime"
            )

        raise CustomToolRuntimeError(f"Unsupported custom tool kind: {tool.kind}")

    def _validate_arguments(self, input_schema: Dict[str, Any], arguments: Dict[str, Any]) -> None:
        self._validate_payload(input_schema, arguments, "argument")

    def _validate_payload(self, schema: Dict[str, Any], payload: Dict[str, Any], label: str) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise CustomToolRuntimeError(f"{label} payload must be an object")

        sanitized = dict(payload)
        for name, spec in schema.items():
            required = spec.get("required", True) if isinstance(spec, dict) else True
            if name not in sanitized:
                if required:
                    raise CustomToolRuntimeError(f"Missing required {label}: {name}")
                if isinstance(spec, dict) and "default" in spec and spec.get("default") is not None:
                    sanitized[name] = spec.get("default")
                continue
            self._validate_value(name, sanitized[name], spec if isinstance(spec, dict) else {}, label)
        return sanitized

    def _validate_value(self, name: str, value: Any, spec: Dict[str, Any], label: str) -> None:
        expected_type = str(spec.get("type") or "string").lower()
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }
        if expected_type in type_checks and not type_checks[expected_type](value):
            raise CustomToolRuntimeError(f"Invalid {label} type for {name}: expected {expected_type}")

        enum_values = spec.get("enum")
        if enum_values and value not in enum_values:
            raise CustomToolRuntimeError(f"Invalid {label} value for {name}: must be one of {enum_values}")

        if expected_type in {"number", "integer"}:
            if spec.get("min") is not None and value < spec["min"]:
                raise CustomToolRuntimeError(f"{label} {name} must be >= {spec['min']}")
            if spec.get("max") is not None and value > spec["max"]:
                raise CustomToolRuntimeError(f"{label} {name} must be <= {spec['max']}")

        if expected_type == "string":
            if spec.get("min_length") is not None and len(value) < spec["min_length"]:
                raise CustomToolRuntimeError(f"{label} {name} is shorter than {spec['min_length']}")
            if spec.get("max_length") is not None and len(value) > spec["max_length"]:
                raise CustomToolRuntimeError(f"{label} {name} is longer than {spec['max_length']}")
            if spec.get("pattern") and not re.fullmatch(str(spec["pattern"]), value):
                raise CustomToolRuntimeError(f"{label} {name} does not match the required pattern")

    async def _execute_http(self, tool: CustomTool, arguments: Dict[str, Any]) -> Dict[str, Any]:
        config = tool.runtime_config or {}
        url = str(config.get("url") or "")
        method = str(config.get("method") or "GET").upper()
        headers = dict(config.get("headers") or {})
        timeout = min(float(config.get("timeout") or self.DEFAULT_TIMEOUT), self.DEFAULT_TIMEOUT)

        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise CustomToolRuntimeError(f"HTTP method is not allowed: {method}")

        await self._assert_url_allowed(url, tool.safety_policy or {})

        params = {}
        json_body = None
        if method == "GET":
            params = arguments
        else:
            json_body = arguments

        api_key = dict(config.get("api_key") or {})
        if api_key.get("enabled"):
            key_name = str(api_key.get("name") or "").strip()
            key_value = str(api_key.get("value") or "")
            prefix = str(api_key.get("prefix") or "").strip()
            if api_key.get("placement") == "query":
                params[key_name] = f"{prefix} {key_value}".strip() if prefix else key_value
            else:
                headers[key_name] = f"{prefix} {key_value}".strip() if prefix else key_value

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
            )

        body = response.content[: self.MAX_RESPONSE_BYTES]
        parsed: Any
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            parsed = response.json()
        else:
            parsed = body.decode("utf-8", errors="replace")

        return {
            "status": "success" if response.is_success else "error",
            "tool": tool.name,
            "http_status": response.status_code,
            "data": parsed,
        }

    async def _execute_rag_query(self, tool: CustomTool, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query") or arguments.get("question")
        if not query:
            raise CustomToolRuntimeError("rag_query tools require a query or question argument")

        from app.services.search_service import search_service

        limit = int((tool.runtime_config or {}).get("limit") or arguments.get("limit") or 5)
        result = await search_service.search(
            query=query,
            tenant_id=tool.tenant_id,
            top_k=min(max(limit, 1), 20),
        )
        return {
            "status": "success",
            "tool": tool.name,
            "data": result,
        }

    def _validate_output(self, tool: CustomTool, result: Dict[str, Any]) -> Dict[str, Any]:
        output_schema = tool.output_schema or {}
        if not output_schema:
            return result
        data = result.get("data", result)
        if list(output_schema.keys()) == ["data"]:
            candidates = {"data": data}
        elif isinstance(data, dict):
            candidates = data
        else:
            return result

        for name, spec in output_schema.items():
            if name not in candidates:
                if spec.get("required", True):
                    raise CustomToolRuntimeError(f"Tool output missing required field: {name}")
                continue
            if name == "data" and spec.get("type") == "object" and not isinstance(candidates[name], dict):
                continue
            self._validate_value(name, candidates[name], spec if isinstance(spec, dict) else {}, "output")
        return result

    async def _assert_url_allowed(self, url: str, safety_policy: Dict[str, Any]) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise CustomToolRuntimeError("Only absolute http/https URLs are allowed")

        allowed_domains = safety_policy.get("allowed_domains") or []
        if allowed_domains and parsed.hostname not in allowed_domains:
            raise CustomToolRuntimeError(f"Domain is not in allowed_domains: {parsed.hostname}")

        if safety_policy.get("allow_private_network", False):
            return

        if allowed_domains and parsed.hostname in allowed_domains:
            return

        infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                raise CustomToolRuntimeError("Private, loopback, link-local, and multicast IPs are blocked")


custom_tool_runtime = CustomToolRuntime()
