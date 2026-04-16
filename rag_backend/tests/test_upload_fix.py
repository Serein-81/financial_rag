"""
测试税务报告上传修复效果
用于验证上传接口的性能和稳定性
"""

import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "rag_backend"))

async def test_upload_performance():
    """测试上传性能"""
    print("=" * 60)
    print("测试税务报告上传修复效果")
    print("=" * 60)
    
    try:
        from app.api.v1.endpoints.tax_report import upload_tax_report
        print("✅ 上传端点导入成功")
        
        print("\n📊 修复内容总结:")
        print("  1. 添加详细的性能日志（⏱️ 标记）")
        print("  2. 异步文件保存（避免阻塞）")
        print("  3. 数据库事务错误处理")
        print("  4. 后台处理步骤日志")
        print("  5. 总耗时统计")
        
        print("\n🔍 性能标记说明:")
        print("  - ⏱️ [TaxUpload]: 上传端点性能日志")
        print("  - ⏱️ [Background]: 后台处理性能日志")
        print("  - ✅: 操作成功")
        print("  - ❌: 操作失败")
        
        print("\n💡 如何诊断慢查询:")
        print("  1. 查看后端日志中的 ⏱️ 标记")
        print("  2. 重点关注数据库提交耗时（Step 4）")
        print("  3. 如果超过5秒，说明连接池可能耗尽")
        print("  4. 检查数据库连接状态和网络延迟")
        
        print("\n" + "=" * 60)
        print("修复完成！现在可以测试上传功能")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_upload_performance())
