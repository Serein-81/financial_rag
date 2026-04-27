from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi import HTTPException

from app.agent_framework.core.base_agent import BaseAgent
from app.api.v1.endpoints import agent_trace as agent_trace_api
from app.api.v1.endpoints import tool_trace as tool_trace_api


class DummyAgent(BaseAgent):
    async def run(self, user_input: str, history=None, **kwargs) -> str:
        return "ok"

    async def stream_run(self, user_input: str, history=None, **kwargs):
        yield "ok"


@pytest.mark.asyncio
async def test_base_agent_passes_current_trace_id_to_tool_manager():
    tool_manager = SimpleNamespace(
        tools={"search": {}},
        call_tool=AsyncMock(return_value="result"),
        get_tools_description=lambda: "",
    )
    agent = DummyAgent(
        llm_adapter=SimpleNamespace(),
        tool_manager=tool_manager,
        system_prompt="",
    )
    agent.current_trace_id = "trace-123"

    result = await agent.call_tool("search", query="hello")

    assert result == "result"
    tool_manager.call_tool.assert_awaited_once_with(
        "search",
        trace_id="trace-123",
        query="hello",
    )


def test_agent_trace_legacy_response_maps_steps_to_events():
    trace = {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "user_query": "find policy",
        "created_at": "2026-04-27T00:00:00",
        "total_time": 1.2,
        "steps": [
            {
                "step_number": 1,
                "step_type": "thought",
                "content": "think",
                "timestamp": 1,
            },
            {
                "step_number": 2,
                "step_type": "action",
                "content": "call search",
                "tool_name": "search",
                "tool_input": {"q": "policy"},
                "timestamp": 2,
            },
            {
                "step_number": 3,
                "step_type": "observation",
                "content": "found",
                "tool_output": "found",
                "timestamp": 3,
            },
        ],
    }

    legacy = agent_trace_api._trace_to_legacy(trace)

    assert legacy["query"] == "find policy"
    assert [event["event_type"] for event in legacy["events"]] == [
        "thinking",
        "tool_call",
        "tool_result",
    ]
    assert legacy["events"][1]["metadata"]["tool_name"] == "search"


def test_tool_trace_legacy_response_shape():
    call = {
        "call_id": "call-1",
        "trace_id": "trace-1",
        "tool_name": "search",
        "tool_type": "function",
        "input_params": {"q": "policy"},
        "output_result": "ok",
        "duration": 12.3,
        "status": "success",
        "error_message": None,
        "start_time": 1,
    }

    legacy = tool_trace_api._call_to_legacy(call)

    assert legacy["tool_id"] == "call-1"
    assert legacy["trace_id"] == "trace-1"
    assert legacy["input"] == {"q": "policy"}
    assert legacy["output"] == "ok"


@pytest.mark.asyncio
async def test_tool_trace_access_helper_rejects_wrong_user_or_tenant(monkeypatch):
    async def fake_get_trace_with_steps(**kwargs):
        assert kwargs["user_id"] == "user-1"
        assert kwargs["tenant_id"] == "tenant-1"
        return None

    monkeypatch.setattr(
        tool_trace_api.agent_tracer,
        "get_trace_with_steps",
        fake_get_trace_with_steps,
    )
    user = SimpleNamespace(id="user-1")

    with pytest.raises(HTTPException) as exc:
        await tool_trace_api._ensure_trace_access(
            "trace-1",
            user,
            {"tenant_id": "tenant-1"},
        )

    assert exc.value.status_code == 404
