"""
统一状态管理模块测试

测试统一状态定义、工厂、验证器和管理器的功能
"""

import pytest
from datetime import datetime

from app.state.unified_state import (
    UnifiedState,
    IntentCategory,
    SpecialistType,
    QualityLevel,
    OrchestrationMode,
    ExecutionStatus,
    TaskPriority,
    AgentMessage,
    SpecialistResult,
    ReflectionResult,
)
from app.state.state_factory import StateFactory
from app.state.state_validator import (
    StateValidator,
    ValidationResult,
)
from app.state.state_manager import StateManager, StateCache


class TestUnifiedState:
    """
    统一状态定义测试
    
    测试 UnifiedState 的类型定义和枚举值
    """
    
    def test_intent_category_enum(self):
        """测试意图分类枚举"""
        assert IntentCategory.RAG_RETRIEVAL.value == "rag_retrieval"
        assert IntentCategory.SINGLE_SPECIALIST.value == "single_specialist"
        assert IntentCategory.MULTI_SPECIALIST.value == "multi_specialist"
        assert IntentCategory.DIRECT_ANSWER.value == "direct_answer"
        assert IntentCategory.HUMAN_REVIEW.value == "human_review"
        assert IntentCategory.EXPERT_CONSULTATION.value == "expert_consultation"
        assert IntentCategory.UNKNOWN.value == "unknown"
    
    def test_specialist_type_enum(self):
        """测试专家类型枚举"""
        assert SpecialistType.FINANCE.value == "finance"
        assert SpecialistType.TAX.value == "tax"
        assert SpecialistType.LEGAL.value == "legal"
        assert SpecialistType.REPORT.value == "report"
        assert SpecialistType.REFLECTION.value == "reflection"
        assert SpecialistType.COORDINATOR.value == "coordinator"
    
    def test_orchestration_mode_enum(self):
        """测试编排模式枚举"""
        assert OrchestrationMode.LANGGRAPH.value == "langgraph"
        assert OrchestrationMode.MESSAGE_BUS.value == "message_bus"
        assert OrchestrationMode.HYBRID.value == "hybrid"
    
    def test_quality_level_enum(self):
        """测试质量等级枚举"""
        assert QualityLevel.EXCELLENT.value == "excellent"
        assert QualityLevel.GOOD.value == "good"
        assert QualityLevel.ACCEPTABLE.value == "acceptable"
        assert QualityLevel.POOR.value == "poor"
        assert QualityLevel.UNACCEPTABLE.value == "unacceptable"
    
    def test_execution_status_enum(self):
        """测试执行状态枚举"""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"
    
    def test_task_priority_enum(self):
        """测试任务优先级枚举"""
        assert TaskPriority.CRITICAL == 1
        assert TaskPriority.HIGH == 2
        assert TaskPriority.NORMAL == 3
        assert TaskPriority.LOW == 4
        assert TaskPriority.BACKGROUND == 5
    
    def test_agent_message_model(self):
        """测试 Agent 消息模型"""
        msg = AgentMessage(
            role="user",
            content="测试消息",
            timestamp=datetime.now()
        )
        
        assert msg.role == "user"
        assert msg.content == "测试消息"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}
    
    def test_specialist_result_model(self):
        """测试专家结果模型"""
        result = SpecialistResult(
            specialist_type=SpecialistType.FINANCE,
            specialist_id="agent-001",
            query="分析财务状况",
            response="财务分析结果...",
            confidence=0.95,
            tools_used=["calculator", "report_generator"]
        )
        
        assert result.specialist_type == SpecialistType.FINANCE
        assert result.confidence == 0.95
        assert len(result.tools_used) == 2
    
    def test_reflection_result_model(self):
        """测试反思结果模型"""
        result = ReflectionResult(
            quality_level=QualityLevel.GOOD,
            overall_score=0.85,
            issues=["回答不够详细"],
            suggestions=["添加更多数据支持"]
        )
        
        assert result.quality_level == QualityLevel.GOOD
        assert result.overall_score == 0.85
        assert len(result.issues) == 1


