# Mock测试完整指南

## 📋 概述

本文档说明如何为RAG后端系统创建Mock测试，实现**无需连接真实数据库和服务**的单元测试和集成测试。

---

## 🎯 核心问题与解决方案

### 当前问题
❌ **CI中使用真实PostgreSQL + Redis**（需要启动Docker容器）  
❌ **现有测试连接真实API**（需要服务运行在localhost:8000）  
❌ **没有Mock数据库依赖**（所有测试都是集成测试）

### 解决方案
✅ **创建完整的Mock依赖注入框架**  
✅ **覆盖FastAPI依赖注入**  
✅ **Mock数据库、Redis、LLM等外部服务**  
✅ **实现真正的单元测试**

---

## 📁 新增文件

### 1. `conftest_mock.py`
**Mock配置的核心文件**，包含：

#### Mock类
- `MockAsyncSession` - Mock数据库会话
- `MockRedisService` - Mock Redis服务
- `MockUser` - Mock用户对象
- `MockTenant` - Mock租户对象
- `MockLLMAdapter` - Mock LLM适配器

#### Fixture工厂函数
- `mock_db_session` - 数据库会话Mock
- `mock_redis_service` - Redis服务Mock
- `mock_user` - 用户Mock
- `mock_tenant` - 租户Mock
- `mock_llm_adapter` - LLM适配器Mock
- `app_with_mock_db` - 带Mock数据库的应用
- `app_with_full_mocks` - 带完整Mock的应用
- `authenticated_client` - 已认证的测试客户端
- `authenticated_async_client` - 已认证的异步客户端

#### 工厂函数
- `create_mock_user(**kwargs)` - 创建Mock用户
- `create_mock_tenant(**kwargs)` - 创建Mock租户

---

### 2. `test_unit_with_mocks.py`
**使用Mock的单元测试示例**，包含：

#### 测试类
- `TestDatabaseMocking` - 数据库Mock测试
- `TestRedisMocking` - Redis Mock测试
- `TestUserMocking` - 用户Mock测试
- `TestTenantMocking` - 租户Mock测试
- `TestLLMAdapterMocking` - LLM适配器Mock测试
- `TestDependencyOverride` - 依赖覆盖测试
- `TestMultiAgentMocking` - 多智能体Mock测试
- `TestServiceLayerMocking` - 服务层Mock测试
- `TestExternalAPIMocking` - 外部API Mock测试
- `TestErrorHandling` - 错误处理Mock测试
- `TestPerformanceMocking` - 性能Mock测试
- `TestSecurityMocking` - 安全Mock测试

---

### 3. `test_api_with_mocks.py`
**使用Mock的API集成测试**，包含：

#### 测试端点
- 健康检查
- 认证（登录、注册）
- 用户管理
- 聊天功能
- 知识库搜索
- 财务分析
- 税务查询
- 多智能体任务
- 混合搜索
- 会话管理

---

## 🚀 使用方法

### 方式一：在测试文件中导入Mock配置

```python
import pytest
from tests.conftest_mock import (
    MockAsyncSession,
    MockRedisService,
    MockUser,
    create_mock_user,
    authenticated_client
)

class TestExample:
    def test_with_mock_db(self, mock_db_session):
        """使用Mock数据库"""
        assert mock_db_session is not None
        
        user = create_mock_user(email="test@example.com")
        mock_db_session.add(user)
        assert user.id in mock_db_session.storage
    
    def test_authenticated_api(self, authenticated_client):
        """使用认证客户端"""
        response = authenticated_client.get("/api/v1/auth/me")
        assert response.status_code in [200, 401, 404]
```

### 方式二：使用依赖覆盖

```python
from app.main import app
from app.api.deps import get_db, get_current_user

@pytest.fixture
def app_with_mocks():
    """覆盖数据库依赖"""
    mock_db = MockAsyncSession()
    
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield app
    
    app.dependency_overrides.clear()

@pytest.fixture
def auth_client_with_mocks(app_with_mocks, mock_user):
    """覆盖认证依赖"""
    def override_get_current_user():
        return mock_user
    
    app_with_mocks.dependency_overrides[get_current_user] = override_get_current_user
    
    yield TestClient(app_with_mocks)
    
    app_with_mocks.dependency_overrides.pop(get_current_user, None)
```

### 方式三：使用patch装饰器

```python
from unittest.mock import patch

class TestWithPatch:
    def test_external_service_mock(self):
        """使用patch Mock外部服务"""
        with patch('app.services.llm_service.LLMService.generate') as mock_generate:
            mock_generate.return_value = "Mock LLM response"
            
            # 调用实际代码，会使用Mock
            result = asyncio.run(call_llm_service("test"))
            
            assert result == "Mock LLM response"
```

---

## 🔧 Mock类详解

### MockAsyncSession

```python
# 基本操作
mock_db = MockAsyncSession()

# 添加对象
mock_db.add(user)

# 提交/回滚
await mock_db.commit()
await mock_db.rollback()

# 查询（返回空列表）
result = await mock_db.execute("SELECT * FROM users")
```

### MockRedisService

