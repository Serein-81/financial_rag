"""
Mock测试配置文件
Mock Test Configuration for FastAPI Testing

这个配置文件提供了完整的依赖注入mock解决方案，
用于在不需要真实数据库和服务的情况下运行测试。
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.api.deps import get_db, get_current_user
from app.models.user import User


class MockAsyncSession:
    """Mock数据库会话"""
    
    def __init__(self):
        self.storage = {}
        self.query_results = []
        self.committed = False
        self.rolled_back = False
    
    async def execute(self, query):
        """执行查询（mock）"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        return mock_result
    
    async def commit(self):
        """提交事务"""
        self.committed = True
    
    async def rollback(self):
        """回滚事务"""
        self.rolled_back = True
    
    async def begin(self):
        """开始事务"""
        pass
    
    async def close(self):
        """关闭会话"""
        pass
    
    def add(self, obj):
        """添加对象"""
        obj_id = getattr(obj, 'id', None) or str(uuid.uuid4())
        self.storage[obj_id] = obj
    
    def delete(self, obj):
        """删除对象"""
        obj_id = getattr(obj, 'id', None)
        if obj_id in self.storage:
            del self.storage[obj_id]
    
    def query(self, model):
        """返回mock查询对象"""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.all.return_value = []
        mock_query.order_by.return_value = mock_query
        return mock_query


class MockRedisService:
    """Mock Redis服务"""
    
    def __init__(self):
        self.storage = {}
        self.expirations = {}
    
    async def get(self, key: str):
        """获取值"""
        return self.storage.get(key)
    
    async def set(self, key: str, value: str, ex: int = None):
        """设置值"""
        self.storage[key] = value
        return True
    
    async def delete(self, key: str):
        """删除键"""
        if key in self.storage:
            del self.storage[key]
            return 1
        return 0
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return key in self.storage
    
    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        self.expirations[key] = seconds
        return True
    
    async def hset(self, name: str, key: str, value: str):
        """设置哈希字段"""
        if name not in self.storage:
            self.storage[name] = {}
        self.storage[name][key] = value
        return 1
    
    async def hget(self, name: str, key: str):
        """获取哈希字段"""
        if name in self.storage and isinstance(self.storage[name], dict):
            return self.storage[name].get(key)
        return None
    
    async def lpush(self, name: str, *values):
        """左推入列表"""
        if name not in self.storage:
            self.storage[name] = []
        self.storage[name] = list(values) + self.storage[name]
        return len(self.storage[name])


class MockUser:
    """Mock用户对象"""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid.uuid4()))
        self.email = kwargs.get('email', 'test@example.com')
        self.phone = kwargs.get('phone', '13800138000')
        self.nickname = kwargs.get('nickname', 'Test User')
        self.tenant_id = kwargs.get('tenant_id', 'test_tenant_001')
        self.is_active = kwargs.get('is_active', True)
        self.is_admin = kwargs.get('is_admin', False)
        self.created_at = kwargs.get('created_at', datetime.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'nickname': self.nickname,
            'tenant_id': self.tenant_id,
            'is_active': self.is_active,
            'is_admin': self.is_admin
        }


class MockTenant:
    """Mock租户对象"""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'test_tenant_001')
        self.name = kwargs.get('name', 'Test Tenant')
        self.plan = kwargs.get('plan', 'enterprise')
        self.is_active = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at', datetime.now())