class TestStateFactory:
    """
    状态工厂测试
    
    测试 StateFactory 的状态创建功能
    """
    
    def test_create_initial_state_basic(self):
        """测试创建基本初始状态"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        # 验证核心字段
        assert state["session_id"] == "session-001"
        assert state["tenant_id"] == "tenant-001"
        assert state["user_id"] == "user-001"
        assert state["user_query"] == "测试查询"
        
        # 验证自动生成的字段
        assert state["request_id"] is not None
        assert state["request_id"] != ""
        assert isinstance(state["query_timestamp"], datetime)
        
        # 验证默认值
        assert state["intent"] is None
        assert state["intent_confidence"] == 0.0
        assert state["iteration"] == 0
        assert state["max_iterations"] == 10
        assert state["retry_count"] == 0
        assert state["max_retries"] == 3
    
    def test_create_initial_state_with_intent(self):
        """测试创建带意图的初始状态"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="分析税务问题",
            intent=IntentCategory.MULTI_SPECIALIST
        )
        
        assert state["intent"] == IntentCategory.MULTI_SPECIALIST
        assert state["current_phase"] == "init"
    
    def test_create_initial_state_with_custom_params(self):
        """测试创建带自定义参数的初始状态"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试",
            max_iterations=5,
            max_retries=2,
            trace_id="trace-123"
        )
        
        assert state["max_iterations"] == 5
        assert state["max_retries"] == 2
        assert state["trace_id"] == "trace-123"
    
    def test_create_initial_state_validation(self):
        """测试创建状态时的参数验证"""
        # 测试空 session_id
        with pytest.raises(ValueError, match="session_id 不能为空"):
            StateFactory.create_initial_state(
                session_id="",
                tenant_id="tenant-001",
                user_id="user-001",
                user_query="测试"
            )
        
        # 测试空 tenant_id
        with pytest.raises(ValueError, match="tenant_id 不能为空"):
            StateFactory.create_initial_state(
                session_id="session-001",
                tenant_id="",
                user_id="user-001",
                user_query="测试"
            )
        
        # 测试空 user_query
        with pytest.raises(ValueError, match="user_query 不能为空"):
            StateFactory.create_initial_state(
                session_id="session-001",
                tenant_id="tenant-001",
                user_id="user-001",
                user_query=""
            )
    
    def test_copy_state(self):
        """测试状态复制"""
        original = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试"
        )
        
        copied = StateFactory.copy_state(original)
        
        # 验证字段复制
        assert copied["session_id"] == original["session_id"]
        assert copied["tenant_id"] == original["tenant_id"]
        assert copied["user_id"] == original["user_id"]
        assert copied["request_id"] != original["request_id"]
        
        # 验证深拷贝
        original["metadata"]["key"] = "value"
        assert "key" not in copied["metadata"]
    
    def test_create_snapshot(self):
        """测试状态快照创建"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试"
        )
        
        snapshot = StateFactory.create_snapshot(state)
        
        assert "snapshot_id" in snapshot
        assert "created_at" in snapshot
        assert "request_id" in snapshot
        assert "state_data" in snapshot
        assert snapshot["state_data"]["session_id"] == "session-001"
    
    def test_restore_from_snapshot(self):
        """测试从快照恢复状态"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试"
        )
        
        snapshot = StateFactory.create_snapshot(state)
        restored = StateFactory.restore_from_snapshot(snapshot)
        
        assert restored["session_id"] == state["session_id"]
        assert restored["request_id"] == state["request_id"]
    
    def test_create_error_state(self):
        """测试创建错误状态"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试"
        )
        
        error_state = StateFactory.create_error_state(
            state,
            error_message="测试错误",
            error_type="TestError"
        )
        
        assert error_state["error"] == "测试错误"
        assert error_state["current_phase"] == "error"
        assert len(error_state["error_history"]) == 1
        assert error_state["error_history"][0]["error"] == "测试错误"
    
    def test_reset_for_retry(self):
        """测试重置状态进行重试"""
        state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试"
        )
        state["iteration"] = 5
        state["retry_count"] = 1
        
        reset_state = StateFactory.reset_for_retry(state)
        
        assert reset_state["retry_count"] == 2
        assert reset_state["iteration"] == 0
        assert reset_state["error"] is None
        assert reset_state["current_phase"] == "init"


