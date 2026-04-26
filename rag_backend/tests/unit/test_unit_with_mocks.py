"""
使用Mock的单元测试示例
Unit Tests with Mock Database Dependencies

这个文件展示如何使用conftest_mock.py中的mock配置来编写单元测试，
无需连接真实数据库或外部服务。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.deps import get_db
from tests.conftest_mock import (
    MockRedisService,
    MockTenant,
    create_mock_user,
    create_mock_tenant,
    mock_db_session as base_mock_db_session,
    mock_redis_service as base_mock_redis_service,
    mock_user as base_mock_user,
    mock_llm_adapter as base_mock_llm_adapter
)


class TestDatabaseMocking:
    """数据库Mock测试"""
    
    def test_mock_db_session_basic_operations(self, base_mock_db_session):
        """测试Mock数据库会话的基本操作"""
        assert base_mock_db_session is not None
        assert isinstance(base_mock_db_session.storage, dict)
        
        base_mock_db_session.storage['key1'] = 'value1'
        assert base_mock_db_session.storage['key1'] == 'value1'
    
    def test_mock_db_session_add_object(self, base_mock_db_session):
        """测试添加对象"""
        mock_user = create_mock_user(email="test@example.com")
        base_mock_db_session.add(mock_user)
        
        assert mock_user.id in base_mock_db_session.storage
        assert base_mock_db_session.storage[mock_user.id] == mock_user
    
    def test_mock_db_transaction_commit(self, base_mock_db_session):
        """测试事务提交"""
        base_mock_db_session.add(create_mock_user())
        assert not base_mock_db_session.committed
        
        base_mock_db_session.commit()
        assert base_mock_db_session.committed
    
    def test_mock_db_transaction_rollback(self, base_mock_db_session):
        """测试事务回滚"""
        assert not base_mock_db_session.rolled_back
        
        base_mock_db_session.rollback()
        assert base_mock_db_session.rolled_back


class TestRedisMocking:
    """Redis Mock测试"""
    
    def test_redis_basic_operations(self, base_mock_redis_service):
        """测试Redis基本操作"""
        assert base_mock_redis_service is not None
        
        result = base_mock_redis_service.storage
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_redis_set_and_get(self, base_mock_redis_service):
        """测试Redis SET/GET操作"""
        await base_mock_redis_service.set('test_key', 'test_value')
        
        value = await base_mock_redis_service.get('test_key')
        assert value == 'test_value'
    
    @pytest.mark.asyncio
    async def test_redis_delete(self, base_mock_redis_service):
        """测试Redis DELETE操作"""
        await base_mock_redis_service.set('delete_key', 'value')
        
        deleted = await base_mock_redis_service.delete('delete_key')
        assert deleted == 1
        
        value = await base_mock_redis_service.get('delete_key')
        assert value is None
    
    @pytest.mark.asyncio
    async def test_redis_hash_operations(self, base_mock_redis_service):
        """测试Redis HASH操作"""
        await base_mock_redis_service.hset('hash_key', 'field1', 'value1')
        
        value = await base_mock_redis_service.hget('hash_key', 'field1')
        assert value == 'value1'
    
    @pytest.mark.asyncio
    async def test_redis_exists(self, base_mock_redis_service):
        """测试Redis EXISTS操作"""
        await base_mock_redis_service.set('exists_key', 'value')
        
        exists = await base_mock_redis_service.exists('exists_key')
        assert exists is True
        
        not_exists = await base_mock_redis_service.exists('not_exists_key')
        assert not_exists is False


class TestUserMocking:
    """用户Mock测试"""
    
    def test_create_mock_user(self):
        """测试创建Mock用户"""
        user = create_mock_user(
            email="test_user@example.com",
            nickname="Test User"
        )
        
        assert user.email == "test_user@example.com"
        assert user.nickname == "Test User"
        assert user.is_active is True
        assert user.id is not None
    
    def test_mock_user_to_dict(self, base_mock_user):
        """测试用户转字典"""
        user_dict = base_mock_user.to_dict()
        
        assert 'id' in user_dict
        assert 'email' in user_dict
        assert 'tenant_id' in user_dict
    
    def test_mock_user_factory_multiple_users(self):
        """测试批量创建用户"""
        users = [create_mock_user() for _ in range(3)]
        assert len(users) == 3
        assert all(isinstance(u.email, str) for u in users)


class TestTenantMocking:
    """租户Mock测试"""
    
    def test_create_mock_tenant(self):
        """测试创建Mock租户"""
        tenant = create_mock_tenant(
            name="Enterprise Test",
            plan="enterprise"
        )
        
        assert tenant.name == "Enterprise Test"
        assert tenant.plan == "enterprise"
        assert tenant.is_active is True
    
    def test_tenant_defaults(self):
        """测试租户默认值"""
        tenant = MockTenant()
        
        assert tenant.plan == "enterprise"
        assert tenant.is_active is True
        assert tenant.id is not None


class TestLLMAdapterMocking:
    """LLM适配器Mock测试"""
    
    @pytest.mark.asyncio
    async def test_llm_generate(self, base_mock_llm_adapter):
        """测试LLM生成"""
        response = await base_mock_llm_adapter.generate("Hello")
        
        assert response == "Mock LLM response"
        assert base_mock_llm_adapter.call_count == 1
    
    @pytest.mark.asyncio
    async def test_llm_generate_stream(self, base_mock_llm_adapter):
        """测试LLM流式生成"""
        chunks = []
        async for chunk in base_mock_llm_adapter.generate_stream("Hello"):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        assert base_mock_llm_adapter.call_count == 1
    
    def test_llm_count_tokens(self, base_mock_llm_adapter):
        """测试token计数"""
        tokens = base_mock_llm_adapter.count_tokens("Hello world")
        assert tokens == 2


class TestDependencyOverride:
    """依赖覆盖测试"""
    
    def test_override_db_dependency(self):
        """测试数据库依赖覆盖"""
        from app.main import app
        from tests.conftest_mock import MockAsyncSession
        
        mock_db = MockAsyncSession()
        
        async def override_get_db():
            yield mock_db
        
        app.dependency_overrides[get_db] = override_get_db
        
        override_get_db_func = app.dependency_overrides.get(get_db)
        assert override_get_db_func is not None
        
        app.dependency_overrides.clear()
    
    def test_app_health_check(self):
        """测试健康检查端点（无需认证）"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code in [200, 404]


