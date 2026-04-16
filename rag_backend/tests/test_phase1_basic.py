"""
阶段 1 基础功能测试
测试多智能体系统的核心组件
"""

import asyncio
import uuid
from datetime import datetime

from app.multi_agent_system import (
    create_initial_state,
    AgentCoordinator,
    MessageBus,
    MessageType,
    TaskDecomposer,
    ResultMerger,
    Finding,
    RiskLevel
)


async def test_state_management():
    """测试状态管理"""
    print("=" * 60)
    print("🧪 测试状态管理")
    print("=" * 60)
    
    # 创建初始状态
    task_id = str(uuid.uuid4())
    tenant_id = "test_tenant"
    user_id = "test_user"
    
    state = create_initial_state(
        task_id=task_id,
        tenant_id=tenant_id,
        user_id=user_id,
        audit_type="comprehensive",
        documents=[
            {"id": "doc1", "content": "测试文档内容", "type": "financial_statement"}
        ]
    )
    
    print(f"✅ 状态创建成功")
    print(f"   任务ID: {state['task_id']}")
    print(f"   租户ID: {state['tenant_id']}")
    print(f"   审查类型: {state['audit_type']}")
    print(f"   文档数量: {len(state['documents'])}")
    print(f"   状态: {state['status']}")
    
    # 更新状态
    state["status"] = "processing"
    state["finance_findings"] = [
        {
            "id": "finding1",
            "description": "测试发现",
            "risk_score": 0.7
        }
    ]
    
    print(f"✅ 状态更新成功")
    print(f"   新状态: {state['status']}")
    print(f"   发现数量: {len(state['finance_findings'])}")


async def test_message_bus():
    """测试消息总线"""
    print("\n" + "=" * 60)
    print("📨 测试消息总线")
    print("=" * 60)
    
    message_bus = MessageBus()
    
    # 测试消息发布
    message_id = await message_bus.publish(
        from_agent="finance_agent",
        to_agent="tax_agent",
        message_type=MessageType.REQUEST,
        content={"request": "需要验证税务数据"},
        task_id="test_task"
    )
    
    print(f"✅ 消息发布成功: {message_id}")
    
    # 测试消息订阅
    received_messages = []
    
    def message_handler(message):
        received_messages.append(message)
        print(f"📥 收到消息: {message.from_agent} → {message.to_agent}")
    
    message_bus.subscribe("tax_agent", message_handler)
    
    # 发送另一条消息
    await message_bus.publish(
        from_agent="coordinator",
        to_agent="tax_agent",
        message_type=MessageType.NOTIFICATION,
        content={"notification": "任务开始"},
        task_id="test_task"
    )
    
    # 获取消息
    messages = await message_bus.get_messages("tax_agent")
    print(f"✅ 获取到 {len(messages)} 条消息")
    
    # 测试统计信息
    stats = message_bus.get_statistics()
    print(f"✅ 消息总线统计:")
    print(f"   总消息数: {stats['total_messages']}")
    print(f"   活跃订阅者: {stats['active_subscribers']}")


async def test_task_decomposer():
    """测试任务分解器"""
    print("\n" + "=" * 60)
    print("🔧 测试任务分解器")
    print("=" * 60)
    
    decomposer = TaskDecomposer()
    
    # 测试文档
    documents = [
        {
            "id": "doc1",
            "content": "资产负债表 资产总额 1000000 负债总额 800000",
            "filename": "财务报表.pdf",
            "type": "financial_statement"
        },
        {
            "id": "doc2", 
            "content": "增值税申报表 销项税额 100000 进项税额 80000",
            "filename": "税务申报.pdf",
            "type": "tax_return"
        },
        {
            "id": "doc3",
            "content": "合同条款 甲方 乙方 签署日期",
            "filename": "合同.pdf",
            "type": "contract"
        }
    ]
    
    # 执行分解
    result = decomposer.decompose(documents, "comprehensive")
    
    print(f"✅ 任务分解完成")
    print(f"   文档总数: {result['total_documents']}")
    print(f"   高优先级文档: {result['high_priority_documents']}")
    print(f"   需要的审查类型: {', '.join(result['required_audit_types'])}")
    print(f"   预估时间: {result['estimated_time_seconds']} 秒")
    
    # 显示文档分析
    print(f"\n📋 文档分析:")
    for doc in result['document_analysis']:
        print(f"   - {doc['document_id']}: {doc['document_type']} ({doc['priority']})")


