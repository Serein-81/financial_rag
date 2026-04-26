"""
Orchestrator Agent 工具测试

测试 breakdown_task_to_blackboard 和 summarize_final_report 功能
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_breakdown_task_to_blackboard():
    """测试任务拆解功能"""
    from app.mcp.orchestrator_tools import breakdown_task_to_blackboard

    with patch('app.mcp.orchestrator_tools.TaskBlackboard') as MockBlackboard:
        mock_blackboard = MagicMock()
        MockBlackboard.return_value = mock_blackboard

        mock_task = MagicMock()
        mock_task.task_id = "test-task-123"
        mock_task.task_type = "finance_analysis"
        mock_task.priority = MagicMock(value="high")
        mock_task.dependencies = []
        mock_task.status = MagicMock(value="pending")
        mock_task.description = "Test task description"

        mock_blackboard.create_task = AsyncMock(return_value=mock_task)
        mock_blackboard.update_shared_data = AsyncMock()

        result = await breakdown_task_to_blackboard(
            user_goal="分析企业2024年度财务状况",
            session_id="test-session-001",
            tenant_id="test-tenant",
            required_expertise=["finance", "tax"],
            priority_tasks=["finance_analysis"]
        )

        assert result["status"] == "success"
        assert "task_graph" in result
        assert "created_tasks" in result
        assert "execution_order" in result
        assert "summary" in result
        assert result["summary"]["total_tasks"] >= 1


@pytest.mark.asyncio
async def test_breakdown_task_with_legal_expertise():
    """测试包含法务专家的任务拆解"""
    from app.mcp.orchestrator_tools import breakdown_task_to_blackboard

    with patch('app.mcp.orchestrator_tools.TaskBlackboard') as MockBlackboard:
        mock_blackboard = MagicMock()
        MockBlackboard.return_value = mock_blackboard

        mock_task = MagicMock()
        mock_task.task_id = "legal-task-456"
        mock_task.task_type = "legal_review"
        mock_task.priority = MagicMock(value="high")
        mock_task.dependencies = []
        mock_task.status = MagicMock(value="pending")
        mock_task.description = "Legal review task"

        mock_blackboard.create_task = AsyncMock(return_value=mock_task)
        mock_blackboard.update_shared_data = AsyncMock()

        result = await breakdown_task_to_blackboard(
            user_goal="审查采购合同合规性",
            session_id="test-session-002",
            tenant_id="test-tenant",
            required_expertise=["legal", "finance"]
        )

        assert result["status"] == "success"
        assert len(result["created_tasks"]) >= 2


@pytest.mark.asyncio
async def test_summarize_final_report():
    """测试最终报告生成功能"""
    from app.mcp.orchestrator_tools import summarize_final_report

    with patch('app.mcp.orchestrator_tools.TaskBlackboard') as MockBlackboard:
        mock_blackboard = MagicMock()
        MockBlackboard.return_value = mock_blackboard

        mock_task = MagicMock()
        mock_task.output_data = {
            "content": "财务分析结果：企业营收增长10%"
        }
        mock_task.task_type = "finance_analysis"
        mock_task.task_id = "task-001"
        mock_task.metadata = {}

        mock_task2 = MagicMock()
        mock_task2.output_data = {
            "content": "税务计算结果：应缴税款50万元"
        }
        mock_task2.task_type = "tax_calculation"
        mock_task2.task_id = "task-002"
        mock_task2.metadata = {}

        mock_blackboard.get_tasks_by_status = AsyncMock(return_value=[mock_task, mock_task2])
        mock_blackboard.get_all_shared_data = AsyncMock(return_value={
            "dag_root_goal": "分析企业年度财务",
            "task_count": 2
        })
        mock_blackboard.update_shared_data = AsyncMock()

        result = await summarize_final_report(
            session_id="test-session-001",
            tenant_id="test-tenant",
            user_query="分析企业2024年度财务状况",
            report_title="年度财务分析报告",
            include_executive_summary=True,
            include_recommendations=True,
            format="markdown"
        )

        assert "metadata" in result
        assert "sections" in result
        assert "report_text" in result or "report_content" in result
        assert len(result["sections"]) >= 3


@pytest.mark.asyncio
async def test_summarize_report_no_completed_tasks():
    """测试无已完成任务时的报告生成"""
    from app.mcp.orchestrator_tools import summarize_final_report

    with patch('app.mcp.orchestrator_tools.TaskBlackboard') as MockBlackboard:
        mock_blackboard = MagicMock()
        MockBlackboard.return_value = mock_blackboard

        mock_blackboard.get_tasks_by_status = AsyncMock(return_value=[])
        mock_blackboard.get_all_shared_data = AsyncMock(return_value={})

        result = await summarize_final_report(
            session_id="test-session-empty",
            tenant_id="test-tenant",
            user_query="测试查询",
            format="markdown"
        )

        assert result["status"] == "warning"
        assert result["report"] is None
        assert "没有找到已完成的任务" in result["message"]


def test_create_orchestrator_tools():
    """测试工具创建函数"""
    from app.mcp.orchestrator_tools import create_orchestrator_tools

    tools = create_orchestrator_tools()

    assert len(tools) == 2
    tool_names = [t.name for t in tools]
    assert "breakdown_task_to_blackboard" in tool_names
    assert "summarize_final_report" in tool_names


def test_tools_registered_in_mcp():
    """测试工具已在 MCP 注册"""
    from app.mcp import get_unified_tools

    unified = get_unified_tools()
    all_tools = unified["all"]

    tool_names = [t.name for t in all_tools if hasattr(t, 'name')]

    assert "breakdown_task_to_blackboard" in tool_names
    assert "summarize_final_report" in tool_names


@pytest.mark.asyncio
async def test_orchestrator_workflow():
    """测试 Orchestrator 完整工作流"""
    from app.multi_agent_system.orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator(
        tenant_id="test-tenant",
        user_id="test-user"
    )

    orchestrator.context = MagicMock()
    orchestrator.context.session_id = "workflow-test-session"

    with patch.object(orchestrator, 'breakdown_task_to_blackboard') as mock_breakdown, \
         patch.object(orchestrator, 'summarize_final_report') as mock_summarize:

        mock_breakdown.return_value = {
            "status": "success",
            "created_tasks": [
                {"task_id": "task-1", "task_type": "finance_analysis"},
                {"task_id": "task-2", "task_type": "tax_calculation"}
            ],
            "summary": {"total_tasks": 2}
        }

        mock_summarize.return_value = {
            "status": "success",
            "report_content": "# 测试报告"
        }

        result = await orchestrator.execute_orchestrator_workflow(
            user_goal="分析企业年度财务",
            generate_report=True
        )

        assert result["status"] == "success"
        assert result["workflow"] == "orchestrator"
        assert len(result["task_ids"]) == 2
        assert result["report_result"] is not None
        assert "工作流完成" in result["message"]


def test_get_available_tools():
    """测试获取可用工具列表"""
    from app.multi_agent_system.orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator(
        tenant_id="test-tenant",
        user_id="test-user"
    )

    tools = orchestrator.get_available_tools()

    assert isinstance(tools, list)
    assert "breakdown_task_to_blackboard" in tools
    assert "summarize_final_report" in tools
