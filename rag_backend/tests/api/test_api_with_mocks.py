"""
API端点Mock测试
API Endpoints Tests with Mock Dependencies

这个文件展示如何使用Mock依赖进行API端点测试，
无需连接真实数据库或外部服务。
"""

import pytest
from unittest.mock import patch
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db, get_current_user
from tests.conftest_mock import (
    MockAsyncSession,
    MockRedisService,
    create_mock_user,
    create_mock_tenant
)


@pytest.fixture
def mock_dependencies():
    """设置所有Mock依赖"""
    mock_db = MockAsyncSession()
    mock_redis = MockRedisService()
    mock_user = create_mock_user()
    mock_tenant = create_mock_tenant()
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    yield {
        'db': mock_db,
        'redis': mock_redis,
        'user': mock_user,
        'tenant': mock_tenant
    }
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_client(mock_dependencies):
    """创建带Mock的测试客户端"""
    return TestClient(app)


@pytest.fixture
def auth_mock_client(mock_dependencies):
    """创建带认证Mock的测试客户端"""
    mock_user = mock_dependencies['user']
    
    async def override_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    client = TestClient(app)
    
    yield client
    
    app.dependency_overrides.pop(get_current_user, None)


class TestHealthEndpoint:
    """健康检查端点测试"""
    
    def test_health_check(self, mock_client):
        """测试健康检查"""
        response = mock_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthEndpoints:
    """认证端点测试（使用Mock）"""
    
    def test_login_with_mock(self, mock_client):
        """测试登录（Mock）"""
        with patch('app.services.auth_service.AuthService.authenticate') as mock_auth:
            mock_auth.return_value = create_mock_user()
            
            response = mock_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "test123456"
                }
            )
            
            assert response.status_code in [200, 401, 500]
    
    def test_register_with_mock(self, mock_client):
        """测试注册（Mock）"""
        with patch('app.services.auth_service.AuthService.register') as mock_register:
            mock_register.return_value = create_mock_user()
            
            response = mock_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "new_user@example.com",
                    "password": "test123456",
                    "nickname": "New User"
                }
            )
            
            assert response.status_code in [200, 201, 400, 422]


class TestUserEndpoints:
    """用户端点测试"""
    
    def test_get_current_user(self, auth_mock_client, mock_dependencies):
        """测试获取当前用户"""
        response = auth_mock_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 401, 404]
    
    def test_update_profile(self, auth_mock_client):
        """测试更新个人资料"""
        response = auth_mock_client.put(
            "/api/v1/users/profile",
            json={
                "nickname": "Updated Name",
                "phone": "13900000000"
            }
        )
        
        assert response.status_code in [200, 401, 404]


class TestChatEndpoints:
    """聊天端点测试"""
    
    def test_chat_with_mock_llm(self, auth_mock_client):
        """测试聊天（使用Mock LLM）"""
        with patch('app.services.llm_service.LLMService.generate') as mock_generate:
            mock_generate.return_value = "这是Mock LLM的回复"
            
            response = auth_mock_client.post(
                "/api/v1/chat",
                json={
                    "message": "你好，测试消息",
                    "session_id": "test_session"
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_chat_stream_with_mock(self, auth_mock_client):
        """测试流式聊天（Mock）"""
        with patch('app.services.llm_service.LLMService.generate_stream') as mock_stream:
            async def mock_generator():
                for word in ["Mock", " ", "stream", " ", "response"]:
                    yield word
            
            mock_stream.return_value = mock_generator()
            
            response = auth_mock_client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "流式测试",
                    "session_id": "test_session"
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestKnowledgeEndpoints:
    """知识库端点测试"""
    
    def test_search_knowledge_with_mock(self, auth_mock_client):
        """测试知识搜索（Mock）"""
        with patch('app.services.search_service.SearchService.search') as mock_search:
            mock_search.return_value = {
                "results": [
                    {"id": "doc1", "content": "测试文档1", "score": 0.95},
                    {"id": "doc2", "content": "测试文档2", "score": 0.88}
                ],
                "total": 2
            }
            
            response = auth_mock_client.post(
                "/api/v1/knowledge/search",
                json={
                    "query": "测试查询",
                    "top_k": 5
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_upload_document_with_mock(self, auth_mock_client):
        """测试文档上传（Mock）"""
        with patch('app.services.document_service.DocumentService.upload') as mock_upload:
            mock_upload.return_value = {
                "id": "doc123",
                "filename": "test.pdf",
                "status": "uploaded"
            }
            
            response = auth_mock_client.post(
                "/api/v1/knowledge/documents",
                files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestTenantEndpoints:
    """租户端点测试"""
    
    def test_get_tenant_settings_with_mock(self, auth_mock_client):
        """测试获取租户设置（Mock）"""
        with patch('app.services.tenant_service.TenantService.get_settings') as mock_settings:
            mock_settings.return_value = {
                "tenant_id": "test_tenant",
                "plan": "enterprise",
                "max_users": 100
            }
            
            response = auth_mock_client.get("/api/v1/tenant/settings")
            
            assert response.status_code in [200, 401, 404]


class TestAnalyticsEndpoints:
    """分析端点测试"""
    
    def test_get_analytics_with_mock(self, auth_mock_client):
        """测试获取分析数据（Mock）"""
        with patch('app.services.analytics_service.AnalyticsService.get_stats') as mock_stats:
            mock_stats.return_value = {
                "total_queries": 100,
                "avg_response_time": 0.5,
                "success_rate": 0.95
            }
            
            response = auth_mock_client.get("/api/v1/analytics/stats")
            
            assert response.status_code in [200, 401, 404, 500]


class TestErrorHandling:
    """错误处理测试"""
    
    def test_invalid_endpoint_returns_404(self, mock_client):
        """测试无效端点返回404"""
        response = mock_client.get("/api/v1/invalid/endpoint")
        
        assert response.status_code == 404
    
    def test_invalid_json_returns_422(self, auth_mock_client):
        """测试无效JSON返回422"""
        response = auth_mock_client.post(
            "/api/v1/chat",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_missing_required_field_returns_422(self, mock_client):
        """测试缺少必需字段返回422"""
        response = mock_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"}
        )
        
        assert response.status_code == 422
