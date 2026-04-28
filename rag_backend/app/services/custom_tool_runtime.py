from __future__ import annotations

import asyncio
import ipaddress
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
        self._validate_arguments(tool.input_schema or {}, arguments)

        if tool.kind == CustomToolKind.ECHO.value:
            return {
                "status": "success",
                "tool": tool.name,
                "data": arguments,
            }

        if tool.kind == CustomToolKind.HTTP.value:
            return await self._execute_http(tool, arguments)

        if tool.kind == CustomToolKind.RAG_QUERY.value:
            return await self._execute_rag_query(tool, arguments)

        if tool.kind == CustomToolKind.PYTHON_CODE.value:
            raise CustomToolRuntimeError(
                "python_code tools are stored for review only and are not executable in this runtime"
            )

        raise CustomToolRuntimeError(f"Unsupported custom tool kind: {tool.kind}")

    def _validate_arguments(self, input_schema: Dict[str, Any], arguments: Dict[str, Any]) -> None:
        for name, spec in input_schema.items():
            required = spec.get("required", True) if isinstance(spec, dict) else True
            if required and name not in arguments:
                raise CustomToolRuntimeError(f"Missing required argument: {name}")

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

    async def _assert_url_allowed(self, url: str, safety_policy: Dict[str, Any]) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise CustomToolRuntimeError("Only absolute http/https URLs are allowed")

        allowed_domains = safety_policy.get("allowed_domains") or []
        if allowed_domains and parsed.hostname not in allowed_domains:
            raise CustomToolRuntimeError(f"Domain is not in allowed_domains: {parsed.hostname}")

        if safety_policy.get("allow_private_network", False):
            return

        infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                raise CustomToolRuntimeError("Private, loopback, link-local, and multicast IPs are blocked")


custom_tool_runtime = CustomToolRuntime()
