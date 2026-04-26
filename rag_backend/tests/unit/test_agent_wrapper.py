"""
Agent 容错机制测试

测试 AgentWrapper 的"鞭打机制"
"""

import pytest
import json
from app.agent_framework.core.agent_wrapper import AgentResponseValidator, AgentWrapper, ValidationError


class TestAgentResponseValidator:
    """测试响应验证器"""
    
    def test_valid_response(self):
        """测试有效的响应"""
        response = {
            "thought_process": "分析中...",
            "blackboard_action": {
                "status": "COMPLETED",
                "output_data": {"result": "test"}
            }
        }
        
        is_valid, parsed, errors = AgentResponseValidator.validate(json.dumps(response))
        
        assert is_valid is True
        assert parsed is not None
        assert len(errors) == 0
    
    def test_missing_blackboard_action(self):
        """测试缺少 blackboard_action"""
        response = {
            "thought_process": "分析中..."
        }
        
        is_valid, parsed, errors = AgentResponseValidator.validate(json.dumps(response))
        
        assert is_valid is False
        assert any(e.error_type == "MISSING_FIELD" and "blackboard_action" in e.field_path for e in errors)
    
    def test_missing_status(self):
        """测试缺少 status"""
        response = {
            "blackboard_action": {
                "output_data": {"result": "test"}
            }
        }
        
        is_valid, parsed, errors = AgentResponseValidator.validate(json.dumps(response))
        
        assert is_valid is False
        assert any(e.error_type == "MISSING_FIELD" and "status" in e.field_path for e in errors)
    
    def test_invalid_status(self):
        """测试无效的 status"""
        response = {
            "blackboard_action": {
                "status": "INVALID_STATUS",
                "output_data": {"result": "test"}
            }
        }
        
        is_valid, parsed, errors = AgentResponseValidator.validate(json.dumps(response))
        
        assert is_valid is False
        assert any(e.error_type == "INVALID_VALUE" for e in errors)
    
    def test_failed_without_error_message(self):
        """测试 FAILED 状态但没有 error_message"""
        response = {
            "blackboard_action": {
                "status": "FAILED",
                "output_data": {}
            }
        }
        
        is_valid, parsed, errors = AgentResponseValidator.validate(json.dumps(response))
        
        assert is_valid is False
        assert any(e.error_type == "MISSING_FIELD" and "error_message" in e.field_path for e in errors)
    
    def test_json_parse_error(self):
        """测试 JSON 解析错误"""
        response = "这不是有效的 JSON"
        
        is_valid, parsed, errors = AgentResponseValidator.validate(response)
        
        assert is_valid is False
        assert any(e.error_type == "JSON_PARSE_ERROR" for e in errors)
    
    def test_json_from_markdown_block(self):
        """测试从 Markdown 代码块中提取 JSON"""
        response = """
        这是一段文本
        ```json
        {
            "thought_process": "分析中",
            "blackboard_action": {
                "status": "COMPLETED",
                "output_data": {"result": "test"}
            }
        }
        ```
        更多文本
        """
        
        is_valid, parsed, errors = AgentResponseValidator.validate(response)
        
        assert is_valid is True
        assert parsed is not None


class TestAgentWrapper:
    """测试 Agent Wrapper"""
    
    @pytest.mark.asyncio
    async def test_wrapper_initialization(self):
        """测试 Wrapper 初始化"""
        class MockAgent:
            async def run(self, input, **kwargs):
                return "test"
        
        agent = MockAgent()
        wrapper = AgentWrapper(agent, max_retries=3)
        
        assert wrapper.agent is agent
        assert wrapper.max_retries == 3
    
    def test_build_whip_prompt(self):
        """测试鞭打提示生成"""
        class MockAgent:
            async def run(self, input, **kwargs):
                return "test"
        
        wrapper = AgentWrapper(MockAgent())
        
        whip_prompt = wrapper._build_whip_prompt("缺少字段: blackboard_action")
        
        assert "blackboard_action" in whip_prompt
        assert "MISSING_FIELD" in whip_prompt or "缺少字段" in whip_prompt
    
    def test_summarize_errors(self):
        """测试错误汇总"""
        class MockAgent:
            async def run(self, input, **kwargs):
                return "test"
        
        wrapper = AgentWrapper(MockAgent())
        
        errors = [
            ValidationError("JSON_PARSE_ERROR", "无法解析 JSON"),
            ValidationError("MISSING_FIELD", "缺少字段", "blackboard_action")
        ]
        
        summary = wrapper._summarize_errors(errors)
        
        assert "JSON" in summary or "解析" in summary
        assert "blackboard_action" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
