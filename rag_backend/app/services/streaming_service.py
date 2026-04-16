"""
流式服务稳定性增强

提供企业级流式响应稳定性保障：
1. 增量保存 - 在流式响应过程中定期保存已生成的内容
2. 断点续传 - 支持从上次保存的位置恢复
3. 优雅降级 - 在服务不可用时允许请求通过
4. 进度追踪 - 实时追踪流式响应进度

使用示例：
```python
streaming_service = StreamingService()
async for chunk in streaming_service.stream_with_progress(query, context):
    yield chunk
```
"""

import asyncio
import logging
import uuid
from typing import AsyncGenerator, Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from app.core.config import settings

logger = logging.getLogger(__name__)


class StreamState(str, Enum):
    """流式状态"""
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StreamProgress:
    """流式进度信息"""
    stream_id: str
    session_id: str
    state: StreamState = StreamState.IDLE
    
    total_chunks: int = 0
    completed_chunks: int = 0
    total_content_length: int = 0
    saved_content_length: int = 0
    
    last_save_index: int = 0
    last_save_time: Optional[datetime] = None
    last_chunk_time: Optional[datetime] = None
    
    error_count: int = 0
    last_error: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress_percent(self) -> float:
        """计算进度百分比"""
        if self.total_chunks == 0:
            return 0.0
        return (self.completed_chunks / self.total_chunks) * 100
    
    @property
    def save_percent(self) -> float:
        """计算保存百分比"""
        if self.total_content_length == 0:
            return 0.0
        return (self.saved_content_length / self.total_content_length) * 100
    
    @property
    def is_alive(self) -> bool:
        """检查流是否还活着"""
        if self.state != StreamState.STREAMING:
            return False
        
        if self.last_chunk_time:
            elapsed = (datetime.now() - self.last_chunk_time).total_seconds()
            return elapsed < 30  # 30秒无数据则认为已断开
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stream_id": self.stream_id,
            "session_id": self.session_id,
            "state": self.state.value,
            "progress_percent": self.progress_percent,
            "save_percent": self.save_percent,
            "completed_chunks": self.completed_chunks,
            "total_chunks": self.total_chunks,
            "saved_content_length": self.saved_content_length,
            "total_content_length": self.total_content_length,
            "last_save_index": self.last_save_index,
            "last_save_time": self.last_save_time.isoformat() if self.last_save_time else None,
            "last_chunk_time": self.last_chunk_time.isoformat() if self.last_chunk_time else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "is_alive": self.is_alive,
            "metadata": self.metadata,
        }


@dataclass
class StreamCheckpoint:
    """流式断点信息"""
    stream_id: str
    session_id: str
    content: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))


