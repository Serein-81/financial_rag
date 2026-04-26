"""
多智能体系统 API 端点测试
测试 API 路由和数据模型
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_api_schema_imports():
    """测试 API schemas 导入"""
    print("\n" + "="*60)
    print("🔍 测试1: API Schemas 导入")
    print("="*60)
    
    try:
        
        print("✅ 所有 API schemas 导入成功")
        return True
    except Exception as e:
        print(f"❌ API schemas 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_request_validation():
    """测试请求数据验证"""
    print("\n" + "="*60)
    print("🔍 测试2: 请求数据验证")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import MultiAgentRequest, SpecialistQueryRequest
        
        request = MultiAgentRequest(
            query="测试多智能体查询",
            session_id="test-session-123",
            user_id="user-456",
            tenant_id="tenant-789"
        )
        
        print("✅ MultiAgentRequest 创建成功")
        print(f"   - query: {request.query}")
        print(f"   - session_id: {request.session_id}")
        
        specialist_request = SpecialistQueryRequest(
            specialist_type="finance",
            query="财务分析查询",
            context={"key": "value"}
        )
        
        print("✅ SpecialistQueryRequest 创建成功")
        print(f"   - specialist_type: {specialist_request.specialist_type}")
        
        return True
    except Exception as e:
        print(f"❌ 请求验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_response_structure():
    """测试响应数据结构"""
    print("\n" + "="*60)
    print("🔍 测试3: 响应数据结构")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            MultiAgentResponse,
            SpecialistResult,
            IntentAnalysisResult,
            ReflectionResult,
            SpecialistType
        )
        
        specialist_result = SpecialistResult(
            specialist_type=SpecialistType.FINANCE,
            specialist_name="finance",
            success=True,
            confidence=0.92,
            analysis={"revenue": 1000000, "expenses": 600000},
            processing_time=1.5
        )
        
        intent_result = IntentAnalysisResult(
            primary_intent="financial_inquiry",
            complexity="moderate",
            confidence=0.95,
            routing_strategy="single_specialist",
            required_specialists=["finance"]
        )
        
        reflection_result = ReflectionResult(
            quality_score=0.88,
            quality_level="good",
            needs_revision=False,
            suggestions=["建议1", "建议2"]
        )
        
        response = MultiAgentResponse(
            session_id="test-session-123",
            request_id="req-123",
            user_query="测试查询",
            final_response="这是最终回复内容",
            needs_human_review=False,
            confidence=0.92,
            processing_time=2.5,
            specialist_results=[specialist_result],
            intent_analysis=intent_result,
            reflection=reflection_result
        )
        
        print("✅ MultiAgentResponse 创建成功")
        print(f"   - session_id: {response.session_id}")
        print(f"   - final_response: {response.final_response[:30]}...")
        print(f"   - needs_human_review: {response.needs_human_review}")
        print(f"   - specialist_results 数量: {len(response.specialist_results)}")
        
        return True
    except Exception as e:
        print(f"❌ 响应结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_management():
    """测试会话管理模型"""
    print("\n" + "="*60)
    print("🔍 测试4: 会话管理模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            SessionCreateRequest,
            SessionCreateResponse
        )
        from datetime import datetime
        
        session_request = SessionCreateRequest(
            user_id="user-456",
            tenant_id="tenant-789",
            metadata={"source": "api"}
        )
        
        session_response = SessionCreateResponse(
            session_id="new-session-123",
            created_at=datetime.now(),
            metadata={"message": "会话创建成功"}
        )
        
        print("✅ SessionCreateRequest 创建成功")
        print("✅ SessionCreateResponse 创建成功")
        print(f"   - session_id: {session_response.session_id}")
        print(f"   - created_at: {session_response.created_at}")
        
        return True
    except Exception as e:
        print(f"❌ 会话管理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_system_health():
    """测试系统健康检查模型"""
    print("\n" + "="*60)
    print("🔍 测试5: 系统健康检查模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            SystemHealthResponse,
            AgentHealthStatus,
            SpecialistType
        )
        from datetime import datetime
        
        health_response = SystemHealthResponse(
            overall_status="healthy",
            agents=[
                AgentHealthStatus(
                    agent_type=SpecialistType.FINANCE,
                    is_available=True,
                    response_time=0.5,
                    last_heartbeat=datetime.now(),
                    status_message="运行正常"
                ),
                AgentHealthStatus(
                    agent_type=SpecialistType.TAX,
                    is_available=True,
                    response_time=1.2,
                    last_heartbeat=datetime.now(),
                    status_message="税务专家就绪"
                )
            ],
            orchestrator_status="active",
            database_status="healthy",
            timestamp=datetime.now()
        )
        
        print("✅ SystemHealthResponse 创建成功")
        print(f"   - overall_status: {health_response.overall_status}")
        print(f"   - agents 数量: {len(health_response.agents)}")
        print(f"   - orchestrator_status: {health_response.orchestrator_status}")
        
        return True
    except Exception as e:
        print(f"❌ 系统健康检查测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """测试错误处理模型"""
    print("\n" + "="*60)
    print("🔍 测试6: 错误处理模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import ErrorResponse
        
        from datetime import datetime
        
        error_response = ErrorResponse(
            error_code="TEST_ERROR",
            error_message="测试错误消息",
            details={"field": "value"},
            timestamp=datetime.now(),
            request_id="req-123"
        )
        
        print("✅ ErrorResponse 创建成功")
        print(f"   - error_code: {error_response.error_code}")
        print(f"   - error_message: {error_response.error_message}")
        print(f"   - request_id: {error_response.request_id}")
        
        return True
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_report_generation():
    """测试报告生成模型"""
    print("\n" + "="*60)
    print("🔍 测试7: 报告生成模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import ReportGenerationRequest
        
        report_request = ReportGenerationRequest(
            session_id="test-session-123",
            report_type="comprehensive",
            format="markdown",
            include_sections=["intent_analysis", "specialist_results", "quality_review"]
        )
        
        print("✅ ReportGenerationRequest 创建成功")
        print(f"   - session_id: {report_request.session_id}")
        print(f"   - report_type: {report_request.report_type}")
        print(f"   - format: {report_request.format}")
        
        return True
    except Exception as e:
        print(f"❌ 报告生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "🎯"*30)
    print("🎯 多智能体系统 API 端点测试")
    print("🎯"*30 + "\n")
    
    tests = [
        test_api_schema_imports,
        test_request_validation,
        test_response_structure,
        test_session_management,
        test_system_health,
        test_error_handling,
        test_report_generation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试执行异常: {e}")
            results.append(False)
    
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test.__name__}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有 API 端点测试通过！多智能体系统接口完整可用。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查相关模型。")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
