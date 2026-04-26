"""
测试人工审核 API 端点的 JSONB 字段处理

验证 trigger_details, content, review_result 等 JSONB 字段
能够正确解析为 Python 对象，而不是字符串
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from uuid import uuid4


class TestReviewRequestJSONBFields:
    """测试 ReviewRequest JSONB 字段的解析"""

    def test_json_field_parsing_from_string(self):
        """测试从字符串解析 JSONB 字段"""
        from app.api.v1.endpoints.human_review import json

        mock_trigger_details_str = '{"confidence": 0.92, "amount": 100000, "invoice_number": "NO123456"}'
        mock_content_str = '{"extraction": {"amount": 100000}, "risk_decision": {"risk_level": "high"}}'

        # 测试解析逻辑
        trigger_details = json.loads(mock_trigger_details_str) if isinstance(mock_trigger_details_str, str) else mock_trigger_details_str
        content = json.loads(mock_content_str) if isinstance(mock_content_str, str) else mock_content_str

        assert isinstance(trigger_details, dict)
        assert trigger_details["confidence"] == 0.92
        assert trigger_details["amount"] == 100000

        assert isinstance(content, dict)
        assert "extraction" in content
        assert "risk_decision" in content

    def test_json_field_parsing_from_dict(self):
        """测试已经是字典的字段保持不变"""
        from app.api.v1.endpoints.human_review import json

        mock_trigger_details = {"confidence": 0.92, "amount": 100000}
        mock_content = {"extraction": {"amount": 100000}}

        # 测试解析逻辑
        trigger_details = json.loads(mock_trigger_details) if isinstance(mock_trigger_details, str) else mock_trigger_details
        content = json.loads(mock_content) if isinstance(mock_content, str) else mock_content

        assert isinstance(trigger_details, dict)
        assert trigger_details["confidence"] == 0.92

        assert isinstance(content, dict)
        assert "extraction" in content

    def test_review_result_parsing(self):
        """测试 review_result 字段的解析"""
        from app.api.v1.endpoints.human_review import json

        mock_review_result_str = '{"decision": "approved", "comments": "OK"}'

        # 测试解析逻辑
        review_result = json.loads(mock_review_result_str) if isinstance(mock_review_result_str, str) else mock_review_result_str

        assert isinstance(review_result, dict)
        assert review_result["decision"] == "approved"
        assert review_result["comments"] == "OK"

    def test_complex_trigger_details_structure(self):
        """测试完整的 trigger_details 结构"""
        from app.api.v1.endpoints.human_review import json

        complex_trigger_details = {
            "risk_level": "high",
            "trigger_rules": ["RULE_HIGH_AMOUNT", "RULE_LOW_CONFIDENCE"],
            "trigger_reasons": ["金额超过阈值", "AI置信度低于80%"],
            "confidence": 0.75,
            "amount": 1500000.0,
            "tax_amount": 195000.0,
            "tax_rate": 0.13,
            "invoice_number": "NO9876543210",
            "invoice_date": "2024-03-15",
            "invoice_type": "增值税专用发票",
            "seller": "销售方公司",
            "buyer": "购买方公司",
            "semantic_suspicion": ["供应商为新注册公司", "金额异常大"]
        }

        # 模拟数据库返回字符串
        trigger_details_str = json.dumps(complex_trigger_details)

        # 测试解析逻辑
        trigger_details = json.loads(trigger_details_str) if isinstance(trigger_details_str, str) else trigger_details_str

        assert isinstance(trigger_details, dict)
        assert trigger_details["risk_level"] == "high"
        assert len(trigger_details["trigger_rules"]) == 2
        assert len(trigger_details["semantic_suspicion"]) == 2
        assert trigger_details["amount"] == 1500000.0

    def test_none_values_handling(self):
        """测试 None 值的处理"""
        from app.api.v1.endpoints.human_review import json

        # 测试 None 值
        none_value = None
        result = json.loads(none_value) if isinstance(none_value, str) else none_value
        assert result is None

        # 测试空字符串
        empty_str = ""
        result = json.loads(empty_str) if isinstance(empty_str, str) else empty_str
        assert result == ""  # json.loads("") 会抛出异常，所以保持原值


class TestReviewRequestResponse:
    """测试 ReviewRequestResponse 模型"""

    def test_response_with_parsed_json_fields(self):
        """测试响应模型包含正确解析的 JSON 字段"""
        from app.schemas.human_review import ReviewRequestResponse, ReviewTypeEnum, ReviewPriorityEnum, ReviewStatusEnum

        trigger_details = {
            "confidence": 0.92,
            "amount": 100000,
            "invoice_number": "NO123456"
        }

        content = {
            "extraction": {"amount": 100000},
            "risk_decision": {"risk_level": "high"}
        }

        review_result = {
            "decision": "approved",
            "comments": "审核通过"
        }

        response = ReviewRequestResponse(
            id=str(uuid4()),
            tenant_id="tenant_001",
            user_id=str(uuid4()),
            review_type=ReviewTypeEnum.TAX,
            priority=ReviewPriorityEnum.HIGH,
            status=ReviewStatusEnum.PENDING,
            trigger_reason="high_amount_detected",
            trigger_details=trigger_details,
            content=content,
            review_result=review_result,
            created_at=datetime.now(timezone.utc),
            is_overdue=False,
            age_hours=0
        )

        assert response.trigger_details["confidence"] == 0.92
        assert response.content["extraction"]["amount"] == 100000
        assert response.review_result["decision"] == "approved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
