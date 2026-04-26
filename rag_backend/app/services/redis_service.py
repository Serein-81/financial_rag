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
    
    async def enqueue_task(self, queue_name: str, task_data: dict) -> bool:
        """
        将任务放入 Redis 队列（用于 ARQ）
        
        Args:
            queue_name: 队列名称，如 "arq:default"
            task_data: 任务数据
            
        Returns:
            是否成功
        """
        try:
            import json
            task_json = json.dumps(task_data, default=str)
            
            if self.client:
                self.client.rpush(queue_name, task_json)
                logger.info(f"[Redis] 任务已入队: queue={queue_name}, data={str(task_data)[:100]}...")
                return True
            else:
                logger.warning("[Redis] Redis 未连接，无法入队")
                return False
        except Exception as e:
            logger.error(f"[Redis] 入队失败: {e}")
            return False
    
    def dequeue_task(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """
        从 Redis 队列取出任务（用于 Worker）
        
        Args:
            queue_name: 队列名称
            timeout: 阻塞等待时间（秒），0 表示非阻塞
            
        Returns:
            任务数据或 None
        """
        try:
            import json
            if self.client:
                if timeout > 0:
                    result = self.client.blpop(queue_name, timeout=timeout)
                    if result:
                        _, task_json = result
                        return json.loads(task_json)
                else:
                    task_json = self.client.lpop(queue_name)
                    if task_json:
                        return json.loads(task_json)
            return None
        except Exception as e:
            logger.error(f"[Redis] 出队失败: {e}")
            return None


# 创建全局实例
redis_service = RedisService()


def get_redis_service() -> RedisService:
    """获取Redis服务实例（单例模式）"""
    return redis_service