async def test_result_merger():
    """测试结果合并器"""
    print("\n" + "=" * 60)
    print("🔀 测试结果合并器")
    print("=" * 60)
    
    merger = ResultMerger()
    
    # 模拟不同 Agent 的发现
    finance_findings = [
        {
            "id": "fin1",
            "agent_name": "finance_agent",
            "category": "资产负债",
            "description": "资产负债表不平衡",
            "risk_level": "high",
            "risk_score": 0.8,
            "confidence": 0.9,
            "evidence": ["资产总额与负债不符"]
        }
    ]
    
    tax_findings = [
        {
            "id": "tax1",
            "agent_name": "tax_agent", 
            "category": "税务合规",
            "description": "增值税计算错误",
            "risk_level": "medium",
            "risk_score": 0.6,
            "confidence": 0.8,
            "evidence": ["税率计算不正确"]
        }
    ]
    
    legal_findings = [
        {
            "id": "leg1",
            "agent_name": "legal_agent",
            "category": "合同条款",
            "description": "合同条款存在法律风险",
            "risk_level": "medium",
            "risk_score": 0.7,
            "confidence": 0.7,
            "evidence": ["条款表述不明确"]
        }
    ]
    
    # 执行合并
    result = merger.merge(finance_findings, tax_findings, legal_findings)
    
    print(f"✅ 结果合并完成")
    print(f"   合并后发现数: {len(result['merged_findings'])}")
    print(f"   检测到冲突: {len(result['conflicts'])}")
    print(f"   综合风险分数: {result['overall_risk_score']:.2f}")
    print(f"   摘要: {result['summary']}")
    
    # 显示统计信息
    stats = result['statistics']
    print(f"\n📊 统计信息:")
    print(f"   风险等级分布: {stats['risk_level_distribution']}")
    print(f"   Agent 贡献: {stats['agent_contribution']}")
    print(f"   平均置信度: {stats['average_confidence']:.2f}")


async def test_coordinator_basic():
    """测试协调器基础功能"""
    print("\n" + "=" * 60)
    print("🎯 测试协调器基础功能")
    print("=" * 60)
    
    coordinator = AgentCoordinator()
    
    print(f"✅ 协调器初始化成功")
    print(f"   消息总线: {'已初始化' if coordinator.message_bus else '未初始化'}")
    
    # 测试状态初始化
    task_id = str(uuid.uuid4())
    documents = [
        {"id": "doc1", "content": "测试内容", "type": "financial_statement"}
    ]
    
    await coordinator._initialize_state(
        task_id=task_id,
        tenant_id="test_tenant",
        user_id="test_user", 
        audit_type="finance",
        documents=documents
    )
    
    print(f"✅ 状态初始化成功")
    print(f"   当前状态: {coordinator.current_state['status'] if coordinator.current_state else 'None'}")
    print(f"   记忆管理器: {'已初始化' if coordinator.memory_manager else '未初始化'}")


async def main():
    """主测试函数"""
    print("🚀 开始阶段 1 基础功能测试")
    print(f"测试时间: {datetime.now()}")
    
    try:
        # 依次执行各项测试
        await test_state_management()
        await test_message_bus()
        await test_task_decomposer()
        await test_result_merger()
        await test_coordinator_basic()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试完成！")
        print("=" * 60)
        print("✅ 状态管理 - 通过")
        print("✅ 消息总线 - 通过")
        print("✅ 任务分解器 - 通过")
        print("✅ 结果合并器 - 通过")
        print("✅ 协调器基础 - 通过")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())