```python
# 基础操作
mock_redis = MockRedisService()

await mock_redis.set('key', 'value')
value = await mock_redis.get('key')
await mock_redis.delete('key')

# 哈希操作
await mock_redis.hset('hash', 'field', 'value')
value = await mock_redis.hget('hash', 'field')

# 检查存在
exists = await mock_redis.exists('key')
```

### MockUser / MockTenant

```python
# 创建对象
user = MockUser(
    email="test@example.com",
    nickname="Test User",
    is_admin=False
)

# 转换为字典
user_dict = user.to_dict()

# 工厂函数
user = create_mock_user(email="custom@example.com")
```

### MockLLMAdapter

```python
# 创建适配器
llm = MockLLMAdapter(response_text="Custom response")

# 同步生成
response = await llm.generate("prompt")

# 流式生成
async for chunk in llm.generate_stream("prompt"):
    print(chunk)

# Token计数
tokens = llm.count_tokens("Hello world")
```

---

## 📊 运行测试

### 运行所有Mock测试
```bash
cd rag_backend
pytest tests/test_unit_with_mocks.py -v
pytest tests/test_api_with_mocks.py -v
```

### 运行特定测试类
```bash
pytest tests/test_unit_with_mocks.py::TestDatabaseMocking -v
pytest tests/test_unit_with_mocks.py::TestRedisMocking -v
```

### 运行带标记的测试
```bash
# 只运行Mock测试（排除需要真实数据库的测试）
pytest tests/ -m "not integration" -v

# 只运行单元测试
pytest tests/test_unit_with_mocks.py -v
```

---

## 🎓 最佳实践

### 1. 优先Mock外部依赖

```python
# ✅ 推荐：Mock外部API调用
with patch('httpx.AsyncClient.get') as mock_get:
    mock_get.return_value = MockResponse({"data": "test"})
    
# ❌ 不推荐：直接调用真实API
async with httpx.AsyncClient() as client:
    response = await client.get("http://real-api.com")
```

### 2. 使用Fixture工厂函数

```python
# ✅ 推荐：使用工厂函数创建测试数据
@pytest.fixture
def sample_users():
    return [create_mock_user(email=f"user{i}@example.com") for i in range(5)]

# ❌ 不推荐：在测试中手动创建
def test_example():
    users = [
        MockUser(email="user1@example.com"),
        MockUser(email="user2@example.com"),
        ...
    ]
```

### 3. 组合使用Mock和Patch

```python
@pytest.fixture
def fully_mocked_client(mock_db_session, mock_redis_service, mock_user):
    """组合多个Mock"""
    def override_get_db():
        yield mock_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with patch('app.services.redis.RedisService', return_value=mock_redis_service):
        with TestClient(app) as client:
            yield client
    
    app.dependency_overrides.clear()
```

### 4. 测试错误处理

```python
def test_error_handling(self):
    """测试Mock错误场景"""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=ConnectionError("DB unavailable"))
    
    with pytest.raises(ConnectionError):
        await mock_db.execute("SELECT * FROM users")
```

---

## 🔄 Mock vs 真实测试

| 特性 | Mock测试 | 真实测试 |
|------|---------|---------|
| **速度** | ⚡ 快速（毫秒级） | 🐢 较慢（秒级） |
| **依赖** | ❌ 无外部依赖 | ✅ 需要DB/Redis等 |
| **稳定性** | ✅ 稳定 | ⚠️ 可能受环境影响 |
| **覆盖范围** | 单元级别 | 集成级别 |
| **CI配置** | 无需Docker | 需要Docker服务 |
| **适用场景** | 快速开发 | 最终验证 |

---

## 📝 CI/CD配置建议

### 分离测试类型

```yaml
# .github/workflows/ci-backend.yml

jobs:
  # 快速Mock测试（无需Docker）
  unit_tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/test_unit_with_mocks.py -v
  
  # 集成测试（需要Docker）
  integration_tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        ...
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/test_integration_real.py -v
```

### 推荐策略

1. **开发阶段**：主要使用Mock测试（快速反馈）
2. **PR审查**：运行Mock + 集成测试
3. **部署前**：完整集成测试
4. **CI优化**：分离快速和慢速测试

---

## 🎯 总结

### 优势

✅ **无需真实数据库** - 可以在任何环境运行  
✅ **快速反馈** - 测试速度提升10-100倍  
✅ **隔离性好** - 不受外部服务影响  
✅ **易于维护** - Mock代码简单直观  
✅ **并行友好** - 不会产生数据冲突  

### 使用建议

1. **单元测试** - 全部使用Mock
2. **API集成测试** - 使用Mock + Patch
3. **端到端测试** - 使用真实环境
4. **CI优化** - 分离快速/慢速测试

### 下一步

1. ✅ 创建Mock配置框架
2. ✅ 编写单元测试示例
3. ✅ 编写API Mock测试
4. ⏳ 更新CI配置分离测试类型
5. ⏳ 建立Mock测试最佳实践文档

---

## 📚 相关资源

- [FastAPI Testing Docs](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Mock Docs](https://docs.pytest.org/en/latest/monkeypatch.html)
- [Unittest.mock Docs](https://docs.python.org/3/library/unittest.mock.html)
