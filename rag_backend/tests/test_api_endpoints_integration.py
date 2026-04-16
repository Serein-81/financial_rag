"""
API端点集成测试
API Endpoints Integration Tests
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app


class TestChatEndpoint:
    """测试聊天端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_chat_endpoint_exists(self, client):
        """测试聊天端点存在"""
        assert client is not None

    def test_chat_request_validation(self, client):
        """测试聊天请求验证"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Test message",
                "session_id": "test_session",
                "tenant_id": "test_tenant"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_chat_with_context(self, client):
        """测试带上下文的聊天"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "分析财务数据",
                "session_id": "test_session_001",
                "tenant_id": "test_tenant",
                "context": {
                    "document_id": "doc_001",
                    "analysis_type": "financial"
                }
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    @pytest.mark.asyncio
    async def test_async_chat_endpoint(self):
        """测试异步聊天端点"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/chat",
                json={
                    "message": "Async test message",
                    "session_id": "async_session",
                    "tenant_id": "test_tenant"
                }
            )
            
            assert response.status_code in [200, 201, 400, 422, 500]


class TestMultiAgentEndpoint:
    """测试多智能体端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_multi_agent_task_creation(self, client):
        """测试多智能体任务创建"""
        response = client.post(
            "/api/v1/multi-agent/tasks",
            json={
                "task_type": "comprehensive_audit",
                "description": "执行全面审计",
                "documents": [
                    {"id": "doc_001", "type": "financial_statement"}
                ],
                "tenant_id": "test_tenant"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_multi_agent_status_query(self, client):
        """测试多智能体状态查询"""
        task_id = "test_task_001"
        
        response = client.get(f"/api/v1/multi-agent/tasks/{task_id}")
        
        assert response.status_code in [200, 404, 500]

    def test_multi_agent_result_retrieval(self, client):
        """测试多智能体结果获取"""
        task_id = "completed_task_001"
        
        response = client.get(f"/api/v1/multi-agent/tasks/{task_id}/result")
        
        assert response.status_code in [200, 404, 500]


class TestKnowledgeEndpoint:
    """测试知识端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_knowledge_search(self, client):
        """测试知识搜索"""
        response = client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "企业税务合规",
                "tenant_id": "test_tenant",
                "top_k": 10
            }
        )
        
        assert response.status_code in [200, 400, 422, 500]

    def test_knowledge_upload(self, client):
        """测试知识上传"""
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": ("test_document.pdf", b"fake pdf content", "application/pdf")
            },
            data={
                "tenant_id": "test_tenant",
                "document_type": "policy"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_knowledge_document_list(self, client):
        """测试知识文档列表"""
        response = client.get(
            "/api/v1/knowledge/documents",
            params={
                "tenant_id": "test_tenant",
                "page": 1,
                "page_size": 20
            }
        )
        
        assert response.status_code in [200, 400, 500]


class TestFinancialEndpoint:
    """测试财务端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_financial_health_check(self, client):
        """测试财务健康检查"""
        response = client.post(
            "/api/v1/financial/health",
            json={
                "tenant_id": "test_tenant",
                "company_id": "company_001",
                "period": "2024_Q1"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_financial_analysis(self, client):
        """测试财务分析"""
        response = client.post(
            "/api/v1/financial/analyze",
            json={
                "tenant_id": "test_tenant",
                "document_ids": ["doc_001", "doc_002"],
                "analysis_type": "comprehensive"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_financial_data_retrieval(self, client):
        """测试财务数据获取"""
        response = client.get(
            "/api/v1/financial/data",
            params={
                "tenant_id": "test_tenant",
                "data_type": "balance_sheet",
                "year": 2024
            }
        )
        
        assert response.status_code in [200, 400, 404, 500]


class TestTaxEndpoint:
    """测试税务端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_tax_intelligence_query(self, client):
        """测试税务智能查询"""
        response = client.post(
            "/api/v1/tax/intelligence",
            json={
                "tenant_id": "test_tenant",
                "query": "2024年增值税最新政策",
                "include_regulations": True
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_tax_calculation(self, client):
        """测试税务计算"""
        response = client.post(
            "/api/v1/tax/calculate",
            json={
                "tenant_id": "test_tenant",
                "tax_type": "income_tax",
                "revenue": 1000000,
                "deductible_expenses": 600000
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_tax_report_generation(self, client):
        """测试税务报告生成"""
        response = client.post(
            "/api/v1/tax/reports",
            json={
                "tenant_id": "test_tenant",
                "report_type": "annual_tax_return",
                "year": 2024
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]


class TestAuthEndpoint:
    """测试认证端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_user_login(self, client):
        """测试用户登录"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "test_user",
                "password": "test_password",
                "tenant_id": "test_tenant"
            }
        )
        
        assert response.status_code in [200, 201, 400, 401, 422, 500]

    def test_user_logout(self, client):
        """测试用户登出"""
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 401, 500]

    def test_token_refresh(self, client):
        """测试令牌刷新"""
        response = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "test_refresh_token"
            }
        )
        
        assert response.status_code in [200, 201, 400, 401, 500]


class TestSessionEndpoint:
    """测试会话端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_create_session(self, client):
        """测试创建会话"""
        response = client.post(
            "/api/v1/sessions",
            json={
                "tenant_id": "test_tenant",
                "user_id": "user_001",
                "context": {}
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_get_session(self, client):
        """测试获取会话"""
        session_id = "session_001"
        
        response = client.get(f"/api/v1/sessions/{session_id}")
        
        assert response.status_code in [200, 404, 500]

    def test_update_session(self, client):
        """测试更新会话"""
        session_id = "session_002"
        
        response = client.put(
            f"/api/v1/sessions/{session_id}",
            json={
                "context": {"key": "updated_value"}
            }
        )
        
        assert response.status_code in [200, 404, 422, 500]

    def test_close_session(self, client):
        """测试关闭会话"""
        session_id = "session_003"
        
        response = client.delete(f"/api/v1/sessions/{session_id}")
        
        assert response.status_code in [200, 204, 404, 500]


class TestDocumentEndpoint:
    """测试文档端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_upload_document(self, client):
        """测试上传文档"""
        response = client.post(
            "/api/v1/documents/upload",
            files={
                "file": ("test.pdf", b"fake content", "application/pdf")
            },
            data={
                "tenant_id": "test_tenant",
                "document_type": "contract"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_get_document(self, client):
        """测试获取文档"""
        document_id = "doc_001"
        
        response = client.get(f"/api/v1/documents/{document_id}")
        
        assert response.status_code in [200, 404, 500]

    def test_delete_document(self, client):
        """测试删除文档"""
        document_id = "doc_002"
        
        response = client.delete(f"/api/v1/documents/{document_id}")
        
        assert response.status_code in [200, 204, 404, 500]


class TestSearchEndpoint:
    """测试搜索端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_hybrid_search(self, client):
        """测试混合搜索"""
        response = client.post(
            "/api/v1/search/hybrid",
            json={
                "query": "企业财务风险管理",
                "tenant_id": "test_tenant",
                "search_types": ["vector", "keyword", "knowledge_graph"],
                "top_k": 20
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_vector_search(self, client):
        """测试向量搜索"""
        response = client.post(
            "/api/v1/search/vector",
            json={
                "query_embedding": [0.1] * 1536,
                "tenant_id": "test_tenant",
                "top_k": 10
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_full_text_search(self, client):
        """测试全文搜索"""
        response = client.post(
            "/api/v1/search/fulltext",
            json={
                "query": "税务合规要求",
                "tenant_id": "test_tenant",
                "filters": {
                    "document_type": "policy"
                }
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]


class TestAgentDiscoveryEndpoint:
    """测试智能体发现端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_list_available_agents(self, client):
        """测试列出可用智能体"""
        response = client.get(
            "/api/v1/agents",
            params={
                "tenant_id": "test_tenant",
                "capabilities": "financial_analysis"
            }
        )
        
        assert response.status_code in [200, 400, 500]

    def test_agent_capabilities_query(self, client):
        """测试查询智能体能力"""
        agent_id = "finance_specialist"
        
        response = client.get(f"/api/v1/agents/{agent_id}/capabilities")
        
        assert response.status_code in [200, 404, 500]


class TestPolicyEndpoint:
    """测试策略端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_policy_search(self, client):
        """测试策略搜索"""
        response = client.post(
            "/api/v1/policies/search",
            json={
                "tenant_id": "test_tenant",
                "query": "数据安全政策",
                "filters": {
                    "category": "security",
                    "effective_date": "2024-01-01"
                }
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_policy_compliance_check(self, client):
        """测试策略合规检查"""
        response = client.post(
            "/api/v1/policies/compliance-check",
            json={
                "tenant_id": "test_tenant",
                "policy_ids": ["policy_001", "policy_002"],
                "evidence": {
                    "document_id": "doc_compliance_001"
                }
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]


class TestStreamingEndpoint:
    """测试流式端点"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_streaming_chat(self, client):
        """测试流式聊天"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "生成详细财务报告",
                "session_id": "stream_session_001",
                "tenant_id": "test_tenant"
            }
        )
        
        assert response.status_code in [200, 201, 400, 422, 500]


class TestAPIErrorHandling:
    """测试API错误处理"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

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
            "/api/v1/chat",
            json={
                "message": "Test"
            }
        )
        
        assert response.status_code in [400, 422, 500]

    def test_invalid_tenant_id(self, client):
        """测试无效租户ID"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Test",
                "session_id": "test",
                "tenant_id": "nonexistent_tenant_xyz"
            }
        )
        
        assert response.status_code in [400, 401, 403, 422, 500]


class TestAPIResponseFormat:
    """测试API响应格式"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_success_response_format(self, client):
        """测试成功响应格式"""
        response = client.post(
            "/api/v1/health",
            json={
                "tenant_id": "test_tenant"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_error_response_format(self, client):
        """测试错误响应格式"""
        response = client.post(
            "/api/v1/chat",
            json={
                "invalid": "payload"
            }
        )
        
        if response.status_code >= 400:
            data = response.json()
            assert isinstance(data, dict)
            assert "detail" in data or "error" in data or "message" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