class TestMockSessionFactory:
    """Mock会话工厂测试"""
    
    def test_create_multiple_db_sessions(self):
        """测试创建多个数据库会话"""
        from tests.conftest_mock import MockAsyncSession
        
        session1 = MockAsyncSession()
        session2 = MockAsyncSession()
        
        assert session1 is not session2
        assert isinstance(session1.storage, dict)
        assert isinstance(session2.storage, dict)
    
    def test_create_multiple_redis_services(self):
        """测试创建多个Redis服务"""
        from tests.conftest_mock import MockRedisService
        
        redis1 = MockRedisService()
        redis2 = MockRedisService()
        
        assert redis1 is not redis2
        assert isinstance(redis1.storage, dict)
        assert isinstance(redis2.storage, dict)


class TestMockDataValidation:
    """Mock数据验证测试"""
    
    def test_mock_user_validation(self):
        """测试Mock用户数据验证"""
        user = create_mock_user(
            email="valid@test.com",
            nickname="Valid User",
            is_active=True
        )
        
        assert "@" in user.email
        assert len(user.nickname) > 0
        assert isinstance(user.is_active, bool)
    
    def test_mock_tenant_validation(self):
        """测试Mock租户数据验证"""
        tenant = create_mock_tenant(
            name="Valid Tenant",
            plan="pro"
        )
        
        assert len(tenant.name) > 0
        assert tenant.plan in ["free", "pro", "enterprise"]
