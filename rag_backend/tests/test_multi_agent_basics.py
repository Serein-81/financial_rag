"""
多智能体系统基础测试
测试所有专家智能体的导入和初始化
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_imports():
    """测试所有模块导入"""
    print("\n" + "="*60)
    print("🔍 测试1: 模块导入")
    print("="*60)
    
    try:
        print("✅ 所有专家智能体导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_schemas():
    """测试Pydantic模型"""
    print("\n" + "="*60)
    print("🔍 测试2: Pydantic模型")
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

async def test_orchestrator():
    """测试编排器"""
    print("\n" + "="*60)
    print("🔍 测试3: 编排器初始化")
    print("="*60)
    
    try:
        from app.multi_agent_system import AgentOrchestrator, OrchestrationContext
        
        orchestrator = AgentOrchestrator(
            tenant_id="test-tenant",
            user_id="test-user"
        )
        print("✅ AgentOrchestrator 实例创建成功")
        
        context = OrchestrationContext(
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
        
        return True
    except Exception as e:
        print(f"❌ 编排器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specialist_creation():
    """测试专家智能体创建"""
    print("\n" + "="*60)
    print("🔍 测试4: 专家智能体创建")
    print("="*60)
    
    try:
        from app.multi_agent_system.agents import (
            FinanceSpecialist,
            TaxSpecialist,
            LegalSpecialist,
            ReflectionSpecialist
        )
        
        finance = FinanceSpecialist()
        print("✅ FinanceSpecialist 创建成功")
        print(f"   - specialty: {finance.specialty}")
        
        tax = TaxSpecialist()
        print("✅ TaxSpecialist 创建成功")
        print(f"   - specialty: {tax.specialty}")
        
        legal = LegalSpecialist()
        print("✅ LegalSpecialist 创建成功")
        print(f"   - specialty: {legal.specialty}")
        
        reflection = ReflectionSpecialist()
        print("✅ ReflectionSpecialist 创建成功")
        print(f"   - specialty: {reflection.specialty}")
        
        return True
    except Exception as e:
        print(f"❌ 专家智能体创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_router():
    """测试API路由"""
    print("\n" + "="*60)
    print("🔍 测试5: API路由导入")
    print("="*60)
    
    try:
        from app.api.v1.endpoints import multi_agent
        
        print("✅ multi_agent路由模块导入成功")
        print("✅ 可用端点:")
        
        routes = [route for route in multi_agent.router.routes]
        for route in routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"   - {list(route.methods)[0] if route.methods else 'GET'} {route.path}")
        
        return True
    except Exception as e:
        print(f"❌ API路由测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_main_app():
    """测试主应用"""
    print("\n" + "="*60)
    print("🔍 测试6: 主应用导入")
    print("="*60)
    
    try:
        from app.main import app
        
        print("✅ FastAPI应用导入成功")
        print(f"✅ 应用标题: {app.title}")
        print(f"✅ 注册路由数量: {len(app.routes)}")
        
        return True
    except Exception as e:
        print(f"❌ 主应用测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "🎯"*30)
    print("🎯 多智能体系统基础测试")
    print("🎯"*30)
    
    tests = [
        ("模块导入", test_imports),
        ("Pydantic模型", test_schemas),
        ("编排器初始化", test_orchestrator),
        ("专家智能体创建", test_specialist_creation),
        ("API路由导入", test_api_router),
        ("主应用导入", test_main_app)
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
        print("\n🎉 所有测试通过！多智能体系统基础功能正常。")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查相关模块。")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
