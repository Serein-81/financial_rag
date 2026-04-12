# app/services/redis_service.py

"""
Redis服务

用于存储验证码、防刷机制等临时数据
"""

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class RedisService:
    """Redis服务类"""
    
    def __init__(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis 模块未安装，RedisService 将不可用")
            self.client = None
            return
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.client.ping()
            logger.info("✅ Redis连接成功")
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            logger.warning("⚠️ 将使用内存字典作为备用存储")
            self.client = None
            self._memory_store = {}  # 备用内存存储
    
    def set_with_expire(self, key: str, value: str, expire: int) -> bool:
        """设置键值对并设置过期时间"""
        try:
            if self.client:
                return self.client.setex(key, expire, value)
            else:
                # 使用内存存储
                import time
                self._memory_store[key] = {
                    'value': value,
                    'expire_at': time.time() + expire
                }
                return True
        except Exception as e:
            logger.error(f"Redis set_with_expire 失败: {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """获取键值"""
        try:
            if self.client:
                return self.client.get(key)
            else:
                # 使用内存存储
                import time
                if key in self._memory_store:
                    data = self._memory_store[key]
                    if time.time() < data['expire_at']:
                        return data['value']
                    else:
                        del self._memory_store[key]
                return None
        except Exception as e:
            logger.error(f"Redis get 失败: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """删除键"""
        try:
            if self.client:
                return self.client.delete(key) > 0
            else:
                # 使用内存存储
                if key in self._memory_store:
                    del self._memory_store[key]
                    return True
                return False
        except Exception as e:
            logger.error(f"Redis delete 失败: {e}")
            return False
    
    def incr(self, key: str) -> int:
        """递增计数器"""
        try:
            if self.client:
                return self.client.incr(key)
            else:
                # 使用内存存储
                if key not in self._memory_store:
                    self._memory_store[key] = {'value': '0', 'expire_at': float('inf')}
                current = int(self._memory_store[key]['value'])
                self._memory_store[key]['value'] = str(current + 1)
                return current + 1
        except Exception as e:
            logger.error(f"Redis incr 失败: {e}")
            return 0
    
    def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            if self.client:
                return self.client.expire(key, seconds)
            else:
                # 使用内存存储
                import time
                if key in self._memory_store:
                    self._memory_store[key]['expire_at'] = time.time() + seconds
                    return True
                return False
        except Exception as e:
            logger.error(f"Redis expire 失败: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            if self.client:
                return self.client.exists(key) > 0
            else:
                # 使用内存存储
                import time
                if key in self._memory_store:
                    if time.time() < self._memory_store[key]['expire_at']:
                        return True
                    else:
                        del self._memory_store[key]
                return False
        except Exception as e:
            logger.error(f"Redis exists 失败: {e}")
            return False


# 创建全局实例
redis_service = RedisService()


def get_redis_service() -> RedisService:
    """获取Redis服务实例（单例模式）"""
    return redis_service