class TestStateValidator:
    """
    状态验证器测试
    
    测试 StateValidator 的验证功能
    """
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例"""
        return StateValidator()
    
    @pytest.fixture
    def valid_state(self):
        """创建有效状态"""
        return StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
    
    def test_validate_valid_state(self, validator, valid_state):
        """测试验证有效状态"""
        result = validator.validate(valid_state)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_missing_required_field(self, validator):
        """测试验证缺失必填字段"""
        state: UnifiedState = {
            "session_id": "session-001",
            # 缺失 tenant_id, user_id, request_id 等
        }
        
        result = validator.validate(state)
        
        assert result.is_valid is False
        assert any("tenant_id" in error for error in result.errors)
        assert any("user_id" in error for error in result.errors)
    
    def test_validate_invalid_field_type(self, validator, valid_state):
        """测试验证无效字段类型"""
        valid_state["intent_confidence"] = "invalid"  # 应该是数字
        
        result = validator.validate(valid_state)
        
        # 先检查类型错误（因为类型验证在范围验证之前）
        assert result.is_valid is False
        assert any("字段类型错误" in error or "置信度" in error for error in result.errors)
    
    def test_validate_confidence_out_of_range(self, validator, valid_state):
        """测试验证置信度超出范围"""
        valid_state["intent_confidence"] = 1.5  # 应该在 0-1 之间
        
        result = validator.validate(valid_state)
        
        assert result.is_valid is False
        assert any("置信度超出范围" in error for error in result.errors)
    
    def test_validate_negative_iteration(self, validator, valid_state):
        """测试验证负数迭代次数"""
        valid_state["iteration"] = -1
        
        result = validator.validate(valid_state)
        
        assert result.is_valid is False
        assert any("iteration" in error and "负数" in error for error in result.errors)
    
    def test_validate_specialist_intent_without_specialists(self, validator, valid_state):
        """测试验证专家意图但无专家列表"""
        valid_state["intent"] = IntentCategory.MULTI_SPECIALIST
        # target_specialists 为空
        
        result = validator.validate(valid_state)
        
        assert result.is_valid is False
        assert any("target_specialists" in error for error in result.errors)
    
    def test_validate_field(self, validator, valid_state):
        """测试验证单个字段"""
        result = validator.validate_field(valid_state, "session_id")
        
        assert result.is_valid is True
        
        # 测试不存在的字段
        result = validator.validate_field(valid_state, "nonexistent_field")
        
        assert result.is_valid is True  # 不存在的字段只会产生警告
        assert len(result.warnings) > 0
    
    def test_validation_result_merge(self):
        """测试验证结果合并"""
        result1 = ValidationResult()
        result1.add_error("错误1")
        
        result2 = ValidationResult()
        result2.add_error("错误2")
        result2.add_warning("警告1")
        
        result1.merge(result2)
        
        assert result1.is_valid is False
        assert len(result1.errors) == 2
        assert len(result1.warnings) == 1
    
    def test_validate_transition(self, validator):
        """测试验证状态转换"""
        from_state = StateFactory.create_initial_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试"
        )
        
        # 验证 from_state 本身是有效的
        validation = validator.validate(from_state)
        assert validation.is_valid, f"初始状态验证失败: {validation.errors}"
        
        # 使用深拷贝（保留request_id）而不是copy_state（会生成新request_id）
        import copy
        to_state = copy.deepcopy(from_state)
        to_state["iteration"] = 1
        to_state["current_phase"] = "processing"
        
        result = validator.validate_transition(from_state, to_state)
        
        assert result.is_valid is True, f"正常转换验证失败: {result.errors}"
        
        # 测试不允许的转换 - tenant_id 变化
        to_state_copy = copy.deepcopy(from_state)
        to_state_copy["tenant_id"] = "different-tenant"
        result = validator.validate_transition(from_state, to_state_copy)
        
        assert result.is_valid is False, "tenant_id变化应该失败"
        assert any("tenant_id" in error and "变化" in error for error in result.errors), \
            f"错误信息应该包含tenant_id变化提示: {result.errors}"


class TestStateCache:
    """
    状态缓存测试
    
    测试 StateCache 的缓存功能
    """
    
    @pytest.fixture
    def cache(self):
        """创建缓存实例"""
        return StateCache(max_size=10, ttl_seconds=60)
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache):
        """测试缓存设置和获取"""
        state = {"request_id": "test-001", "data": "test"}
        
        await cache.set("test-001", state)
        cached = await cache.get("test-001")
        
        assert cached is not None
        assert cached["request_id"] == "test-001"
        assert cached["data"] == "test"
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """测试缓存未命中"""
        cached = await cache.get("nonexistent")
        
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache):
        """测试缓存删除"""
        state = {"request_id": "test-001"}
        
        await cache.set("test-001", state)
        await cache.delete("test-001")
        
        cached = await cache.get("test-001")
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_cache_max_size(self):
        """测试缓存大小限制"""
        cache = StateCache(max_size=2, ttl_seconds=60)
        
        await cache.set("key-1", {"id": 1})
        await cache.set("key-2", {"id": 2})
        await cache.set("key-3", {"id": 3})  # 应该删除 key-1
        
        assert await cache.get("key-1") is None
        assert await cache.get("key-2") is not None
        assert await cache.get("key-3") is not None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache):
        """测试清空缓存"""
        await cache.set("key-1", {"id": 1})
        await cache.set("key-2", {"id": 2})
        
        await cache.clear()
        
        assert await cache.get("key-1") is None
        assert await cache.get("key-2") is None


class TestStateManager:
    """
    状态管理器测试
    
    测试 StateManager 的状态管理功能
    """
    
    @pytest.fixture
    def manager(self):
        """创建状态管理器实例"""
        return StateManager(enable_cache=True, enable_history=True)
    
    @pytest.mark.asyncio
    async def test_create_state(self, manager):
        """测试创建状态"""
        state = await manager.create_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        assert state["session_id"] == "session-001"
        assert state["request_id"] is not None
        assert state["current_phase"] == "init"
    
    @pytest.mark.asyncio
    async def test_get_state(self, manager):
        """测试获取状态"""
        created = await manager.create_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        retrieved = await manager.get_state(created["request_id"])
        
        assert retrieved is not None
        assert retrieved["request_id"] == created["request_id"]
        assert retrieved["session_id"] == "session-001"
    
    @pytest.mark.asyncio
    async def test_update_state(self, manager):
        """测试更新状态"""
        state = await manager.create_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        state["current_phase"] = "processing"
        state["iteration"] = 1
        
        updated = await manager.update_state(state)
        
        assert updated["current_phase"] == "processing"
        assert updated["iteration"] == 1
        
        # 验证缓存已更新
        retrieved = await manager.get_state(state["request_id"])
        assert retrieved["current_phase"] == "processing"
    
    @pytest.mark.asyncio
    async def test_delete_state(self, manager):
        """测试删除状态"""
        state = await manager.create_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        await manager.delete_state(state["request_id"])
        
        retrieved = await manager.get_state(state["request_id"])
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_state_history(self, manager):
        """测试状态历史记录"""
        state = await manager.create_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        state["current_phase"] = "processing"
        await manager.update_state(state, action="update_phase")
        
        state["iteration"] = 1
        await manager.update_state(state, action="increment_iteration")
        
        history = await manager.get_state_history(state["request_id"])
        
        assert len(history) == 3  # create + 2 updates
        assert history[0].action == "create"
        assert history[1].action == "update_phase"
        assert history[2].action == "increment_iteration"
    
    @pytest.mark.asyncio
    async def test_transaction_context(self, manager):
        """测试事务上下文管理器"""
        state = await manager.create_state(
            session_id="session-001",
            tenant_id="tenant-001",
            user_id="user-001",
            user_query="测试查询"
        )
        
        try:
            async with manager.transaction(state["request_id"]) as s:
                s["current_phase"] = "processing"
                s["iteration"] = 10
                # 抛出异常
                raise ValueError("测试回滚")
        except ValueError:
            pass
        
        # 验证状态已回滚
        retrieved = await manager.get_state(state["request_id"])
        assert retrieved["current_phase"] == "init"
        assert retrieved["iteration"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
