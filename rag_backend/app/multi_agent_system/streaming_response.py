"""
流式输出机制 (Streaming Response)
支持SSE、WebSocket和分块传输的流式响应
"""

import asyncio
import json
from typing import AsyncIterator, Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """流事件类型"""
    TEXT = "text"                     # 文本片段
    THINKING = "thinking"            # 思考中
    TOOL_CALL = "tool_call"          # 工具调用
    TOOL_RESULT = "tool_result"      # 工具结果
    AGENT_START = "agent_start"      # 智能体开始
    AGENT_END = "agent_end"          # 智能体结束
    ERROR = "error"                  # 错误
    COMPLETE = "complete"            # 完成
    HEARTBEAT = "heartbeat"          # 心跳


@dataclass
class StreamEvent:
    """
    流事件
    
    代表一个流式响应事件
    """
    event_type: StreamEventType
    content: Any
    agent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.event_type.value,
            "content": self.content,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    def to_sse_format(self) -> str:
        """转换为SSE格式"""
        data = self.to_dict()
        return f"event: {self.event_type.value}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    def to_json_line(self) -> str:
        """转换为JSON行格式"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class StreamBuffer:
    """
    流缓冲区
    
    管理事件缓冲和批处理
    """
    
    def __init__(self, max_size: int = 100, flush_interval: float = 0.1):
        self.max_size = max_size
        self.flush_interval = flush_interval
        self._buffer: List[StreamEvent] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def add(self, event: StreamEvent):
        """添加事件"""
        async with self._lock:
            self._buffer.append(event)
            
            if len(self._buffer) >= self.max_size:
                return await self.flush()
        
        return None
    
    async def flush(self) -> List[StreamEvent]:
        """刷新缓冲区"""
        async with self._lock:
            if not self._buffer:
                return []
            
            events = self._buffer
            self._buffer = []
            return events
    
    async def start_flush_loop(self, callback: Callable[[List[StreamEvent]], Awaitable[None]]):
        """启动自动刷新循环"""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop(callback))
    
    async def stop_flush_loop(self):
        """停止刷新循环"""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
    
    async def _flush_loop(self, callback: Callable[[List[StreamEvent]], Awaitable[None]]):
        """刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                events = await self.flush()
                if events:
                    await callback(events)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [流缓冲区] 刷新异常: {e}")


class StreamManager:
    """
    流管理器
    
    管理多个流式输出通道
    """
    
    def __init__(self):
        self._streams: Dict[str, asyncio.Queue] = {}
        self._handlers: Dict[str, Callable[[StreamEvent], Awaitable[None]]] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        
        logger.info("🌊 [流管理器] 初始化完成")
    
    async def register_stream(self, stream_id: str) -> asyncio.Queue:
        """注册流"""
        async with self._lock:
            if stream_id not in self._streams:
                self._streams[stream_id] = asyncio.Queue(maxsize=1000)
                logger.info(f"🌊 [流管理器] 注册流: {stream_id}")
            return self._streams[stream_id]
    
    async def unregister_stream(self, stream_id: str):
        """注销流"""
        async with self._lock:
            if stream_id in self._streams:
                del self._streams[stream_id]
                logger.info(f"🌊 [流管理器] 注销流: {stream_id}")
    
    async def send_event(self, stream_id: str, event: StreamEvent):
        """发送事件"""
        if stream_id not in self._streams:
            logger.warning(f"⚠️ [流管理器] 流不存在: {stream_id}")
            return
        
        try:
            await asyncio.wait_for(
                self._streams[stream_id].put(event),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ [流管理器] 发送超时: {stream_id}")
        except Exception as e:
            logger.error(f"❌ [流管理器] 发送失败: {stream_id}, {e}")
    
    async def broadcast(self, event: StreamEvent):
        """广播事件到所有流"""
        async with self._lock:
            stream_ids = list(self._streams.keys())
        
        for stream_id in stream_ids:
            asyncio.create_task(self.send_event(stream_id, event))
    
    async def get_event_stream(self, stream_id: str) -> AsyncIterator[StreamEvent]:
        """获取事件流"""
        if stream_id not in self._streams:
            return
        
        queue = self._streams[stream_id]
        
        while not self._closed:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                yield StreamEvent(
                    event_type=StreamEventType.HEARTBEAT,
                    content={"timestamp": datetime.now().isoformat()}
                )
    
    async def close(self):
        """关闭所有流"""
        self._closed = True
        async with self._lock:
            self._streams.clear()
        logger.info("🌊 [流管理器] 已关闭")


class StreamingResponse:
    """
    流式响应处理器
    
    处理流式响应的生成和格式化
    """
    
    def __init__(
        self,
        stream_id: str,
        manager: Optional[StreamManager] = None,
        enable_buffering: bool = True,
        buffer_size: int = 10
    ):
        self.stream_id = stream_id
        self.manager = manager or StreamManager()
        self.enable_buffering = enable_buffering
        self.buffer_size = buffer_size
        
        self._buffer: List[StreamEvent] = []
        self._lock = asyncio.Lock()
        self._closed = False
        
        logger.debug(f"🌊 [流式响应] 创建: {stream_id}")
    
    async def send(
        self,
        event_type: StreamEventType,
        content: Any,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        flush: bool = False
    ):
        """发送事件"""
        if self._closed:
            return
        
        event = StreamEvent(
            event_type=event_type,
            content=content,
            agent_id=agent_id,
            metadata=metadata or {}
        )
        
        if self.enable_buffering and not flush:
            async with self._lock:
                self._buffer.append(event)
                
                if len(self._buffer) >= self.buffer_size:
                    await self._flush_buffer()
        else:
            await self._send_event(event)
    
    async def send_text(self, text: str, agent_id: Optional[str] = None):
        """发送文本片段"""
        await self.send(StreamEventType.TEXT, text, agent_id)
    
    async def send_thinking(self, thought: str, agent_id: Optional[str] = None):
        """发送思考状态"""
        await self.send(StreamEventType.THINKING, thought, agent_id)
    
    async def send_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        agent_id: Optional[str] = None
    ):
        """发送工具调用"""
        await self.send(
            StreamEventType.TOOL_CALL,
            {"name": tool_name, "arguments": tool_args},
            agent_id
        )
    
    async def send_tool_result(
        self,
        tool_name: str,
        result: Any,
        agent_id: Optional[str] = None
    ):
        """发送工具结果"""
        await self.send(
            StreamEventType.TOOL_RESULT,
            {"name": tool_name, "result": result},
            agent_id
        )
    
    async def send_agent_start(
        self,
        agent_name: str,
        task: str,
        agent_id: Optional[str] = None
    ):
        """发送智能体开始"""
        await self.send(
            StreamEventType.AGENT_START,
            {"name": agent_name, "task": task},
            agent_id
        )
    
    async def send_agent_end(
        self,
        agent_name: str,
        summary: str,
        agent_id: Optional[str] = None
    ):
        """发送智能体结束"""
        await self.send(
            StreamEventType.AGENT_END,
            {"name": agent_name, "summary": summary},
            agent_id
        )
    
    async def send_error(
        self,
        error: str,
        agent_id: Optional[str] = None
    ):
        """发送错误"""
        await self.send(StreamEventType.ERROR, error, agent_id, flush=True)
    
    async def complete(self):
        """完成流"""
        await self.send(StreamEventType.COMPLETE, {"status": "done"}, flush=True)
        self._closed = True
        await self._flush_buffer()
    
    async def _send_event(self, event: StreamEvent):
        """发送事件到管理器"""
        await self.manager.send_event(self.stream_id, event)
    
    async def _flush_buffer(self):
        """刷新缓冲区"""
        if not self._buffer:
            return
        
        events = self._buffer.copy()
        self._buffer.clear()
        
        for event in events:
            await self._send_event(event)
    
    async def flush(self):
        """手动刷新"""
        async with self._lock:
            await self._flush_buffer()


