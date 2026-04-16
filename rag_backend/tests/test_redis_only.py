"""
专门测试Redis连接
"""

import asyncio
import redis.asyncio as redis
from app.core.config import settings


async def test_redis_connection():
    """测试Redis连接"""
    
    print("📦 测试Redis连接")
    print("=" * 40)
    print(f"主机: {settings.REDIS_HOST}")
    print(f"端口: {settings.REDIS_PORT}")
    print(f"数据库: {settings.REDIS_DB}")
    print(f"密码: {settings.REDIS_PASSWORD}")
    
    try:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 测试连接
        await redis_client.ping()
        print("✅ Redis连接成功！")
        
        # 测试读写
        test_key = "test_final"
        test_value = "redis_working"
        
        await redis_client.set(test_key, test_value, ex=10)
        retrieved_value = await redis_client.get(test_key)
        
        if retrieved_value == test_value:
            print("✅ Redis读写测试成功！")
            await redis_client.delete(test_key)
            
            # 测试应用的Redis服务
            try:
                from app.services.redis_service import redis_service
                await redis_service.set("app_test", "working", expire=10)
                app_value = await redis_service.get("app_test")
                
                if app_value == "working":
                    print("✅ 应用Redis服务正常！")
                    await redis_service.delete("app_test")
                else:
                    print("❌ 应用Redis服务异常")
                    
            except Exception as e:
                print(f"❌ 应用Redis服务测试失败: {e}")
            
            await redis_client.aclose()
            return True
        else:
            print(f"❌ Redis读写测试失败")
            await redis_client.aclose()
            return False
        
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_redis_connection())