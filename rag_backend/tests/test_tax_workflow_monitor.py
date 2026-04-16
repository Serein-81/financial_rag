"""
第二阶段 - 税务工作流监控测试

测试税务工作流与监控系统的集成：
1. 工作流生命周期追踪
2. 节点执行追踪
3. 人工审核追踪
4. 错误追踪

使用方法:
1. 确保数据库表已创建（第一阶段完成）
2. 运行: python test_tax_workflow_monitor.py
"""

import asyncio
import sys
from datetime import datetime
from uuid import uuid4

async def test_tax_workflow_monitor():
    """测试税务工作流监控"""
    print("\n" + "="*60)
    print("测试: 税务工作流监控集成")
    print("="*60)
    
    try:
        from app.workflow import NodeType, ReviewPriority
        from app.workflow.tax_workflow_monitor import TaxWorkflowMonitor
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            monitor = TaxWorkflowMonitor(db)
            
            print(f"✓ TaxWorkflowMonitor 初始化成功")
            
            test_state = {
                "analysis_id": str(uuid4()),
                "tenant_id": "test_tenant_001",
                "user_id": uuid4(),
                "session_id": uuid4(),
                "fiscal_year": 2024,
                "tax_types": ["vat", "income_tax"],
                "validation_level": "normal",
                "status": "pending"
            }
            
            workflow_trace_id = monitor.start_workflow(
                state=test_state,
                total_nodes=8
            )
            
            print(f"✓ 工作流追踪启动成功")
            print(f"  - workflow_trace_id: {workflow_trace_id}")
            
            node_execution_id = monitor.start_node(
                node_name="validate_submission",
                node_type=NodeType.AGENT,
                input_data={"fiscal_year": test_state["fiscal_year"]}
            )
            
            print(f"✓ 节点追踪启动成功")
            print(f"  - node_execution_id: {node_execution_id}")
            
            monitor.complete_node(
                node_name="validate_submission",
                output_data={"is_valid": True},
                execution_time_ms=150.5
            )
            
            print(f"✓ 节点追踪完成")
            
            summary = monitor.get_execution_summary()
            print(f"✓ 获取执行摘要成功")
            print(f"  - status: {summary.get('status')}")
            print(f"  - completed_nodes: {summary.get('completed_nodes')}")
            
            monitor.complete_workflow(
                status="completed",
                output_data={"analysis_id": test_state["analysis_id"]}
            )
            
            print(f"✓ 工作流追踪完成")
            
            return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_node_tracking():
    """测试节点追踪功能"""
    print("\n" + "="*60)
    print("测试: 节点追踪装饰器")
    print("="*60)
    
    try:
        from app.workflow import NodeType
        from app.workflow.tax_workflow_monitor import TaxWorkflowMonitor
        from app.workflow.base_nodes import NodeExecutionTracker
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            monitor = TaxWorkflowMonitor(db)
            tracker = NodeExecutionTracker(monitor)
            
            test_state = {
                "analysis_id": str(uuid4()),
                "tenant_id": "test_tenant_001",
                "user_id": uuid4(),
                "session_id": uuid4(),
                "fiscal_year": 2024,
                "tax_types": ["vat"],
                "status": "pending"
            }
            
            workflow_trace_id = monitor.start_workflow(test_state, total_nodes=3)
            
            @tracker.track_node_execution(
                node_name="test_node",
                node_type=NodeType.AGENT
            )
            async def sample_node(state):
                await asyncio.sleep(0.1)
                return {"result": "success", "status": "completed"}
            
            result = await sample_node(test_state)
            
            print(f"✓ 节点追踪装饰器测试成功")
            print(f"  - result: {result}")
            
            monitor.complete_workflow(status="completed")
            
            return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_human_review_tracking():
    """测试人工审核追踪"""
    print("\n" + "="*60)
    print("测试: 人工审核追踪")
    print("="*60)
    
    try:
        from app.workflow import ReviewAction, ReviewPriority
        from app.workflow.tax_workflow_monitor import TaxWorkflowMonitor
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            monitor = TaxWorkflowMonitor(db)
            
            test_state = {
                "analysis_id": str(uuid4()),
                "tenant_id": "test_tenant_001",
                "user_id": uuid4(),
                "session_id": uuid4(),
                "fiscal_year": 2024,
                "tax_types": ["vat"],
                "status": "pending"
            }
            
            workflow_trace_id = monitor.start_workflow(test_state, total_nodes=8)
            
            from app.langgraph.tax_workflow.state import RiskItem
            test_risk_items = [
                RiskItem(
                    risk_id="risk_001",
                    risk_type="high_tax_rate",
                    severity="high",
                    description="增值税税负率异常偏高",
                    confidence=0.85
                )
            ]
            
            tracking_id = await monitor.start_human_review(
                state=test_state,
                risk_items=test_risk_items,
                priority=ReviewPriority.HIGH
            )
            
            print(f"✓ 人工审核追踪创建成功")
            print(f"  - tracking_id: {tracking_id}")
            
            await monitor.record_review_action(
                tracking_id=tracking_id,
                action=ReviewAction.APPROVE,
                reviewer_id=str(test_state["user_id"]),
                comments="审核通过，数据核实无误"
            )
            
            print(f"✓ 审核动作记录成功")
            
            monitor.complete_workflow(status="completed")
            
            return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_error_tracking():
    """测试错误追踪"""
    print("\n" + "="*60)
    print("测试: 错误追踪")
    print("="*60)
    
    try:
        from app.workflow import NodeType
        from app.workflow.tax_workflow_monitor import TaxWorkflowMonitor
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            monitor = TaxWorkflowMonitor(db)
            
            test_state = {
                "analysis_id": str(uuid4()),
                "tenant_id": "test_tenant_001",
                "user_id": uuid4(),
                "session_id": uuid4(),
                "fiscal_year": 2024,
                "status": "pending"
            }
            
            workflow_trace_id = monitor.start_workflow(test_state, total_nodes=8)
            
            node_execution_id = monitor.start_node(
                node_name="calculate_taxes",
                node_type=NodeType.AGENT
            )
            
            test_error = ValueError("税务计算失败：数据格式错误")
            
            monitor.record_error(
                node_name="calculate_taxes",
                error=test_error,
                error_context={
                    "calculation_data": {"tax_type": "vat"},
                    "error_code": "INVALID_DATA_FORMAT"
                }
            )
            
            print(f"✓ 错误追踪记录成功")
            
            monitor.complete_workflow(
                status="failed",
                error_message=str(test_error)
            )
            
            print(f"✓ 工作流失败状态记录成功")
            
            return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integration_with_tax_workflow():
    """测试与税务工作流的集成"""
    print("\n" + "="*60)
    print("测试: 与税务工作流集成")
    print("="*60)
    
    try:
        from app.langgraph.tax_workflow import TaxSubmissionWorkflow
        from app.workflow.tax_workflow_monitor import TaxWorkflowMonitor
        
        print(f"✓ TaxSubmissionWorkflow 导入成功")
        print(f"✓ TaxWorkflowMonitor 导入成功")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🚀 第二阶段 - 税务工作流监控测试")
    print("="*60)
    print(f"开始时间: {datetime.now()}")
    
    tests = [
        ("税务工作流监控", test_tax_workflow_monitor),
        ("节点追踪装饰器", test_node_tracking),
        ("人工审核追踪", test_human_review_tracking),
        ("错误追踪", test_error_tracking),
        ("税务工作流集成", test_integration_with_tax_workflow),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} 测试异常: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    print(f"结束时间: {datetime.now()}")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
