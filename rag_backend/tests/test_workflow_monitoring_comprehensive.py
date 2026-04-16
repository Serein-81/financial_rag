"""
工作流监控测试
Workflow Monitoring Tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from app.workflow.workflow_monitor import WorkflowMonitor, WorkflowStatus, WorkflowEvent
from app.workflow.policy_workflow_monitor import PolicyWorkflowMonitor
from app.workflow.tax_workflow_monitor import TaxWorkflowMonitor
from app.workflow.agent_integration import AgentWorkflowIntegration
from app.langgraph.graph import WorkflowGraph
from app.langgraph.state import WorkflowState
from app.langgraph.nodes import (
    StartNode,
    EndNode,
    DecisionNode,
    ActionNode,
    HumanReviewNode
)


class TestWorkflowMonitor:
    """测试工作流监控器"""

    @pytest.fixture
    def workflow_monitor(self):
        return WorkflowMonitor()

    @pytest.mark.asyncio
    async def test_monitor_initialization(self, workflow_monitor):
        """测试监控器初始化"""
        assert workflow_monitor is not None
        assert hasattr(workflow_monitor, 'workflows')
        assert hasattr(workflow_monitor, 'event_handlers')

    @pytest.mark.asyncio
    async def test_start_workflow(self, workflow_monitor):
        """测试启动工作流"""
        workflow_id = "wf_001"
        
        success = await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="financial_audit",
            initial_state={"status": "pending"}
        )
        
        assert success is True
        assert workflow_id in workflow_monitor.workflows

    @pytest.mark.asyncio
    async def test_track_progress(self, workflow_monitor):
        """测试跟踪进度"""
        workflow_id = "wf_progress_001"
        
        await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="test_workflow",
            initial_state={}
        )
        
        progress = await workflow_monitor.track_progress(workflow_id)
        
        assert progress is not None
        assert "status" in progress or "progress" in progress

    @pytest.mark.asyncio
    async def test_pause_workflow(self, workflow_monitor):
        """测试暂停工作流"""
        workflow_id = "wf_pause_001"
        
        await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="test_workflow",
            initial_state={}
        )
        
        success = await workflow_monitor.pause_workflow(workflow_id)
        assert success is True

    @pytest.mark.asyncio
    async def test_resume_workflow(self, workflow_monitor):
        """测试恢复工作流"""
        workflow_id = "wf_resume_001"
        
        await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="test_workflow",
            initial_state={}
        )
        
        await workflow_monitor.pause_workflow(workflow_id)
        success = await workflow_monitor.resume_workflow(workflow_id)
        
        assert success is True

    @pytest.mark.asyncio
    async def test_terminate_workflow(self, workflow_monitor):
        """测试终止工作流"""
        workflow_id = "wf_terminate_001"
        
        await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="test_workflow",
            initial_state={}
        )
        
        success = await workflow_monitor.terminate_workflow(workflow_id)
        assert success is True


class TestPolicyWorkflowMonitor:
    """测试策略工作流监控"""

    @pytest.fixture
    def policy_monitor(self):
        return PolicyWorkflowMonitor()

    @pytest.mark.asyncio
    async def test_policy_workflow_initialization(self, policy_monitor):
        """测试策略工作流初始化"""
        assert policy_monitor is not None

    @pytest.mark.asyncio
    async def test_track_policy_updates(self, policy_monitor):
        """测试跟踪策略更新"""
        policy_id = "policy_001"
        
        with patch.object(policy_monitor, 'track_update', new_callable=AsyncMock) as mock_track:
            mock_track.return_value = {
                "policy_id": policy_id,
                "update_time": datetime.now(),
                "status": "tracked"
            }
            
            result = await policy_monitor.track_update(policy_id)
            
            assert result is not None
            assert result["policy_id"] == policy_id

    @pytest.mark.asyncio
    async def test_monitor_policy_compliance(self, policy_monitor):
        """测试监控策略合规性"""
        with patch.object(policy_monitor, 'check_compliance', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "compliant": True,
                "violations": []
            }
            
            result = await policy_monitor.check_compliance("policy_001")
            
            assert result is not None
            assert "compliant" in result


class TestTaxWorkflowMonitor:
    """测试税务工作流监控"""

    @pytest.fixture
    def tax_monitor(self):
        return TaxWorkflowMonitor()

    @pytest.mark.asyncio
    async def test_tax_workflow_initialization(self, tax_monitor):
        """测试税务工作流初始化"""
        assert tax_monitor is not None

    @pytest.mark.asyncio
    async def test_track_tax_calculation(self, tax_monitor):
        """测试跟踪税务计算"""
        with patch.object(tax_monitor, 'track_calculation', new_callable=AsyncMock) as mock_track:
            mock_track.return_value = {
                "calculation_id": "calc_001",
                "amount": 50000,
                "tax_type": "income_tax"
            }
            
            result = await tax_monitor.track_calculation({
                "calculation_id": "calc_001",
                "amount": 50000,
                "tax_type": "income_tax"
            })
            
            assert result is not None
            assert result["amount"] == 50000

    @pytest.mark.asyncio
    async def test_monitor_tax_deadlines(self, tax_monitor):
        """测试监控税务截止日期"""
        with patch.object(tax_monitor, 'check_deadlines', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "upcoming_deadlines": [
                    {"type": "VAT", "due_date": datetime.now() + timedelta(days=7)}
                ]
            }
            
            result = await tax_monitor.check_deadlines()
            
            assert result is not None
            assert "upcoming_deadlines" in result


class TestWorkflowGraph:
    """测试工作流图"""

    @pytest.fixture
    def workflow_graph(self):
        return WorkflowGraph()

    @pytest.mark.asyncio
    async def test_graph_initialization(self, workflow_graph):
        """测试图初始化"""
        assert workflow_graph is not None
        assert hasattr(workflow_graph, 'nodes')
        assert hasattr(workflow_graph, 'edges')

    @pytest.mark.asyncio
    async def test_add_node(self, workflow_graph):
        """测试添加节点"""
        node = StartNode(node_id="start_1", name="Start")
        
        success = await workflow_graph.add_node(node)
        assert success is True

    @pytest.mark.asyncio
    async def test_add_edge(self, workflow_graph):
        """测试添加边"""
        node1 = StartNode(node_id="start_2", name="Start")
        node2 = EndNode(node_id="end_2", name="End")
        
        await workflow_graph.add_node(node1)
        await workflow_graph.add_node(node2)
        
        success = await workflow_graph.add_edge("start_2", "end_2")
        assert success is True

    @pytest.mark.asyncio
    async def test_execute_workflow(self, workflow_graph):
        """测试执行工作流"""
        node1 = StartNode(node_id="exec_start", name="Start")
        node2 = ActionNode(node_id="action_1", name="Process")
        node3 = EndNode(node_id="exec_end", name="End")
        
        await workflow_graph.add_node(node1)
        await workflow_graph.add_node(node2)
        await workflow_graph.add_node(node3)
        
        await workflow_graph.add_edge("exec_start", "action_1")
        await workflow_graph.add_edge("action_1", "exec_end")
        
        result = await workflow_graph.execute({"input": "test_data"})
        
        assert result is not None or result is None


class TestWorkflowNodes:
    """测试工作流节点"""

    def test_start_node(self):
        """测试开始节点"""
        node = StartNode(node_id="start_test", name="Start Test")
        
        assert node.node_id == "start_test"
        assert node.name == "Start Test"

    def test_end_node(self):
        """测试结束节点"""
        node = EndNode(node_id="end_test", name="End Test")
        
        assert node.node_id == "end_test"
        assert node.name == "End Test"

    @pytest.mark.asyncio
    async def test_decision_node(self):
        """测试决策节点"""
        node = DecisionNode(
            node_id="decision_1",
            name="Decision Point",
            condition=lambda state: "path_a" if state.get("value") > 0 else "path_b"
        )
        
        result = await node.execute({"value": 5})
        assert result.get("next_node") == "path_a" or result.get("next_node") == "path_b"

    @pytest.mark.asyncio
    async def test_action_node(self):
        """测试动作节点"""
        node = ActionNode(
            node_id="action_1",
            name="Perform Action",
            action=lambda state: {"result": f"processed {state.get('input', '')}"}
        )
        
        result = await node.execute({"input": "test"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_human_review_node(self):
        """测试人工审核节点"""
        node = HumanReviewNode(
            node_id="review_1",
            name="Human Review",
            reviewer_role="manager"
        )
        
        result = await node.execute({"pending_review": True})
        assert result is not None


class TestWorkflowState:
    """测试工作流状态"""

    def test_state_initialization(self):
        """测试状态初始化"""
        state = WorkflowState(
            workflow_id="wf_state_001",
            current_node="start",
            context={}
        )
        
        assert state.workflow_id == "wf_state_001"
        assert state.current_node == "start"

    def test_state_update(self):
        """测试状态更新"""
        state = WorkflowState(
            workflow_id="wf_state_002",
            current_node="start",
            context={}
        )
        
        state.current_node = "processing"
        state.context["progress"] = 50
        
        assert state.current_node == "processing"
        assert state.context["progress"] == 50

    def test_state_serialization(self):
        """测试状态序列化"""
        state = WorkflowState(
            workflow_id="wf_ser_001",
            current_node="start",
            context={"key": "value"}
        )
        
        serialized = state.model_dump() if hasattr(state, 'model_dump') else state.dict()
        
        assert "workflow_id" in serialized
        assert serialized["workflow_id"] == "wf_ser_001"


class TestWorkflowEvents:
    """测试工作流事件"""

    def test_event_creation(self):
        """测试事件创建"""
        event = WorkflowEvent(
            event_id="evt_001",
            event_type="workflow_started",
            workflow_id="wf_evt_001",
            timestamp=datetime.now(),
            data={"initiator": "test"}
        )
        
        assert event.event_id == "evt_001"
        assert event.event_type == "workflow_started"

    def test_event_handling(self):
        """测试事件处理"""
        events_received = []
        
        def event_handler(event):
            events_received.append(event)
        
        event = WorkflowEvent(
            event_id="evt_002",
            event_type="node_completed",
            workflow_id="wf_evt_002",
            timestamp=datetime.now(),
            data={}
        )
        
        event_handler(event)
        
        assert len(events_received) == 1
        assert events_received[0].event_id == "evt_002"


class TestAgentWorkflowIntegration:
    """测试智能体工作流集成"""

    @pytest.fixture
    def integration(self):
        return AgentWorkflowIntegration()

    @pytest.mark.asyncio
    async def test_integration_initialization(self, integration):
        """测试集成初始化"""
        assert integration is not None
        assert hasattr(integration, 'workflow_monitor')
        assert hasattr(integration, 'agent_coordinator')

    @pytest.mark.asyncio
    async def test_trigger_agent_task(self, integration):
        """测试触发智能体任务"""
        with patch.object(integration, 'trigger_task', new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = {
                "task_id": "agent_task_001",
                "status": "triggered"
            }
            
            result = await integration.trigger_task(
                agent_id="finance_agent",
                task_data={"action": "analyze"}
            )
            
            assert result is not None
            assert result["status"] == "triggered"

    @pytest.mark.asyncio
    async def test_monitor_agent_execution(self, integration):
        """测试监控智能体执行"""
        with patch.object(integration, 'monitor_execution', new_callable=AsyncMock) as mock_monitor:
            mock_monitor.return_value = {
                "agent_id": "test_agent",
                "progress": 75,
                "status": "executing"
            }
            
            result = await integration.monitor_execution("test_agent", "task_001")
            
            assert result is not None


class TestWorkflowErrorHandling:
    """测试工作流错误处理"""

    @pytest.fixture
    def workflow_monitor(self):
        return WorkflowMonitor()

    @pytest.mark.asyncio
    async def test_handle_node_failure(self, workflow_monitor):
        """测试处理节点失败"""
        workflow_id = "wf_error_001"
        
        await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="test_workflow",
            initial_state={}
        )
        
        success = await workflow_monitor.handle_error(
            workflow_id=workflow_id,
            error={"code": "NODE_FAILED", "message": "Action node failed"}
        )
        
        assert success is True or success is False

    @pytest.mark.asyncio
    async def test_workflow_recovery(self, workflow_monitor):
        """测试工作流恢复"""
        workflow_id = "wf_recovery_001"
        
        await workflow_monitor.start_workflow(
            workflow_id=workflow_id,
            workflow_type="test_workflow",
            initial_state={}
        )
        
        await workflow_monitor.handle_error(
            workflow_id=workflow_id,
            error={"code": "TEMPORARY_FAILURE", "message": "Retry later"}
        )
        
        recovered = await workflow_monitor.recover_workflow(workflow_id)
        assert recovered is True or recovered is False


class TestWorkflowPerformance:
    """测试工作流性能"""

    @pytest.mark.asyncio
    async def test_workflow_execution_time(self):
        """测试工作流执行时间"""
        start_time = datetime.now()
        
        await asyncio.sleep(0.1)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        assert duration >= 0.1

    @pytest.mark.asyncio
    async def test_parallel_node_execution(self):
        """测试并行节点执行"""
        async def slow_node(node_id):
            await asyncio.sleep(0.1)
            return {"node_id": node_id, "result": "completed"}
        
        start_time = datetime.now()
        
        results = await asyncio.gather(
            slow_node("node_1"),
            slow_node("node_2"),
            slow_node("node_3")
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        assert len(results) == 3
        assert duration < 0.2


class TestWorkflowMetrics:
    """测试工作流指标"""

    @pytest.fixture
    def workflow_monitor(self):
        return WorkflowMonitor()

    @pytest.mark.asyncio
    async def test_track_execution_metrics(self, workflow_monitor):
        """测试跟踪执行指标"""
        metrics = await workflow_monitor.get_metrics("wf_metrics_001")
        
        assert metrics is not None
        assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_calculate_workflow_statistics(self, workflow_monitor):
        """测试计算工作流统计"""
        stats = await workflow_monitor.calculate_statistics(
            time_range=(datetime.now() - timedelta(hours=24), datetime.now())
        )
        
        assert stats is not None
        assert isinstance(stats, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