class StreamingService:
    """
    流式服务稳定性增强
    
    功能：
    1. 增量保存 - 定期保存已生成内容
    2. 断点续传 - 从保存点恢复
    3. 进度追踪 - 实时监控流式状态
    4. 优雅降级 - 服务异常时允许请求通过
    """
    
    # 默认保存间隔（字符数）
    DEFAULT_SAVE_INTERVAL = 500
    
    # 默认检查点过期时间（小时）
    DEFAULT_CHECKPOINT_TTL = 24
    
    # 默认最大内容长度
    DEFAULT_MAX_CONTENT_LENGTH = 100000
    
    def __init__(
        self,
        save_interval: int = None,
        checkpoint_ttl: int = None,
        max_content_length: int = None,
    ):
        self.save_interval = save_interval or settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        self.checkpoint_ttl = checkpoint_ttl or self.DEFAULT_CHECKPOINT_TTL
        self.max_content_length = max_content_length or self.DEFAULT_MAX_CONTENT_LENGTH
        
        # 流状态存储: {stream_id: StreamProgress}
        self._streams: Dict[str, StreamProgress] = {}
        
        # 断点存储: {stream_id: StreamCheckpoint}
        self._checkpoints: Dict[str, StreamCheckpoint] = {}
        
        # 内容缓冲区: {stream_id: list of chunks}
        self._buffers: Dict[str, List[str]] = defaultdict(list)
        
        # 异步锁
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # 统计信息
        self._stats = {
            "total_streams": 0,
            "completed_streams": 0,
            "failed_streams": 0,
            "total_saves": 0,
            "total_resumes": 0,
        }
        
        logger.info(
            f"🚀 StreamingService 初始化完成, "
            f"保存间隔: {self.save_interval}字符, "
            f"检查点TTL: {self.checkpoint_ttl}小时"
        )
    
    async def create_stream(
        self,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建新的流式会话
        
        Args:
            session_id: 会话ID
            metadata: 元数据
            
        Returns:
            str: 流ID
        """
        stream_id = str(uuid.uuid4())
        
        progress = StreamProgress(
            stream_id=stream_id,
            session_id=session_id,
            state=StreamState.IDLE,
            metadata=metadata or {}
        )
        
        self._streams[stream_id] = progress
        self._stats["total_streams"] += 1
        
        logger.info(f"🆕 创建流式会话: {stream_id}, session: {session_id}")
        
        return stream_id
    
    async def start_stream(self, stream_id: str):
        """开始流式响应"""
        if stream_id not in self._streams:
            logger.warning(f"⚠️ 流不存在: {stream_id}")
            return
        
        async with self._locks[stream_id]:
            self._streams[stream_id].state = StreamState.STREAMING
            self._streams[stream_id].last_chunk_time = datetime.now()
        
        logger.debug(f"▶️ 开始流: {stream_id}")
    
    async def stream_with_save(
        self,
        stream_id: str,
        generator: AsyncGenerator[str, None],
        save_callback: Optional[callable] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成器增强版 - 带增量保存
        
        Args:
            stream_id: 流ID
            generator: 原始生成器
            save_callback: 保存回调函数
            
        Yields:
            str: 生成的文本块
        """
        if stream_id not in self._streams:
            logger.warning(f"⚠️ 流不存在: {stream_id}")
            async for chunk in generator:
                yield chunk
            return
        
        progress = self._streams[stream_id]
        progress.state = StreamState.STREAMING
        
        buffer = self._buffers[stream_id]
        content_length = 0
        chunk_index = 0
        
        try:
            async for chunk in generator:
                yield chunk
                
                # 更新状态
                progress.completed_chunks += 1
                progress.last_chunk_time = datetime.now()
                progress.total_content_length += len(chunk)
                content_length += len(chunk)
                
                # 缓冲内容
                buffer.append(chunk)
                
                # 检查是否需要保存
                if content_length - progress.saved_content_length >= self.save_interval:
                    await self._save_checkpoint(
                        stream_id,
                        "".join(buffer),
                        chunk_index,
                        progress.token_count if "token_count" in progress.metadata else 0,
                        save_callback
                    )
                    progress.saved_content_length = content_length
                    progress.last_save_index = chunk_index
                    progress.last_save_time = datetime.now()
                
                chunk_index += 1
            
            # 流结束，保存最终内容
            if buffer and progress.saved_content_length < content_length:
                await self._save_checkpoint(
                    stream_id,
                    "".join(buffer),
                    chunk_index,
                    progress.token_count if "token_count" in progress.metadata else 0,
                    save_callback
                )
            
            progress.state = StreamState.COMPLETED
            self._stats["completed_streams"] += 1
            
            logger.info(
                f"✅ 流完成: {stream_id}, "
                f"总字符: {content_length}, "
                f"总块: {chunk_index}"
            )
            
        except (ValueError, KeyError) as _:
            progress.state = StreamState.FAILED
            progress.error_count += 1
        except (OSError, IOError) as _:
            progress.state = StreamState.FAILED
            progress.error_count += 1
        except Exception as e:
            progress.state = StreamState.FAILED
            progress.error_count += 1
            progress.last_error = str(e)
            self._stats["failed_streams"] += 1
            
            logger.error(f"❌ 流失败: {stream_id}, error: {e}")
            
            # 保存已生成的内容作为断点
            if buffer:
                await self._save_checkpoint(
                    stream_id,
                    "".join(buffer),
                    chunk_index,
                    0,
                    save_callback
                )
            
            raise
        
        finally:
            # 清理缓冲区（保留检查点）
            if stream_id in self._buffers:
                del self._buffers[stream_id]
    
    async def _save_checkpoint(
        self,
        stream_id: str,
        content: str,
        chunk_index: int,
        token_count: int,
        callback: Optional[callable] = None
    ):
        """保存检查点"""
        try:
            checkpoint = StreamCheckpoint(
                stream_id=stream_id,
                session_id=self._streams[stream_id].session_id,
                content=content,
                chunk_index=chunk_index,
                token_count=token_count,
                metadata=self._streams[stream_id].metadata,
                expires_at=datetime.now() + timedelta(hours=self.checkpoint_ttl)
            )
            
            self._checkpoints[stream_id] = checkpoint
            self._stats["total_saves"] += 1
            
            # 调用保存回调
            if callback:
                await callback(stream_id, content, chunk_index, token_count)
            
            logger.debug(
                f"💾 保存检查点: {stream_id}, "
                f"字符: {len(content)}, "
                f"块: {chunk_index}"
            )
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 保存检查点数据失败: {stream_id}, error: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 保存检查点IO失败: {stream_id}, error: {e}")
        except Exception as e:
            logger.error(f"❌ 保存检查点失败: {stream_id}, error: {e}")
    
    async def get_checkpoint(self, stream_id: str) -> Optional[StreamCheckpoint]:
        """
        获取断点信息
        
        Args:
            stream_id: 流ID
            
        Returns:
            Optional[StreamCheckpoint]: 断点信息，不存在或已过期返回None
        """
        checkpoint = self._checkpoints.get(stream_id)
        
        if not checkpoint:
            logger.debug(f"🔍 未找到断点: {stream_id}")
            return None
        
        # 检查是否过期
        if datetime.now() > checkpoint.expires_at:
            logger.info(f"🗑️ 断点已过期: {stream_id}")
            del self._checkpoints[stream_id]
            return None
        
        return checkpoint
    
    async def resume_stream(
        self,
        stream_id: str,
        generator: AsyncGenerator[str, None],
    ) -> Tuple[str, AsyncGenerator[str, None]]:
        """
        恢复流式响应
        
        Args:
            stream_id: 流ID
            generator: 新的生成器
            
        Returns:
            Tuple[str, AsyncGenerator]: (已生成的内容, 剩余内容的生成器)
        """
        checkpoint = await self.get_checkpoint(stream_id)
        
        if not checkpoint:
            logger.warning(f"⚠️ 无法恢复流: {stream_id}, 断点不存在")
            return "", generator
        
        self._stats["total_resumes"] += 1
        
        # 更新流状态
        if stream_id in self._streams:
            self._streams[stream_id].state = StreamState.STREAMING
            self._streams[stream_id].last_chunk_time = datetime.now()
        
        logger.info(
            f"🔄 恢复流: {stream_id}, "
            f"已生成: {len(checkpoint.content)}字符, "
            f"从块: {checkpoint.chunk_index}"
        )
        
        # 返回已生成内容和新的生成器
        return checkpoint.content, generator
    
    async def pause_stream(self, stream_id: str):
        """暂停流式响应"""
        if stream_id not in self._streams:
            return
        
        async with self._locks[stream_id]:
            self._streams[stream_id].state = StreamState.PAUSED
        
        logger.info(f"⏸️ 暂停流: {stream_id}")
    
    async def cancel_stream(self, stream_id: str):
        """取消流式响应"""
        if stream_id not in self._streams:
            return
        
        async with self._locks[stream_id]:
            self._streams[stream_id].state = StreamState.CANCELLED
        
        # 清理资源
        if stream_id in self._buffers:
            del self._buffers[stream_id]
        
        logger.info(f"🛑 取消流: {stream_id}")
    
    async def get_progress(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """
        获取流式进度
        
        Args:
            stream_id: 流ID
            
        Returns:
            Optional[Dict]: 进度信息
        """
        progress = self._streams.get(stream_id)
        
        if not progress:
            return None
        
        return progress.to_dict()
    
    async def list_active_streams(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出活跃流
        
        Args:
            session_id: 可选，按会话ID过滤
            
        Returns:
            List[Dict]: 活跃流列表
        """
        active_streams = []
        
        for stream_id, progress in self._streams.items():
            if progress.state == StreamState.STREAMING:
                if session_id is None or progress.session_id == session_id:
                    active_streams.append(progress.to_dict())
        
        return active_streams
    
    async def cleanup_expired(self):
        """清理过期的检查点和流"""
        now = datetime.now()
        
        # 清理过期的检查点
        expired_checkpoints = [
            stream_id for stream_id, checkpoint in self._checkpoints.items()
            if now > checkpoint.expires_at
        ]
        for stream_id in expired_checkpoints:
            del self._checkpoints[stream_id]
        
        # 清理已完成或失败的流
        expired_streams = [
            stream_id for stream_id, progress in self._streams.items()
            if progress.state in [StreamState.COMPLETED, StreamState.FAILED, StreamState.CANCELLED]
            and (now - progress.updated_at).total_seconds() > 3600  # 1小时后清理
        ]
        for stream_id in expired_streams:
            del self._streams[stream_id]
            if stream_id in self._checkpoints:
                del self._checkpoints[stream_id]
        
        if expired_checkpoints or expired_streams:
            logger.info(
                f"🧹 清理: {len(expired_checkpoints)}个过期检查点, "
                f"{len(expired_streams)}个过期流"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "active_streams": sum(
                1 for p in self._streams.values()
                if p.state == StreamState.STREAMING
            ),
            "total_checkpoints": len(self._checkpoints),
        }


# 全局单例
streaming_service = StreamingService()
