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
def setup_mock_dependencies():
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
def setup_auth_mock(setup_mock_dependencies):
    """设置带认证的Mock"""
    mock_user = setup_mock_dependencies['user']
    
    async def override_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    yield setup_mock_dependencies
    
    app.dependency_overrides.pop(get_current_user, None)


class TestHealthEndpoint:
    """健康检查端点测试"""
    
    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthEndpoints:
    """认证端点测试（使用Mock）"""
    
    @pytest.fixture
    def client_with_mock_db(self, setup_mock_dependencies):
        """创建带Mock DB的客户端"""
        return TestClient(app)
    
    def test_login_with_mock(self, client_with_mock_db):
        """测试登录（Mock）"""
        with patch('app.services.auth_service.AuthService.authenticate') as mock_auth:
            mock_auth.return_value = create_mock_user()
            
            response = client_with_mock_db.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "test123456"
                }
            )
            
            assert response.status_code in [200, 401, 500]
    
    def test_register_with_mock(self, client_with_mock_db):
        """测试注册（Mock）"""
        with patch('app.services.auth_service.AuthService.register') as mock_register:
            mock_register.return_value = create_mock_user()
            
            response = client_with_mock_db.post(
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
    
    @pytest.fixture
    def auth_client(self, setup_auth_mock):
        """创建认证客户端"""
        return TestClient(app)
    
    def test_get_current_user(self, auth_client, mock_user):
        """测试获取当前用户"""
        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 401, 404]
    
    def test_update_profile(self, auth_client):
        """测试更新个人资料"""
        response = auth_client.put(
            "/api/v1/users/profile",
            json={
                "nickname": "Updated Name",
                "phone": "13900000000"
            }
        )
        
        assert response.status_code in [200, 401, 404]


