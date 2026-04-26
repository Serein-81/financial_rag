"""
LangGraph PostgreSQL 持久化 Checkpointer

基于 LangGraph 原生 PostgresSaver 实现状态持久化

特性：
- 使用 PostgreSQL 作为状态存储
- 支持 thread_id 跨会话恢复
- 自动创建检查点表
- 支持 checkpoint_metadata 存储
"""

import json
import logging
from typing import Optional, Any, Dict, List, Sequence, TypedDict
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CheckpointMetadata(TypedDict, total=False):
    """检查点元数据"""
    thread_id: str
    tenant_id: str
    user_id: str
    created_at: str
    checkpoint_id: str


class LangGraphPostgresSaver:
    """
    LangGraph PostgreSQL 状态持久化器
    
    实现了 LangGraph 的 CheckpointSaver 接口，
    支持在 PostgreSQL 中存储和恢复工作流状态
    """
    
    _table_created = False
    _migration_completed = False
    
    def __init__(
        self,
        db_session_factory=None,
        table_name: str = "langgraph_checkpoints",
        enable_auto_migrate: bool = True
    ):
        """
        初始化 PostgresSaver
        
        Args:
            db_session_factory: 异步数据库会话工厂
            table_name: 存储检查点的表名
            enable_auto_migrate: 是否自动创建表
        """
        self.db_session_factory = db_session_factory
        self.table_name = table_name
        self.enable_auto_migrate = enable_auto_migrate
        
        logger.info(f"[LangGraph PostgresSaver] 初始化")
        logger.info(f"  - 表名: {table_name}")
        logger.info(f"  - 自动迁移: {enable_auto_migrate}")
    
    async def _ensure_table(self) -> bool:
        """确保检查点表存在"""
        if LangGraphPostgresSaver._table_created:
            return True
        
        if not self.enable_auto_migrate:
            logger.warning("[LangGraph PostgresSaver] 自动迁移已禁用，表可能不存在")
            return False
        
        if self.db_session_factory is None:
            logger.error("[LangGraph PostgresSaver] 无数据库会话工厂")
            return False
        
        try:
            async with self.db_session_factory() as session:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    thread_id VARCHAR(255) NOT NULL,
                    checkpoint_id VARCHAR(255) NOT NULL,
                    parent_checkpoint_id VARCHAR(255),
                    checkpoint_data JSONB NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
                """
                
                await session.execute(text(create_table_sql))
                
                index_sqls = [
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_thread_id ON {self.table_name}(thread_id)",
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_updated_at ON {self.table_name}(updated_at)",
                    f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_parent ON {self.table_name}(parent_checkpoint_id)"
                ]
                
                for index_sql in index_sqls:
                    try:
                        await session.execute(text(index_sql))
                    except Exception as idx_err:
                        logger.warning(f"[LangGraph PostgresSaver] 索引创建/已存在: {idx_err}")
                
                await session.commit()
                
                LangGraphPostgresSaver._table_created = True
                logger.info(f"[LangGraph PostgresSaver] 表 {self.table_name} 创建完成")
                return True
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 表创建失败: {e}")
            return False
    
    async def get_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取检查点
        
        Args:
            thread_id: 线程 ID（会话 ID）
            checkpoint_id: 检查点 ID（可选，默认获取最新的）
            
        Returns:
            检查点数据或 None
        """
        if not await self._ensure_table():
            logger.warning(f"[LangGraph PostgresSaver] 表不存在，无法获取检查点: {self.table_name}")
            return None
        
        if self.db_session_factory is None:
            return None
        
        try:
            async with self.db_session_factory() as session:
                check_columns_sql = text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = 'metadata'
                """)
                col_result = await session.execute(check_columns_sql, {"table_name": self.table_name})
                has_metadata = col_result.fetchone() is not None
                
                if checkpoint_id:
                    if has_metadata:
                        query = text(f"""
                            SELECT checkpoint_data, metadata 
                            FROM {self.table_name} 
                            WHERE thread_id = :thread_id AND checkpoint_id = :checkpoint_id
                        """)
                        result = await session.execute(query, {
                            "thread_id": thread_id,
                            "checkpoint_id": checkpoint_id
                        })
                        row = result.fetchone()
                        if row:
                            checkpoint_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                            return {
                                "checkpoint": checkpoint_data,
                                "metadata": row[1] or {},
                                "checkpoint_id": checkpoint_id
                            }
                    else:
                        query = text(f"""
                            SELECT checkpoint_data 
                            FROM {self.table_name} 
                            WHERE thread_id = :thread_id AND checkpoint_id = :checkpoint_id
                        """)
                        result = await session.execute(query, {
                            "thread_id": thread_id,
                            "checkpoint_id": checkpoint_id
                        })
                        row = result.fetchone()
                        if row:
                            checkpoint_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                            return {
                                "checkpoint": checkpoint_data,
                                "metadata": {},
                                "checkpoint_id": checkpoint_id
                            }
                else:
                    if has_metadata:
                        query = text(f"""
                            SELECT checkpoint_data, metadata, checkpoint_id
                            FROM {self.table_name} 
                            WHERE thread_id = :thread_id 
                            ORDER BY updated_at DESC 
                            LIMIT 1
                        """)
                        result = await session.execute(query, {
                            "thread_id": thread_id
                        })
                    else:
                        query = text(f"""
                            SELECT checkpoint_data, checkpoint_id
                            FROM {self.table_name} 
                            WHERE thread_id = :thread_id 
                            ORDER BY updated_at DESC 
                            LIMIT 1
                        """)
                        result = await session.execute(query, {
                            "thread_id": thread_id
                        })
                    
                    row = result.fetchone()
                    
                    if row:
                        checkpoint_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                        
                        if has_metadata:
                            return {
                                "checkpoint": checkpoint_data,
                                "metadata": row[1] or {},
                                "checkpoint_id": row[2] if len(row) > 2 else None
                            }
                        else:
                            return {
                                "checkpoint": checkpoint_data,
                                "metadata": {},
                                "checkpoint_id": row[1] if len(row) > 1 else None
                            }
                
                logger.debug(f"[LangGraph PostgresSaver] 未找到检查点: thread={thread_id[:8]}...")
                return None
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 获取检查点失败: {e}")
            return None
    
    async def put_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_data: Dict[str, Any],
        parent_checkpoint_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存检查点
        
        Args:
            thread_id: 线程 ID
            checkpoint_id: 检查点 ID
            checkpoint_data: 检查点数据
            parent_checkpoint_id: 父检查点 ID
            metadata: 元数据
            
        Returns:
            是否成功
        """
        if not await self._ensure_table():
            logger.warning(f"[LangGraph PostgresSaver] 表不存在，无法保存检查点: {self.table_name}")
            return False
        
        if self.db_session_factory is None:
            return False
        
        try:
            async with self.db_session_factory() as session:
                checkpoint_json = json.dumps(checkpoint_data, default=str)
                
                check_columns_sql = text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = 'metadata'
                """)
                col_result = await session.execute(check_columns_sql, {"table_name": self.table_name})
                has_metadata = col_result.fetchone() is not None
                
                if has_metadata:
                    metadata_json = json.dumps(metadata or {}, default=str) if metadata else None
                    upsert_sql = f"""
                    INSERT INTO {self.table_name} 
                    (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint_data, metadata, updated_at)
                    VALUES (:thread_id, :checkpoint_id, :parent_checkpoint_id, :checkpoint_data::jsonb, :metadata::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT (thread_id, checkpoint_id) 
                    DO UPDATE SET 
                        checkpoint_data = :checkpoint_data::jsonb,
                        metadata = COALESCE(:metadata::jsonb, {self.table_name}.metadata),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    
                    await session.execute(text(upsert_sql), {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "parent_checkpoint_id": parent_checkpoint_id,
                        "checkpoint_data": checkpoint_json,
                        "metadata": metadata_json
                    })
                else:
                    upsert_sql = f"""
                    INSERT INTO {self.table_name} 
                    (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint_data, updated_at)
                    VALUES (:thread_id, :checkpoint_id, :parent_checkpoint_id, :checkpoint_data::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT (thread_id, checkpoint_id) 
                    DO UPDATE SET 
                        checkpoint_data = :checkpoint_data::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    """
                    
                    await session.execute(text(upsert_sql), {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "parent_checkpoint_id": parent_checkpoint_id,
                        "checkpoint_data": checkpoint_json
                    })
                
                await session.commit()
                
                logger.debug(f"[LangGraph PostgresSaver] 保存检查点: thread={thread_id[:8]}..., checkpoint={checkpoint_id[:8]}...")
                return True
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 保存检查点失败: {e}")
            return False
    
    async def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        列出线程的所有检查点
        
        Args:
            thread_id: 线程 ID
            limit: 返回数量限制
            
        Returns:
            检查点列表
        """
        if not await self._ensure_table():
            logger.warning(f"[LangGraph PostgresSaver] 表不存在，无法列出检查点: {self.table_name}")
            return []
        
        if self.db_session_factory is None:
            return []
        
        try:
            async with self.db_session_factory() as session:
                check_columns_sql = text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = 'metadata'
                """)
                col_result = await session.execute(check_columns_sql, {"table_name": self.table_name})
                has_metadata = col_result.fetchone() is not None
                
                if has_metadata:
                    query = text(f"""
                        SELECT checkpoint_id, parent_checkpoint_id, metadata, created_at, updated_at
                        FROM {self.table_name} 
                        WHERE thread_id = :thread_id 
                        ORDER BY updated_at DESC 
                        LIMIT :limit
                    """)
                else:
                    query = text(f"""
                        SELECT checkpoint_id, parent_checkpoint_id, created_at, updated_at
                        FROM {self.table_name} 
                        WHERE thread_id = :thread_id 
                        ORDER BY updated_at DESC 
                        LIMIT :limit
                    """)
                
                result = await session.execute(query, {
                    "thread_id": thread_id,
                    "limit": limit
                })
                
                checkpoints = []
                for row in result.fetchall():
                    if has_metadata:
                        checkpoints.append({
                            "checkpoint_id": row[0],
                            "parent_checkpoint_id": row[1],
                            "metadata": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "updated_at": row[4].isoformat() if row[4] else None
                        })
                    else:
                        checkpoints.append({
                            "checkpoint_id": row[0],
                            "parent_checkpoint_id": row[1],
                            "created_at": row[2].isoformat() if row[2] else None,
                            "updated_at": row[3].isoformat() if row[3] else None
                        })
                
                return checkpoints
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 列出检查点失败: {e}")
            return []
    
    async def delete_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> bool:
        """
        删除检查点
        
        Args:
            thread_id: 线程 ID
            checkpoint_id: 检查点 ID（可选，为 None 则删除所有）
            
        Returns:
            是否成功
        """
        if not await self._ensure_table():
            logger.warning(f"[LangGraph PostgresSaver] 表不存在，无法删除检查点: {self.table_name}")
            return False
        
        if self.db_session_factory is None:
            return False
        
        try:
            async with self.db_session_factory() as session:
                if checkpoint_id:
                    query = text(f"""
                        DELETE FROM {self.table_name} 
                        WHERE thread_id = :thread_id AND checkpoint_id = :checkpoint_id
                    """)
                    await session.execute(query, {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id
                    })
                else:
                    query = text(f"""
                        DELETE FROM {self.table_name} 
                        WHERE thread_id = :thread_id
                    """)
                    await session.execute(query, {
                        "thread_id": thread_id
                    })
                
                await session.commit()
                
                logger.debug(f"[LangGraph PostgresSaver] 删除检查点: thread={thread_id[:8]}...")
                return True
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 删除检查点失败: {e}")
            return False
    
    async def get_thread_history(
        self,
        thread_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取线程的完整历史（按时间顺序）
        
        Args:
            thread_id: 线程 ID
            limit: 返回数量限制
            
        Returns:
            历史检查点列表（按时间排序）
        """
        if not await self._ensure_table():
            logger.warning(f"[LangGraph PostgresSaver] 表不存在，无法获取线程历史: {self.table_name}")
            return []
        
        if self.db_session_factory is None:
            return []
        
        try:
            async with self.db_session_factory() as session:
                check_columns_sql = text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = 'metadata'
                """)
                col_result = await session.execute(check_columns_sql, {"table_name": self.table_name})
                has_metadata = col_result.fetchone() is not None
                
                if has_metadata:
                    query = text(f"""
                        WITH RECURSIVE checkpoint_chain AS (
                            SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, metadata, created_at, updated_at, 1 as depth
                            FROM {self.table_name} 
                            WHERE thread_id = :thread_id
                            AND parent_checkpoint_id IS NULL
                            
                            UNION ALL
                            
                            SELECT c.checkpoint_id, c.parent_checkpoint_id, c.checkpoint_data, c.metadata, c.created_at, c.updated_at, cc.depth + 1
                            FROM {self.table_name} c
                            JOIN checkpoint_chain cc ON c.parent_checkpoint_id = cc.checkpoint_id
                            WHERE c.thread_id = :thread_id
                        )
                        SELECT checkpoint_id, checkpoint_data, metadata, created_at, updated_at
                        FROM checkpoint_chain
                        ORDER BY depth ASC
                        LIMIT :limit
                    """)
                else:
                    query = text(f"""
                        WITH RECURSIVE checkpoint_chain AS (
                            SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, created_at, updated_at, 1 as depth
                            FROM {self.table_name} 
                            WHERE thread_id = :thread_id
                            AND parent_checkpoint_id IS NULL
                            
                            UNION ALL
                            
                            SELECT c.checkpoint_id, c.parent_checkpoint_id, c.checkpoint_data, c.created_at, c.updated_at, cc.depth + 1
                            FROM {self.table_name} c
                            JOIN checkpoint_chain cc ON c.parent_checkpoint_id = cc.checkpoint_id
                            WHERE c.thread_id = :thread_id
                        )
                        SELECT checkpoint_id, checkpoint_data, created_at, updated_at
                        FROM checkpoint_chain
                        ORDER BY depth ASC
                        LIMIT :limit
                    """)
                
                result = await session.execute(query, {
                    "thread_id": thread_id,
                    "limit": limit
                })
                
                history = []
                for row in result.fetchall():
                    checkpoint_data = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                    
                    if has_metadata:
                        history.append({
                            "checkpoint_id": row[0],
                            "checkpoint": checkpoint_data,
                            "metadata": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "updated_at": row[4].isoformat() if row[4] else None
                        })
                    else:
                        history.append({
                            "checkpoint_id": row[0],
                            "checkpoint": checkpoint_data,
                            "created_at": row[2].isoformat() if row[2] else None,
                            "updated_at": row[3].isoformat() if row[3] else None
                        })
                
                return history
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 获取线程历史失败: {e}")
            return []
    
    async def get_latest_checkpoint_id(self, thread_id: str) -> Optional[str]:
        """获取最新的检查点 ID"""
        if not await self._ensure_table():
            logger.warning(f"[LangGraph PostgresSaver] 表不存在，无法获取最新检查点 ID: {self.table_name}")
            return None
        
        if self.db_session_factory is None:
            return None
        
        try:
            async with self.db_session_factory() as session:
                query = text(f"""
                    SELECT checkpoint_id 
                    FROM {self.table_name} 
                    WHERE thread_id = :thread_id 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """)
                
                result = await session.execute(query, {
                    "thread_id": thread_id
                })
                
                row = result.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"[LangGraph PostgresSaver] 获取最新检查点 ID 失败: {e}")
            return None
    
    async def has_checkpoints(self, thread_id: str) -> bool:
        """检查线程是否有检查点"""
        latest_id = await self.get_latest_checkpoint_id(thread_id)
        return latest_id is not None


_saver_instance: Optional[LangGraphPostgresSaver] = None


def get_postgres_saver(
    db_session_factory=None,
    table_name: str = "langgraph_checkpoints"
) -> LangGraphPostgresSaver:
    """
    获取 PostgresSaver 单例
    
    Args:
        db_session_factory: 数据库会话工厂
        table_name: 表名
        
    Returns:
        LangGraphPostgresSaver 实例
    """
    global _saver_instance
    
    if _saver_instance is None:
        _saver_instance = LangGraphPostgresSaver(
            db_session_factory=db_session_factory,
            table_name=table_name
        )
        logger.info("[LangGraph PostgresSaver] 创建单例")
    
    return _saver_instance


def reset_saver():
    """重置单例（用于测试）"""
    global _saver_instance
    _saver_instance = None