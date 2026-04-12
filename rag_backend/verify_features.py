"""
新功能验证脚本

用于验证所有新增功能是否正常工作
"""

import asyncio
import sys
from datetime import datetime
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'

async def verify_all():
    """验证所有新功能"""
    print("=" * 80)
    print("RAG Backend 新功能验证")
    print("=" * 80)
    print()
    
    results = {
        "success": [],
        "failed": []
    }
    
    # 1. 验证导入
    print("[1/6] 验证模块导入...")
    try:
        from app.middleware.rate_limit_middleware import (
            RateLimitMiddleware,
            RateLimitStrategy,
            RateLimitTier
        )
        from app.services.streaming_service import (
            StreamingService,
            StreamState,
            streaming_service
        )
        from app.services.snapshot_service import (
            SnapshotService,
            SnapshotType,
            snapshot_service
        )
        from app.services.suggestion_service import (
            SuggestionService,
            SuggestionType,
            suggestion_service
        )
        from app.services.health_service import (
            HealthService,
            HealthStatus,
            health_service
        )
        
        print("   [OK] 所有模块导入成功")
        results["success"].append("模块导入")
    except Exception as e:
        print(f"   [FAIL] 模块导入失败: {e}")
        results["failed"].append(f"模块导入: {e}")
    
    # 2. 验证限流服务
    print("\n[2/6] 验证限流服务...")
    try:
        from app.middleware.rate_limit_middleware import RateLimitMiddleware, RateLimitTier
        
        tier = RateLimitTier(requests_per_minute=60, requests_per_hour=1000, burst_size=10)
        print(f"   [OK] 限流层级配置成功")
        print(f"   [OK] 端点限流数: {len(RateLimitMiddleware.ENDPOINT_TIERS)}")
        
        results["success"].append("限流服务")
    except Exception as e:
        print(f"   [FAIL] 限流服务验证失败: {e}")
        results["failed"].append(f"限流服务: {e}")
    
    # 3. 验证流式服务
    print("\n[3/6] 验证流式服务...")
    try:
        from app.services.streaming_service import streaming_service
        
        stream_id = await streaming_service.create_stream(
            session_id="test_session",
            metadata={"test": True}
        )
        print(f"   [OK] 流创建成功: {stream_id}")
        
        await streaming_service.start_stream(stream_id)
        print(f"   [OK] 流启动成功")
        
        progress = await streaming_service.get_progress(stream_id)
        print(f"   [OK] 进度查询成功: {progress['state']}")
        
        results["success"].append("流式服务")
    except Exception as e:
        print(f"   [FAIL] 流式服务验证失败: {e}")
        results["failed"].append(f"流式服务: {e}")
    
    # 4. 验证快照服务
    print("\n[4/6] 验证快照服务...")
    try:
        from app.services.snapshot_service import SnapshotService, SnapshotType
        
        # 验证服务类和类型存在
        service = SnapshotService()
        print(f"   [OK] 快照服务实例化成功")
        print(f"   [OK] 快照类型数量: {len(SnapshotType)}")
        
        # 注意：创建快照需要真实数据库会话，这里只验证API存在
        print(f"   [OK] 快照API验证完成（需要真实会话才能完整测试）")
        
        results["success"].append("快照服务")
    except Exception as e:
        print(f"   [FAIL] 快照服务验证失败: {e}")
        results["failed"].append(f"快照服务: {e}")
    
    # 5. 验证建议服务
    print("\n[5/6] 验证建议服务...")
    try:
        from app.services.suggestion_service import suggestion_service, SuggestionType, ConversationContext
        
        context = ConversationContext(
            topic="机器学习",
            entities=["机器学习", "人工智能"],
            intents=["学习", "了解"],
            sentiment="neutral",
            complexity="medium",
            domain="技术"
        )
        
        suggestions = await suggestion_service.generate_suggestions(
            context=context,
            current_answer="机器学习是人工智能的一个分支...",
            suggestion_types=[SuggestionType.DEEPEN, SuggestionType.EXAMPLE],
            count=3
        )
        print(f"   [OK] 建议生成成功: {len(suggestions)} 条")
        
        for i, s in enumerate(suggestions[:2], 1):
            print(f"      {i}. [{s.type.value}] {s.text[:50]}...")
        
        results["success"].append("建议服务")
    except Exception as e:
        print(f"   [FAIL] 建议服务验证失败: {e}")
        results["failed"].append(f"建议服务: {e}")
    
    # 6. 验证健康检查
    print("\n[6/6] 验证健康检查服务...")
    try:
        from app.services.health_service import health_service
        
        # 快速检查
        quick_report = await health_service.check_quick()
        print(f"   [OK] 快速健康检查完成")
        print(f"      状态: {quick_report['status']}")
        print(f"      组件数: {len(quick_report['components'])}")
        
        results["success"].append("健康检查")
    except Exception as e:
        print(f"   [FAIL] 健康检查验证失败: {e}")
        results["failed"].append(f"健康检查: {e}")
    
    # 打印总结
    print("\n" + "=" * 80)
    print("验证总结")
    print("=" * 80)
    print(f"[SUCCESS] 成功: {len(results['success'])} 项")
    for item in results["success"]:
        print(f"   - {item}")
    
    if results["failed"]:
        print(f"\n[FAIL] 失败: {len(results['failed'])} 项")
        for item in results["failed"]:
            print(f"   - {item}")
        print("\n[WARN] 部分功能验证失败，请检查错误信息")
        return False
    else:
        print("\n[COMPLETE] 所有功能验证通过！")
        return True


if __name__ == "__main__":
    try:
        success = asyncio.run(verify_all())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] 验证被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] 验证过程异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
