"""
第三阶段 - 政策推送工作流监控测试

测试政策推送工作流与监控系统的集成：
1. 工作流生命周期追踪
2. 政策采集追踪
3. 企业匹配追踪
4. 通知发送追踪
5. 订阅管理追踪

使用方法:
1. 确保数据库表已创建（第一阶段完成）
2. 运行: python test_policy_workflow_monitor.py
"""

import sys
import asyncio
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, "d:/Python/Codebase/My_rag/rag_backend")

from app.db.session import AsyncSessionLocal
from app.workflow.policy_workflow_monitor import (
    PolicyWorkflowMonitor,
    PolicyMatchLevel,
    NotificationChannel,
)
from app.workflow.human_review_tracker import ReviewAction, ReviewPriority


async def test_policy_workflow_monitor():
    """测试政策推送工作流监控"""
    print("\n" + "="*60)
    print("测试: 政策推送工作流监控")
    print("="*60)
    
    async with AsyncSessionLocal() as db:
        try:
            monitor = PolicyWorkflowMonitor(db)
            
            policy_id = str(uuid4())
            tenant_id = "tenant_001"
            
            print(f"✓ PolicyWorkflowMonitor 初始化成功")
            print(f"  - policy_id: {policy_id}")
            print(f"  - tenant_id: {tenant_id}")
            
            workflow_trace_id = monitor.start_workflow(
                policy_id=policy_id,
                tenant_id=tenant_id,
                total_nodes=8
            )
            
            print(f"✓ 工作流追踪启动成功")
            print(f"  - workflow_trace_id: {workflow_trace_id}")
            
            return True
            
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_policy_monitoring():
    """测试政策监控功能"""
    print("\n" + "="*60)
    print("测试: 政策监控功能")
    print("="*60)
    
    async with AsyncSessionLocal() as db:
        try:
            monitor = PolicyWorkflowMonitor(db)
            
            policy_id = str(uuid4())
            
            workflow_trace_id = monitor.start_workflow(
                policy_id=policy_id,
                tenant_id="tenant_001",
                total_nodes=8
            )
            
            monitor.record_policy_collection(
                policy_id=policy_id,
                source="国家税务总局",
                collection_count=1,
                is_update=False
            )
            print(f"✓ 政策采集记录成功")
            
            monitor.record_policy_parsing(
                policy_id=policy_id,
                parsed_fields=["industries", "regions", "tax_types", "priority"],
                extraction_success=True
            )
            print(f"✓ 政策解析记录成功")
            
            enterprise_id = str(uuid4())
            monitor.record_enterprise_matching(
                policy_id=policy_id,
                enterprise_id=enterprise_id,
                match_score=0.85,
                match_level=PolicyMatchLevel.HIGH,
                match_criteria={
                    "industry_match": True,
                    "region_match": True
                },
                match_reasons=[
                    "适用于行业: 制造业",
                    "适用地区: 广东省"
                ]
            )
            print(f"✓ 企业匹配记录成功 (分数: 0.85)")
            
            monitor.record_match_scoring(
                policy_id=policy_id,
                enterprise_id=enterprise_id,
                industry_score=0.4,
                region_score=0.2,
                tax_type_score=0.3,
                scale_score=0.1,
                final_score=0.85
            )
            print(f"✓ 匹配评分记录成功")
            
            monitor.record_notification_preparation(
                policy_id=policy_id,
                enterprise_id=enterprise_id,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.SSE
                ],
                notification_content={
                    "title": "新政策通知",
                    "policy_title": "关于支持中小企业发展的税收优惠政策"
                },
                priority="high"
            )
            print(f"✓ 通知准备记录成功")
            
            monitor.record_notification_sending(
                policy_id=policy_id,
                enterprise_id=enterprise_id,
                channel=NotificationChannel.EMAIL,
                sent=True,
                sent_at=datetime.now()
            )
            print(f"✓ 通知发送记录成功")
            
            monitor.complete_workflow(
                status="completed",
                matched_count=1,
                notified_count=1
            )
            print(f"✓ 工作流完成记录成功")
            
            return True
            
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_subscription_management():
    """测试订阅管理追踪"""
    print("\n" + "="*60)
    print("测试: 订阅管理追踪")
    print("="*60)
    
    async with AsyncSessionLocal() as db:
        try:
            monitor = PolicyWorkflowMonitor(db)
            
            subscription_id = str(uuid4())
            tenant_id = "tenant_001"
            
            workflow_trace_id = monitor.start_workflow(
                policy_id="subscription_workflow",
                tenant_id=tenant_id,
                total_nodes=1
            )
            
            monitor.record_subscription_management(
                subscription_id=subscription_id,
                action="create",
                tenant_id=tenant_id,
                categories=["税收优惠", "技术创新"],
                channels=["email", "webhook"],
                success=True
            )
            print(f"✓ 订阅创建记录成功")
            
            monitor.record_subscription_management(
                subscription_id=subscription_id,
                action="update",
                tenant_id=tenant_id,
                categories=["税收优惠", "技术创新", "人才引进"],
                channels=["email", "webhook", "sse"],
                success=True
            )
            print(f"✓ 订阅更新记录成功")
            
            monitor.complete_workflow(status="completed")
            print(f"✓ 订阅管理工作流完成")
            
            return True
            
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_policy_update_detection():
    """测试政策更新检测追踪"""
    print("\n" + "="*60)
    print("测试: 政策更新检测追踪")
    print("="*60)
    
    async with AsyncSessionLocal() as db:
        try:
            monitor = PolicyWorkflowMonitor(db)
            
            policy_id = str(uuid4())
            
            workflow_trace_id = monitor.start_workflow(
                policy_id=policy_id,
                tenant_id="tenant_001",
                total_nodes=1
            )
            
            affected_enterprises = [str(uuid4()) for _ in range(5)]
            
            monitor.record_policy_update_detection(
                policy_id=policy_id,
                update_type="amendment",
                affected_enterprises=affected_enterprises,
                notification_sent=True
            )
            print(f"✓ 政策更新检测记录成功 (影响: {len(affected_enterprises)} 个企业)")
            
            monitor.complete_workflow(status="completed")
            print(f"✓ 政策更新检测工作流完成")
            
            return True
            
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("🚀 第三阶段功能测试 - 政策推送工作流监控")
    print("="*60)
    print(f"开始时间: {datetime.now()}")
    
    results = []
    
    results.append(("政策推送工作流监控", await test_policy_workflow_monitor()))
    results.append(("政策监控功能", await test_policy_monitoring()))
    results.append(("订阅管理追踪", await test_subscription_management()))
    results.append(("政策更新检测追踪", await test_policy_update_detection()))
    
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
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
