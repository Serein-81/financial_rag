"""
LangGraph 持久化存储

提供 Redis 和 PostgreSQL 两种 Checkpointer 实现
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseCheckpointer(ABC):
    """检查点基类"""
    
    @abstractmethod
    async def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取检查点"""
        pass
    
    @abstractmethod
    async def put(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        """保存检查点"""
        pass
    
    @abstractmethod
    async def delete(self, thread_id: str) -> None:
        """删除检查点"""
        pass
    
    @abstractmethod
    async def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        pass


class RedisCheckpointer(BaseCheckpointer):
    """
    Redis 检查点存储
    
    适用于：
    - 高性能要求
    - 分布式部署
    - TTL 自动过期
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "langgraph:checkpoint:",
        ttl_seconds: int = 86400 * 7
    ):
        """
        初始化 Redis 检查点存储
        
        Args:
            redis_url: Redis 连接 URL
            key_prefix: 键前缀
            ttl_seconds: 过期时间（秒），默认 7 天
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
        self._redis = None
        
        logger.info(f"[Redis Checkpointer] 初始化 | URL: {redis_url}")
        logger.info(f"  - Key 前缀: {key_prefix}")
        logger.info(f"  - TTL: {ttl_seconds}s ({ttl_seconds // 86400} 天)")
    
    async def _get_redis(self):
        """获取 Redis 连接"""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                logger.warning("[Redis Checkpointer] redis.asyncio 未安装，使用模拟实现")
                self._redis = None
        return self._redis
    
    async def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取检查点"""
        redis = await self._get_redis()
        if redis is None:
            return None
        
        try:
            key = f"{self.key_prefix}{thread_id}"
            data = await redis.get(key)
            
            if data:
                checkpoint = json.loads(data)
                logger.debug(f"[Redis Checkpointer] 获取检查点: {thread_id[:8]}...")
                return checkpoint
            
            return None
        except Exception as e:
            logger.error(f"[Redis Checkpointer] 获取失败: {e}")
            return None
    
    async def put(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        """保存检查点"""
        redis = await self._get_redis()
        if redis is None:
            return
        
        try:
            key = f"{self.key_prefix}{thread_id}"
            checkpoint["_updated_at"] = datetime.now().isoformat()
            
            await redis.setex(
                key,
                self.ttl_seconds,
                json.dumps(checkpoint, default=str)
            )
            
            logger.debug(f"[Redis Checkpointer] 保存检查点: {thread_id[:8]}... TTL: {self.ttl_seconds}s")
        except Exception as e:
            logger.error(f"[Redis Checkpointer] 保存失败: {e}")
    
    async def delete(self, thread_id: str) -> None:
        """删除检查点"""
        redis = await self._get_redis()
        if redis is None:
            return
        
        try:
            key = f"{self.key_prefix}{thread_id}"
            await redis.delete(key)
            logger.debug(f"[Redis Checkpointer] 删除检查点: {thread_id[:8]}...")
        except Exception as e:
            logger.error(f"[Redis Checkpointer] 删除失败: {e}")
    
    async def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        redis = await self._get_redis()
        if redis is None:
            return []
        
        try:
            pattern = f"{self.key_prefix}*"
            keys = []
            
            async for key in redis.scan_iter(match=pattern, count=limit):
                keys.append(key)
            
            checkpoints = []
            for key in keys[:limit]:
                data = await redis.get(key)
                if data:
                    checkpoint = json.loads(data)
                    checkpoint["_thread_id"] = key.replace(self.key_prefix, "")
                    checkpoints.append(checkpoint)
            
            return checkpoints
        except Exception as e:
            logger.error(f"[Redis Checkpointer] 列出失败: {e}")
            return []


class PostgresCheckpointer(BaseCheckpointer):
    """
    PostgreSQL 检查点存储
    
    适用于：
    - 持久性要求高
    - 需要复杂查询
    - 审计追踪
    """
    
    _table_created = False
    
    def __init__(
        self,
        db_session_factory=None,
        table_name: str = "langgraph_checkpoints"
    ):
        """
        初始化 PostgreSQL 检查点存储
        
        Args:
            db_session_factory: 数据库会话工厂
            table_name: 表名
        """
        self.db_session_factory = db_session_factory
        self.table_name = table_name
        
        logger.info(f"[Postgres Checkpointer] 初始化 | 表: {table_name}")
    
    async def _ensure_table(self):
        """确保表存在"""
        if PostgresCheckpointer._table_created:
            return
        
        if self.db_session_factory is None:
            logger.warning("[Postgres Checkpointer] 无数据库会话工厂，跳过表创建")
            return
        
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    thread_id VARCHAR(255) PRIMARY KEY,
                    checkpoint JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_updated_at 
                ON {self.table_name}(updated_at);
                """
                
                await session.execute(text(create_table_sql))
                await session.commit()
                
                PostgresCheckpointer._table_created = True
                logger.info(f"[Postgres Checkpointer] 表 {self.table_name} 创建完成")
        except Exception as e:
            logger.error(f"[Postgres Checkpointer] 表创建失败: {e}")
    
    async def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取检查点"""
        await self._ensure_table()
        
        if self.db_session_factory is None:
            return None
        
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import select, text
                
                result = await session.execute(
                    text(f"SELECT checkpoint, updated_at FROM {self.table_name} WHERE thread_id = :thread_id"),
                    {"thread_id": thread_id}
                )
                row = result.fetchone()
                
                if row:
                    checkpoint = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    checkpoint["_updated_at"] = row[1].isoformat() if row[1] else None
                    logger.debug(f"[Postgres Checkpointer] 获取检查点: {thread_id[:8]}...")
                    return checkpoint
                
                return None
        except Exception as e:
            logger.error(f"[Postgres Checkpointer] 获取失败: {e}")
            return None
    
    async def put(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        """保存检查点"""
        await self._ensure_table()
        
        if self.db_session_factory is None:
            return
        
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                
                checkpoint_json = json.dumps(checkpoint, default=str)
                
                upsert_sql = f"""
                INSERT INTO {self.table_name} (thread_id, checkpoint, updated_at)
                VALUES (:thread_id, :checkpoint::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (thread_id) 
                DO UPDATE SET checkpoint = :checkpoint::jsonb, updated_at = CURRENT_TIMESTAMP
                """
                
                await session.execute(text(upsert_sql), {
                    "thread_id": thread_id,
                    "checkpoint": checkpoint_json
                })
                await session.commit()
                
                logger.debug(f"[Postgres Checkpointer] 保存检查点: {thread_id[:8]}...")
        except Exception as e:
            logger.error(f"[Postgres Checkpointer] 保存失败: {e}")
    
    async def delete(self, thread_id: str) -> None:
        """删除检查点"""
        await self._ensure_table()
        
        if self.db_session_factory is None:
            return
        
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                
                await session.execute(
                    text(f"DELETE FROM {self.table_name} WHERE thread_id = :thread_id"),
                    {"thread_id": thread_id}
                )
                await session.commit()
                
                logger.debug(f"[Postgres Checkpointer] 删除检查点: {thread_id[:8]}...")
        except Exception as e:
            logger.error(f"[Postgres Checkpointer] 删除失败: {e}")
    
    async def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        await self._ensure_table()
        
        if self.db_session_factory is None:
            return []
        
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                
                result = await session.execute(
                    text(f"""
                        SELECT thread_id, checkpoint, updated_at 
                        FROM {self.table_name} 
                        ORDER BY updated_at DESC 
                        LIMIT :limit
                    """),
                    {"limit": limit}
                )
                
                checkpoints = []
                for row in result.fetchall():
                    checkpoint = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                    checkpoint["_thread_id"] = row[0]
                    checkpoint["_updated_at"] = row[2].isoformat() if row[2] else None
                    checkpoints.append(checkpoint)
                
                return checkpoints
        except Exception as e:
            logger.error(f"[Postgres Checkpointer] 列出失败: {e}")
            return []


class MemoryCheckpointer(BaseCheckpointer):
    """
    内存检查点存储（仅用于开发/测试）
    
    警告：生产环境不要使用！
    """
    
    def __init__(self):
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        logger.warning("[Memory Checkpointer] 仅用于开发/测试，不要在生产环境使用！")
    
    async def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取检查点"""
        checkpoint = self._checkpoints.get(thread_id)
        if checkpoint:
            logger.debug(f"[Memory Checkpointer] 获取检查点: {thread_id[:8]}...")
        return checkpoint
    
    async def put(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        """保存检查点"""
        checkpoint["_updated_at"] = datetime.now().isoformat()
        self._checkpoints[thread_id] = checkpoint
        logger.debug(f"[Memory Checkpointer] 保存检查点: {thread_id[:8]}...")
    
    async def delete(self, thread_id: str) -> None:
        """删除检查点"""
        if thread_id in self._checkpoints:
            del self._checkpoints[thread_id]
            logger.debug(f"[Memory Checkpointer] 删除检查点: {thread_id[:8]}...")
    
    async def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        checkpoints = list(self._checkpoints.values())[:limit]
        return checkpoints


_checkpointer_instance: Optional[BaseCheckpointer] = None


def get_checkpointer(
    backend: str = "auto",
    **kwargs
) -> Optional[BaseCheckpointer]:
    """
    获取检查点实例
    
    Args:
        backend: 存储后端 ("redis", "postgres", "memory", "auto")
        **kwargs: 其他参数
        
    Returns:
        BaseCheckpointer 实例
    """
    global _checkpointer_instance
    
    if _checkpointer_instance is not None:
        return _checkpointer_instance
    
    if backend == "memory":
        _checkpointer_instance = MemoryCheckpointer()
        return _checkpointer_instance
    
    if backend == "redis":
        _checkpointer_instance = RedisCheckpointer(**kwargs)
        return _checkpointer_instance
    
    if backend == "postgres":
        _checkpointer_instance = PostgresCheckpointer(**kwargs)
        return _checkpointer_instance
    
    if backend == "auto":
        import os
        if os.getenv("REDIS_URL"):
            return get_checkpointer("redis", redis_url=os.getenv("REDIS_URL"))
        logger.info("[Checkpointer] 未配置 Redis，使用 Memory（仅开发环境）")
        return get_checkpointer("memory")
    
    return None


def set_checkpointer(checkpointer: BaseCheckpointer):
    """设置检查点实例"""
    global _checkpointer_instance
    _checkpointer_instance = checkpointer
