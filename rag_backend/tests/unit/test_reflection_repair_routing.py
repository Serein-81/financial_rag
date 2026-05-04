import pytest

pytest.importorskip("pydantic_settings")

from app.multi_agent_system.agents.tax_specialist import TaxEntity, TaxSpecialist
from app.multi_agent_system.orchestrator import AgentOrchestrator


def test_tax_guidance_skips_enterprise_data_query():
    should_query = TaxSpecialist._should_query_enterprise_data(
        None,
        "税务申报指导",
        TaxEntity(tax_type="other"),
        {},
    )

    assert should_query is False


def test_company_tax_calculation_queries_enterprise_data():
    should_query = TaxSpecialist._should_query_enterprise_data(
        None,
        "我司今年企业所得税测算",
        TaxEntity(tax_type="income_tax"),
        {},
    )

    assert should_query is True


def test_reflection_repair_target_uses_domain_specialist():
    orch = AgentOrchestrator(tenant_id="tenant", user_id="user")

    plan = orch._build_repair_plan(
        review_result={
            "is_quality_acceptable": False,
            "scores": {"overall": 0.4},
            "issues": [{"description": "回答过于笼统，缺少办理流程"}],
        },
        user_input="税务申报指导",
        specialist_results=[{"specialist_type": "tax", "source": "tax"}],
        fallback_target="tax_specialist",
    )

    assert plan["target"] == "tax_specialist"
    assert plan["failure_type"] == "shallow_answer"
