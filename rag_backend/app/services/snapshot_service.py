"""
会话快照服务

提供会话状态保存、恢复、对比等功能：
1. 创建快照 - 保存会话完整状态
2. 恢复快照 - 从快照恢复会话
3. 对比快照 - 对比两个快照的差异
4. 自动快照 - 定期自动创建快照
"""

import logging
import json
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
from app.models.chat import ChatSession, ChatMessage
from app.db import AsyncSessionLocal
from sqlalchemy import select

logger = logging.getLogger(__name__)


class SnapshotType(str, Enum):
    """快照类型"""
    MANUAL = "manual"  # 手动创建
    AUTO = "auto"  # 自动创建
    BEFORE_TASK = "before_task"  # 任务前
    AFTER_TASK = "after_task"  # 任务后


@dataclass
class SnapshotDiff:
    """快照差异"""
    added_messages: List[Dict[str, Any]] = field(default_factory=list)
    removed_messages: List[Dict[str, Any]] = field(default_factory=list)
    modified_messages: List[Dict[str, Any]] = field(default_factory=list)
    
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    
    summary: str = ""


@dataclass
class SessionSnapshot:
    """会话快照"""
    id: str
    session_id: str
    type: SnapshotType
    
    title: str
    messages: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    message_count: int = 0
    total_tokens: int = 0
    content_hash: str = ""
    
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    @property
    def age_minutes(self) -> float:
        """获取快照年龄（分钟）"""
        return (datetime.now() - self.created_at).total_seconds() / 60
    
    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "type": self.type.value,
            "title": self.title,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "age_minutes": self.age_minutes,
            "is_expired": self.is_expired,
            "metadata": self.metadata,
        }
    
    def to_full_dict(self) -> Dict[str, Any]:
        """转换为完整字典（包含消息）"""
        return {
            **self.to_dict(),
            "messages": self.messages,
        }


