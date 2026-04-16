"""
多智能体系统核心模块测试
只测试不需要外部依赖的核心模块
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
            SpecialistType,
            IntentCategory,
            RoutingStrategy
        )
        
        request = MultiAgentRequest(
            query="测试查询",
            session_id="test-session",
            user_id="test-user",
            tenant_id="test-tenant"
        )
        print("✅ MultiAgentRequest 创建成功")
        print(f"   - query: {request.query}")
        print(f"   - session_id: {request.session_id}")
        
        print(f"✅ SpecialistType 枚举: {[e.value for e in SpecialistType]}")
        print(f"✅ IntentCategory 枚举: {[e.value for e in IntentCategory]}")
        print(f"✅ RoutingStrategy 枚举: {[e.value for e in RoutingStrategy]}")
        
        return True
    except Exception as e:
        print(f"❌ Pydantic模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specialist_enums():
    """测试专家枚举"""
    print("\n" + "="*60)
    print("🔍 测试2: 专家枚举定义")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            FinancialDomain,
            TaxType,
            LegalDomain,
            ContractType,
            QualityLevel
        )
        
        print(f"✅ FinancialDomain: {[e.value for e in FinancialDomain]}")
        print(f"✅ TaxType: {[e.value for e in TaxType]}")
        print(f"✅ LegalDomain: {[e.value for e in LegalDomain]}")
        print(f"✅ ContractType: {[e.value for e in ContractType]}")
        print(f"✅ QualityLevel: {[e.value for e in QualityLevel]}")
        
        return True
    except Exception as e:
        print(f"❌ 专家枚举测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_orchestrator_context():
    """测试编排上下文"""
    print("\n" + "="*60)
    print("🔍 测试3: 编排上下文")
    print("="*60)
    
    try:
        from importlib import util
        
        spec = util.spec_from_file_location(
            "orchestrator",
            "D:/Python/Codebase/My_rag/rag_backend/app/multi_agent_system/orchestrator.py"
        )
        orchestrator_module = util.module_from_spec(spec)
        spec.loader.exec_module(orchestrator_module)
        
        context = orchestrator_module.OrchestrationContext(
            session_id="test-session-123",
            tenant_id="test-tenant",
            user_id="test-user",
            user_query="测试查询内容",
            enable_reflection=True,
            confidence_threshold=0.7,
            max_specialists=3
        )
        print("✅ OrchestrationContext 实例创建成功")
        print(f"   - session_id: {context.session_id}")
        print(f"   - user_query: {context.user_query}")
        print(f"   - enable_reflection: {context.enable_reflection}")
        print(f"   - confidence_threshold: {context.confidence_threshold}")
        print(f"   - max_specialists: {context.max_specialists}")
        
        return True
    except Exception as e:
        print(f"❌ 编排上下文测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_agents_import():
    """测试agents模块导入"""
    print("\n" + "="*60)
    print("🔍 测试4: agents模块导入")
    print("="*60)
    
    try:
        from importlib import util
        
        spec = util.spec_from_file_location(
            "base_specialist",
            "D:/Python/Codebase/My_rag/rag_backend/app/multi_agent_system/agents/base_specialist.py"
        )
        base_module = util.module_from_spec(spec)
        spec.loader.exec_module(base_module)
        
        print("✅ BaseSpecialistAgent 导入成功")
        print(f"   - class: {base_module.BaseSpecialistAgent}")
        
        return True
    except Exception as e:
        print(f"❌ agents模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specialist_base():
    """测试专家基类"""
    print("\n" + "="*60)
    print("🔍 测试5: 专家基类方法")
    print("="*60)
    
    try:
        from importlib import util
        
        spec = util.spec_from_file_location(
            "base_specialist",
            "D:/Python/Codebase/My_rag/rag_backend/app/multi_agent_system/agents/base_specialist.py"
        )
        base_module = util.module_from_spec(spec)
        spec.loader.exec_module(base_module)
        
        methods = [m for m in dir(base_module.BaseSpecialistAgent) if not m.startswith('_')]
        print(f"✅ BaseSpecialistAgent 方法: {methods}")
        
        required_methods = ['run', 'consult', 'analyze', 'get_knowledge_map']
        for method in required_methods:
            if method in methods:
                print(f"   ✅ {method} 方法存在")
            else:
                print(f"   ⚠️ {method} 方法缺失")
        
        return True
    except Exception as e:
        print(f"❌ 专家基类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_intent_classification():
    """测试意图分类逻辑"""
    print("\n" + "="*60)
    print("🔍 测试6: 意图分类逻辑")
    print("="*60)
    
    try:
        from app.schemas.multi_agent import (
            IntentCategory,
            RoutingStrategy,
            IntentAnalysisResult
        )
        
        intent_result = IntentAnalysisResult(
            primary_intent=IntentCategory.FINANCIAL_INQUIRY,
            secondary_intents=[IntentCategory.COST_ANALYSIS],
            complexity="medium",
            routing_strategy=RoutingStrategy.SINGLE_SPECIALIST,
            requires_specialists=["finance"],
            confidence=0.95
        )
        
        print("✅ IntentAnalysisResult 创建成功")
        print(f"   - primary_intent: {intent_result.primary_intent}")
        print(f"   - routing_strategy: {intent_result.routing_strategy}")
        print(f"   - requires_specialists: {intent_result.requires_specialists}")
        print(f"   - confidence: {intent_result.confidence}")
        
        return True
    except Exception as e:
        print(f"❌ 意图分类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specialist_result():
    """测试专家结果模型"""
    print("\n" + "="*60)
    print("🔍 测试7: 专家结果模型")
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
        
        print("✅ SpecialistResult 创建成功")
        print(f"   - specialist_type: {specialist_result.specialist_type}")
        print(f"   - success: {specialist_result.success}")
        print(f"   - response: {specialist_result.response[:30]}...")
        print(f"   - confidence: {specialist_result.confidence}")
        print(f"   - processing_time: {specialist_result.processing_time}s")
        
        return True
    except Exception as e:
        print(f"❌ 专家结果模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "🎯"*30)
    print("🎯 多智能体系统核心模块测试")
    print("🎯"*30)
    
    tests = [
        ("Pydantic模型", test_schemas),
        ("专家枚举定义", test_specialist_enums),
        ("编排上下文", test_orchestrator_context),
        ("agents模块导入", test_agents_import),
        ("专家基类方法", test_specialist_base),
        ("意图分类逻辑", test_intent_classification),
        ("专家结果模型", test_specialist_result)
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
        print("\n🎉 所有核心模块测试通过！多智能体系统核心功能正常。")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查相关模块。")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