class SSEFormatter:
    """
    SSE格式化器
    
    将事件转换为Server-Sent Events格式
    """
    
    @staticmethod
    def format_event(event: StreamEvent) -> str:
        """格式化单个事件"""
        return event.to_sse_format()
    
    @staticmethod
    def format_events(events: List[StreamEvent]) -> str:
        """格式化多个事件"""
        return "".join(SSEFormatter.format_event(e) for e in events)
    
    @staticmethod
    async def stream_generator(
        stream: AsyncIterator[StreamEvent]
    ) -> AsyncIterator[str]:
        """流式生成器"""
        async for event in stream:
            yield SSEFormatter.format_event(event)


class JSONLineFormatter:
    """
    JSON行格式化器
    
    将事件转换为JSON行格式
    """
    
    @staticmethod
    def format_event(event: StreamEvent) -> str:
        """格式化单个事件"""
        return event.to_json_line() + "\n"
    
    @staticmethod
    def format_events(events: List[StreamEvent]) -> str:
        """格式化多个事件"""
        return "".join(JSONLineFormatter.format_event(e) for e in events)
    
    @staticmethod
    async def stream_generator(
        stream: AsyncIterator[StreamEvent]
    ) -> AsyncIterator[str]:
        """流式生成器"""
        async for event in stream:
            yield JSONLineFormatter.format_event(event)


class ChunkedFormatter:
    """
    分块格式化器
    
    将事件转换为HTTP分块传输编码格式
    """
    
    @staticmethod
    def format_event(event: StreamEvent) -> bytes:
        """格式化单个事件"""
        content = json.dumps(event.to_dict(), ensure_ascii=False)
        chunk = f"{len(content):x}\r\n{content}\r\n"
        return chunk.encode()
    
    @staticmethod
    def format_events(events: List[StreamEvent]) -> bytes:
        """格式化多个事件"""
        result = b""
        for event in events:
            result += ChunkedFormatter.format_event(event)
        return result
    
    @staticmethod
    def get_termination_chunk() -> bytes:
        """获取结束块"""
        return b"0\r\n\r\n"
    
    @staticmethod
    async def stream_generator(
        stream: AsyncIterator[StreamEvent]
    ) -> AsyncIterator[bytes]:
        """流式生成器"""
        async for event in stream:
            yield ChunkedFormatter.format_event(event)
        
        yield ChunkedFormatter.get_termination_chunk()


# 全局流管理器
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """获取全局流管理器"""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager


async def create_streaming_response(
    request_id: str,
    enable_buffering: bool = True
) -> StreamingResponse:
    """创建流式响应"""
    manager = get_stream_manager()
    await manager.register_stream(request_id)
    
    return StreamingResponse(
        stream_id=request_id,
        manager=manager,
        enable_buffering=enable_buffering
    )
