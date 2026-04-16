"""
第一阶段功能测试脚本
测试工作流监控、Agent集成和人工审核追踪功能

使用方法:
1. 确保数据库表已创建成功
2. 运行: python test_workflow_monitor.py
"""

import asyncio
import sys
from datetime import datetime
from uuid import uuid4

async def test_workflow_monitoring():
    """测试工作流监控功能"""
    print("\n" + "="*60)
    print("测试 1: 工作流监控 (WorkflowMonitor)")
    print("="*60)
    
    try:
        from app.workflow import WorkflowMonitor, WorkflowConfig, NodeType
        
        workflow_id = uuid4()
        config = WorkflowConfig(
            workflow_type="test_tax_workflow",
            workflow_version="1.0",
            session_id=workflow_id,
            tenant_id="test_tenant",
            user_id=uuid4(),
            metadata={"test": True}
        )
        
        print(f"✓ 工作流配置创建成功")
        print(f"  - workflow_type: {config.workflow_type}")
        print(f"  - workflow_id: {workflow_id}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_workflow_integration():
    """测试Agent-Workflow集成"""
    print("\n" + "="*60)
    print("测试 2: Agent-Workflow 集成")
    print("="*60)
    
    try:
        from app.workflow import AgentWorkflowIntegrator, WorkflowContext
        
        workflow_trace_id = uuid4()
        node_execution_id = uuid4()
        
        context = WorkflowContext(
            workflow_trace_id=workflow_trace_id,
            node_execution_id=node_execution_id,
            node_name="test_node",
            workflow_type="test",
            execution_order=0
        )
        
        print(f"✓ 工作流上下文创建成功")
        print(f"  - workflow_trace_id: {workflow_trace_id}")
        print(f"  - node_execution_id: {node_execution_id}")
        print(f"  - node_name: {context.node_name}")
        print(f"  - workflow_type: {context.workflow_type}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_human_review_tracker():
    """测试人工审核追踪器"""
    print("\n" + "="*60)
    print("测试 3: 人工审核追踪器")
    print("="*60)
    
    try:
        from app.workflow import HumanReviewTracker, ReviewAction, ReviewPriority
        
        print(f"✓ 人工审核追踪器导入成功")
        print(f"  - ReviewAction: {list(ReviewAction)}")
        print(f"  - ReviewPriority: {list(ReviewPriority)}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database_connection():
    """测试数据库连接和表"""
    print("\n" + "="*60)
    print("测试 4: 数据库连接和表结构")
    print("="*60)
    
    try:
        from sqlalchemy import text
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            print(f"✓ 数据库连接成功")
            
            result = await session.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('workflow_traces', 'workflow_node_executions')
                """)
            )
            tables = [row[0] for row in result.fetchall()]
            
            if 'workflow_traces' in tables and 'workflow_node_executions' in tables:
                print(f"✓ 表创建成功: {tables}")
                return True
            else:
                print(f"✗ 缺少表: {tables}")
                return False
                
    except Exception as e:
        print(f"✗ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🚀 第一阶段功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now()}")
    
    tests = [
        ("数据库连接", test_database_connection),
        ("工作流监控", test_workflow_monitoring),
        ("Agent集成", test_agent_workflow_integration),
        ("人工审核追踪", test_human_review_tracker),
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
