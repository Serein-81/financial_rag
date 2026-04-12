import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisConnectionPool:
    _instance: Optional["RedisConnectionPool"] = None
    _pool: Optional[redis.ConnectionPool] = None
    _lock: asyncio.Lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if cls._lock is None:
                cls._lock = asyncio.Lock()
        return cls._instance
    
    @classmethod
    async def initialize(cls) -> None:
        if cls._pool is not None:
            return
        
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        
        async with cls._lock:
            if cls._pool is not None:
                return
            
            logger.info("初始化 Redis 连接池...")
            cls._pool = redis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
                max_connections=20,
            )
            logger.info("Redis 连接池初始化完成")
    
    @classmethod
    async def get_client(cls) -> redis.Redis:
        if cls._pool is None:
            await cls.initialize()
        return redis.Redis(connection_pool=cls._pool)
    
    @classmethod
    async def close(cls) -> None:
        if cls._pool is not None:
            async with cls._lock:
                if cls._pool is not None:
                    logger.info("关闭 Redis 连接池...")
                    await cls._pool.disconnect()
                    cls._pool = None
                    logger.info("Redis 连接池已关闭")


class ResourceManager:
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        if self._initialized:
            return
        
        logger.info("初始化 ResourceManager...")
        self._redis_client = await RedisConnectionPool.get_client()
        await self._redis_client.ping()
        self._initialized = True
        logger.info("ResourceManager 初始化完成")
    
    @property
    def redis(self) -> redis.Redis:
        if self._redis_client is None:
            raise RuntimeError("ResourceManager 未初始化，请先调用 initialize()")
        return self._redis_client
    
    async def close(self) -> None:
        if self._redis_client is not None:
            logger.info("关闭 ResourceManager...")
            self._redis_client = None
            self._initialized = False
            logger.info("ResourceManager 已关闭")
    
    async def health_check(self) -> dict:
        checks = {
            "redis": False,
        }
        
        try:
            if self._redis_client:
                await self._redis_client.ping()
                checks["redis"] = True
        except Exception as e:
            logger.error(f"Redis 健康检查失败: {e}")
        
        return checks


_resource_manager_instance: Optional[ResourceManager] = None


@asynccontextmanager
async def make_resource_manager() -> AsyncIterator[ResourceManager]:
    """
    异步上下文管理器，用于统一管理应用资源
    
    用法:
    async with make_resource_manager() as rm:
        await rm.redis.get("key")
    
    退出时自动清理所有资源
    """
    global _resource_manager_instance
    
    rm = ResourceManager()
    try:
        await rm.initialize()
        _resource_manager_instance = rm
        yield rm
    finally:
        await rm.close()
        _resource_manager_instance = None


async def get_resource_manager() -> ResourceManager:
    """
    获取全局 ResourceManager 实例
    
    注意: 必须确保在 make_resource_manager 上下文中调用
    """
    global _resource_manager_instance
    
    if _resource_manager_instance is None:
        raise RuntimeError(
            "ResourceManager 未初始化，请在 FastAPI lifespan 中使用 "
            "make_resource_manager() 上下文管理器"
        )
    return _resource_manager_instance
