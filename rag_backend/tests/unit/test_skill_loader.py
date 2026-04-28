import shutil
import uuid
from pathlib import Path

import pytest

from app.prompts.skill_loader import SkillLibraryImporter, SkillLoader


class FakeToolManager:
    def __init__(self):
        self.tools = {}

    def register_function(self, name, func, description, args_schema=None):
        self.tools[name] = {
            "func": func,
            "description": description,
            "parameters": {},
            "args_schema": args_schema,
            "type": "function",
        }


def test_loads_structured_and_legacy_skills():
    loader = SkillLoader()

    names = loader.list_skills()

    assert "enterprise_knowledge_search" in names
    assert "web_research" in names
    assert "policy_impact_analysis" in names
    assert "tax_invoice_review" in names
    assert "contract_risk_review" in names
    assert "evidence_gap_check" in names
    assert "business_deadline_planner" in names
    assert "table_data_profile" in names
    assert "search_web" in names


def test_selects_skill_by_tool_and_keyword():
    loader = SkillLoader()

    selected = loader.select_skills(
        user_input="请查询知识库里的公司制度",
        tools=[{"name": "search_enterprise_knowledge"}],
    )

    assert selected
    assert selected[0].name == "enterprise_knowledge_search"


def test_selects_policy_skill_by_intent():
    loader = SkillLoader()

    selected = loader.select_skills(
        user_input="分析这项补贴政策是否适用于我们企业。",
        tools=[{"name": "search_enterprise_knowledge"}],
        agent_name="policy_notification",
        intent="policy_match",
    )

    assert selected
    assert selected[0].name == "policy_impact_analysis"


def test_selects_tax_skill_by_file_type():
    loader = SkillLoader()

    selected = loader.select_skills(
        user_input="审查这张增值税发票的抵扣风险。",
        tools=[{"name": "calculate_tax_vat"}],
        agent_name="tax",
        file_type="invoice",
    )

    assert selected
    assert selected[0].name == "tax_invoice_review"


def test_contract_skill_respects_allowed_agents():
    loader = SkillLoader()

    tax_selected = loader.select_skills(
        user_input="审查这份合同的风险。",
        tools=[{"name": "check_contract_essentials"}],
        agent_name="tax",
        intent="contract_review",
    )
    legal_selected = loader.select_skills(
        user_input="审查这份合同的风险。",
        tools=[{"name": "check_contract_essentials"}],
        agent_name="legal",
        intent="contract_review",
    )

    assert "contract_risk_review" not in [skill.name for skill in tax_selected]
    assert legal_selected
    assert legal_selected[0].name == "contract_risk_review"


def test_loads_skill_tool_definitions():
    loader = SkillLoader()

    tools = loader.load_tool_definitions(["evidence_gap_check", "business_deadline_planner", "table_data_profile"])
    tool_names = [tool.name for tool in tools]

    assert "analyze_evidence_gaps" in tool_names
    assert "calculate_business_deadline" in tool_names
    assert "profile_table_text" in tool_names


def test_registers_and_executes_skill_tool():
    loader = SkillLoader()
    manager = FakeToolManager()

    registered = loader.register_skill_tools(manager, ["evidence_gap_check"])
    result = manager.tools["analyze_evidence_gaps"]["func"](
        required_items="营业执照,纳税申报表,合同",
        provided_items="营业执照,合同",
    )

    assert "analyze_evidence_gaps" in registered
    assert "纳税申报表" in result
    assert "缺失证据" in result


def test_business_deadline_skill_tool_calculates_weekdays():
    loader = SkillLoader()
    manager = FakeToolManager()
    loader.register_skill_tools(manager, ["business_deadline_planner"])

    result = manager.tools["calculate_business_deadline"]["func"](
        start_date="2026-04-24",
        business_days=3,
        holidays="",
    )

    assert "2026-04-29" in result
    assert "截止日期" in result


def test_render_prompt_can_include_skills():
    from app.prompts.loader import get_agent_prompt_loader

    prompt = get_agent_prompt_loader().render_prompt(
        "react",
        {
            "user_input": "帮我联网查一下最新政策",
            "tools": [{"name": "search_web"}],
        },
    )

    assert prompt is not None
    assert "可用技能" in prompt
    assert "web_research" in prompt or "search_web" in prompt


def test_skill_selection_refreshes_between_agent_rounds():
    loader = SkillLoader()

    first_round = loader.select_skills(
        user_input="查询知识库里的公司制度",
        tools=[{"name": "search_enterprise_knowledge"}],
        agent_name="react",
    )
    assert first_round
    assert first_round[0].name == "enterprise_knowledge_search"

    second_round = loader.select_skills(
        user_input="再联网查一下最新政策",
        tools=[{"name": "search_web"}],
        active_skills=[skill.name for skill in first_round],
        agent_name="react",
        skill_strategy="refresh",
    )

    second_round_names = [skill.name for skill in second_round]
    assert "web_research" in second_round_names
    assert "enterprise_knowledge_search" not in second_round_names


def test_skill_selection_can_merge_active_skills_between_rounds():
    loader = SkillLoader()

    selected = loader.select_skills(
        user_input="再联网查一下最新政策",
        tools=[{"name": "search_web"}, {"name": "search_enterprise_knowledge"}],
        active_skills=["enterprise_knowledge_search"],
        agent_name="react",
        skill_strategy="merge",
    )

    selected_names = [skill.name for skill in selected]
    assert "enterprise_knowledge_search" in selected_names
    assert "web_research" in selected_names


def test_importer_rejects_unsafe_zip_paths():
    import zipfile

    tmp_path = Path("tests/.tmp_skill_loader") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True)
    archive_path = tmp_path / "unsafe.zip"
    try:
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("../skill.yaml", "name: unsafe\n")

        importer = SkillLibraryImporter(skills_dir=tmp_path / "skills")

        with pytest.raises(ValueError):
            importer.import_from_zip(archive_path)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