class SnapshotService:
    """
    会话快照服务
    
    功能：
    1. 创建快照 - 保存会话完整状态
    2. 恢复快照 - 从快照恢复会话
    3. 对比快照 - 对比两个快照的差异
    4. 自动快照 - 定期自动创建快照
    """
    
    # 默认快照过期时间（天）
    DEFAULT_SNAPSHOT_TTL_DAYS = 30
    
    # 默认最大快照数（每个会话）
    DEFAULT_MAX_SNAPSHOTS_PER_SESSION = 10
    
    # 自动快照间隔（分钟）
    DEFAULT_AUTO_SNAPSHOT_INTERVAL = 60
    
    def __init__(
        self,
        ttl_days: int = None,
        max_snapshots_per_session: int = None,
        auto_snapshot_interval: int = None,
    ):
        self.ttl_days = ttl_days or self.DEFAULT_SNAPSHOT_TTL_DAYS
        self.max_snapshots_per_session = max_snapshots_per_session or self.DEFAULT_MAX_SNAPSHOTS_PER_SESSION
        self.auto_snapshot_interval = auto_snapshot_interval or self.DEFAULT_AUTO_SNAPSHOT_INTERVAL
        
        # 内存存储（快照内容）
        self._snapshots: Dict[str, SessionSnapshot] = {}
        
        # 快照索引 {session_id: [snapshot_ids]}
        self._session_snapshots: Dict[str, List[str]] = {}
        
        # 统计信息
        self._stats = {
            "total_snapshots": 0,
            "manual_snapshots": 0,
            "auto_snapshots": 0,
            "restores": 0,
            "comparisons": 0,
        }
        
        logger.info(
            f"🚀 SnapshotService 初始化完成, "
            f"TTL: {self.ttl_days}天, "
            f"最大快照数/会话: {self.max_snapshots_per_session}"
        )
    
    async def create_snapshot(
        self,
        session_id: str,
        snapshot_type: SnapshotType = SnapshotType.MANUAL,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionSnapshot:
        """
        创建会话快照
        
        Args:
            session_id: 会话ID
            snapshot_type: 快照类型
            title: 快照标题
            metadata: 额外元数据
            
        Returns:
            SessionSnapshot: 创建的快照
        """
        try:
            async with AsyncSessionLocal() as db:
                # 获取会话
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                
                if not session:
                    raise ValueError(f"会话不存在: {session_id}")
                
                # 获取消息
                result = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at)
                )
                messages = result.scalars().all()
                
                # 转换为字典
                messages_data = []
                total_tokens = 0
                
                for msg in messages:
                    msg_dict = {
                        "id": str(msg.id),
                        "role": msg.role,
                        "content": msg.content,
                        "sources": msg.sources,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    }
                    messages_data.append(msg_dict)
                    
                    # 统计token（估算）
                    if hasattr(msg, "metadata") and msg.metadata:
                        total_tokens += msg.metadata.get("token_count", 0)
                
                # 生成内容哈希
                content_str = json.dumps(messages_data, ensure_ascii=False)
                content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]
                
                # 创建快照ID
                snapshot_id = str(uuid.uuid4())
                
                # 计算过期时间
                expires_at = datetime.now() + timedelta(days=self.ttl_days)
                
                # 创建快照对象
                snapshot = SessionSnapshot(
                    id=snapshot_id,
                    session_id=session_id,
                    type=snapshot_type,
                    title=title or session.title or f"快照 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    messages=messages_data,
                    metadata={
                        **(metadata or {}),
                        "session_title": session.title,
                        "last_message_id": str(messages[-1].id) if messages else None,
                    },
                    message_count=len(messages),
                    total_tokens=total_tokens,
                    content_hash=content_hash,
                    created_at=datetime.now(),
                    expires_at=expires_at,
                )
                
                # 存储快照
                self._snapshots[snapshot_id] = snapshot
                
                if session_id not in self._session_snapshots:
                    self._session_snapshots[session_id] = []
                self._session_snapshots[session_id].append(snapshot_id)
                
                # 更新统计
                self._stats["total_snapshots"] += 1
                if snapshot_type == SnapshotType.MANUAL:
                    self._stats["manual_snapshots"] += 1
                else:
                    self._stats["auto_snapshots"] += 1
                
                # 清理多余快照
                await self._cleanup_old_snapshots(session_id)
                
                logger.info(
                    f"📸 创建快照: {snapshot_id}, "
                    f"会话: {session_id}, "
                    f"类型: {snapshot_type.value}, "
                    f"消息数: {len(messages)}"
                )
                
                return snapshot
                
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 创建快照数据失败: {session_id}, error: {e}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"❌ 创建快照IO失败: {session_id}, error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 创建快照失败: {session_id}, error: {e}")
            raise
    
    async def _cleanup_old_snapshots(self, session_id: str):
        """清理旧的快照"""
        if session_id not in self._session_snapshots:
            return
        
        snapshot_ids = self._session_snapshots[session_id]
        
        # 如果快照数量超过限制，删除最老的
        while len(snapshot_ids) > self.max_snapshots_per_session:
            oldest_id = None
            oldest_time = None
            
            for sid in snapshot_ids:
                snapshot = self._snapshots.get(sid)
                if snapshot:
                    if oldest_time is None or snapshot.created_at < oldest_time:
                        oldest_time = snapshot.created_at
                        oldest_id = sid
            
            if oldest_id:
                del self._snapshots[oldest_id]
                snapshot_ids.remove(oldest_id)
                logger.debug(f"🗑️ 删除旧快照: {oldest_id}")
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[SessionSnapshot]:
        """
        获取快照
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            Optional[SessionSnapshot]: 快照，不存在或已过期返回None
        """
        snapshot = self._snapshots.get(snapshot_id)
        
        if not snapshot:
            logger.debug(f"🔍 未找到快照: {snapshot_id}")
            return None
        
        if snapshot.is_expired:
            logger.info(f"🗑️ 快照已过期: {snapshot_id}")
            del self._snapshots[snapshot_id]
            if snapshot.session_id in self._session_snapshots:
                self._session_snapshots[snapshot.session_id].remove(snapshot_id)
            return None
        
        return snapshot
    
    async def list_snapshots(
        self,
        session_id: Optional[str] = None,
        snapshot_type: Optional[SnapshotType] = None,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        列出快照
        
        Args:
            session_id: 可选，按会话ID过滤
            snapshot_type: 可选，按类型过滤
            include_expired: 是否包含已过期的
            
        Returns:
            List[Dict]: 快照列表
        """
        snapshots = []
        
        for snapshot_id, snapshot in self._snapshots.items():
            # 过滤会话
            if session_id and snapshot.session_id != session_id:
                continue
            
            # 过滤类型
            if snapshot_type and snapshot.type != snapshot_type:
                continue
            
            # 过滤过期
            if not include_expired and snapshot.is_expired:
                continue
            
            snapshots.append(snapshot.to_dict())
        
        # 按创建时间排序
        snapshots.sort(key=lambda x: x["created_at"], reverse=True)
        
        return snapshots
    
    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        删除快照
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            bool: 是否成功
        """
        snapshot = self._snapshots.get(snapshot_id)
        
        if not snapshot:
            return False
        
        del self._snapshots[snapshot_id]
        
        if snapshot.session_id in self._session_snapshots:
            if snapshot_id in self._session_snapshots[snapshot.session_id]:
                self._session_snapshots[snapshot.session_id].remove(snapshot_id)
        
        logger.info(f"🗑️ 删除快照: {snapshot_id}")
        
        return True
    
    async def restore_snapshot(
        self,
        snapshot_id: str,
        target_session_id: Optional[str] = None,
        merge: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        恢复快照
        
        Args:
            snapshot_id: 快照ID
            target_session_id: 目标会话ID，不传则创建新会话
            merge: 是否合并到现有会话
            
        Returns:
            Tuple[str, List[Dict]]: (会话ID, 恢复的消息列表)
        """
        snapshot = await self.get_snapshot(snapshot_id)
        
        if not snapshot:
            raise ValueError(f"快照不存在或已过期: {snapshot_id}")
        
        self._stats["restores"] += 1
        
        try:
            async with AsyncSessionLocal() as db:
                # 确定目标会话
                if not target_session_id:
                    if merge:
                        target_session_id = snapshot.session_id
                    else:
                        # 创建新会话
                        new_session = ChatSession(
                            user_id=snapshot.metadata.get("user_id", "unknown"),
                            title=f"{snapshot.title} (恢复)"
                        )
                        db.add(new_session)
                        await db.commit()
                        await db.refresh(new_session)
                        target_session_id = str(new_session.id)
                
                # 如果是合并，需要获取当前会话的最后消息时间
                last_message_time = None
                if merge:
                    result = await db.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == target_session_id)
                        .order_by(ChatMessage.created_at.desc())
                        .limit(1)
                    )
                    last_msg = result.scalar_one_or_none()
                    if last_msg:
                        last_message_time = last_msg.created_at
                
                # 恢复消息
                restored_messages = []
                
                for msg_data in snapshot.messages:
                    # 如果是合并，跳过已有的消息
                    if merge and last_message_time:
                        msg_time = datetime.fromisoformat(msg_data["created_at"])
                        if msg_time <= last_message_time:
                            continue
                    
                    new_msg = ChatMessage(
                        session_id=target_session_id,
                        role=msg_data["role"],
                        content=msg_data["content"],
                        sources=msg_data.get("sources"),
                    )
                    db.add(new_msg)
                    restored_messages.append(msg_data)
                
                await db.commit()
                
                logger.info(
                    f"🔄 恢复快照: {snapshot_id}, "
                    f"到会话: {target_session_id}, "
                    f"恢复消息数: {len(restored_messages)}"
                )
                
                return target_session_id, restored_messages
                
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 恢复快照数据失败: {snapshot_id}, error: {e}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"❌ 恢复快照IO失败: {snapshot_id}, error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 恢复快照失败: {snapshot_id}, error: {e}")
            raise
    
    async def compare_snapshots(
        self,
        snapshot_id1: str,
        snapshot_id2: str,
    ) -> SnapshotDiff:
        """
        对比两个快照
        
        Args:
            snapshot_id1: 第一个快照ID
            snapshot_id2: 第二个快照ID
            
        Returns:
            SnapshotDiff: 差异信息
        """
        snapshot1 = await self.get_snapshot(snapshot_id1)
        snapshot2 = await self.get_snapshot(snapshot_id2)
        
        if not snapshot1 or not snapshot2:
            raise ValueError("快照不存在")
        
        self._stats["comparisons"] += 1
        
        # 提取消息ID集合
        msgs1 = {msg["id"]: msg for msg in snapshot1.messages}
        msgs2 = {msg["id"]: msg for msg in snapshot2.messages}
        
        ids1 = set(msgs1.keys())
        ids2 = set(msgs2.keys())
        
        # 新增的消息
        added_ids = ids2 - ids1
        added_messages = [msgs2[sid] for sid in added_ids]
        
        # 删除的消息
        removed_ids = ids1 - ids2
        removed_messages = [msgs1[sid] for sid in removed_ids]
        
        # 修改的消息
        modified_messages = []
        common_ids = ids1 & ids2
        for sid in common_ids:
            msg1 = msgs1[sid]
            msg2 = msgs2[sid]
            if msg1 != msg2:
                modified_messages.append({
                    "before": msg1,
                    "after": msg2,
                })
        
        # 生成摘要
        summary_parts = []
        if added_messages:
            summary_parts.append(f"新增 {len(added_messages)} 条消息")
        if removed_messages:
            summary_parts.append(f"删除 {len(removed_messages)} 条消息")
        if modified_messages:
            summary_parts.append(f"修改 {len(modified_messages)} 条消息")
        
        summary = ", ".join(summary_parts) if summary_parts else "无变化"
        
        diff = SnapshotDiff(
            added_messages=added_messages,
            removed_messages=removed_messages,
            modified_messages=modified_messages,
            added_count=len(added_messages),
            removed_count=len(removed_messages),
            modified_count=len(modified_messages),
            summary=summary,
        )
        
        logger.info(
            f"📊 对比快照: {snapshot_id1} vs {snapshot_id2}, "
            f"{diff.summary}"
        )
        
        return diff
    
    async def cleanup_expired(self):
        """清理过期的快照"""
        expired_ids = [
            snapshot_id for snapshot_id, snapshot in self._snapshots.items()
            if snapshot.is_expired
        ]
        
        for snapshot_id in expired_ids:
            snapshot = self._snapshots[snapshot_id]
            
            # 从索引中移除
            if snapshot.session_id in self._session_snapshots:
                if snapshot_id in self._session_snapshots[snapshot.session_id]:
                    self._session_snapshots[snapshot.session_id].remove(snapshot_id)
            
            # 删除快照
            del self._snapshots[snapshot_id]
        
        if expired_ids:
            logger.info(f"🧹 清理: {len(expired_ids)}个过期快照")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "total_snapshots": len(self._snapshots),
            "sessions_with_snapshots": len(self._session_snapshots),
            "avg_snapshots_per_session": (
                len(self._snapshots) / len(self._session_snapshots)
                if self._session_snapshots else 0
            ),
        }


# 全局单例
snapshot_service = SnapshotService()
