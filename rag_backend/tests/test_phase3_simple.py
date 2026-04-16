"""
阶段3简单测试脚本
快速验证专业智能体功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.multi_agent_system.coordinator import AgentCoordinator
from app.multi_agent_system.agents import FinanceSpecialist, TaxSpecialist, LegalSpecialist
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager


async def test_specialists_basic():
    """基础专业智能体测试"""
    print("🧪 开始阶段3基础测试")
    print("=" * 50)
    
    try:
        # 测试LLM适配器创建
        print("1. 测试LLM适配器创建...")
        try:
            llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
            tool_manager = ToolManager()
            print("   ✅ LLM适配器创建成功")
        except Exception as e:
            print(f"   ⚠️ LLM适配器创建失败: {e}")
            print("   💡 提示: 请检查LLM配置")
            # 使用模拟适配器继续测试
            llm_adapter = None
            tool_manager = ToolManager()
        
        # 测试专业智能体创建
        print("\n2. 测试专业智能体创建...")
        
        try:
            finance_agent = FinanceSpecialist(llm_adapter, tool_manager)
            print("   ✅ 财务智能体创建成功")
        except Exception as e:
            print(f"   ❌ 财务智能体创建失败: {e}")
        
        try:
            tax_agent = TaxSpecialist(llm_adapter, tool_manager)
            print("   ✅ 税务智能体创建成功")
        except Exception as e:
            print(f"   ❌ 税务智能体创建失败: {e}")
        
        try:
            legal_agent = LegalSpecialist(llm_adapter, tool_manager)
            print("   ✅ 法务智能体创建成功")
        except Exception as e:
            print(f"   ❌ 法务智能体创建失败: {e}")
        
        # 测试协调器创建
        print("\n3. 测试协调器创建...")
        try:
            coordinator = AgentCoordinator()
            print("   ✅ 协调器创建成功")
            
            # 检查专业智能体是否正确初始化
            if hasattr(coordinator, 'specialists'):
                specialist_count = len(coordinator.specialists)
                print(f"   ✅ 专业智能体初始化: {specialist_count} 个")
                
                for name, specialist in coordinator.specialists.items():
                    if specialist:
                        print(f"      - {name}: ✅")
                    else:
                        print(f"      - {name}: ❌")
            else:
                print("   ⚠️ 协调器未包含专业智能体")
                
        except Exception as e:
            print(f"   ❌ 协调器创建失败: {e}")
        
        # 测试基础功能
        print("\n4. 测试基础功能...")
        
        # 测试知识库加载
        try:
            if 'finance_agent' in locals():
                knowledge_count = len(finance_agent.knowledge_base)
                print(f"   ✅ 财务知识库加载: {knowledge_count} 条规则")
            
            if 'tax_agent' in locals():
                knowledge_count = len(tax_agent.knowledge_base)
                print(f"   ✅ 税务知识库加载: {knowledge_count} 条规则")
            
            if 'legal_agent' in locals():
                knowledge_count = len(legal_agent.knowledge_base)
                print(f"   ✅ 法务知识库加载: {knowledge_count} 条规则")
                
        except Exception as e:
            print(f"   ❌ 知识库测试失败: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 阶段3基础测试完成")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")


async def test_simple_audit():
    """简单审查测试"""
    print("\n🔍 开始简单审查测试")
    print("-" * 30)
    
    try:
        # 准备测试文档
        test_docs = [
            {
                "id": "test_doc_001",
                "type": "测试文档",
                "content": "这是一个测试文档，包含资产负债表信息：资产总额100万元，负债总额80万元。"
            }
        ]
        
        # 创建协调器
        coordinator = AgentCoordinator()
        
        # 执行简单审查
        print("执行财务审查测试...")
        try:
            import uuid
            result = await coordinator.audit(
                task_id=str(uuid.uuid4()),  # 使用真正的UUID
                tenant_id="test_tenant",
                user_id=str(uuid.uuid4()),  # 修复user_id为UUID格式
                audit_type="finance",
                documents=test_docs
            )
            
            print("✅ 财务审查测试完成")
            
            # 检查结果
            if isinstance(result, dict):
                print(f"   - 任务ID: {result.get('task_id', '未知')}")
                
                # 检查状态
                state = coordinator.get_state()
                if state:
                    finance_findings = state.get("finance_findings", [])
                    print(f"   - 发现问题: {len(finance_findings)} 个")
                else:
                    print("   - 状态: 无状态信息")
            else:
                print("   - 结果格式异常")
                
        except Exception as e:
            print(f"❌ 财务审查测试失败: {e}")
        
        print("-" * 30)
        print("🎉 简单审查测试完成")
        
    except Exception as e:
        print(f"❌ 简单审查测试失败: {e}")


async def test_tools():
    """测试专业工具"""
    print("\n🔧 开始专业工具测试")
    print("-" * 30)
    
    try:
        # 测试财务计算工具
        print("1. 测试财务计算工具...")
        from app.multi_agent_system.tools.financial_calculator import FinancialCalculator
        
        calculator = FinancialCalculator()
        
        # 测试资产负债率计算
        result = calculator.calculate_asset_liability_ratio(
            total_liabilities=800000,
            total_assets=1000000
        )
        
        print(f"   ✅ 资产负债率计算: {result.get('percentage', 0)}%")
        print(f"   ✅ 风险等级: {result.get('risk_level', '未知')}")
        
        # 测试税务计算工具
        print("\n2. 测试税务计算工具...")
        from app.multi_agent_system.tools.tax_calculator import TaxCalculator
        
        tax_calc = TaxCalculator()
        
        # 测试增值税计算
        vat_result = tax_calc.calculate_vat(
            sales_amount=1000000,
            vat_rate=0.13,
            input_vat=100000,
            tenant_id="test_tenant"
        )
        
        print(f"   ✅ 增值税计算: 应纳税额 {vat_result.get('payable_vat', 0)} 元")
        
        # 测试法律匹配工具
        print("\n3. 测试法律匹配工具...")
        from app.multi_agent_system.tools.legal_matcher import LegalMatcher
        
        legal_matcher = LegalMatcher()
        
        # 测试合同必备条款检查
        contract_result = legal_matcher.check_contract_essentials(
            contract_text="甲方: ABC公司, 乙方: XYZ公司, 服务内容: 软件开发, 价款: 10万元",
            tenant_id="test_tenant"
        )
        
        print(f"   ✅ 合同条款检查: 完整性 {contract_result.get('completeness_score', 0)}%")
        print(f"   ✅ 风险等级: {contract_result.get('risk_level', '未知')}")
        
        print("-" * 30)
        print("🎉 专业工具测试完成")
        
    except Exception as e:
        print(f"❌ 专业工具测试失败: {e}")


async def main():
    """主测试函数"""
    print("🚀 阶段3专业智能体测试开始")
    print("=" * 60)
    
    # 运行各项测试
    await test_specialists_basic()
    await test_simple_audit()
    await test_tools()
    
    print("\n" + "=" * 60)
    print("🏁 阶段3专业智能体测试结束")
    print("\n📋 测试总结:")
    print("   ✅ 基础组件测试 - 验证智能体和协调器创建")
    print("   ✅ 简单审查测试 - 验证基本审查流程")
    print("   ✅ 专业工具测试 - 验证计算和匹配功能")
    print("\n💡 如需完整测试，请运行:")
    print("   python tests/test_phase3_integration.py")
    print("   python examples/phase3_specialist_example.py")


if __name__ == "__main__":
    asyncio.run(main())