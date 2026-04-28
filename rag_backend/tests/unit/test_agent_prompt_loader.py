from pathlib import Path
import shutil
import uuid

import pytest

from app.prompts.loader import AgentPromptLoader
from app.prompts.loader import PromptLoader


@pytest.fixture
def prompt_tmp_path():
    path = Path(__file__).parent / ".prompt_loader_tmp" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_agent(root: Path, name: str, config: str, prompt: str) -> None:
    agent_dir = root / "agents" / name
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(config, encoding="utf-8")
    (agent_dir / "system.md").write_text(prompt, encoding="utf-8")


def _loader_for(tmp_path: Path) -> AgentPromptLoader:
    loader = AgentPromptLoader()
    loader.clear_cache()
    loader.prompts_root = tmp_path
    loader.agents_dir = tmp_path / "agents"
    loader.shared_dir = tmp_path / "shared"
    loader.shared_dir.mkdir(parents=True)
    return loader


def test_load_system_prompt_supports_legacy_agent_prompts_schema(prompt_tmp_path: Path):
    loader = _loader_for(prompt_tmp_path)
    _write_agent(
        prompt_tmp_path,
        "legacy",
        """
agent:
  name: legacy
  prompts:
    system: system.md
""",
        "legacy system prompt",
    )

    assert loader.load_system_prompt("legacy") == "legacy system prompt"


def test_load_system_prompt_supports_prompt_system_file_schema(prompt_tmp_path: Path):
    loader = _loader_for(prompt_tmp_path)
    _write_agent(
        prompt_tmp_path,
        "new_schema",
        """
name: new_schema
prompt:
  system_file: system.md
""",
        "new schema system prompt",
    )

    assert loader.load_system_prompt("new_schema") == "new schema system prompt"


def test_render_prompt_keeps_json_braces_and_handles_nested_context(prompt_tmp_path: Path):
    loader = _loader_for(prompt_tmp_path)
    _write_agent(
        prompt_tmp_path,
        "json_agent",
        """
agent:
  name: json_agent
  prompts:
    system: system.md
""",
        'Hello {user.name}\nReturn JSON like {"status": "ok", "items": []}\nMode: {{ mode }}',
    )

    rendered = loader.render_prompt(
        "json_agent",
        {
            "user": {"name": "Alice"},
            "mode": "strict",
            "tools": [{"name": "search"}],
        },
    )

    assert "Hello Alice" in rendered
    assert '{"status": "ok", "items": []}' in rendered
    assert "Mode: strict" in rendered


def test_render_prompt_leaves_unknown_placeholders_unchanged(prompt_tmp_path: Path):
    loader = _loader_for(prompt_tmp_path)
    _write_agent(
        prompt_tmp_path,
        "partial",
        """
agent:
  name: partial
  prompts:
    system: system.md
""",
        "Known: {known}; Unknown: {missing.value}",
    )

    rendered = loader.render_prompt("partial", {"known": "yes"})

    assert rendered == "Known: yes; Unknown: {missing.value}"


def test_load_system_prompt_can_append_shared_includes(prompt_tmp_path: Path):
    loader = _loader_for(prompt_tmp_path)
    (prompt_tmp_path / "shared" / "common_rules.yaml").write_text(
        "shared rules",
        encoding="utf-8",
    )
    _write_agent(
        prompt_tmp_path,
        "with_includes",
        """
agent:
  name: with_includes
  prompts:
    system: system.md
    includes:
      - common_rules
""",
        "base prompt",
    )

    prompt = loader.load_system_prompt("with_includes")

    assert "base prompt" in prompt
    assert "shared rules" in prompt


def test_prompt_loader_template_uses_safe_rendering(prompt_tmp_path: Path):
    (prompt_tmp_path / "template.md").write_text(
        'Hello {name}\nKeep JSON: {"status": "ok"}',
        encoding="utf-8",
    )

    rendered = PromptLoader(prompt_tmp_path).load_template("template.md", name="Alice")

    assert "Hello Alice" in rendered
    assert '{"status": "ok"}' in rendered