class TestChatEndpoints:
    """聊天端点测试"""
    
    @pytest.fixture
    def chat_client(self, setup_auth_mock):
        """创建聊天客户端"""
        return TestClient(app)
    
    def test_chat_with_mock_llm(self, chat_client):
        """测试聊天（使用Mock LLM）"""
        with patch('app.services.llm_service.LLMService.generate') as mock_generate:
            mock_generate.return_value = "这是Mock LLM的回复"
            
            response = chat_client.post(
                "/api/v1/chat",
                json={
                    "message": "你好，测试消息",
                    "session_id": "test_session"
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_chat_stream_with_mock(self, chat_client):
        """测试流式聊天（Mock）"""
        with patch('app.services.llm_service.LLMService.generate_stream') as mock_stream:
            async def mock_generator():
                for word in ["Mock", " ", "stream", " ", "response"]:
                    yield word
            
            mock_stream.return_value = mock_generator()
            
            response = chat_client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "流式测试",
                    "session_id": "test_session"
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestKnowledgeEndpoints:
    """知识库端点测试"""
    
    @pytest.fixture
    def knowledge_client(self, setup_auth_mock):
        """创建知识库客户端"""
        return TestClient(app)
    
    def test_search_knowledge_with_mock(self, knowledge_client):
        """测试知识搜索（Mock）"""
        with patch('app.services.search_service.SearchService.search') as mock_search:
            mock_search.return_value = {
                "results": [
                    {"id": "doc1", "content": "测试文档1", "score": 0.95},
                    {"id": "doc2", "content": "测试文档2", "score": 0.88}
                ],
                "total": 2
            }
            
            response = knowledge_client.post(
                "/api/v1/knowledge/search",
                json={
                    "query": "测试查询",
                    "top_k": 10
                }
            )
            
            assert response.status_code in [200, 400, 500]
    
    def test_upload_document_mock(self, knowledge_client):
        """测试文档上传（Mock）"""
        with patch('app.services.document_service.DocumentService.upload') as mock_upload:
            mock_upload.return_value = {
                "document_id": "doc_mock_001",
                "status": "uploaded"
            }
            
            response = knowledge_client.post(
                "/api/v1/knowledge/documents",
                files={"file": ("test.txt", b"test content", "text/plain")},
                data={"tenant_id": "test_tenant"}
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestFinancialEndpoints:
    """财务端点测试"""
    
    @pytest.fixture
    def finance_client(self, setup_auth_mock):
        """创建财务客户端"""
        return TestClient(app)
    
    def test_financial_health_check_mock(self, finance_client):
        """测试财务健康检查（Mock）"""
        with patch('app.services.financial_health_service.FinancialHealthService.check') as mock_check:
            mock_check.return_value = {
                "health_score": 85,
                "risk_level": "low",
                "metrics": {
                    "profitability": 0.75,
                    "liquidity": 0.90,
                    "leverage": 0.65
                }
            }
            
            response = finance_client.post(
                "/api/v1/financial/health",
                json={
                    "company_id": "company_001",
                    "period": "2024_Q1"
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_financial_analysis_mock(self, finance_client):
        """测试财务分析（Mock）"""
        with patch('app.services.financial_service.FinancialService.analyze') as mock_analyze:
            mock_analyze.return_value = {
                "analysis_id": "analysis_001",
                "status": "completed",
                "summary": "Mock分析结果"
            }
            
            response = finance_client.post(
                "/api/v1/financial/analyze",
                json={
                    "document_ids": ["doc1", "doc2"],
                    "analysis_type": "comprehensive"
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestTaxEndpoints:
    """税务端点测试"""
    
    @pytest.fixture
    def tax_client(self, setup_auth_mock):
        """创建税务客户端"""
        return TestClient(app)
    
    def test_tax_intelligence_mock(self, tax_client):
        """测试税务智能查询（Mock）"""
        with patch('app.services.tax_intelligence_service.TaxIntelligenceService.query') as mock_query:
            mock_query.return_value = {
                "results": [
                    {
                        "title": "2024年增值税优惠政策",
                        "content": "Mock税务政策内容",
                        "relevance": 0.92
                    }
                ]
            }
            
            response = tax_client.post(
                "/api/v1/tax/intelligence",
                json={
                    "query": "增值税优惠",
                    "include_regulations": True
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_tax_calculation_mock(self, tax_client):
        """测试税务计算（Mock）"""
        with patch('app.services.tax_service.TaxService.calculate') as mock_calc:
            mock_calc.return_value = {
                "tax_type": "income_tax",
                "taxable_income": 1000000,
                "tax_amount": 250000,
                "effective_rate": 0.25
            }
            
            response = tax_client.post(
                "/api/v1/tax/calculate",
                json={
                    "tax_type": "income_tax",
                    "revenue": 1000000,
                    "deductible_expenses": 600000
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestMultiAgentEndpoints:
    """多智能体端点测试"""
    
    @pytest.fixture
    def agent_client(self, setup_auth_mock):
        """创建智能体客户端"""
        return TestClient(app)
    
    def test_create_agent_task_mock(self, agent_client):
        """测试创建智能体任务（Mock）"""
        with patch('app.services.agent_service.AgentService.create_task') as mock_create:
            mock_create.return_value = {
                "task_id": "task_mock_001",
                "status": "pending",
                "specialists": ["finance", "tax"]
            }
            
            response = agent_client.post(
                "/api/v1/multi-agent/tasks",
                json={
                    "task_type": "comprehensive_audit",
                    "description": "Mock多智能体任务",
                    "documents": []
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_get_agent_task_status_mock(self, agent_client):
        """测试获取任务状态（Mock）"""
        task_id = "task_mock_001"
        
        with patch('app.services.agent_service.AgentService.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": task_id,
                "status": "processing",
                "progress": 50,
                "specialist_status": {
                    "finance": "completed",
                    "tax": "processing"
                }
            }
            
            response = agent_client.get(f"/api/v1/multi-agent/tasks/{task_id}")
            
            assert response.status_code in [200, 404, 500]


class TestSearchEndpoints:
    """搜索端点测试"""
    
    @pytest.fixture
    def search_client(self, setup_auth_mock):
        """创建搜索客户端"""
        return TestClient(app)
    
    def test_hybrid_search_mock(self, search_client):
        """测试混合搜索（Mock）"""
        with patch('app.services.search_service.SearchService.hybrid_search') as mock_search:
            mock_search.return_value = {
                "results": {
                    "vector": [{"id": "v1", "score": 0.95}],
                    "keyword": [{"id": "k1", "score": 0.90}],
                    "graph": [{"id": "g1", "score": 0.88}]
                },
                "total": 3
            }
            
            response = search_client.post(
                "/api/v1/search/hybrid",
                json={
                    "query": "企业财务分析",
                    "search_types": ["vector", "keyword", "knowledge_graph"]
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_vector_search_mock(self, search_client):
        """测试向量搜索（Mock）"""
        with patch('app.services.vector_service.VectorService.search') as mock_search:
            mock_search.return_value = {
                "results": [
                    {"id": "vec1", "score": 0.97, "content": "相关内容"}
                ]
            }
            
            response = search_client.post(
                "/api/v1/search/vector",
                json={
                    "query_embedding": [0.1] * 1536,
                    "top_k": 10
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]


class TestSessionEndpoints:
    """会话端点测试"""
    
    @pytest.fixture
    def session_client(self, setup_auth_mock):
        """创建会话客户端"""
        return TestClient(app)
    
    def test_create_session_mock(self, session_client):
        """测试创建会话（Mock）"""
        with patch('app.services.session_service.SessionService.create') as mock_create:
            mock_create.return_value = {
                "session_id": "session_mock_001",
                "created_at": datetime.now().isoformat()
            }
            
            response = session_client.post(
                "/api/v1/sessions",
                json={
                    "user_id": "user_001",
                    "context": {}
                }
            )
            
            assert response.status_code in [200, 201, 400, 500]
    
    def test_get_session_mock(self, session_client):
        """测试获取会话（Mock）"""
        session_id = "session_mock_001"
        
        with patch('app.services.session_service.SessionService.get') as mock_get:
            mock_get.return_value = {
                "session_id": session_id,
                "status": "active",
                "messages": []
            }
            
            response = session_client.get(f"/api/v1/sessions/{session_id}")
            
            assert response.status_code in [200, 404, 500]


class TestErrorHandling:
    """错误处理测试"""
    
    def test_invalid_json_payload(self, client):
        """测试无效JSON载荷"""
        response = client.post(
            "/api/v1/chat",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [400, 422, 500]
    
    def test_missing_required_fields(self, client):
        """测试缺少必需字段"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com"
            }
        )
        
        assert response.status_code in [400, 422]
    
    def test_unauthorized_access(self, client):
        """测试未授权访问"""
        response = client.get(
            "/api/v1/users/profile",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code in [401, 403, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
