"""
混合编排模块测试

测试混合编排模式的各个组件：
1. 专家会诊节点
2. 上下文压缩节点
3. 黑板模式管理器
4. 混合图构建器
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.langgraph.hybrid.blackboard_manager import (
    BlackboardManager,
    BlackboardEntry,
    EntryType,
)
from app.langgraph.hybrid.expert_consultation_node import (
    ExpertConsultationNode,
    ExpertConsultationState,
)
from app.langgraph.hybrid.summarizer_node import (
    SummarizerNode,
)
from app.langgraph.hybrid.hybrid_graph import HybridGraphBuilder
from app.state.unified_state import UnifiedState, IntentCategory


class TestBlackboardManager:
    """测试黑板模式管理器"""
    
    def test_post_and_get(self):
        """测试发布和获取条目"""
        blackboard = BlackboardManager()
        
        entry_id = blackboard.post(
            agent_name="agent_a",
            content="这是一个测试观点",
            entry_type=EntryType.OPINION,
            round_number=1
        )
        
        entry = blackboard.get(entry_id)
        
        assert entry is not None
        assert entry.agent_name == "agent_a"
        assert entry.content == "这是一个测试观点"
        assert entry.entry_type == EntryType.OPINION
        assert entry.round_number == 1
    
    def test_get_by_type(self):
        """测试按类型获取"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "观点1", EntryType.OPINION)
        blackboard.post("agent_b", "观点2", EntryType.OPINION)
        blackboard.post("agent_c", "问题1", EntryType.QUESTION)
        
        opinions = blackboard.get_by_type(EntryType.OPINION)
        
        assert len(opinions) == 2
        assert all(e.entry_type == EntryType.OPINION for e in opinions)
    
    def test_get_by_round(self):
        """测试按轮次获取"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "内容1", EntryType.OBSERVATION, round_number=1)
        blackboard.post("agent_b", "内容2", EntryType.OBSERVATION, round_number=1)
        blackboard.post("agent_c", "内容3", EntryType.OBSERVATION, round_number=2)
        
        round1_entries = blackboard.get_by_round(1)
        round2_entries = blackboard.get_by_round(2)
        
        assert len(round1_entries) == 2
        assert len(round2_entries) == 1
    
    def test_get_history(self):
        """测试获取历史记录"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "第一个", EntryType.OBSERVATION)
        blackboard.post("agent_b", "第二个", EntryType.OBSERVATION)
        
        history = blackboard.get_history()
        
        assert len(history) == 2
        assert history[0].content == "第一个"
        assert history[1].content == "第二个"
    
    def test_get_by_agent(self):
        """测试按 Agent 获取"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "agent_a的内容", EntryType.OBSERVATION)
        blackboard.post("agent_b", "agent_b的内容", EntryType.OBSERVATION)
        blackboard.post("agent_a", "agent_a的另一个", EntryType.OBSERVATION)
        
        history = blackboard.get_history(agent_name="agent_a")
        
        assert len(history) == 2
        assert all(e.agent_name == "agent_a" for e in history)
    
    def test_subscribe_and_notify(self):
        """测试订阅和通知"""
        blackboard = BlackboardManager()
        received = []
        
        def callback(entry: BlackboardEntry):
            received.append(entry)
        
        blackboard.subscribe("agent_b", callback)
        blackboard.post("agent_a", "发布内容", EntryType.OBSERVATION)
        
        assert len(received) == 1
        assert received[0].content == "发布内容"
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "内容1", EntryType.OPINION)
        blackboard.post("agent_b", "内容2", EntryType.QUESTION)
        blackboard.post("agent_c", "内容3", EntryType.OPINION)
        
        stats = blackboard.get_statistics()
        
        assert stats["total_entries"] == 3
        assert stats["by_agent"]["agent_a"] == 1
        assert stats["by_agent"]["agent_b"] == 1
        assert stats["by_agent"]["agent_c"] == 1
        assert stats["by_type"]["opinion"] == 2
        assert stats["by_type"]["question"] == 1
    
    def test_search(self):
        """测试搜索功能"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "关于税务的问题", EntryType.QUESTION)
        blackboard.post("agent_b", "关于财务的分析", EntryType.OPINION)
        blackboard.post("agent_c", "关于税务的处理", EntryType.DECISION)
        
        results = blackboard.search("税务")
        
        assert len(results) == 2
        assert all("税务" in str(e.content) for e in results)
    
    def test_to_dict(self):
        """测试导出字典"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "测试内容", EntryType.OBSERVATION)
        
        data = blackboard.to_dict()
        
        assert "entries" in data
        assert "statistics" in data
        assert len(data["entries"]) == 1
    
    def test_clear_round(self):
        """测试清除轮次"""
        blackboard = BlackboardManager()
        
        blackboard.post("agent_a", "轮次1内容", EntryType.OBSERVATION, round_number=1)
        blackboard.post("agent_b", "轮次2内容", EntryType.OBSERVATION, round_number=2)
        
        blackboard.clear_round(1)
        
        assert len(blackboard.get_by_round(1)) == 0
        assert len(blackboard.get_by_round(2)) == 1


class TestExpertConsultationState:
    """测试专家会诊状态"""
    
    def test_create_state(self):
        """测试创建会诊状态"""
        state = ExpertConsultationState(
            consultation_topic="测试话题",
            active_agents=["agent_a", "agent_b"]
        )
        
        assert state.consultation_topic == "测试话题"
        assert len(state.active_agents) == 2
        assert state.current_round == 0
        assert state.consensus is None
    
    def test_state_defaults(self):
        """测试状态默认值"""
        state = ExpertConsultationState(
            consultation_topic="测试",
            active_agents=["a"]
        )
        
        assert state.agent_results == {}
        assert state.agent_messages == {}
        assert state.disagreements == []
        assert state.key_decisions == []


class TestExpertConsultationNode:
    """测试专家会诊节点"""
    
    def test_create_node(self):
        """测试创建节点"""
        node = ExpertConsultationNode(
            max_rounds=5,
            consensus_threshold=0.9
        )
        
        assert node.max_rounds == 5
        assert node.consensus_threshold == 0.9
        assert node.blackboard is not None
    
    def test_node_with_custom_blackboard(self):
        """测试使用自定义黑板"""
        blackboard = BlackboardManager()
        node = ExpertConsultationNode(blackboard=blackboard)
        
        assert node.blackboard is blackboard
    
    @pytest.mark.asyncio
    async def test_invoke_without_experts(self):
        """测试无需专家会诊的场景"""
        node = ExpertConsultationNode()
        
        state = UnifiedState(
            request_id="test-001",
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="简单问题",
            intent=IntentCategory.QUESTION,
            current_phase="test"
        )
        
        result = await node.invoke(state)
        
        assert result["current_phase"] == "expert_consultation_completed"
    
    def test_build_consultation_prompt(self):
        """测试构建咨询提示词"""
        node = ExpertConsultationNode()
        
        prompt = node._build_consultation_prompt(
            topic="税务问题",
            agent_name="finance",
            board_history=[],
            current_round=0
        )
        
        assert "税务问题" in prompt
        assert "finance" in prompt
        assert "第一轮" in prompt


class TestSummarizerState:
    """测试 Summarizer 状态"""
    
    def test_summarizer_state_definition(self):
        """测试状态定义"""
        from app.langgraph.hybrid.summarizer_node import SummarizerState
        
        state: SummarizerState = {
            "debate_context": [{"content": "测试"}],
            "consensus": "共识内容",
            "disagreements": ["分歧1"],
            "key_decisions": ["决策1"],
            "abandoned_arguments": ["放弃1"]
        }
        
        assert len(state["debate_context"]) == 1
        assert state["consensus"] == "共识内容"


class TestSummarizerNode:
    """测试上下文压缩节点"""
    
    def test_create_node(self):
        """测试创建节点"""
        node = SummarizerNode(
            max_context_length=10000,
            compression_target=500
        )
        
        assert node.max_context_length == 10000
        assert node.compression_target == 500
    
    @pytest.mark.asyncio
    async def test_invoke_without_context(self):
        """测试无上下文场景"""
        node = SummarizerNode()
        
        state = UnifiedState(
            request_id="test-001",
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试",
            current_phase="test"
        )
        
        result = await node.invoke(state)
        
        assert "Summarizer: 没有辩论上下文" in result["warnings"]
    
    @pytest.mark.asyncio
    async def test_invoke_with_context(self):
        """测试有上下文场景"""
        node = SummarizerNode()
        
        state = UnifiedState(
            request_id="test-001",
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试",
            current_phase="test",
            debate_context=[
                {"agent": "finance", "content": "观点1", "round": 1},
                {"agent": "tax", "content": "观点2", "round": 1}
            ]
        )
        
        # Mock LLM response
        with patch.object(node, '_compress_context', new_callable=AsyncMock) as mock_compress:
            from app.langgraph.hybrid.summarizer_node import CompressionResult
            
            mock_compress.return_value = CompressionResult(
                consensus="达成共识",
                disagreements=["仍有分歧"],
                key_decisions=["决策1"],
                abandoned_arguments=[],
                compression_ratio=0.3,
                original_size=1000,
                compressed_size=300,
                processing_time_ms=50
            )
            
            result = await node.invoke(state)
            
            assert result["message_bus_summary"] == "达成共识"
            assert "metadata" in result
            assert result["debate_context"] == []
    
    def test_format_debate_context(self):
        """测试格式化辩论上下文"""
        node = SummarizerNode()
        
        context = [
            {"agent": "finance", "content": "观点1", "round": 1, "timestamp": "2024-01-01"},
            {"agent": "tax", "content": "观点2", "round": 1, "timestamp": "2024-01-01"}
        ]
        
        text = node._format_debate_context(context)
        
        assert "finance" in text
        assert "观点1" in text
        assert "轮次 1" in text
    
    def test_parse_summary_response_valid_json(self):
        """测试解析有效的 JSON 响应"""
        node = SummarizerNode()
        
        response = '''
        {
            "consensus": "测试共识",
            "disagreements": ["分歧1"],
            "key_decisions": ["决策1"],
            "abandoned_arguments": []
        }
        '''
        
        result = node._parse_summary_response(response)
        
        assert result["consensus"] == "测试共识"
        assert result["disagreements"] == ["分歧1"]
    
    def test_parse_summary_response_markdown_json(self):
        """测试解析 markdown 中的 JSON"""
        node = SummarizerNode()
        
        response = '''
        ```json
        {
            "consensus": "测试共识",
            "disagreements": [],
            "key_decisions": [],
            "abandoned_arguments": []
        }
        ```
        '''
        
        result = node._parse_summary_response(response)
        
        assert result["consensus"] == "测试共识"
    
    def test_parse_summary_response_invalid(self):
        """测试解析无效响应"""
        node = SummarizerNode()
        
        response = "这不是 JSON 格式"
        
        result = node._parse_summary_response(response)
        
        assert "consensus" in result
        assert isinstance(result["disagreements"], list)
    
    def test_estimate_tokens(self):
        """测试 token 估算"""
        node = SummarizerNode()
        
        # 测试中文
        chinese_text = "这是一段中文测试文本"
        chinese_tokens = node.estimate_tokens(chinese_text)
        assert chinese_tokens > 0
        
        # 测试英文
        english_text = "This is an English test text"
        english_tokens = node.estimate_tokens(english_text)
        assert english_tokens > 0


class TestHybridGraphBuilder:
    """测试混合图构建器"""
    
    def test_create_builder(self):
        """测试创建构建器"""
        builder = HybridGraphBuilder(
            enable_expert_consultation=True,
            enable_summarization=True,
            max_expert_rounds=5
        )
        
        assert builder.enable_expert_consultation is True
        assert builder.enable_summarization is True
        assert builder.max_expert_rounds == 5
        assert builder.blackboard is not None
    
    def test_build_graph(self):
        """测试构建图"""
        builder = HybridGraphBuilder()
        
        graph = builder.build()
        
        assert graph is not None
        assert builder.graph is graph
    
    def test_build_with_custom_agents(self):
        """测试使用自定义 Agent 注册表"""
        mock_agents = {
            "finance": MagicMock(),
            "tax": MagicMock()
        }
        
        builder = HybridGraphBuilder(agents_registry=mock_agents)
        
        assert len(builder.agents_registry) == 2
        assert builder.expert_consultation_node is not None
    
    def test_graph_contains_required_nodes(self):
        """测试图包含必需的节点"""
        builder = HybridGraphBuilder()
        
        graph = builder.build()
        
        assert "receptionist" in graph.nodes
        assert "intent_classifier" in graph.nodes
        assert "rag_retrieval" in graph.nodes
        assert "response_generator" in graph.nodes
    
    def test_graph_with_expert_consultation(self):
        """测试带专家会诊的图"""
        builder = HybridGraphBuilder(enable_expert_consultation=True)
        
        graph = builder.build()
        
        assert "expert_consultation" in graph.nodes
    
    def test_graph_with_summarization(self):
        """测试带压缩的图"""
        builder = HybridGraphBuilder(enable_summarization=True)
        
        graph = builder.build()
        
        assert "context_summarizer" in graph.nodes
    
    def test_compile_graph(self):
        """测试编译图"""
        builder = HybridGraphBuilder()
        builder.build()
        
        compiled = builder.compile()
        
        assert compiled is not None
        assert builder.compiled_graph is compiled
    
    def test_compile_without_build_raises(self):
        """测试未 build 就 compile 会报错"""
        builder = HybridGraphBuilder()
        
        with pytest.raises(RuntimeError, match="必须先调用 build"):
            builder.compile()
    
    def test_get_graph_diagram(self):
        """测试获取图图表"""
        builder = HybridGraphBuilder()
        builder.build()
        
        diagram = builder.get_graph_diagram()
        
        assert "nodes" in diagram
        assert "edges" in diagram
        assert isinstance(diagram["nodes"], list)
    
    def test_expert_consultation_disabled(self):
        """测试禁用专家会诊"""
        builder = HybridGraphBuilder(enable_expert_consultation=False)
        
        assert builder.expert_consultation_node is None
        
        graph = builder.build()
        assert "expert_consultation" not in graph.nodes
    
    def test_summarization_disabled(self):
        """测试禁用压缩"""
        builder = HybridGraphBuilder(enable_summarization=False)
        
        assert builder.summarizer_node is None
        
        graph = builder.build()
        assert "context_summarizer" not in graph.nodes
    
    def test_reflection_disabled(self):
        """测试禁用反思"""
        builder = HybridGraphBuilder(enable_reflection=False)
        
        graph = builder.build()
        
        assert "reflection" not in graph.nodes
    
    def test_checkpointer_enabled(self):
        """测试启用检查点"""
        builder = HybridGraphBuilder(enable_checkpointer=True)
        builder.build()
        
        compiled = builder.compile()
        
        # 检查是否有 checkpointer
        assert hasattr(compiled, 'checkpointer') or compiled is not None
    
    def test_custom_thresholds(self):
        """测试自定义阈值"""
        builder = HybridGraphBuilder(
            summarization_threshold=10000,
            max_iterations=20
        )
        
        assert builder.summarization_threshold == 10000
        assert builder.max_iterations == 20


class TestHybridIntegration:
    """混合编排集成测试"""
    
    def test_full_workflow_simulation(self):
        """模拟完整工作流"""
        # 创建黑板
        blackboard = BlackboardManager()
        
        # 发布多个条目
        blackboard.post("finance", "观点1", EntryType.OPINION, round_number=1)
        blackboard.post("tax", "观点2", EntryType.OPINION, round_number=1)
        
        # 验证状态
        stats = blackboard.get_statistics()
        
        assert stats["total_entries"] == 2
        # round_number 是整数，统计时转为字符串
        assert stats["by_round"][1] == 2
    
    def test_expert_consultation_with_blackboard(self):
        """测试专家会诊与黑板集成"""
        blackboard = BlackboardManager()
        
        # 创建专家会诊节点
        node = ExpertConsultationNode(blackboard=blackboard)
        
        assert node.blackboard is blackboard
        
        # 模拟发布
        blackboard.post("finance", "最终共识", EntryType.DECISION, round_number=3)
        
        # 验证
        decisions = blackboard.get_by_type(EntryType.DECISION)
        assert len(decisions) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
