import importlib.util
from pathlib import Path


STATE_PATH = Path(__file__).resolve().parents[2] / "app" / "langgraph" / "state.py"
SPEC = importlib.util.spec_from_file_location("langgraph_state_for_test", STATE_PATH)
langgraph_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(langgraph_state)


def test_create_initial_state_preserves_reflection_toggle():
    state = langgraph_state.create_initial_state(
        session_id="session-001",
        tenant_id="tenant-001",
        user_id="user-001",
        user_query="analyze financial risk",
        enable_reflection=False,
    )

    assert state["enable_reflection"] is False


def test_create_initial_state_enables_reflection_by_default():
    state = langgraph_state.create_initial_state(
        session_id="session-001",
        tenant_id="tenant-001",
        user_id="user-001",
        user_query="analyze financial risk",
    )

    assert state["enable_reflection"] is True
