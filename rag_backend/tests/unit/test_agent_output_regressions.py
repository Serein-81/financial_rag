import pytest

pytest.importorskip("pydantic_settings")

from app.agent_framework.components.result_synthesizer import ResultSynthesizer
from app.multi_agent_system.agents.finance_specialist import (
    FinanceSpecialist,
    FinancialAnalysisResult,
    FinancialDomain,
    FinancialEntity,
    FinancialQueryResult,
)
from app.services.agent_tracer import _coerce_text


def test_agent_tracer_coerces_structured_tool_output_to_text():
    assert _coerce_text({"intent": "tax_calculation", "confidence": 0.9}) == (
        '{"intent": "tax_calculation", "confidence": 0.9}'
    )


def test_result_synthesizer_merge_preserves_string_details():
    synthesizer = ResultSynthesizer(llm_adapter=None)

    response = synthesizer._generate_merge_response({
        "summary": {},
        "details": {"tax": {"content": "企业所得税分析明细"}}
    })

    assert "企业所得税分析明细" in response


def test_result_synthesizer_prefers_public_report_over_internal_fields():
    synthesizer = ResultSynthesizer(llm_adapter=None)

    response = synthesizer._generate_merge_response({
        "summary": {
            "success": [{"value": True, "source": "tax", "confidence": 0.8}],
            "has_tax_db_data": [{"value": True, "source": "tax", "confidence": 0.8}],
            "tax_data": [{"value": {"total_revenue": 910965492.0}, "source": "tax", "confidence": 0.8}],
            "tax_type": [{"value": "TaxType.OTHER", "source": "tax", "confidence": 0.8}],
        },
        "details": {
            "tax": {
                "success": True,
                "has_tax_db_data": True,
                "tax_data": {"total_revenue": 910965492.0},
                "analysis_report": "# 税务分析报告\n\n建议进行详细的合规性审查。",
            }
        },
    })

    assert "税务分析报告" in response
    assert "建议进行详细的合规性审查" in response
    assert "has_tax_db_data" not in response
    assert "tax_data" not in response
    assert "TaxType.OTHER" not in response


def test_finance_specialist_generates_public_report_from_db_summary():
    analysis = FinancialAnalysisResult(
        domain=FinancialDomain.FINANCIAL_STATEMENT,
        financial_indicators={},
        key_metrics=[],
        risk_factors=["资金链风险"],
        recommendations=["建立财务预警机制"],
        confidence=0.9,
    )

    report = FinanceSpecialist._generate_analysis_report(
        None,
        user_input="分析企业财务风险",
        domain=FinancialDomain.FINANCIAL_STATEMENT,
        analysis=analysis,
        risk_assessment={"risk_level": "high", "risk_factors": ["资金链风险"]},
        recommendations=["建立财务预警机制"],
        data_summary={
            "total_revenue": 910965492.0,
            "total_expenses": 595054447.0,
            "total_profit": 315911045.0,
            "avg_profit_margin": 34.48,
            "fiscal_years": [2024, 2025],
        },
        has_financial_data=True,
    )

    assert "企业财务风险分析报告" in report
    assert "营业收入" in report
    assert "910,965,492.00 元" in report
    assert "核心指标" in report
    assert "风险判断" in report
    assert "数据来源与限制" in report
    assert "domain:" not in report


def test_finance_timeout_fallback_keeps_db_data_public_report():
    result = FinanceSpecialist._build_timeout_fallback_result(
        None,
        user_input="分析企业财务风险",
        domain=FinancialDomain.FINANCIAL_STATEMENT,
        entities=FinancialEntity(),
        query_result=FinancialQueryResult(
            has_data=True,
            data_summary={
                "total_revenue": 910965492.0,
                "total_expenses": 595054447.0,
                "total_profit": 315911045.0,
                "avg_profit_margin": 34.48,
                "fiscal_years": [2024, 2025],
            },
        ),
        rag_enabled=True,
        error_message="LLM 调用超时，已改用企业数据生成兜底分析",
    )

    assert result["success"] is True
    assert result["degraded"] is True
    assert result["has_financial_db_data"] is True
    assert "analysis_report" in result
    assert "910,965,492.00" in result["analysis_report"]
    assert "未知领域" not in result["analysis_report"]
