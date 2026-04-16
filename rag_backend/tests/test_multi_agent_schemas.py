"""
多智能体系统Schemas测试
只测试schemas模块，不依赖外部模块
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_schemas():
    """测试Pydantic模型"""
    print("\n" + "="*60)
    print("🔍 测试1: Pydantic模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            MultiAgentRequest,
            MultiAgentResponse,
            SpecialistType,
            IntentCategory,
            RoutingStrategy,
            IntentAnalysisResult,
            SpecialistResult,
            ReflectionResult,
            ComplexityLevel
        )
        
        print("✅ 所有核心模型导入成功")
        return True
    except Exception as e:
        print(f"❌ Pydantic模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_request_model():
    """测试请求模型"""
    print("\n" + "="*60)
    print("🔍 测试2: MultiAgentRequest模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import MultiAgentRequest
        
        request = MultiAgentRequest(
            query="测试查询",
            session_id="test-session",
            user_id="test-user",
            tenant_id="test-tenant"
        )
        print(f"✅ MultiAgentRequest 创建成功")
        print(f"   - query: {request.query}")
        print(f"   - session_id: {request.session_id}")
        
        return True
    except Exception as e:
        print(f"❌ 请求模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_intent_analysis_result():
    """测试意图分析结果模型"""
    print("\n" + "="*60)
    print("🔍 测试3: IntentAnalysisResult模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            IntentCategory,
            RoutingStrategy,
            IntentAnalysisResult,
            ComplexityLevel
        )
        
        intent_result = IntentAnalysisResult(
            primary_intent=IntentCategory.FINANCIAL_INQUIRY,
            secondary_intents=[IntentCategory.COST_ANALYSIS],
            complexity=ComplexityLevel.MODERATE,
            routing_strategy=RoutingStrategy.SINGLE_SPECIALIST,
            required_specialists=[],
            confidence=0.95
        )
        
        print(f"✅ IntentAnalysisResult 创建成功")
        print(f"   - primary_intent: {intent_result.primary_intent.value}")
        print(f"   - routing_strategy: {intent_result.routing_strategy.value}")
        print(f"   - confidence: {intent_result.confidence}")
        
        return True
    except Exception as e:
        print(f"❌ 意图分析结果模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specialist_result():
    """测试专家结果模型"""
    print("\n" + "="*60)
    print("🔍 测试4: SpecialistResult模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            SpecialistType,
            SpecialistResult
        )
        
        specialist_result = SpecialistResult(
            specialist_type=SpecialistType.FINANCE,
            specialist_name="finance",
            success=True,
            confidence=0.92,
            analysis={"revenue": 1000000, "expenses": 600000},
            processing_time=1.5
        )
        
        print(f"✅ SpecialistResult 创建成功")
        print(f"   - specialist_type: {specialist_result.specialist_type.value}")
        print(f"   - specialist_name: {specialist_result.specialist_name}")
        print(f"   - success: {specialist_result.success}")
        print(f"   - confidence: {specialist_result.confidence}")
        print(f"   - analysis: {specialist_result.analysis}")
        print(f"   - processing_time: {specialist_result.processing_time}s")
        
        return True
    except Exception as e:
        print(f"❌ 专家结果模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_reflection_result():
    """测试反思结果模型"""
    print("\n" + "="*60)
    print("🔍 测试5: ReflectionResult模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import ReflectionResult
        
        reflection_result = ReflectionResult(
            quality_score=0.88,
            quality_level="good",
            needs_revision=False,
            suggestions=["建议1", "建议2"]
        )
        
        print(f"✅ ReflectionResult 创建成功")
        print(f"   - quality_score: {reflection_result.quality_score}")
        print(f"   - quality_level: {reflection_result.quality_level}")
        print(f"   - needs_revision: {reflection_result.needs_revision}")
        print(f"   - suggestions: {reflection_result.suggestions}")
        
        return True
    except Exception as e:
        print(f"❌ 反思结果模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_multi_agent_response():
    """测试响应模型"""
    print("\n" + "="*60)
    print("🔍 测试6: MultiAgentResponse模型")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            MultiAgentResponse,
            SpecialistType,
            SpecialistResult,
            IntentCategory,
            RoutingStrategy,
            IntentAnalysisResult,
            ComplexityLevel
        )
        
        intent_result = IntentAnalysisResult(
            primary_intent=IntentCategory.FINANCIAL_INQUIRY,
            secondary_intents=[IntentCategory.COST_ANALYSIS],
            complexity=ComplexityLevel.MODERATE,
            routing_strategy=RoutingStrategy.SINGLE_SPECIALIST,
            requires_specialists=["finance"],
            confidence=0.95
        )
        
        specialist_result = SpecialistResult(
            specialist_type=SpecialistType.FINANCE,
            specialist_name="finance",
            success=True,
            confidence=0.92,
            analysis={"revenue": 1000000},
            processing_time=1.5
        )
        
        response = MultiAgentResponse(
            session_id="test-session-123",
            request_id="req-123",
            user_query="测试查询",
            intent_analysis=intent_result,
            specialist_results=[specialist_result],
            final_response="这是最终回复",
            needs_human_review=False,
            confidence=0.92,
            processing_time=2.5
        )
        
        print(f"✅ MultiAgentResponse 创建成功")
        print(f"   - session_id: {response.session_id}")
        print(f"   - request_id: {response.request_id}")
        print(f"   - user_query: {response.user_query}")
        print(f"   - final_response: {response.final_response}")
        print(f"   - needs_human_review: {response.needs_human_review}")
        print(f"   - confidence: {response.confidence}")
        print(f"   - processing_time: {response.processing_time}s")
        
        return True
    except Exception as e:
        print(f"❌ 响应模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_enums():
    """测试所有枚举"""
    print("\n" + "="*60)
    print("🔍 测试7: 枚举定义")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            SpecialistType,
            IntentCategory,
            RoutingStrategy,
            ComplexityLevel
        )
        
        print(f"✅ SpecialistType: {[e.value for e in SpecialistType]}")
        print(f"✅ IntentCategory: {[e.value for e in IntentCategory]}")
        print(f"✅ RoutingStrategy: {[e.value for e in RoutingStrategy]}")
        print(f"✅ ComplexityLevel: {[e.value for e in ComplexityLevel]}")
        print("✅ 注意: FinancialDomain等枚举在各自specialist中定义")
        
        return True
    except Exception as e:
        print(f"❌ 枚举测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "🎯"*30)
    print("🎯 多智能体系统Schemas模块测试")
    print("🎯"*30)
    
    tests = [
        ("Pydantic模型导入", test_schemas),
        ("MultiAgentRequest模型", test_request_model),
        ("IntentAnalysisResult模型", test_intent_analysis_result),
        ("SpecialistResult模型", test_specialist_result),
        ("ReflectionResult模型", test_reflection_result),
        ("MultiAgentResponse模型", test_multi_agent_response),
        ("枚举定义", test_enums)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 {test_name} 异常: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有Schemas模块测试通过！多智能体系统数据模型正常。")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查相关模型。")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