class MockLLMAdapter:
    """Mock LLM适配器"""
    
    def __init__(self, response_text: str = "Mock LLM response"):
        self.response_text = response_text
        self.call_count = 0
    
    async def generate(self, prompt: str, **kwargs):
        """生成文本"""
        self.call_count += 1
        return self.response_text
    
    async def generate_stream(self, prompt: str, **kwargs):
        """流式生成文本"""
        self.call_count += 1
        words = self.response_text.split()
        for word in words:
            yield word + " "
    
    def count_tokens(self, text: str) -> int:
        """计算token数量"""
        return len(text.split())


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Mock数据库会话"""
    return MockAsyncSession()


@pytest.fixture
def mock_redis_service():
    """Mock Redis服务"""
    return MockRedisService()


@pytest.fixture
def mock_user():
    """Mock用户"""
    return MockUser()


@pytest.fixture
def mock_tenant():
    """Mock租户"""
    return MockTenant()


@pytest.fixture
def mock_llm_adapter():
    """Mock LLM适配器"""
    return MockLLMAdapter()


@pytest.fixture
def test_app():
    """创建测试用FastAPI应用"""
    app = FastAPI(title="Test App")
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "mode": "test"}
    
    @app.get("/protected")
    async def protected_endpoint(current_user: User = Depends(get_current_user)):
        return {"user_id": current_user.id}
    
    return app


@pytest.fixture
def client(test_app):
    """同步测试客户端"""
    return TestClient(test_app)


@pytest.fixture
async def async_client(test_app):
    """异步测试客户端"""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def app_with_mock_db(mock_db_session, mock_user):
    """创建带有mock数据库的FastAPI应用"""
    from app.main import app
    
    async def override_get_db():
        yield mock_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield app
    
    app.dependency_overrides.clear()


@pytest.fixture
def app_with_full_mocks(mock_db_session, mock_redis_service, mock_user, mock_tenant):
    """创建带有完整mock的FastAPI应用"""
    from app.main import app
    
    async def override_get_db():
        yield mock_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with patch('app.services.redis_service.RedisService', return_value=mock_redis_service):
        yield app
    
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(app_with_full_mocks, mock_user):
    """创建已认证的测试客户端"""
    from app.api.deps import get_current_user
    
    async def override_get_current_user():
        return mock_user
    
    app_with_full_mocks.dependency_overrides[get_current_user] = override_get_current_user
    
    with TestClient(app_with_full_mocks) as client:
        yield client
    
    app_with_full_mocks.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
@pytest.fixture
async def authenticated_async_client(app_with_full_mocks, mock_user):
    """创建已认证的异步测试客户端"""
    from app.api.deps import get_current_user
    
    async def override_get_current_user():
        return mock_user
    
    app_with_full_mocks.dependency_overrides[get_current_user] = override_get_current_user
    
    async with AsyncClient(transport=ASGITransport(app=app_with_full_mocks)) as ac:
        yield ac
    
    app_with_full_mocks.dependency_overrides.pop(get_current_user, None)


class MockResponse:
    """通用Mock响应对象"""
    
    def __init__(self, data=None, status_code: int = 200):
        self.data = data or {}
        self.status_code = status_code
    
    def json(self):
        return self.data


@pytest.fixture
def mock_http_response():
    """Mock HTTP响应"""
    def _create_response(data=None, status_code=200):
        return MockResponse(data, status_code)
    return _create_response


def create_mock_user(**kwargs) -> MockUser:
    """创建Mock用户的工厂函数"""
    defaults = {
        'id': str(uuid.uuid4()),
        'email': f'test_{uuid.uuid4().hex[:8]}@example.com',
        'phone': f'138{uuid.uuid4().hex[:8]}',
        'nickname': 'Test User',
        'tenant_id': 'test_tenant_001',
        'is_active': True,
        'is_admin': False
    }
    defaults.update(kwargs)
    return MockUser(**defaults)


def create_mock_tenant(**kwargs) -> MockTenant:
    """创建Mock租户的工厂函数"""
    defaults = {
        'id': f'tenant_{uuid.uuid4().hex[:8]}',
        'name': 'Test Tenant',
        'plan': 'enterprise',
        'is_active': True
    }
    defaults.update(kwargs)
    return MockTenant(**defaults)


@pytest.fixture
def sample_users():
    """生成多个测试用户"""
    return [
        create_mock_user(email="user1@example.com", is_admin=False),
        create_mock_user(email="user2@example.com", is_admin=False),
        create_mock_user(email="admin@example.com", is_admin=True)
    ]


@pytest.fixture
def sample_tenants():
    """生成多个测试租户"""
    return [
        create_mock_tenant(name="Enterprise A", plan="enterprise"),
        create_mock_tenant(name="Enterprise B", plan="professional"),
        create_mock_tenant(name="Startup C", plan="starter")
    ]
