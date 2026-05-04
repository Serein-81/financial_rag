import pytest

pytest.importorskip("email_validator")

from app.schemas.search import SearchResultItem
from app.services.search_service import SearchService


def test_answerability_prefers_process_evidence_over_code_fragment():
    service = SearchService()
    query = "解释一下增值税怎么申报"
    results = [
        SearchResultItem(
            chunk_id="code",
            document_id="doc-code",
            score=0.68,
            content=(
                "class TaxRPAIntegration:\n"
                "    async def submit_tax_declaration_draft(self):\n"
                "        return await api.submit(payload)"
            ),
            source_file="tech.md",
        ),
        SearchResultItem(
            chunk_id="flow",
            document_id="doc-flow",
            score=0.64,
            content=(
                "增值税申报流程：首先登录电子税务局，然后选择增值税申报表，"
                "填写销售额、进项税额和附列资料，确认后提交申报并按提示缴款。"
            ),
            source_file="tax.md",
        ),
    ]

    ranked = service._annotate_answerability(query, results)

    assert ranked[0].chunk_id == "flow"
    assert ranked[0].evidence_flags["has_process_steps"] is True
    assert ranked[1].evidence_flags["is_code_or_plan_fragment"] is True
    assert ranked[0].answerability_score > ranked[1].answerability_score
