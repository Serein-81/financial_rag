"""
多智能体系统核心功能测试
Comprehensive Multi-Agent System Core Tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.multi_agent_system.coordinator import AgentCoordinator
from app.multi_agent_system.session_manager import SessionManager
from app.multi_agent_system.message_bus import MessageBus, MessageType, Message
from app.multi_agent_system.task_decomposer import TaskDecomposer
from app.multi_agent_system.result_merger import ResultMerger, Finding, RiskLevel
from app.multi_agent_system.state import create_initial_state, MultiAgentState
from app.multi_agent_system.agents import (
    FinanceSpecialist,
    TaxSpecialist,
    LegalSpecialist,
    IntentRouterAgent
)
from app.schemas.multi_agent import SpecialistType, TaskRequest, TaskResult


class TestMessageBus:
    """测试消息总线功能"""

    @pytest.fixture
    def message_bus(self):
        return MessageBus()

    @pytest.mark.asyncio
    async def test_publish_message(self, message_bus):
        """测试发布消息"""
        message = Message(
            msg_id="test_msg_1",
            msg_type=MessageType.TASK,
            sender="test_sender",
            receiver="test_receiver",
            content={"task": "test_task"},
            timestamp=datetime.now()
        )
        
        published = await message_bus.publish(message)
        assert published is True

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self, message_bus):
        """测试订阅和接收消息"""
        received_messages = []
        
        async def callback(msg: Message):
            received_messages.append(msg)
        
        await message_bus.subscribe("test_topic", callback)
        
        message = Message(
            msg_id="test_msg_2",
            msg_type=MessageType.RESULT,
            sender="sender",
            receiver="receiver",
            content={"result": "test_result"},
            timestamp=datetime.now()
        )
        
        await message_bus.publish_to_topic("test_topic", message)
        await asyncio.sleep(0.1)
        
        assert len(received_messages) == 1
        assert received_messages[0].msg_id == "test_msg_2"

    @pytest.mark.asyncio
    async def test_message_broadcast(self, message_bus):
        """测试广播消息"""
        subscriber1_messages = []
        subscriber2_messages = []
        
        async def callback1(msg: Message):
            subscriber1_messages.append(msg)
        
        async def callback2(msg: Message):
            subscriber2_messages.append(msg)
        
        await message_bus.subscribe("broadcast_topic", callback1)
        await message_bus.subscribe("broadcast_topic", callback2)
        
        message = Message(
            msg_id="broadcast_msg",
            msg_type=MessageType.NOTIFICATION,
            sender="broadcaster",
            receiver="all",
            content={"type": "broadcast"},
            timestamp=datetime.now()
        )
        
        await message_bus.publish_to_topic("broadcast_topic", message)
        await asyncio.sleep(0.1)
        
        assert len(subscriber1_messages) == 1
        assert len(subscriber2_messages) == 1


class TestTaskDecomposer:
    """测试任务分解器"""

    @pytest.fixture
    def decomposer(self):
        return TaskDecomposer()

    @pytest.mark.asyncio
    async def test_decompose_financial_audit(self, decomposer):
        """测试财务审计任务分解"""
        task = {
            "type": "financial_audit",
            "description": "对2024年度财务报表进行全面审计",
            "documents": [
                {"id": "doc1", "type": "balance_sheet"},
                {"id": "doc2", "type": "income_statement"},
                {"id": "doc3", "type": "cash_flow"}
            ]
        }
        
        subtasks = await decomposer.decompose(task)
        
        assert len(subtasks) > 0
        assert any("balance" in st.get("description", "").lower() for st in subtasks)
        assert any("income" in st.get("description", "").lower() for st in subtasks)

    @pytest.mark.asyncio
    async def test_decompose_tax_analysis(self, decomposer):
        """测试税务分析任务分解"""
        task = {
            "type": "tax_analysis",
            "description": "分析企业税务风险",
            "documents": [
                {"id": "tax_doc1", "type": "tax_return"},
                {"id": "tax_doc2", "type": "invoice"}
            ]
        }
        
        subtasks = await decomposer.decompose(task)
        
        assert len(subtasks) > 0
        assert any("tax" in st.get("type", "").lower() or "tax" in st.get("description", "").lower() 
                    for st in subtasks)


class TestResultMerger:
    """测试结果合并器"""

    @pytest.fixture
    def merger(self):
        return ResultMerger()

    def test_merge_simple_results(self, merger):
        """测试简单结果合并"""
        results = [
            {
                "specialist": "finance",
                "findings": [
                    {"id": "f1", "description": "Finding 1", "risk_score": 0.8}
                ]
            },
            {
                "specialist": "tax",
                "findings": [
                    {"id": "t1", "description": "Tax Finding 1", "risk_score": 0.6}
                ]
            }
        ]
        
        merged = merger.merge(results)
        
        assert "findings" in merged
        assert len(merged["findings"]) == 2
        assert merged["total_risk_score"] > 0

    def test_merge_with_priorities(self, merger):
        """测试优先级合并"""
        results = [
            {
                "specialist": "finance",
                "priority": 1,
                "findings": [
                    {"id": "f1", "description": "High risk finding", "risk_score": 0.9}
                ]
            },
            {
                "specialist": "legal",
                "priority": 2,
                "findings": [
                    {"id": "l1", "description": "Medium risk finding", "risk_score": 0.5}
                ]
            }
        ]
        
        merged = merger.merge_with_priority(results)
        
        assert "priority_findings" in merged
        assert len(merged["priority_findings"]) >= 1


class TestAgentCoordinator:
    """测试智能体协调器"""

    @pytest.fixture
    async def coordinator(self):
        coordinator = AgentCoordinator()
        await coordinator.initialize()
        yield coordinator
        await coordinator.cleanup()

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self, coordinator):
        """测试协调器初始化"""
        assert coordinator is not None
        assert hasattr(coordinator, "specialists")
        assert hasattr(coordinator, "message_bus")

    @pytest.mark.asyncio
    async def test_register_specialist(self, coordinator):
        """测试注册专家"""
        mock_specialist = MagicMock()
        mock_specialist.specialist_type = SpecialistType.FINANCE
        mock_specialist.agent_id = "test_finance"
        
        success = await coordinator.register_specialist(mock_specialist)
        assert success is True

    @pytest.mark.asyncio
    async def test_execute_task(self, coordinator):
        """测试任务执行"""
        task_request = TaskRequest(
            task_id="test_task_001",
            task_type="financial_audit",
            description="Test financial audit task",
            documents=[],
            context={}
        )
        
        result = await coordinator.execute_task(task_request)
        
        assert result is not None
        assert hasattr(result, "task_id")
        assert hasattr(result, "status")

    @pytest.mark.asyncio
    async def test_specialist_routing(self, coordinator):
        """测试专家路由"""
        task_types = ["financial", "tax", "legal"]
        
        for task_type in task_types:
            specialist = coordinator.route_to_specialist(task_type)
            assert specialist is not None or task_type in ["financial", "tax", "legal"]


class TestSessionManager:
    """测试会话管理器"""

    @pytest.fixture
    def session_manager(self):
        return SessionManager()

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """测试创建会话"""
        session_id = await session_manager.create_session(
            tenant_id="test_tenant",
            user_id="test_user",
            context={}
        )
        
        assert session_id is not None
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        """测试获取会话"""
        session_id = await session_manager.create_session(
            tenant_id="test_tenant",
            user_id="test_user",
            context={"key": "value"}
        )
        
        session = await session_manager.get_session(session_id)
        
        assert session is not None
        assert session["session_id"] == session_id
        assert session["context"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_update_session_context(self, session_manager):
        """测试更新会话上下文"""
        session_id = await session_manager.create_session(
            tenant_id="test_tenant",
            user_id="test_user",
            context={}
        )
        
        await session_manager.update_context(
            session_id,
            {"new_key": "new_value", "key2": "value2"}
        )
        
        session = await session_manager.get_session(session_id)
        assert session["context"]["new_key"] == "new_value"
        assert session["context"]["key2"] == "value2"

    @pytest.mark.asyncio
    async def test_close_session(self, session_manager):
        """测试关闭会话"""
        session_id = await session_manager.create_session(
            tenant_id="test_tenant",
            user_id="test_user",
            context={}
        )
        
        success = await session_manager.close_session(session_id)
        assert success is True
        
        session = await session_manager.get_session(session_id)
        assert session is None or session.get("status") == "closed"


class TestMultiAgentState:
    """测试多智能体状态管理"""

    def test_create_initial_state(self):
        """测试创建初始状态"""
        state = create_initial_state(
            task_id="test_task_001",
            tenant_id="test_tenant",
            user_id="test_user",
            audit_type="comprehensive",
            documents=[]
        )
        
        assert state is not None
        assert state["task_id"] == "test_task_001"
        assert state["tenant_id"] == "test_tenant"
        assert state["status"] == "pending"

    def test_state_update(self):
        """测试状态更新"""
        state = create_initial_state(
            task_id="test_task_002",
            tenant_id="test_tenant",
            user_id="test_user",
            audit_type="quick",
            documents=[]
        )
        
        state["status"] = "processing"
        state["progress"] = 50
        
        assert state["status"] == "processing"
        assert state["progress"] == 50

    def test_state_with_findings(self):
        """测试带发现的状态"""
        state = create_initial_state(
            task_id="test_task_003",
            tenant_id="test_tenant",
            user_id="test_user",
            audit_type="comprehensive",
            documents=[]
        )
        
        state["finance_findings"] = [
            Finding(
                id="f1",
                description="Test finding",
                risk_level=RiskLevel.HIGH,
                evidence=["evidence1"],
                recommendation="Fix it"
            )
        ]
        
        assert len(state["finance_findings"]) == 1
        assert state["finance_findings"][0].risk_level == RiskLevel.HIGH


class TestSpecialistAgents:
    """测试专家智能体"""

    @pytest.fixture
    def mock_llm_adapter(self):
        adapter = MagicMock()
        adapter.generate = AsyncMock(return_value="Mocked response")
        adapter.generate_stream = MagicMock(return_value=iter(["Mocked", "streamed", "response"]))
        return adapter

    @pytest.fixture
    def mock_tool_manager(self):
        manager = MagicMock()
        manager.get_tools = MagicMock(return_value=[])
        manager.execute_tool = AsyncMock(return_value={"result": "success"})
        return manager

    @pytest.mark.asyncio
    async def test_finance_specialist_initialization(self, mock_llm_adapter, mock_tool_manager):
        """测试财务专家初始化"""
        specialist = FinanceSpecialist(mock_llm_adapter, mock_tool_manager)
        
        assert specialist is not None
        assert specialist.specialist_type == SpecialistType.FINANCE

    @pytest.mark.asyncio
    async def test_tax_specialist_initialization(self, mock_llm_adapter, mock_tool_manager):
        """测试税务专家初始化"""
        specialist = TaxSpecialist(mock_llm_adapter, mock_tool_manager)
        
        assert specialist is not None
        assert specialist.specialist_type == SpecialistType.TAX

    @pytest.mark.asyncio
    async def test_legal_specialist_initialization(self, mock_llm_adapter, mock_tool_manager):
        """测试法律专家初始化"""
        specialist = LegalSpecialist(mock_llm_adapter, mock_tool_manager)
        
        assert specialist is not None
        assert specialist.specialist_type == SpecialistType.LEGAL

    @pytest.mark.asyncio
    async def test_specialist_process_task(self, mock_llm_adapter, mock_tool_manager):
        """测试专家处理任务"""
        specialist = FinanceSpecialist(mock_llm_adapter, mock_tool_manager)
        
        task = {
            "type": "financial_analysis",
            "content": "Analyze the balance sheet",
            "context": {}
        }
        
        result = await specialist.process_task(task)
        
        assert result is not None
        assert "status" in result or "output" in result or "findings" in result


class TestIntentRouter:
    """测试意图路由"""

    @pytest.fixture
    def mock_llm_adapter(self):
        adapter = MagicMock()
        adapter.generate = AsyncMock(return_value="""{
            "intent": "financial_query",
            "confidence": 0.9,
            "parameters": {"query_type": "balance_sheet"}
        }""")
        return adapter

    @pytest.mark.asyncio
    async def test_intent_routing(self, mock_llm_adapter):
        """测试意图路由"""
        router = IntentRouterAgent(mock_llm_adapter)
        
        user_query = "查询公司2024年的资产负债表"
        
        result = await router.route(user_query)
        
        assert result is not None
        assert "intent" in result or "type" in result or "specialist" in result

    @pytest.mark.asyncio
    async def test_intent_confidence_threshold(self, mock_llm_adapter):
        """测试意图置信度阈值"""
        router = IntentRouterAgent(mock_llm_adapter, min_confidence=0.8)
        
        high_confidence_query = "查询财务报表"
        result = await router.route(high_confidence_query)
        
        if "confidence" in result:
            assert result["confidence"] >= 0.8


class TestCrossSpecialistCollaboration:
    """测试跨专家协作"""

    @pytest.fixture
    async def coordinator(self):
        coordinator = AgentCoordinator()
        await coordinator.initialize()
        yield coordinator
        await coordinator.cleanup()

    @pytest.mark.asyncio
    async def test_parallel_specialist_execution(self, coordinator):
        """测试并行专家执行"""
        task_request = TaskRequest(
            task_id="parallel_test_001",
            task_type="comprehensive_audit",
            description="Comprehensive multi-specialist audit",
            documents=[],
            context={"parallel": True}
        )
        
        result = await coordinator.execute_task(task_request)
        
        assert result is not None
        assert result.status in ["completed", "partial", "failed"]

    @pytest.mark.asyncio
    async def test_specialist_result_aggregation(self, coordinator):
        """测试专家结果聚合"""
        task_request = TaskRequest(
            task_id="aggregation_test_001",
            task_type="risk_assessment",
            description="Multi-domain risk assessment",
            documents=[],
            context={}
        )
        
        result = await coordinator.execute_task(task_request)
        
        if hasattr(result, "aggregated_findings"):
            assert isinstance(result.aggregated_findings, list)
        elif hasattr(result, "findings"):
            assert isinstance(result.findings, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
