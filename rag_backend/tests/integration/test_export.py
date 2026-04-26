"""
测试会话导出功能
"""
import asyncio
import sys
sys.path.insert(0, 'd:/Python/Codebase/My_rag/rag_backend')

from app.services.chat_log_service import ChatLogService

async def test_export():
    service = ChatLogService()
    
    print("测试导出功能...")
    try:
        # 测试获取会话列表
        result = await service.get_sessions(
            current_user_id="4df4ba33-4ee8-41d4-b40f-b9e930551d9d",  # 替换为实际用户ID
            page=1,
            page_size=10
        )
        print(f"✅ 获取会话成功！总数: {result['total']}")
        print(f"会话数量: {len(result['sessions'])}")
        
        if result['sessions']:
            print("\n示例会话数据:")
            session = result['sessions'][0]
            for key, value in session.items():
                print(f"  {key}: {value}")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_export())
