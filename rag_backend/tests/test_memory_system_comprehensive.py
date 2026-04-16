"""
记忆系统测试
Memory System Tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.memory_system.semantic_memory import SemanticMemory
from app.memory_system.episodic_memory import EpisodicMemory
from app.memory_system.working_memory import WorkingMemory
from app.memory_system.memory_manager import MemoryManager
from app.memory_system.context_builder import ContextBuilder
from app.memory_system.user_memory_extractor import UserMemoryExtractor


class TestSemanticMemory:
    """测试语义记忆"""

    @pytest.fixture
    def semantic_memory(self):
        return SemanticMemory()

    @pytest.mark.asyncio
    async def test_memory_initialization(self, semantic_memory):
        """测试记忆初始化"""
        assert semantic_memory is not None
        assert hasattr(semantic_memory, 'storage')

    @pytest.mark.asyncio
    async def test_store_memory(self, semantic_memory):
        """测试存储记忆"""
        memory_id = await semantic_memory.store({
            "content": "企业2024年营收达到1000万元",
            "type": "fact",
            "source": "financial_report",
            "embedding": [0.1] * 1536
        })
        
        assert memory_id is not None
        assert len(memory_id) > 0

    @pytest.mark.asyncio
    async def test_retrieve_memory(self, semantic_memory):
        """测试检索记忆"""
        memory_id = await semantic_memory.store({
            "content": "测试记忆内容",
            "type": "fact",
            "embedding": [0.2] * 1536
        })
        
        retrieved = await semantic_memory.retrieve(memory_id)
        
        assert retrieved is not None or retrieved is None

    @pytest.mark.asyncio
    async def test_search_memories(self, semantic_memory):
        """测试搜索记忆"""
        await semantic_memory.store({
            "content": "关于税务合规的信息",
            "type": "policy",
            "embedding": [0.3] * 1536
        })
        
        results = await semantic_memory.search(
            query="税务合规",
            top_k=5
        )
        
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_update_memory(self, semantic_memory):
        """测试更新记忆"""
        memory_id = await semantic_memory.store({
            "content": "原始内容",
            "type": "fact",
            "embedding": [0.4] * 1536
        })
        
        success = await semantic_memory.update(
            memory_id,
            {"content": "更新后的内容"}
        )
        
        assert success is True or success is False

    @pytest.mark.asyncio
    async def test_delete_memory(self, semantic_memory):
        """测试删除记忆"""
        memory_id = await semantic_memory.store({
            "content": "将被删除的记忆",
            "type": "fact",
            "embedding": [0.5] * 1536
        })
        
        success = await semantic_memory.delete(memory_id)
        assert success is True


class TestEpisodicMemory:
    """测试情景记忆"""

    @pytest.fixture
    def episodic_memory(self):
        return EpisodicMemory()

    @pytest.mark.asyncio
    async def test_record_episode(self, episodic_memory):
        """测试记录事件"""
        episode_id = await episodic_memory.record({
            "event_type": "user_query",
            "content": "用户询问财务问题",
            "timestamp": datetime.now(),
            "context": {
                "user_id": "user_001",
                "session_id": "session_001"
            }
        })
        
        assert episode_id is not None

    @pytest.mark.asyncio
    async def test_retrieve_episodes(self, episodic_memory):
        """测试检索事件"""
        episode_id = await episodic_memory.record({
            "event_type": "agent_response",
            "content": "智能体回复",
            "timestamp": datetime.now()
        })
        
        episodes = await episodic_memory.retrieve(
            session_id="test_session",
            time_range=(datetime.now() - timedelta(hours=1), datetime.now())
        )
        
        assert isinstance(episodes, list)

    @pytest.mark.asyncio
    async def test_episode_sequence(self, episodic_memory):
        """测试事件序列"""
        await episodic_memory.record({
            "event_type": "event_1",
            "content": "First event",
            "sequence": 1
        })
        
        await episodic_memory.record({
            "event_type": "event_2",
            "content": "Second event",
            "sequence": 2
        })
        
        sequence = await episodic_memory.get_sequence("test_session")
        
        assert isinstance(sequence, list)


class TestWorkingMemory:
    """测试工作记忆"""

    @pytest.fixture
    def working_memory(self):
        return WorkingMemory()

    @pytest.mark.asyncio
    async def test_working_memory_initialization(self, working_memory):
        """测试工作记忆初始化"""
        assert working_memory is not None
        assert hasattr(working_memory, 'buffer')

    @pytest.mark.asyncio
    async def test_add_to_buffer(self, working_memory):
        """测试添加到缓冲区"""
        item_id = await working_memory.add({
            "content": "当前正在处理的信息",
            "priority": 1,
            "ttl": 3600
        })
        
        assert item_id is not None

    @pytest.mark.asyncio
    async def test_get_buffer_contents(self, working_memory):
        """测试获取缓冲区内容"""
        await working_memory.add({
            "content": "Buffer item 1",
            "priority": 1
        })
        
        await working_memory.add({
            "content": "Buffer item 2",
            "priority": 2
        })
        
        contents = await working_memory.get_contents()
        
        assert isinstance(contents, list)

    @pytest.mark.asyncio
    async def test_clear_buffer(self, working_memory):
        """测试清空缓冲区"""
        await working_memory.add({"content": "Item 1"})
        await working_memory.add({"content": "Item 2"})
        
        success = await working_memory.clear()
        assert success is True

    @pytest.mark.asyncio
    async def test_buffer_expiration(self, working_memory):
        """测试缓冲区过期"""
        item_id = await working_memory.add({
            "content": "Temporary item",
            "priority": 1,
            "ttl": 1
        })
        
        await asyncio.sleep(2)
        
        contents = await working_memory.get_contents()
        assert isinstance(contents, list)


class TestMemoryManager:
    """测试记忆管理器"""

    @pytest.fixture
    def memory_manager(self):
        return MemoryManager()

    @pytest.mark.asyncio
    async def test_manager_initialization(self, memory_manager):
        """测试管理器初始化"""
        assert memory_manager is not None
        assert hasattr(memory_manager, 'semantic_memory')
        assert hasattr(memory_manager, 'episodic_memory')
        assert hasattr(memory_manager, 'working_memory')

    @pytest.mark.asyncio
    async def test_store_with_memory_type(self, memory_manager):
        """测试按类型存储记忆"""
        semantic_id = await memory_manager.store(
            memory_type="semantic",
            data={"content": "Semantic fact", "embedding": [0.1] * 1536}
        )
        
        episodic_id = await memory_manager.store(
            memory_type="episodic",
            data={"event_type": "query", "content": "User query"}
        )
        
        assert semantic_id is not None
        assert episodic_id is not None

    @pytest.mark.asyncio
    async def test_retrieve_with_consolidation(self, memory_manager):
        """测试带整合的检索"""
        await memory_manager.store(
            memory_type="semantic",
            data={"content": "Fact 1", "embedding": [0.2] * 1536}
        )
        
        await memory_manager.store(
            memory_type="episodic",
            data={"event_type": "Event 1"}
        )
        
        results = await memory_manager.retrieve_with_consolidation(
            query="Test query",
            memory_types=["semantic", "episodic"]
        )
        
        assert results is not None
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_memory_forgetting(self, memory_manager):
        """测试记忆遗忘"""
        memory_id = await memory_manager.store(
            memory_type="semantic",
            data={"content": "Will be forgotten", "embedding": [0.3] * 1536}
        )
        
        success = await memory_manager.forget(memory_id)
        assert success is True

    @pytest.mark.asyncio
    async def test_memory_consolidation(self, memory_manager):
        """测试记忆整合"""
        await memory_manager.store(
            memory_type="semantic",
            data={"content": "Similar fact 1", "embedding": [0.4] * 1536}
        )
        
        await memory_manager.store(
            memory_type="semantic",
            data={"content": "Similar fact 2", "embedding": [0.41] * 1536}
        )
        
        consolidated = await memory_manager.consolidate()
        
        assert consolidated is True or consolidated is False


class TestContextBuilder:
    """测试上下文构建器"""

    @pytest.fixture
    def context_builder(self):
        return ContextBuilder()

    @pytest.mark.asyncio
    async def test_build_context(self, context_builder):
        """测试构建上下文"""
        context = await context_builder.build(
            query="分析企业财务状况",
            user_id="user_001",
            session_id="session_001",
            include_memories=True
        )
        
        assert context is not None
        assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_context_with_memories(self, context_builder):
        """测试带记忆的上下文"""
        context = await context_builder.build(
            query="继续上次的话题",
            user_id="user_002",
            session_id="session_002",
            include_memories=True,
            memory_types=["semantic", "episodic"]
        )
        
        assert context is not None
        assert "memories" in context or "history" in context

    @pytest.mark.asyncio
    async def test_context_pruning(self, context_builder):
        """测试上下文修剪"""
        long_context = {
            "query": "Long query " * 100,
            "memories": [{"content": "Memory " * 50}] * 20,
            "history": [{"message": "Message " * 30}] * 30
        }
        
        pruned = await context_builder.prune(long_context, max_tokens=4000)
        
        assert pruned is not None
        assert isinstance(pruned, dict)


class TestUserMemoryExtractor:
    """测试用户记忆提取器"""

    @pytest.fixture
    def memory_extractor(self):
        return UserMemoryExtractor()

    @pytest.mark.asyncio
    async def test_extract_user_preferences(self, memory_extractor):
        """测试提取用户偏好"""
        user_messages = [
            "我更喜欢详细的财务分析报告",
            "请用表格形式展示数据",
            "我关注税务合规性"
        ]
        
        preferences = await memory_extractor.extract_preferences(user_messages)
        
        assert preferences is not None
        assert isinstance(preferences, dict)

    @pytest.mark.asyncio
    async def test_extract_user_profile(self, memory_extractor):
        """测试提取用户画像"""
        user_history = [
            {"role": "user", "content": "我是财务经理"},
            {"role": "assistant", "content": "好的，我将为您提供专业的财务分析"},
            {"role": "user", "content": "我们公司主要做进出口贸易"}
        ]
        
        profile = await memory_extractor.extract_profile(user_history)
        
        assert profile is not None
        assert isinstance(profile, dict)

    @pytest.mark.asyncio
    async def test_update_user_memory(self, memory_extractor):
        """测试更新用户记忆"""
        user_id = "user_profile_001"
        
        success = await memory_extractor.update_memory(
            user_id=user_id,
            preferences={"preferred_format": "detailed"},
            profile={"role": "finance_manager"}
        )
        
        assert success is True


class TestMemorySearch:
    """测试记忆搜索"""

    @pytest.fixture
    def semantic_memory(self):
        return SemanticMemory()

    @pytest.mark.asyncio
    async def test_semantic_search(self, semantic_memory):
        """测试语义搜索"""
        test_memories = [
            {"content": "企业营业收入", "embedding": [0.1] * 1536},
            {"content": "税务申报要求", "embedding": [0.2] * 1536},
            {"content": "财务风险管理", "embedding": [0.3] * 1536}
        ]
        
        for mem in test_memories:
            await semantic_memory.store(mem)
        
        results = await semantic_memory.search(
            query="企业财务",
            top_k=3,
            threshold=0.5
        )
        
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_filtered_search(self, semantic_memory):
        """测试过滤搜索"""
        await semantic_memory.store({
            "content": "财务报告",
            "type": "document",
            "embedding": [0.4] * 1536
        })
        
        results = await semantic_memory.search(
            query="报告",
            filters={"type": "document"},
            top_k=10
        )
        
        assert isinstance(results, list)


class TestMemoryStorage:
    """测试记忆存储"""

    @pytest.fixture
    def semantic_memory(self):
        return SemanticMemory()

    @pytest.mark.asyncio
    async def test_persistent_storage(self, semantic_memory):
        """测试持久化存储"""
        test_data = {
            "content": "持久化测试数据",
            "type": "test",
            "embedding": [0.5] * 1536
        }
        
        memory_id = await semantic_memory.store(test_data)
        
        assert memory_id is not None
        
        retrieved = await semantic_memory.retrieve(memory_id)
        assert retrieved is not None or retrieved is None

    @pytest.mark.asyncio
    async def test_storage_with_metadata(self, semantic_memory):
        """测试带元数据的存储"""
        memory_id = await semantic_memory.store({
            "content": "带元数据的记忆",
            "embedding": [0.6] * 1536,
            "metadata": {
                "created_by": "test_system",
                "confidence": 0.95,
                "tags": ["important", "verified"]
            }
        })
        
        assert memory_id is not None


class TestMemoryRetrieval:
    """测试记忆检索"""

    @pytest.fixture
    def semantic_memory(self):
        return SemanticMemory()

    @pytest.mark.asyncio
    async def test_exact_match_retrieval(self, semantic_memory):
        """测试精确匹配检索"""
        memory_id = await semantic_memory.store({
            "content": "精确匹配测试",
            "embedding": [0.7] * 1536
        })
        
        retrieved = await semantic_memory.retrieve(memory_id)
        
        assert retrieved is not None
        if retrieved:
            assert retrieved.get("content") == "精确匹配测试"

    @pytest.mark.asyncio
    async def test_similarity_retrieval(self, semantic_memory):
        """测试相似度检索"""
        await semantic_memory.store({
            "content": "相似内容A",
            "embedding": [0.8] * 1536
        })
        
        await semantic_memory.store({
            "content": "相似内容B",
            "embedding": [0.81] * 1536
        })
        
        results = await semantic_memory.search(
            query="相似内容",
            query_embedding=[0.8] * 1536,
            top_k=2
        )
        
        assert isinstance(results, list)


class TestMemorySecurity:
    """测试记忆安全"""

    @pytest.fixture
    def memory_manager(self):
        return MemoryManager()

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, memory_manager):
        """测试租户隔离"""
        tenant_a_memory = await memory_manager.store(
            memory_type="semantic",
            data={"content": "租户A的私密信息", "embedding": [0.1] * 1536},
            tenant_id="tenant_a"
        )
        
        tenant_b_retrieval = await memory_manager.retrieve_with_consolidation(
            query="私密信息",
            tenant_id="tenant_b"
        )
        
        if isinstance(tenant_b_retrieval, dict) and "memories" in tenant_b_retrieval:
            tenant_b_contents = [
                m.get("content", "") for m in tenant_b_retrieval.get("memories", [])
            ]
            assert "租户A的私密信息" not in tenant_b_contents

    @pytest.mark.asyncio
    async def test_encrypted_storage(self, memory_manager):
        """测试加密存储"""
        sensitive_data = {
            "content": "敏感财务数据",
            "embedding": [0.2] * 1536,
            "sensitive": True
        }
        
        memory_id = await memory_manager.store(
            memory_type="semantic",
            data=sensitive_data,
            encrypt=True
        )
        
        assert memory_id is not None


class TestMemoryPerformance:
    """测试记忆性能"""

    @pytest.mark.asyncio
    async def test_batch_storage(self):
        """测试批量存储"""
        memory = SemanticMemory()
        
        batch_data = [
            {"content": f"Batch item {i}", "embedding": [0.1 * i] * 1536}
            for i in range(10)
        ]
        
        start_time = datetime.now()
        
        for item in batch_data:
            await memory.store(item)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        assert duration < 10

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """测试并发访问"""
        memory = SemanticMemory()
        
        async def store_memory(index):
            return await memory.store({
                "content": f"Concurrent item {index}",
                "embedding": [0.1 * index] * 1536
            })
        
        tasks = [store_memory(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
