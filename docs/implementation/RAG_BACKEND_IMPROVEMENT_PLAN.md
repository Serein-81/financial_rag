# RAG 后端系统详细改进方案

## 文档信息

| 项目 | 内容 |
|------|------|
| 项目名称 | RAG Backend 企业级知识库系统 |
| 文档版本 | v1.1 |
| 创建日期 | 2026-04-04 |
| 更新日期 | 2026-04-04 |
| 文档类型 | 技术改进方案 |
| 状态 | 已完成第一轮实现情况核查 |

---

## 一、方案概述

### 1.1 改进目标

本方案旨在从**用户体验、系统稳定性、性能优化、安全合规**四个维度对现有 RAG 后端系统进行系统性改进，打造一款**企业级、高可用、可扩展**的智能知识库产品。

### 1.2 改进原则

| 原则 | 说明 |
|------|------|
| **用户价值优先** | 每一项改进都应直接提升用户使用体验 |
| **渐进式演进** | 采用模块化设计，支持分阶段实施 |
| **向后兼容** | 确保新功能不破坏现有业务流程 |
| **可观测可回滚** | 所有改动支持监控告警和快速回滚 |

### 1.3 改进范围总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RAG 后端系统改进范围                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  P0 紧急    │  │  P1 重要    │  │  P2 一般    │  │  P3 规划   │ │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├───────────┤ │
│  │ 流式稳定性   │  │ ✅ 智能搜索  │  │ ✅ 会话快照  │  │ Python SDK │ │
│  │ 多租户隔离   │  │ ✅ 性能优化  │  │ 追问建议    │  │ 移动端适配 │ │
│  │ API 限流    │  │ ✅ 记忆增强  │  │ ✅ 批量处理  │  │ 多语言支持 │ │
│  │ ✅ 监控增强  │  │ 日志优化    │  │ ✅ 健康检查  │  │ 插件系统   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
│                                                                     │
│  ✅ = 已实现  │  🔶 = 部分实现/需要增强  │  ❌ = 待实现              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.4 实现情况核查结果 (v1.1)

基于对代码库的全面审查，以下是各模块的实现状态：

#### ✅ P0 已实现模块

| 模块 | 实现状态 | 关键文件 | 备注 |
|------|---------|---------|------|
| **多租户隔离** | ✅ 已完整实现 | `middleware/tenant_middleware.py` | TenantContextMiddleware with ContextVar, JWT/Header提取, PostgreSQL session variable |
| **监控增强** | ✅ 已完整实现 | `services/monitor_service.py` | MonitorService with EventType/CallStatus enums, 完整的事件追踪 |
| **健康检查** | ✅ 已完整实现 | `main.py` | 已在主应用中注册中间件和健康检查端点 |

#### 🔶 P0 部分实现/待增强模块

| 模块 | 实现状态 | 关键文件 | 差距说明 |
|------|---------|---------|---------|
| **流式稳定性** | 🔶 部分实现 | `endpoints/chat.py` | 有基本流式响应，但缺少专用StreamingService、增量保存、断点续传 |
| **API 限流** | 🔶 部分实现 | `services/policy_collector/rate_limiter.py` | 有RateLimiter但仅用于政策采集，缺少通用API级别限流中间件 |

#### ✅ P1 已实现模块

| 模块 | 实现状态 | 关键文件 | 备注 |
|------|---------|---------|------|
| **智能搜索路由** | ✅ 已完整实现 | `smart_router.py`, `intent_agent.py`, `orchestrator.py` | SmartRouter with RouteMode, IntentAgent with 20+ intent, AgentOrchestrator |
| **性能优化/缓存** | ✅ 已完整实现 | `memory_system/memory_cache.py` | Redis旁路缓存，Cache-Aside模式，完整TTL管理 |
| **记忆系统增强** | ✅ 已完整实现 | `memory_system/` (10个文件) | 三层记忆架构 Working/Episodic/Semantic，MemoryManager完整管理 |

#### 🔶 P2 部分实现模块

| 模块 | 实现状态 | 关键文件 | 差距说明 |
|------|---------|---------|---------|
| **会话快照** | 🔶 部分实现 | `models/multi_agent_report.py` | 有MultiAgentReportVersion和content_snapshot，但缺少主动快照生成API |
| **追问建议** | 🔶 部分实现 | `schemas/multi_agent.py` | 有PendingQuestion和suggested_questions字段，但缺少LLM生成逻辑 |
| **批量处理** | ✅ 已完整实现 | `multi_agent_system/async_task_scheduler.py` | AsyncTaskScheduler完整实现，TaskGroup/CircuitBreaker/超时控制 |

#### 核查结论

**已实现: 7/12 个模块 (58%)**
**待实现/增强: 5/12 个模块 (42%)**

主要差距集中在:
1. **P0**: 流式稳定性和API限流需要增强为企业级实现
2. **P2**: 追问建议生成和会话快照功能需要完善

---

## 二、总体技术架构

### 2.1 改进后系统架构图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              客户端层                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Web 界面  │  │ 移动端   │  │ API SDK  │  │ WebSocket│  │ 第三方集成 │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └───────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              网关层 (Gateway)                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────────┐ │
│  │ Nginx/Traefik│  │ 认证鉴权   │  │ API 限流   │  │ 请求路由 & 负载均衡 │ │
│  └────────────┘  └────────────┘  └────────────┘  └───────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              API 层 (FastAPI)                             │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      OpenAPI 统一入口                                │ │
│  ├─────────────┬─────────────┬─────────────┬─────────────┬──────────┤ │
│  │ /api/v1/chat│ /api/v1/doc │ /api/v1/kb  │ /api/v1/mem │ /api/v1/*│ │
│  └─────────────┴─────────────┴─────────────┴─────────────┴──────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │              中间件层 (Middleware)                               │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐  │   │
│  │  │ 多租户隔离 │ │ 请求日志  │ │ 链路追踪  │ │ 统一错误处理   │  │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────────┘  │   │
│  └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            业务服务层 (Service Layer)                      │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    企业级 Agent 服务                                 │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐            │ │
│  │  │  Agent Orchestrator │ │ Smart Router │ │ Tool Manager │            │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐   │
│  │ 统一检索服务      │ │ 记忆管理服务      │ │ 监控追踪服务          │   │
│  │ UnifiedRetriever │ │ MemoryManager    │ │ MonitorService       │   │
│  │ + 多级缓存        │ │ + 持久化上下文    │ │ + 业务指标           │   │
│  │ + 智能路由        │ │ + 遗忘机制       │ │ + 性能指标           │   │
│  └──────────────────┘ └──────────────────┘ └──────────────────────┘   │
│                                                                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐   │
│  │ 流式输出服务      │ │ 会话管理服务      │ │ 批处理服务            │   │
│  │ StreamingService │ │ SessionService   │ │ BatchProcessService │   │
│  │ + 断点续传        │ │ + 快照保存        │ │ + 进度追踪           │   │
│  │ + 增量保存        │ │ + 状态恢复        │ │ + 错误重试           │   │
│  └──────────────────┘ └──────────────────┘ └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            基础设施层 (Infrastructure)                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────┐ │
│  │ PostgreSQL │ │   Redis    │ │   MinIO    │ │   Neo4j    │ │ pgvector│ │
│  │  (主数据)   │ │  (缓存)    │ │  (文件)    │ │ (知识图谱)  │ │(向量) │ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └───────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块依赖关系

```
用户请求
    │
    ▼
┌─────────────────┐
│   API Gateway   │ ─── 限流、认证、路由
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  StreamingService│ ◀─── 断点续传
└─────────────────┘
    │
    ▼
┌─────────────────┐     ┌─────────────────┐
│  UnifiedRetriever│ ──▶ │   Redis Cache   │
└─────────────────┘     └─────────────────┘
    │
    ├──▶ 智能路由 (SmartRouter)
    │       │
    │       ├──▶ RAG检索 ──▶ pgvector
    │       ├──▶ 记忆检索 ──▶ MemoryManager
    │       └──▶ 混合检索 ──▶ 融合两者
    │
    ▼
┌─────────────────┐
│ MemoryManager   │ ◀─── 遗忘机制
└─────────────────┘
    │
    ├──▶ WorkingMemory
    ├──▶ EpisodicMemory
    └──▶ SemanticMemory
            │
            └──▶ 持久化上下文 (用户、项目实体)
    │
    ▼
┌─────────────────┐
│ AgentFramework  │
└─────────────────┘
    │
    ├──▶ LLM Adapter (多供应商)
    │
    └──▶ ToolManager
            │
            └──▶ 企业知识检索 / 关键词搜索 / 文档级搜索
```

---

## 三、P0 紧急改进模块

### 3.1 流式输出稳定性优化

#### 3.1.1 问题分析

**现状痛点**：

- 网络中断时已生成内容丢失
- 浏览器刷新后无法继续
- 长响应被截断无法保存

**根本原因**：

1. 当前仅在响应完成后一次性保存
2. 缺少增量保存机制
3. 缺少断点检测和恢复能力

#### 3.1.2 解决方案设计

**新增模块：`app/services/streaming_service.py`**

```python
"""
流式输出服务
提供断点续传、增量保存、优雅降级能力
"""
import asyncio
import json
from typing import AsyncGenerator, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

class StreamState(Enum):
    """流状态枚举"""
    INITIALIZING = "initializing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ERROR = "error"

@dataclass
class StreamContext:
    """流上下文"""
    session_id: str
    message_id: str
    user_id: str
    kb_id: Optional[str] = None
    state: StreamState = StreamState.INITIALIZING
    buffer: list = field(default_factory=list)
    last_save_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    total_tokens: int = 0
    chunk_count: int = 0

class StreamingService:
    """
    流式输出服务
    
    核心功能：
    1. 增量保存 - 每个 chunk 都异步保存
    2. 断点续传 - 支持从 last_save_index 恢复
    3. 优雅降级 - 异常时保存已有内容并通知客户端
    4. 心跳检测 - 检测连接是否存活
    """
    
    def __init__(
        self,
        redis_client,  # Redis 客户端
        db_session,    # 数据库会话工厂
        save_interval: int = 5,  # 每 N 个 chunk 保存一次
        heartbeat_interval: float = 30.0,  # 心跳间隔秒
        max_buffer_size: int = 100,  # 最大缓冲区
    ):
        self.redis = redis_client
        self.db_factory = db_session
        self.save_interval = save_interval
        self.heartbeat_interval = heartbeat_interval
        self.max_buffer_size = max_buffer_size
        self._contexts: dict[str, StreamContext] = {}
    
    async def create_context(
        self,
        session_id: str,
        message_id: str,
        user_id: str,
        kb_id: Optional[str] = None,
    ) -> StreamContext:
        """创建流上下文"""
        ctx = StreamContext(
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            kb_id=kb_id,
        )
        self._contexts[message_id] = ctx
        
        # 检查是否有未完成的流可以恢复
        existing = await self._load_partial_stream(message_id)
        if existing:
            ctx.buffer = existing["buffer"]
            ctx.last_save_index = existing["save_index"]
            ctx.state = StreamState.INTERRUPTED
        
        return ctx
    
    async def stream_with_save(
        self,
        ctx: StreamContext,
        generator: AsyncGenerator[str, None],
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        带保存功能的流式生成
        
        使用方式:
        async for event in streaming_service.stream_with_save(ctx, llm_stream):
            yield format_sse(event)
        """
        ctx.state = StreamState.STREAMING
        
        try:
            async for chunk in generator:
                # 更新上下文
                ctx.buffer.append({
                    "content": chunk,
                    "timestamp": datetime.utcnow().isoformat(),
                    "index": ctx.chunk_count,
                })
                ctx.chunk_count += 1
                ctx.total_tokens += len(chunk)
                ctx.last_activity = datetime.utcnow()
                
                # 触发回调
                if on_chunk:
                    await on_chunk(chunk)
                
                # 增量保存
                if ctx.chunk_count % self.save_interval == 0:
                    await self._save_partial(ctx)
                
                # 缓冲区满时强制保存
                if len(ctx.buffer) >= self.max_buffer_size:
                    await self._save_partial(ctx)
                
                yield {
                    "type": "chunk",
                    "content": chunk,
                    "index": ctx.chunk_count,
                }
            
            # 正常完成
            ctx.state = StreamState.COMPLETED
            await self._finalize_stream(ctx)
            
            yield {
                "type": "done",
                "total_chunks": ctx.chunk_count,
                "total_tokens": ctx.total_tokens,
            }
            
        except asyncio.CancelledError:
            # 客户端断开
            ctx.state = StreamState.INTERRUPTED
            await self._save_partial(ctx)
            raise
            
        except Exception as e:
            # 异常降级
            ctx.state = StreamState.ERROR
            await self._save_partial(ctx)
            
            yield {
                "type": "error",
                "error": str(e),
                "partial_saved": True,
                "saved_chunks": ctx.chunk_count,
            }
    
    async def restore_stream(self, message_id: str) -> Optional[StreamContext]:
        """恢复中断的流"""
        existing = await self._load_partial_stream(message_id)
        if not existing:
            return None
        
        ctx = self._contexts.get(message_id)
        if not ctx:
            return None
        
        ctx.buffer = existing["buffer"]
        ctx.last_save_index = existing["save_index"]
        ctx.state = StreamState.INTERRUPTED
        
        return ctx
    
    async def get_remaining_content(self, message_id: str) -> list[str]:
        """获取已保存但未发送的内容"""
        existing = await self._load_partial_stream(message_id)
        return [item["content"] for item in existing.get("buffer", [])] if existing else []
    
    async def _save_partial(self, ctx: StreamContext):
        """保存部分流数据到 Redis"""
        key = f"stream:partial:{ctx.message_id}"
        data = {
            "session_id": ctx.session_id,
            "user_id": ctx.user_id,
            "kb_id": ctx.kb_id,
            "state": ctx.state.value,
            "buffer": ctx.buffer[ctx.last_save_index:],
            "save_index": ctx.chunk_count,
            "last_activity": ctx.last_activity.isoformat(),
        }
        # 保留 24 小时
        await self.redis.setex(key, 86400, json.dumps(data))
        ctx.last_save_index = ctx.chunk_count
    
    async def _load_partial_stream(self, message_id: str) -> Optional[dict]:
        """从 Redis 加载部分流数据"""
        key = f"stream:partial:{message_id}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def _finalize_stream(self, ctx: StreamContext):
        """最终保存并清理"""
        # 保存到数据库
        async with self.db_factory() as db:
            from app.models.chat import Message
            message = await db.get(Message, ctx.message_id)
            if message:
                message.content = "".join(item["content"] for item in ctx.buffer)
                message.state = "completed"
                await db.commit()
        
        # 清理 Redis
        await self.redis.delete(f"stream:partial:{ctx.message_id}")
        self._contexts.pop(ctx.message_id, None)
```

**模型扩展：`app/models/chat.py`**

```python
from sqlalchemy import Column, String, Text, DateTime, Enum, Integer
from app.db.base import Base
import enum

class MessageState(enum.Enum):
    """消息状态"""
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ERROR = "error"

class Message(Base):
    """消息模型"""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=True)
    token_count = Column(Integer, default=0)
    state = Column(
        Enum(MessageState),
        default=MessageState.PENDING,
        index=True
    )
    partial_content = Column(Text, nullable=True)  # 用于存储未完成的流内容
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**API 端点改造：`app/api/v1/endpoints/chat.py`**

```python
from app.services.streaming_service import StreamingService, StreamState
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat"])

class AgentChatRequest(BaseModel):
    query: str
    kb_id: str
    session_id: Optional[str] = None
    stream: bool = True
    restore_previous: bool = True  # 新增：是否尝试恢复之前的流

@router.post("/agent_chat")
async def chat_with_agent(
    request: AgentChatRequest,
    current_user: User = Depends(deps.get_current_user),
    streaming_service: StreamingService = Depends(get_streaming_service),
):
    # ... 现有授权检查 ...
    
    # 创建或恢复流上下文
    if request.restore_previous and not request.session_id:
        # 查找最近的未完成消息
        existing_msg = await find_last_interrupted_message(
            user_id=current_user.id,
            kb_id=request.kb_id,
        )
        if existing_msg:
            ctx = await streaming_service.restore_stream(existing_msg.id)
            if ctx:
                # 恢复并继续
                remaining = await streaming_service.get_remaining_content(existing_msg.id)
                return StreamingResponse(
                    message_id=existing_msg.id,
                    restored=True,
                    remaining_content=remaining,
                    state=StreamState.INTERRUPTED,
                )
    
    # 新建流
    ctx = await streaming_service.create_context(
        session_id=request.session_id,
        message_id=generate_uuid(),
        user_id=current_user.id,
        kb_id=request.kb_id,
    )
    
    async def generate_stream():
        # 获取 LLM 流式响应
        llm_generator = await agent_service.chat_stream(
            query=request.query,
            kb_id=request.kb_id,
            session_id=request.session_id,
        )
        
        async for event in streaming_service.stream_with_save(
            ctx=ctx,
            generator=llm_generator,
        ):
            if event["type"] == "chunk":
                yield f"data: {json.dumps({'chunk': event['content']})}\n\n"
            elif event["type"] == "done":
                yield f"data: {json.dumps({'done': True, **event})}\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'error': event})}\n\n"
    
    return StreamingResponse(
        content=generate_stream(),
        media_type="text/event-stream",
        headers={
            "X-Message-Id": ctx.message_id,
            "X-Stream-State": ctx.state.value,
        }
    )
```

#### 3.1.3 性能指标

| 指标 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| 网络中断后内容丢失率 | 100% | 0% | ✅ 100% |
| 断点恢复耗时 | N/A | < 500ms | ✅ 新增 |
| 平均响应延迟增加 | N/A | < 5ms | ✅ 可接受 |
| Redis 存储开销 | N/A | ~10KB/会话 | ✅ 低 |

---

### 3.2 多租户安全隔离加强

#### 3.2.1 问题分析

**现状痛点**：

- 仅检查 `user_id`，未检查 `tenant_id`
- Enterprise 用户可能跨租户访问资源
- 日志中可能泄露其他租户信息

#### 3.2.2 解决方案设计

**新增模块：`app/core/tenant_security.py`**

```python
"""
多租户安全隔离模块
确保租户间数据完全隔离
"""
from typing import Optional, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Depends

T = TypeVar("T")

class AccessLevel(Enum):
    """访问级别"""
    OWNER = "owner"           # 完全所有权
    TENANT_MEMBER = "tenant"  # 租户成员
    SHARED = "shared"        # 已共享资源
    PUBLIC = "public"        # 公开资源

@dataclass
class AccessContext:
    """访问上下文"""
    user_id: str
    tenant_id: str
    user_role: str
    access_level: AccessLevel

class TenantSecurity:
    """
    多租户安全检查器
    
    使用方式:
    1. 在 API 端点中注入依赖
    2. 使用 verify_access 检查资源访问权限
    3. 使用 apply_tenant_filter 自动添加租户过滤
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache = {}  # 简单内存缓存
    
    async def verify_knowledge_base_access(
        self,
        kb_id: str,
        user_id: str,
        tenant_id: str,
        require_owner: bool = False,
    ) -> AccessContext:
        """
        验证知识库访问权限
        
        检查项:
        1. 知识库是否存在
        2. 知识库是否属于当前租户
        3. 用户是否有权访问（所有者/成员/已共享）
        """
        # 查询知识库
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        kb = result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        
        # 检查租户隔离
        if kb.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="无权访问该知识库"
            )
        
        # 检查访问权限
        if kb.user_id == user_id:
            access_level = AccessLevel.OWNER
        elif kb.visibility == "public":
            access_level = AccessLevel.PUBLIC
        elif kb.visibility == "enterprise":
            access_level = AccessLevel.TENANT_MEMBER
        else:
            # 检查共享列表
            access_level = await self._check_shared_access(kb_id, user_id)
        
        if require_owner and access_level != AccessLevel.OWNER:
            raise HTTPException(
                status_code=403,
                detail="需要知识库所有者权限"
            )
        
        return AccessContext(
            user_id=user_id,
            tenant_id=tenant_id,
            user_role=kb.role,
            access_level=access_level,
        )
    
    async def verify_document_access(
        self,
        doc_id: str,
        user_id: str,
        tenant_id: str,
    ) -> AccessContext:
        """验证文档访问权限"""
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 文档属于哪个实体
        if doc.kb_id:
            # 继承知识库的访问控制
            return await self.verify_knowledge_base_access(
                kb_id=doc.kb_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        elif doc.tenant_id:
            # 直接属于租户
            if doc.tenant_id != tenant_id:
                raise HTTPException(status_code=403, detail="无权访问该文档")
            return AccessContext(
                user_id=user_id,
                tenant_id=tenant_id,
                user_role="member",
                access_level=AccessLevel.TENANT_MEMBER,
            )
        else:
            # 公开文档
            return AccessContext(
                user_id=user_id,
                tenant_id=tenant_id,
                user_role="guest",
                access_level=AccessLevel.PUBLIC,
            )
    
    def apply_tenant_filter(self, query, model, tenant_id: str):
        """
        自动为查询添加租户过滤
        
        使用方式:
        query = tenant_security.apply_tenant_filter(
            query=select(Document),
            model=Document,
            tenant_id=current_user.tenant_id
        )
        """
        if hasattr(model, "tenant_id"):
            return query.where(model.tenant_id == tenant_id)
        elif hasattr(model, "user_id"):
            return query.where(model.user_id == tenant_id)  # 租户 ID 作为 user_id
        return query
    
    async def _check_shared_access(self, kb_id: str, user_id: str) -> AccessLevel:
        """检查共享访问"""
        cache_key = f"shared:{kb_id}:{user_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = await self.db.execute(
            select(ShareRecord).where(
                ShareRecord.kb_id == kb_id,
                ShareRecord.shared_with == user_id,
                ShareRecord.is_active == True,
            )
        )
        share = result.scalar_one_or_none()
        
        if share:
            self._cache[cache_key] = AccessLevel.SHARED
            return AccessLevel.SHARED
        
        self._cache[cache_key] = AccessLevel.PUBLIC  # 降级为公开
        return AccessLevel.PUBLIC


# 依赖注入
async def get_tenant_security(
    db: AsyncSession = Depends(get_db),
) -> TenantSecurity:
    return TenantSecurity(db)


async def require_kb_access(
    kb_id: str,
    require_owner: bool = False,
    security: TenantSecurity = Depends(get_tenant_security),
    current_user: User = Depends(get_current_user),
) -> AccessContext:
    """知识库访问验证依赖"""
    return await security.verify_knowledge_base_access(
        kb_id=kb_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        require_owner=require_owner,
    )
```

**API 端点改造示例**：

```python
@router.post("/agent_chat")
async def chat_with_agent(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    security: TenantSecurity = Depends(get_tenant_security),  # 新增
):
    # ✅ 强制的租户隔离检查
    access_ctx = await security.verify_knowledge_base_access(
        kb_id=request.kb_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    
    # ... 后续逻辑 ...
```

#### 3.2.3 安全检查清单

```
┌────────────────────────────────────────────────────────────────┐
│                    多租户安全检查清单                             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ✅ 知识库访问    - [x] 租户 ID 验证                             │
│                   - [x] 所有者验证                               │
│                   - [x] 共享权限验证                             │
│                                                                │
│  ✅ 文档访问      - [x] 继承知识库权限                           │
│                   - [x] 租户边界检查                            │
│                   - [x] 公开文档白名单                           │
│                                                                │
│  ✅ API 查询      - [x] 自动注入 tenant_id 过滤                  │
│                   - [x] JOIN 查询租户验证                       │
│                   - [x] 跨租户聚合禁止                           │
│                                                                │
│  ✅ 日志脱敏      - [x] 敏感字段掩码                             │
│                   - [x] 租户 ID 校验                            │
│                   - [x] 审计日志分离                            │
│                                                                │
│  ✅ 审计追踪      - [x] 租户维度统计                             │
│                   - [x] 异常访问告警                            │
│                   - [x] 权限变更记录                            │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

### 3.3 API 限流与配额管理

#### 3.3.1 解决方案设计

**新增模块：`app/core/rate_limiter.py`**

```python
"""
API 限流与配额管理
支持多维度限流：用户、租户、API Key、知识库
"""
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import asyncio
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

class LimitType(Enum):
    """限流类型"""
    USER = "user"           # 按用户限流
    TENANT = "tenant"       # 按租户限流
    API_KEY = "api_key"     # 按 API Key 限流
    KB = "kb"              # 按知识库限流
    IP = "ip"              # 按 IP 限流

@dataclass
class RateLimit:
    """限流规则"""
    limit_type: LimitType
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10  # 突发容量

@dataclass
class QuotaUsage:
    """配额使用情况"""
    used_today: int = 0
    used_this_hour: int = 0
    used_this_minute: int = 0
    remaining_today: int = 10000
    remaining_this_hour: int = 1000
    remaining_this_minute: int = 60
    reset_at: int = 0  #  Unix 时间戳

class RateLimiter:
    """
    滑动窗口限流器
    
    特性:
    1. 滑动窗口算法 - 更精确的限流
    2. 多维度限流 - 用户/租户/API Key/知识库/IP
    3. 配额预警 - 达到阈值时触发通知
    4. 优雅拒绝 - 返回 Retry-After 头
    """
    
    # 默认限流规则
    DEFAULT_LIMITS = {
        LimitType.USER: RateLimit(LimitType.USER, 60, 1000, 10000),
        LimitType.TENANT: RateLimit(LimitType.TENANT, 600, 10000, 100000),
        LimitType.KB: RateLimit(LimitType.KB, 100, 2000, 20000),
        LimitType.IP: RateLimit(LimitType.IP, 120, 2000, 20000),
    }
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_and_increment(
        self,
        key: str,
        limit_type: LimitType,
        custom_limit: Optional[RateLimit] = None,
    ) -> QuotaUsage:
        """
        检查限流并增加计数
        
        返回配额使用情况，如果超限则抛出 HTTPException
        """
        limit = custom_limit or self.DEFAULT_LIMITS.get(limit_type)
        now = int(time.time())
        
        # 构建 Redis 键
        minute_key = f"ratelimit:{key}:{limit_type.value}:minute"
        hour_key = f"ratelimit:{key}:{limit_type.value}:hour"
        day_key = f"ratelimit:{key}:{limit_type.value}:day"
        
        # 使用 Lua 脚本保证原子性
        lua_script = """
        local minute_key = KEYS[1]
        local hour_key = KEYS[2]
        local day_key = KEYS[3]
        local now = tonumber(ARGV[1])
        local minute_limit = tonumber(ARGV[2])
        local hour_limit = tonumber(ARGV[3])
        local day_limit = tonumber(ARGV[4])
        local window = 60
        
        -- 清理过期数据
        redis.call('ZREMRANGEBYSCORE', minute_key, 0, now - window)
        redis.call('ZREMRANGEBYSCORE', hour_key, 0, now - 3600)
        redis.call('ZREMRANGEBYSCORE', day_key, 0, now - 86400)
        
        -- 检查并计数
        local minute_count = redis.call('ZCARD', minute_key)
        local hour_count = redis.call('ZCARD', hour_key)
        local day_count = redis.call('ZCARD', day_key)
        
        if minute_count >= minute_limit then
            return {1, minute_count, hour_count, day_count, minute_limit, hour_limit, day_limit, now + 60}
        end
        
        if hour_count >= hour_limit then
            return {2, minute_count, hour_count, day_count, minute_limit, hour_limit, day_limit, now + 3600}
        end
        
        if day_count >= day_limit then
            return {3, minute_count, hour_count, day_count, minute_limit, hour_limit, day_limit, now + 86400}
        end
        
        -- 通过检查，添加计数
        redis.call('ZADD', minute_key, now, now)
        redis.call('ZADD', hour_key, now, now)
        redis.call('ZADD', day_key, now, now)
        redis.call('EXPIRE', minute_key, 120)
        redis.call('EXPIRE', hour_key, 3700)
        redis.call('EXPIRE', day_key, 87000)
        
        return {0, minute_count + 1, hour_count + 1, day_count + 1, minute_limit, hour_limit, day_limit, now}
        """
        
        result = await self.redis.eval(
            lua_script,
            3,
            minute_key, hour_key, day_key,
            now,
            limit.requests_per_minute,
            limit.requests_per_hour,
            limit.requests_per_day,
        )
        
        status, minute_count, hour_count, day_count, minute_limit, hour_limit, day_limit, reset_at = result
        
        if status != 0:
            retry_after = reset_at - now
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "type": ["minute", "hour", "day"][status - 1],
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(day_limit),
                    "X-RateLimit-Remaining": str(day_limit - day_count),
                    "X-RateLimit-Reset": str(reset_at),
                }
            )
        
        return QuotaUsage(
            used_today=day_count,
            used_this_hour=hour_count,
            used_this_minute=minute_count,
            remaining_today=day_limit - day_count,
            remaining_this_hour=hour_limit - hour_count,
            remaining_this_minute=minute_limit - minute_count,
            reset_at=reset_at,
        )
    
    async def get_usage(
        self,
        key: str,
        limit_type: LimitType,
    ) -> QuotaUsage:
        """获取当前配额使用情况"""
        now = int(time.time())
        
        minute_count = await self.redis.zcount(
            f"ratelimit:{key}:{limit_type.value}:minute",
            now - 60, now
        )
        hour_count = await self.redis.zcount(
            f"ratelimit:{key}:{limit_type.value}:hour",
            now - 3600, now
        )
        day_count = await self.redis.zcount(
            f"ratelimit:{key}:{limit_type.value}:day",
            now - 86400, now
        )
        
        limit = self.DEFAULT_LIMITS.get(limit_type)
        
        return QuotaUsage(
            used_today=day_count,
            used_this_hour=hour_count,
            used_this_minute=minute_count,
            remaining_today=limit.requests_per_day - day_count,
            remaining_this_hour=limit.requests_per_hour - hour_count,
            remaining_this_minute=limit.requests_per_minute - minute_count,
            reset_at=now + 86400,
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    def __init__(self, app, rate_limiter: RateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.exempt_paths = {"/health", "/docs", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # 获取限流键
        if api_key := request.headers.get("X-API-Key"):
            key = f"apikey:{hashlib.md5(api_key).hexdigest()}"
            limit_type = LimitType.API_KEY
        elif user := getattr(request.state, "user", None):
            key = f"user:{user.id}"
            limit_type = LimitType.USER
        elif tenant := getattr(request.state, "tenant_id", None):
            key = f"tenant:{tenant}"
            limit_type = LimitType.TENANT
        else:
            client_ip = request.client.host
            key = f"ip:{client_ip}"
            limit_type = LimitType.IP
        
        try:
            usage = await self.rate_limiter.check_and_increment(key, limit_type)
            
            response = await call_next(request)
            
            # 添加限流头
            response.headers["X-RateLimit-Remaining"] = str(usage.remaining_this_minute)
            response.headers["X-RateLimit-Reset"] = str(usage.reset_at)
            
            return response
            
        except HTTPException:
            raise
```

**配置扩展：`app/core/config.py`**

```python
class Settings(BaseSettings):
    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_USER_PER_MINUTE: int = 60
    RATE_LIMIT_USER_PER_HOUR: int = 1000
    RATE_LIMIT_USER_PER_DAY: int = 10000
    RATE_LIMIT_TENANT_PER_MINUTE: int = 600
    RATE_LIMIT_TENANT_PER_HOUR: int = 10000
    
    # 配额预警阈值
    QUOTA_WARNING_THRESHOLD: float = 0.8  # 80% 告警
    QUOTA_CRITICAL_THRESHOLD: float = 0.95  # 95% 阻断提示
```

#### 3.3.2 配额管理 API

```python
@router.get("/quota")
async def get_quota_usage(
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """获取当前用户配额使用情况"""
    user_usage = await rate_limiter.get_usage(
        key=f"user:{current_user.id}",
        limit_type=LimitType.USER,
    )
    
    tenant_usage = await rate_limiter.get_usage(
        key=f"tenant:{current_user.tenant_id}",
        limit_type=LimitType.TENANT,
    )
    
    return {
        "user": {
            "used_today": user_usage.used_today,
            "remaining_today": user_usage.remaining_today,
            "used_this_hour": user_usage.used_this_hour,
            "remaining_this_hour": user_usage.remaining_this_hour,
            "reset_at": user_usage.reset_at,
        },
        "tenant": {
            "used_today": tenant_usage.used_today,
            "remaining_today": tenant_usage.remaining_today,
            "quota_warning": tenant_usage.remaining_today < 1000,
        }
    }
```

---

## 四、P1 重要改进模块

### 4.1 智能搜索路由与降级 ✅ 已实现

#### 4.1.1 现有实现确认

根据代码审查，项目已经实现了完整的智能路由系统，包括：

**已实现的组件**：

| 组件 | 文件路径 | 功能描述 |
|------|----------|----------|
| `SmartRouter` | [smart_router.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/services/smart_router.py) | 查询级路由，支持 GREETING/RAG_ONLY/MEMORY_ONLY/HYBRID 模式 |
| `UnifiedRetriever` | [unified_retriever.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/services/unified_retriever.py) | 统一检索，集成 Memory 和 RAG |
| `IntentAgent` | [intent_agent.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/multi_agent_system/agents/intent_agent.py) | 意图分类，支持 20+ 意图类别 |
| `AgentOrchestrator` | [orchestrator.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/multi_agent_system/orchestrator.py) | 多智能体编排协调 |
| `LLMToolRouter` | [llm_tool_router.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/agent_framework/routing/llm_tool_router.py) | LLM 驱动的工具选择 |

**现有路由架构**：

```
用户查询
    │
    ├──▶ SmartRouter.route() ──▶ RouteMode (GREETING/RAG_ONLY/MEMORY_ONLY/HYBRID)
    │                                │
    │                                ├──▶ GREETING → 直接返回问候
    │                                ├──▶ RAG_ONLY → 向量检索
    │                                ├──▶ MEMORY_ONLY → 记忆检索
    │                                └──▶ HYBRID → 混合检索
    │
    ├──▶ IntentAgent.analyze() ──▶ IntentCategory + RoutingStrategy
    │                                │
    │                                ├──▶ DIRECT_ANSWER
    │                                ├──▶ RAG_RETRIEVAL
    │                                ├──▶ SINGLE_SPECIALIST
    │                                └──▶ MULTI_SPECIALIST_PARALLEL
    │
    └──▶ AgentOrchestrator ──▶ 调度专业智能体
                                     │
                                     ├──▶ FinanceSpecialist
                                     ├──▶ TaxSpecialist
                                     ├──▶ LegalSpecialist
                                     └──▶ ...
```

#### 4.1.2 优化建议（非重新实现）

虽然路由功能已实现，以下是可以进一步优化的方向：

**优化 1：路由结果缓存**

```python
# smart_router.py 优化建议
class SmartRouter:
    async def route(self, query: str, ...) -> RouteMode:
        # 建议增加：路由结果缓存，减少 LLM 调用
        cache_key = f"route:{hashlib.md5(query.encode()).hexdigest()}:{kb_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return RouteMode(cached)
        
        # ... 现有逻辑 ...
        
        await self.redis.setex(cache_key, 300, mode.value)  # 5分钟 TTL
        return mode
```

**优化 2：降级策略增强**

```python
# 在 UnifiedRetriever 中增强降级逻辑
async def retrieve(self, query, kb_id, ...):
    try:
        return await self._vector_search(query, kb_id)
    except VectorSearchError as e:
        logger.warning(f"向量检索失败，降级到关键词搜索: {e}")
        return await self._keyword_search(query, kb_id)
    except KeywordSearchError as e:
        logger.error(f"关键词搜索也失败: {e}")
        return await self._memory_search(query, session_id)
```

**优化 3：路由准确性反馈**

```python
# 收集用户反馈，持续优化路由模型
async def log_routing_feedback(
    query: str,
    predicted_route: RouteMode,
    actual_route: Optional[RouteMode] = None,
    user_rating: Optional[int] = None,  # 1-5
):
    """记录路由决策反馈，用于后续模型优化"""
    await self.db.execute(
        insert(RoutingFeedback).values(
            query=query,
            predicted_route=predicted_route,
            actual_route=actual_route,
            user_rating=user_rating,
            created_at=datetime.utcnow(),
        )
    )
```

**优化 4：IntentAgent 意图覆盖扩展**

当前 IntentAgent 支持 20+ 意图类别，建议：
- 增加业务特定意图（如：`CONTRACT_REVIEW`, `COMPLIANCE_CHECK`）
- 支持意图置信度阈值，低于阈值时降级到通用路由
- 增加意图组合支持（一个查询可能涉及多个意图）

#### 4.1.3 结论

智能搜索路由功能**已在项目中完整实现**，无需重新开发。建议将精力放在：
1. 路由缓存优化
2. 降级策略完善
3. 路由反馈收集
4. 意图类别扩展
                items=items,
                reasoning="向量检索模式",
            )
        
        elif route.mode == RetrievalMode.HYBRID:
            # 并行执行多种检索
            vector_task = self.search.vector_search(query, kb_id, top_k=5)
            keyword_task = self.search.keyword_search(query, kb_id, top_k=5)
            memory_task = self.memory.search(query, session_id, top_k=3)
            
            vector_results, keyword_results, memory_results = await asyncio.gather(
                vector_task, keyword_task, memory_task
            )
            
            # RRF 融合
            fused = self._rrf_fusion(
                results=[vector_results, keyword_results, memory_results],
                weights=[0.5, 0.3, 0.2],
                k=60,  # RRF 参数
            )
            
            return RetrievalResult(
                mode=RetrievalMode.HYBRID,
                items=fused[:route.suggested_top_k],
                reasoning="混合检索融合结果",
            )
        
        else:
            # Fallback: 降级检索
            return await self._fallback_retrieve(query, kb_id)
    
    async def _fallback_retrieve(
        self,
        query: str,
        kb_id: str,
    ) -> RetrievalResult:
        """
        降级检索策略
        
        当向量检索失败时的备选方案
        """
        try:
            # 尝试放宽阈值
            items = await self.search.vector_search(
                query=query,
                kb_id=kb_id,
                top_k=10,
                score_threshold=0.3,  # 放宽阈值
            )
            
            if items:
                return RetrievalResult(
                    mode=RetrievalMode.FALLBACK,
                    items=items,
                    reasoning="降级模式：放宽阈值重试",
                )
            
            # 最终降级：全文搜索
            items = await self.search.fulltext_search(query, kb_id)
            return RetrievalResult(
                mode=RetrievalMode.FALLBACK,
                items=items,
                reasoning="降级模式：全文搜索",
            )
            
        except Exception as e:
            # 记录错误但返回空结果
            logger.error(f"Fallback retrieval failed: {e}")
            return RetrievalResult(
                mode=RetrievalMode.FALLBACK,
                items=[],
                reasoning=f"检索失败: {str(e)}",
            )
    
    def _rrf_fusion(
        self,
        results: List[List[SearchItem]],
        weights: List[float],
        k: int = 60,
    ) -> List[SearchItem]:
        """
        RRF (Reciprocal Rank Fusion) 融合算法
        
        融合多个检索结果列表
        """
        scores: Dict[str, float] = {}
        
        for result_list, weight in zip(results, weights):
            for rank, item in enumerate(result_list):
                # RRF 分数
                rrf_score = weight / (k + rank + 1)
                scores[item.id] = scores.get(item.id, 0) + rrf_score
        
        # 按融合分数排序
        sorted_items = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 构建结果
        id_to_item = {item.id: item for result in results for item in result}
        fused = []
        seen_ids = set()
        
        for item_id, score in sorted_items:
            if item_id not in seen_ids:
                item = id_to_item[item_id]
                item.score = score
                fused.append(item)
                seen_ids.add(item_id)
        
        return fused
```

---

### 4.2 记忆系统增强

#### 4.2.1 解决方案设计

**新增模块：`app/services/entity_memory.py`**

```python
"""
实体持久化记忆
用于保存跨会话的重要实体上下文
"""
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

class EntityType(Enum):
    """实体类型"""
    PROJECT = "project"
    PERSON = "person"
    COMPANY = "company"
    PRODUCT = "product"
    TOPIC = "topic"
    CUSTOM = "custom"

@dataclass
class EntityContext:
    """实体上下文"""
    id: Optional[str]
    entity_type: EntityType
    entity_name: str
    description: Optional[str]
    user_id: str
    tenant_id: str
    last_mentioned: datetime
    mention_count: int
    importance: float  # 0.0 - 1.0
    aliases: List[str]  # 别名列表
    metadata: Dict  # 自定义元数据
    expires_at: datetime

class EntityMemory:
    """
    实体持久化记忆
    
    功能:
    1. 跨会话记忆用户提到的关键实体
    2. 自动维护实体的重要性评分
    3. 支持别名识别
    4. 自动过期和清理
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_entity(
        self,
        entity_type: EntityType,
        entity_name: str,
        user_id: str,
        tenant_id: str,
        description: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ):
        """记录/更新实体"""
        now = datetime.utcnow()
        
        # 检查是否已存在
        result = await self.db.execute(
            select(EntityContextRecord).where(
                EntityContextRecord.entity_name == entity_name,
                EntityContextRecord.user_id == user_id,
                EntityContextRecord.entity_type == entity_type,
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # 更新已有实体
            existing.mention_count += 1
            existing.last_mentioned = now
            existing.importance = self._calculate_importance(
                existing.mention_count,
                existing.created_at,
                now,
            )
            if description:
                existing.description = description
            if aliases:
                existing.aliases = list(set(existing.aliases + aliases))
        else:
            # 创建新实体
            entity = EntityContextRecord(
                entity_type=entity_type.value,
                entity_name=entity_name,
                description=description,
                user_id=user_id,
                tenant_id=tenant_id,
                last_mentioned=now,
                mention_count=1,
                importance=0.5,  # 初始重要性
                aliases=aliases or [],
                metadata=metadata or {},
                expires_at=now + timedelta(days=90),  # 90 天过期
            )
            self.db.add(entity)
        
        await self.db.commit()
    
    async def get_relevant_entities(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        limit: int = 10,
    ) -> List[EntityContext]:
        """获取与查询相关的实体"""
        # 查询活跃实体
        result = await self.db.execute(
            select(EntityContextRecord)
            .where(
                EntityContextRecord.user_id == user_id,
                EntityContextRecord.tenant_id == tenant_id,
                EntityContextRecord.expires_at > datetime.utcnow(),
            )
            .order_by(EntityContextRecord.importance.desc())
            .limit(limit * 2)  # 多取一些用于过滤
        )
        
        entities = result.scalars().all()
        
        # 简单关键词匹配
        matched = []
        query_keywords = set(query.lower().split())
        
        for entity in entities:
            # 检查名称和别名
            name_words = set(entity.entity_name.lower().split())
            alias_words = set()
            for alias in entity.aliases:
                alias_words.update(alias.lower().split())
            
            if query_keywords & (name_words | alias_words):
                matched.append(entity)
        
        # 如果匹配不够，返回重要性最高的
        if len(matched) < limit:
            matched.extend(
                e for e in entities
                if e not in matched
            )
        
        return matched[:limit]
    
    async def get_session_context(
        self,
        user_id: str,
        tenant_id: str,
        session_id: str,
    ) -> str:
        """
        构建会话上下文摘要
        
        返回格式化的上下文字符串，供 LLM 使用
        """
        entities = await self.get_relevant_entities(
            query="",
            user_id=user_id,
            tenant_id=tenant_id,
            limit=20,
        )
        
        if not entities:
            return ""
        
        context_parts = ["【相关上下文】"]
        
        # 按类型分组
        by_type = {}
        for e in entities:
            if e.entity_type not in by_type:
                by_type[e.entity_type] = []
            by_type[e.entity_type].append(e)
        
        for entity_type, type_entities in by_type.items():
            context_parts.append(f"\n{entity_type.value}:")
            for e in type_entities[:5]:  # 每类最多 5 个
                context_parts.append(f"  - {e.entity_name}")
                if e.description:
                    context_parts.append(f"    ({e.description})")
        
        return "\n".join(context_parts)
    
    async def cleanup_expired(self):
        """清理过期实体"""
        await self.db.execute(
            delete(EntityContextRecord).where(
                EntityContextRecord.expires_at < datetime.utcnow()
            )
        )
        await self.db.commit()
    
    def _calculate_importance(
        self,
        mention_count: int,
        first_mentioned: datetime,
        last_mentioned: datetime,
    ) -> float:
        """
        计算实体重要性
        
        因素:
        1. 提及次数
        2. 首次提及距今时间
        3. 最后提及距今时间
        """
        days_active = (last_mentioned - first_mentioned).days + 1
        
        # 提及频率
        frequency = mention_count / days_active
        
        # 近期提及加成
        days_since_last = (datetime.utcnow() - last_mentioned).days
        recency = max(0, 1 - days_since_last / 30)  # 30 天内线性衰减
        
        # 综合评分
        importance = min(1.0, (frequency * 0.3 + recency * 0.7))
        
        return importance


# 数据库模型
class EntityContextRecord(Base):
    __tablename__ = "entity_contexts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    user_id = Column(String(36), nullable=False, index=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    last_mentioned = Column(DateTime, nullable=False)
    mention_count = Column(Integer, default=1)
    importance = Column(Float, default=0.5)
    aliases = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
```

**记忆管理器增强：`app/memory_system/memory_manager.py`**

```python
class MemoryManager:
    """
    记忆管理器 - 增强版
    
    新增功能:
    1. 真正的遗忘机制
    2. 实体上下文持久化
    3. 智能压缩
    """
    
    def __init__(
        self,
        db_factory,
        entity_memory: EntityMemory,  # 新增
        redis_client,
    ):
        # ... 现有初始化 ...
        self.entity_memory = entity_memory
    
    async def auto_cleanup(self, session_id: str):
        """
        自动清理低价值记忆
        
        策略:
        1. 删除重要度低于阈值且超过一定时间的记忆
        2. 保留高价值记忆更长时间
        """
        threshold = 0.3
        grace_period = timedelta(days=7)
        
        async with self.db_factory() as db:
            # 查找低价值记忆
            result = await db.execute(
                select(SemanticMemoryRecord)
                .where(
                    SemanticMemoryRecord.session_id == session_id,
                    SemanticMemoryRecord.importance < threshold,
                    SemanticMemoryRecord.created_at < datetime.utcnow() - grace_period,
                )
            )
            
            low_value = result.scalars().all()
            
            for record in low_value:
                await record.mark_as_forgotten(db)
            
            await db.commit()
    
    async def extract_and_persist_context(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str,
        query: str,
        response: str,
    ):
        """
        提取并持久化关键实体上下文
        
        从对话中识别项目、人名、公司等实体并保存
        """
        # 使用 LLM 提取实体
        extraction_prompt = f"""
从以下对话中提取关键实体:

用户问题: {query}
AI回答: {response}

请提取以下类型的实体:
- 项目名称 (PROJECT)
- 人名 (PERSON)
- 公司/组织名称 (COMPANY)
- 产品名称 (PRODUCT)
- 话题关键词 (TOPIC)

以 JSON 格式返回:
{{"entities": [{{"type": "类型", "name": "名称", "description": "描述(可选)"}}]}}
"""
        
        try:
            response = await self.llm_adapter.chat([
                {"role": "user", "content": extraction_prompt}
            ])
            
            entities = json.loads(response.content)["entities"]
            
            for entity_data in entities:
                await self.entity_memory.record_entity(
                    entity_type=EntityType(entity_data["type"]),
                    entity_name=entity_data["name"],
                    user_id=user_id,
                    tenant_id=tenant_id,
                    description=entity_data.get("description"),
                )
                
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
    
    async def get_contextual_memory(
        self,
        session_id: str,
        query: str,
        user_id: str,
        tenant_id: str,
    ) -> str:
        """
        获取上下文增强的记忆内容
        """
        # 1. 获取会话记忆
        session_memory = await self.get_session_context(session_id)
        
        # 2. 获取相关实体
        entity_context = await self.entity_memory.get_session_context(
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        
        # 3. 合并返回
        parts = []
        if entity_context:
            parts.append(entity_context)
        if session_memory:
            parts.append(session_memory)
        
        return "\n\n".join(parts)
```

---

### 4.3 性能优化

#### 4.3.1 LLM 调用限流与优化

**新增模块：`app/services/llm_budget_manager.py`**

```python
"""
LLM 调用预算管理器
控制 Token 消耗，防止超额使用
"""
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class BudgetAlert(Enum):
    """预算告警级别"""
    NORMAL = "normal"
    WARNING = "warning"      # 80%
    CRITICAL = "critical"    # 95%
    EXCEEDED = "exceeded"    # 100%

@dataclass
class BudgetInfo:
    """预算信息"""
    total_tokens: int
    used_tokens: int
    remaining_tokens: int
    alert_level: BudgetAlert
    reset_at: datetime
    daily_limit: int
    monthly_limit: int

class LLMBudgetManager:
    """
    LLM 预算管理器
    
    功能:
    1. 用户/租户 Token 配额管理
    2. 实时消耗追踪
    3. 智能限流和告警
    4. 预算超限保护
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_and_reserve(
        self,
        user_id: str,
        tenant_id: str,
        estimated_tokens: int,
    ) -> bool:
        """
        检查预算并预留
        
        返回是否允许调用
        """
        key = f"llm_budget:{tenant_id}"
        
        # 使用 Lua 脚本保证原子性
        lua_script = """
        local key = KEYS[1]
        local estimated = tonumber(ARGV[1])
        local daily_limit = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        -- 获取当前使用量
        local data = redis.call('HGETALL', key)
        local used = 0
        for i = 1, #data, 2 do
            if data[i] == 'used' then
                used = tonumber(data[i+1])
                break
            end
        end
        
        -- 检查预算
        if used + estimated > daily_limit then
            return {0, used, daily_limit}
        end
        
        -- 预留
        redis.call('HSET', key, 'used', used + estimated)
        redis.call('EXPIRE', key, 86400)
        
        return {1, used + estimated, daily_limit}
        """
        
        daily_limit = await self._get_daily_limit(tenant_id)
        now = int(datetime.utcnow().timestamp())
        
        result = await self.redis.eval(
            lua_script, 1, key, estimated_tokens, daily_limit, now
        )
        
        allowed, used, limit = result
        
        if not allowed:
            # 触发限流
            await self._trigger_rate_limit(user_id, tenant_id, "budget_exceeded")
        
        return bool(allowed)
    
    async def record_usage(
        self,
        tenant_id: str,
        actual_tokens: int,
        cost: float,
    ):
        """记录实际使用量"""
        key = f"llm_budget:{tenant_id}"
        
        # 更新使用量
        await self.redis.hincrby(key, "used", actual_tokens)
        await self.redis.hincrbyfloat(key, "cost", cost)
        
        # 检查告警阈值
        budget_info = await self.get_budget_info(tenant_id)
        
        if budget_info.alert_level == BudgetAlert.CRITICAL:
            await self._send_alert(tenant_id, "CRITICAL", budget_info)
    
    async def get_budget_info(self, tenant_id: str) -> BudgetInfo:
        """获取预算信息"""
        key = f"llm_budget:{tenant_id}"
        data = await self.redis.hgetall(key)
        
        used = int(data.get("used", 0))
        cost = float(data.get("cost", 0))
        daily_limit = await self._get_daily_limit(tenant_id)
        
        remaining = max(0, daily_limit - used)
        usage_ratio = used / daily_limit if daily_limit > 0 else 0
        
        if usage_ratio >= 1.0:
            alert_level = BudgetAlert.EXCEEDED
        elif usage_ratio >= 0.95:
            alert_level = BudgetAlert.CRITICAL
        elif usage_ratio >= 0.8:
            alert_level = BudgetAlert.WARNING
        else:
            alert_level = BudgetAlert.NORMAL
        
        return BudgetInfo(
            total_tokens=daily_limit,
            used_tokens=used,
            remaining_tokens=remaining,
            alert_level=alert_level,
            reset_at=datetime.utcnow() + timedelta(hours=24 - datetime.utcnow().hour),
            daily_limit=daily_limit,
            monthly_limit=daily_limit * 30,
        )
    
    async def _send_alert(self, tenant_id: str, level: str, info: BudgetInfo):
        """发送告警通知"""
        alert_key = f"alert:llm_budget:{tenant_id}:{datetime.utcnow().date()}"
        
        if await self.redis.exists(alert_key):
            return  # 今天已发送过
        
        # TODO: 集成邮件/钉钉/飞书通知
        logger.warning(
            f"LLM Budget Alert [{level}] for tenant {tenant_id}: "
            f"used={info.used_tokens}/{info.daily_limit}"
        )
        
        await self.redis.setex(alert_key, 86400, "1")
```

#### 4.3.2 向量检索性能优化

**检索服务改造：`app/services/search_service.py`**

```python
class SearchService:
    """
    搜索服务 - 性能优化版
    
    优化点:
    1. 向量检索缓存
    2. 查询预热
    3. 批量查询优化
    4. 连接池调优
    """
    
    async def search_optimized(
        self,
        query: str,
        kb_id: str,
        top_k: int = 5,
        score_threshold: float = 0.6,
        tenant_id: str = None,
        user_id: str = None,
    ) -> List[SearchResultItem]:
        """
        优化版搜索
        
        策略:
        1. 查询 embedding 缓存
        2. 结果缓存 (短期)
        3. 降级策略
        """
        # 1. 生成缓存键
        cache_key = self._generate_cache_key(query, kb_id, top_k)
        
        # 2. 检查缓存
        cached = await self.redis.get(cache_key)
        if cached:
            return self._deserialize_results(cached)
        
        # 3. 生成 embedding
        query_embedding = await self._get_embedding_with_cache(query)
        
        # 4. 执行检索
        try:
            results = await self._execute_vector_search(
                query_embedding=query_embedding,
                kb_id=kb_id,
                top_k=top_k,
                score_threshold=score_threshold,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            # 降级: 放宽阈值重试
            results = await self._execute_vector_search(
                query_embedding=query_embedding,
                kb_id=kb_id,
                top_k=top_k * 2,
                score_threshold=0.3,
            )
        
        # 5. 过滤和格式化
        filtered = [r for r in results if r.score >= score_threshold][:top_k]
        
        # 6. 缓存结果
        if filtered:
            await self.redis.setex(
                cache_key,
                300,  # 5分钟 TTL
                self._serialize_results(filtered)
            )
        
        return filtered
    
    async def batch_search(
        self,
        queries: List[str],
        kb_id: str,
        top_k: int = 5,
    ) -> Dict[str, List[SearchResultItem]]:
        """
        批量搜索
        
        使用场景:
        - 批量文档检索
        - 离线分析
        """
        # 并行执行查询
        tasks = [
            self.search_optimized(
                query=q,
                kb_id=kb_id,
                top_k=top_k,
            )
            for q in queries
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        output = {}
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.error(f"Batch search failed for '{query}': {result}")
                output[query] = []
            else:
                output[query] = result
        
        return output
```

---

### 4.4 监控可观测性增强

#### 4.4.1 业务指标监控

**新增模块：`app/services/business_metrics.py`**

```python
"""
业务指标监控
追踪有意义的业务指标
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 累加计数
    GAUGE = "gauge"          # 瞬时值
    HISTOGRAM = "histogram"  # 分布统计
    RATE = "rate"           # 速率

@dataclass
class BusinessMetric:
    """业务指标"""
    name: str
    value: float
    unit: str
    metric_type: MetricType
    tags: Dict[str, str]
    timestamp: datetime

class BusinessMetricsCollector:
    """
    业务指标收集器
    
    追踪的指标:
    1. 对话统计 - 对话数、成功率、用户满意度
    2. 检索统计 - 检索次数、平均结果数、缓存命中率
    3. Token 消耗 - 每日/每月 Token 消耗
    4. 性能指标 - 响应时间、P99 延迟
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self._buffer: List[BusinessMetric] = []
        self._flush_interval = 60  # 秒
    
    async def record_conversation(
        self,
        user_id: str,
        tenant_id: str,
        kb_id: str,
        duration_ms: int,
        token_used: int,
        tool_calls: int,
        success: bool,
        error: Optional[str] = None,
    ):
        """记录对话指标"""
        metrics = [
            BusinessMetric(
                name="rag.conversation.count",
                value=1,
                unit="count",
                metric_type=MetricType.COUNTER,
                tags={
                    "tenant_id": tenant_id,
                    "kb_id": kb_id,
                    "success": str(success),
                },
                timestamp=datetime.utcnow(),
            ),
            BusinessMetric(
                name="rag.conversation.duration",
                value=duration_ms,
                unit="ms",
                metric_type=MetricType.HISTOGRAM,
                tags={"tenant_id": tenant_id},
                timestamp=datetime.utcnow(),
            ),
            BusinessMetric(
                name="rag.token.usage",
                value=token_used,
                unit="tokens",
                metric_type=MetricType.COUNTER,
                tags={"tenant_id": tenant_id},
                timestamp=datetime.utcnow(),
            ),
        ]
        
        for metric in metrics:
            await self._record(metric)
    
    async def record_retrieval(
        self,
        tenant_id: str,
        kb_id: str,
        mode: str,  # rag, memory, hybrid, keyword
        result_count: int,
        cache_hit: bool,
        duration_ms: int,
    ):
        """记录检索指标"""
        metrics = [
            BusinessMetric(
                name="rag.retrieval.count",
                value=1,
                unit="count",
                metric_type=MetricType.COUNTER,
                tags={
                    "tenant_id": tenant_id,
                    "kb_id": kb_id,
                    "mode": mode,
                },
                timestamp=datetime.utcnow(),
            ),
            BusinessMetric(
                name="rag.retrieval.cache_hit",
                value=1 if cache_hit else 0,
                unit="count",
                metric_type=MetricType.COUNTER,
                tags={"tenant_id": tenant_id},
                timestamp=datetime.utcnow(),
            ),
            BusinessMetric(
                name="rag.retrieval.results",
                value=result_count,
                unit="count",
                metric_type=MetricType.GAUGE,
                tags={"mode": mode},
                timestamp=datetime.utcnow(),
            ),
        ]
        
        for metric in metrics:
            await self._record(metric)
    
    async def get_dashboard_data(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict:
        """获取仪表盘数据"""
        return {
            "conversation_stats": await self._get_conversation_stats(
                tenant_id, start_date, end_date
            ),
            "retrieval_stats": await self._get_retrieval_stats(
                tenant_id, start_date, end_date
            ),
            "token_usage": await self._get_token_usage(
                tenant_id, start_date, end_date
            ),
            "performance_stats": await self._get_performance_stats(
                tenant_id, start_date, end_date
            ),
        }
    
    async def _record(self, metric: BusinessMetric):
        """内部: 记录指标"""
        key = f"metrics:{metric.name}:{metric.timestamp.strftime('%Y%m%d%H')}"
        
        await self.redis.hincrbyfloat(
            f"{key}:{metric.tags_str}",
            metric.value
        )
        await self.redis.expire(key, 604800)  # 保留7天
    
    async def _get_conversation_stats(
        self,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> Dict:
        """获取对话统计"""
        # 实现聚合查询
        return {
            "total": 0,
            "success_rate": 0.0,
            "avg_duration_ms": 0,
        }
```

#### 4.4.2 健康检查增强

**新增端点：`app/api/v1/endpoints/health.py`**

```python
"""
健康检查 API
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import asyncio

router = APIRouter(prefix="/health", tags=["Health"])

class ComponentHealth(BaseModel):
    """组件健康状态"""
    name: str
    status: str  # healthy, degraded, unhealthy
    latency_ms: float
    details: Dict = {}

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    version: str
    components: List[ComponentHealth]

@router.get("", response_model=HealthCheckResponse)
async def health_check():
    """
    基础健康检查
    用于 K8s 存活探针 (liveness probe)
    """
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.VERSION,
        components=[],
    )

@router.get("/detailed", response_model=HealthCheckResponse)
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis),
):
    """
    详细健康检查
    
    用于 K8s 就绪探针 (readiness probe)
    检查所有依赖服务
    """
    components = []
    overall_healthy = True
    
    # 1. 数据库检查
    try:
        start = datetime.utcnow()
        await db.execute("SELECT 1")
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        
        components.append(ComponentHealth(
            name="postgresql",
            status="healthy",
            latency_ms=latency,
        ))
    except Exception as e:
        overall_healthy = False
        components.append(ComponentHealth(
            name="postgresql",
            status="unhealthy",
            latency_ms=0,
            details={"error": str(e)},
        ))
    
    # 2. Redis 检查
    try:
        start = datetime.utcnow()
        await redis.ping()
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        
        components.append(ComponentHealth(
            name="redis",
            status="healthy",
            latency_ms=latency,
        ))
    except Exception as e:
        overall_healthy = False
        components.append(ComponentHealth(
            name="redis",
            status="unhealthy",
            latency_ms=0,
            details={"error": str(e)},
        ))
    
    # 3. 向量数据库检查
    try:
        start = datetime.utcnow()
        await db.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        
        components.append(ComponentHealth(
            name="pgvector",
            status="healthy",
            latency_ms=latency,
        ))
    except Exception as e:
        components.append(ComponentHealth(
            name="pgvector",
            status="degraded",
            latency_ms=0,
            details={"error": "Vector extension not found"},
        ))
    
    status = "healthy" if overall_healthy else "unhealthy"
    
    # 如果所有关键组件都正常但有问题组件，降级处理
    unhealthy_count = sum(1 for c in components if c.status == "unhealthy")
    if unhealthy_count == 0:
        degraded_count = sum(1 for c in components if c.status == "degraded")
        if degraded_count > 0:
            status = "degraded"
    
    return HealthCheckResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=settings.VERSION,
        components=components,
    )

@router.get("/ready")
async def readiness_check():
    """
    就绪检查
    
    返回 200 表示可以接收流量
    返回 503 表示暂时不能接收流量
    """
    return {"ready": True}

@router.get("/live")
async def liveness_check():
    """
    存活检查
    
    返回 200 表示服务存活
    返回其他表示需要重启
    """
    return {"alive": True}
```

---

## 五、P2 功能增强

### 5.1 会话快照与恢复

#### 5.1.1 功能设计

**场景**：
- 用户在生成报告时中断
- 用户需要回退到某个版本
- 用户想保存当前进度稍后继续

**新增模型：`app/models/session_snapshot.py`**

```python
"""
会话快照
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, ForeignKey
from app.db.base import Base

class SessionSnapshot(Base):
    """
    会话快照
    
    保存用户工作进度，支持一键恢复
    """
    __tablename__ = "session_snapshots"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 快照元数据
    name = Column(String(200), nullable=True)  # 用户自定义名称
    description = Column(Text, nullable=True)   # 快照描述
    
    # 状态数据
    query = Column(Text, nullable=False)        # 当前输入
    partial_response = Column(Text, nullable=True)  # 部分响应
    memory_state = Column(JSON, nullable=True)  # 记忆状态序列化
    tool_calls = Column(JSON, nullable=True)    # 工具调用历史
    
    # 元信息
    progress_percent = Column(Integer, default=0)  # 预估进度 0-100
    chunk_count = Column(Integer, default=0)     # 已生成 chunk 数
    token_count = Column(Integer, default=0)    # Token 消耗
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # 过期时间，默认7天
    
    def __repr__(self):
        return f"<SessionSnapshot {self.id}: {self.name or 'Unnamed'}>"
```

**新增服务：`app/services/snapshot_service.py`**

```python
"""
会话快照服务
"""
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, delete

class SnapshotService:
    """
    会话快照服务
    
    功能:
    1. 创建快照
    2. 列出快照
    3. 恢复快照
    4. 删除快照
    5. 自动清理过期快照
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_snapshot(
        self,
        session_id: str,
        user_id: str,
        query: str,
        partial_response: str,
        memory_state: dict,
        tool_calls: List[dict],
        name: Optional[str] = None,
    ) -> SessionSnapshot:
        """创建快照"""
        snapshot = SessionSnapshot(
            session_id=session_id,
            user_id=user_id,
            name=name,
            query=query,
            partial_response=partial_response,
            memory_state=memory_state,
            tool_calls=tool_calls,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        
        return snapshot
    
    async def list_snapshots(
        self,
        session_id: str,
        user_id: str,
    ) -> List[SessionSnapshot]:
        """列出会话快照"""
        result = await self.db.execute(
            select(SessionSnapshot)
            .where(
                SessionSnapshot.session_id == session_id,
                SessionSnapshot.user_id == user_id,
                SessionSnapshot.expires_at > datetime.utcnow(),
            )
            .order_by(SessionSnapshot.created_at.desc())
        )
        return result.scalars().all()
    
    async def restore_snapshot(
        self,
        snapshot_id: str,
        user_id: str,
    ) -> dict:
        """
        恢复快照
        
        返回恢复所需的完整状态
        """
        result = await self.db.execute(
            select(SessionSnapshot)
            .where(
                SessionSnapshot.id == snapshot_id,
                SessionSnapshot.user_id == user_id,
            )
        )
        snapshot = result.scalar_one_or_none()
        
        if not snapshot:
            raise HTTPException(status_code=404, detail="快照不存在")
        
        return {
            "snapshot_id": snapshot.id,
            "query": snapshot.query,
            "partial_response": snapshot.partial_response,
            "memory_state": snapshot.memory_state,
            "tool_calls": snapshot.tool_calls,
            "created_at": snapshot.created_at,
        }
    
    async def cleanup_expired(self):
        """清理过期快照"""
        await self.db.execute(
            delete(SessionSnapshot)
            .where(SessionSnapshot.expires_at < datetime.utcnow())
        )
        await self.db.commit()
```

**API 端点：`app/api/v1/endpoints/snapshot.py`**

```python
@router.post("/sessions/{session_id}/snapshots")
async def create_snapshot(
    session_id: str,
    request: CreateSnapshotRequest,
    current_user: User = Depends(get_current_user),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
):
    """创建会话快照"""
    # 获取当前状态
    state = await agent_service.get_current_state(session_id)
    
    snapshot = await snapshot_service.create_snapshot(
        session_id=session_id,
        user_id=current_user.id,
        query=state["query"],
        partial_response=state["partial_response"],
        memory_state=state["memory_state"],
        tool_calls=state["tool_calls"],
        name=request.name,
    )
    
    return {"snapshot_id": snapshot.id}

@router.get("/sessions/{session_id}/snapshots")
async def list_snapshots(
    session_id: str,
    current_user: User = Depends(get_current_user),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
):
    """列出会话快照"""
    snapshots = await snapshot_service.list_snapshots(
        session_id=session_id,
        user_id=current_user.id,
    )
    
    return {
        "snapshots": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "created_at": s.created_at,
                "progress_percent": s.progress_percent,
            }
            for s in snapshots
        ]
    }

@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    snapshot_id: str,
    current_user: User = Depends(get_current_user),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
):
    """恢复快照"""
    state = await snapshot_service.restore_snapshot(
        snapshot_id=snapshot_id,
        user_id=current_user.id,
    )
    
    # 创建新会话并恢复状态
    new_session = await session_service.create_with_restore(state)
    
    return {"session_id": new_session.id}
```

---

### 5.2 智能追问建议

#### 5.2.1 功能设计

**新增服务：`app/services/followup_service.py`**

```python
"""
追问建议服务
"""
from typing import List, Optional
from pydantic import BaseModel

class FollowupSuggestion(BaseModel):
    """追问建议"""
    question: str
    reason: str
    priority: int  # 1-5, 越高越推荐

class FollowupService:
    """
    追问建议服务
    
    基于当前对话上下文生成追问建议
    """
    
    def __init__(self, llm_adapter):
        self.llm = llm_adapter
    
    async def generate_suggestions(
        self,
        query: str,
        response: str,
        context: List[dict],
        max_suggestions: int = 3,
    ) -> List[FollowupSuggestion]:
        """
        生成追问建议
        
        策略:
        1. 分析当前回答的关键点
        2. 识别可能的追问方向
        3. 生成自然的追问问题
        """
        prompt = f"""
基于以下对话，生成 {max_suggestions} 个可能的追问建议:

用户问题: {query}

AI回答: 
{response}

请分析回答中的关键信息，生成3个用户可能会追问的问题。
每个问题应该:
1. 聚焦于回答中的一个具体点
2. 使用自然语言
3. 对用户有实际价值

以 JSON 格式返回:
{{
    "suggestions": [
        {{"question": "追问问题", "reason": "为什么推荐这个问题", "priority": 1-5}}
    ]
}}
"""
        
        try:
            llm_response = await self.llm.chat([
                {"role": "user", "content": prompt}
            ])
            
            data = json.loads(llm_response.content)
            return [
                FollowupSuggestion(**s) 
                for s in data["suggestions"]
            ]
        except Exception as e:
            logger.warning(f"Followup generation failed: {e}")
            return self._get_default_suggestions(query)
    
    def _get_default_suggestions(self, query: str) -> List[FollowupSuggestion]:
        """获取默认建议"""
        return [
            FollowupSuggestion(
                question="能详细解释一下吗？",
                reason="获取更详细的说明",
                priority=1,
            ),
            FollowupSuggestion(
                question="有什么例子吗？",
                reason="通过示例加深理解",
                priority=2,
            ),
        ]
```

**API 集成**：

```python
@router.post("/chat/with_suggestions")
async def chat_with_suggestions(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    followup_service: FollowupService = Depends(get_followup_service),
):
    """
    带追问建议的对话
    
    返回对话结果和追问建议
    """
    # 执行对话
    response = await agent_service.chat(
        query=request.query,
        kb_id=request.kb_id,
        session_id=request.session_id,
    )
    
    # 生成追问建议
    suggestions = await followup_service.generate_suggestions(
        query=request.query,
        response=response.content,
        context=response.context,
    )
    
    return {
        "response": response.content,
        "suggestions": [s.dict() for s in suggestions],
    }
```

---

### 5.3 批量文档处理

#### 5.3.1 功能设计

**新增模型：`app/models/batch_task.py`**

```python
"""
批量处理任务
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Enum
from app.db.base import Base
import enum

class BatchTaskStatus(enum.Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BatchTask(Base):
    """批量处理任务"""
    __tablename__ = "batch_tasks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    
    # 任务信息
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False)  # document_processing, bulk_search, etc.
    
    # 配置
    config = Column(JSON, nullable=True)  # 任务特定配置
    
    # 进度
    status = Column(Enum(BatchTaskStatus), default=BatchTaskStatus.PENDING)
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    # 错误记录
    errors = Column(JSON, nullable=True)  # [{"item": "...", "error": "..."}]
    
    # 结果
    result = Column(JSON, nullable=True)
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    @property
    def progress_percent(self) -> int:
        if self.total_items == 0:
            return 0
        return int(self.processed_items / self.total_items * 100)

class BatchTaskItem(Base):
    """批量任务项"""
    __tablename__ = "batch_task_items"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("batch_tasks.id"), nullable=False)
    
    # 输入
    input_data = Column(JSON, nullable=False)
    
    # 输出
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # 状态
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
```

**WebSocket 进度推送**：

```python
"""
批量处理 WebSocket 服务
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json

class BatchProgressNotifier:
    """
    批量处理进度通知器
    
    通过 WebSocket 推送实时进度
    """
    
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """建立连接"""
        await websocket.accept()
        
        if task_id not in self._connections:
            self._connections[task_id] = set()
        self._connections[task_id].add(websocket)
    
    async def disconnect(self, websocket: WebSocket, task_id: str):
        """断开连接"""
        if task_id in self._connections:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
    
    async def notify_progress(
        self,
        task_id: str,
        processed: int,
        total: int,
        failed: int,
        current_item: str,
    ):
        """推送进度更新"""
        if task_id not in self._connections:
            return
        
        message = {
            "type": "progress",
            "task_id": task_id,
            "processed": processed,
            "total": total,
            "failed": failed,
            "percent": int(processed / total * 100) if total > 0 else 0,
            "current_item": current_item,
        }
        
        dead_connections = set()
        for websocket in self._connections[task_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.add(websocket)
        
        # 清理死连接
        for ws in dead_connections:
            self._connections[task_id].discard(ws)

@router.websocket("/batch/{task_id}/ws")
async def batch_progress_websocket(
    websocket: WebSocket,
    task_id: str,
    notifier: BatchProgressNotifier = Depends(get_notifier),
):
    """批量处理进度 WebSocket"""
    await notifier.connect(websocket, task_id)
    
    try:
        while True:
            # 保持连接，等待心跳或关闭
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await notifier.disconnect(websocket, task_id)
```

---

## 六、实施方案

### 6.1 实施阶段划分

| 阶段 | 时间 | 模块 | 优先级 | 风险 |
|------|------|------|--------|------|
| **Phase 1** | Week 1-2 | P0: 流式稳定性 + 多租户隔离 | P0 | 中 |
| **Phase 2** | Week 3-4 | P0: API 限流 + 监控增强 | P0 | 低 |
| **Phase 3** | ~~Week 5-6~~ | ✅ P1: 智能搜索路由 (已完成) | - | 已上线 |
| **Phase 4** | Week 5-6 | P1: 智能路由优化 (缓存+降级) | P1 | 低 |
| **Phase 5** | Week 7-8 | P1: 性能优化 (缓存) | P1 | 低 |
| **Phase 6** | Week 9-10 | P1: 记忆系统增强 | P1 | 中 |
| **Phase 7** | Week 11-12 | P2: 会话快照 + 追问建议 | P2 | 低 |
| **Phase 8** | Week 13-14 | P2: 批量处理 + 健康检查 | P2 | 低 |

### 6.2 实施里程碑

```
Week 1-2: P0 模块开发
    ├── 流式服务核心逻辑
    ├── 断点续传 API
    ├── 多租户安全中间件
    └── 单元测试 + 集成测试
    
Week 3-4: P0 基础设施
    ├── 限流服务 + 中间件
    ├── 配额管理 API
    ├── 业务指标收集
    └── 详细健康检查
    
Week 5-6: P1 智能检索优化
    ├── ✅ 智能路由服务 (已上线)
    ├── ✅ 混合检索实现 (已上线)
    ├── ✅ 降级策略 (已上线)
    └── 优化项: 路由缓存 + 反馈收集
    
Week 7-8: P1 性能
    ├── 多级缓存服务
    ├── LLM 预算管理
    └── 检索性能优化
    
Week 9-10: P1 记忆
    ├── 实体持久化
    ├── 遗忘机制
    └── 上下文增强
    
Week 11-12: P2 体验
    ├── 快照服务 + API
    ├── 追问建议服务
    └── 前端集成
    
Week 13-14: P2 工具
    ├── 批量处理服务
    ├── WebSocket 进度
    └── 文档 + 部署
```

### 6.3 回滚策略

每个阶段都需要准备回滚方案：

| 模块 | 回滚方式 | 回滚时间 | 影响范围 |
|------|----------|----------|----------|
| 流式稳定性 | 删除新表/路由 | < 5 min | 仅新功能 |
| 多租户隔离 | 禁用中间件 | < 2 min | 全局 |
| API 限流 | 配置关闭 | < 1 min | 全局 |
| 智能路由 | 回退到固定模式 | < 2 min | 检索功能 |
| 缓存服务 | 禁用缓存层 | < 1 min | 性能 |

---

## 七、验收标准

### 7.1 P0 模块验收

#### 流式输出稳定性
- [ ] 网络中断后内容恢复率 = 100%
- [ ] 断点恢复 API 响应时间 < 500ms
- [ ] 单元测试覆盖率 > 80%

#### 多租户隔离
- [ ] 跨租户访问尝试被正确拦截
- [ ] 单元测试覆盖所有隔离边界
- [ ] 安全审计无漏洞

#### API 限流
- [ ] 滑动窗口算法准确
- [ ] 超限请求返回 429 + Retry-After
- [ ] 配额预警正常触发

### 7.2 P1 模块验收

#### ✅ 智能搜索路由 (已上线)
- [x] 闲聊识别准确率 > 90%
- [x] 混合检索召回率提升 > 20%
- [x] 降级策略生效
- [ ] **优化项**: 路由结果缓存 (减少 LLM 调用)
- [ ] **优化项**: 路由准确性反馈收集

#### 智能路由优化
- [ ] 路由缓存命中率 > 40%
- [ ] 降级策略覆盖向量/关键词/记忆三级
- [ ] 路由延迟 < 50ms

#### 性能优化
- [ ] 缓存命中率 > 50%
- [ ] P95 响应时间降低 > 30%
- [ ] 无缓存雪崩风险

#### 记忆系统
- [ ] 实体识别准确率 > 85%
- [ ] 遗忘机制正常运行
- [ ] 上下文增强有效

### 7.3 P2 模块验收

#### 会话快照
- [ ] 快照创建/恢复功能正常
- [ ] WebSocket 推送及时
- [ ] 前端集成流畅

#### 追问建议
- [ ] 建议生成成功 > 80%
- [ ] 建议相关性评分 > 3.5/5
- [ ] 响应时间 < 2s

#### 批量处理
- [ ] 大规模任务稳定运行
- [ ] 错误重试机制正常
- [ ] 进度推送准确

---

## 八、风险评估与应对

### 8.1 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 缓存一致性 | 中 | 高 | 合理设置 TTL + 主动失效 |
| LLM 调用超时 | 中 | 中 | 完善重试 + 降级策略 |
| 向量检索性能 | 低 | 中 | 预先优化索引 |
| 分布式锁竞争 | 低 | 低 | 使用 Redisson |

### 8.2 业务风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 新功能用户不接受 | 低 | 中 | 灰度发布 + 用户调研 |
| 性能回退 | 中 | 高 | 充分性能测试 |
| 数据迁移问题 | 低 | 高 | 完整备份 + 回滚方案 |

### 8.3 资源需求

| 资源 | 数量 | 备注 |
|------|------|------|
| 开发人力 | 2 人 | 前后端配合 |
| 测试环境 | 1 套 | 等同生产配置 |
| 压测工具 | 1 套 | JMeter / Locust |
| 监控资源 | 额外 10% | 指标存储 |

---

## 九、附录

### 9.1 新增文件清单

```
app/
├── services/
│   ├── streaming_service.py      # 流式输出服务
│   ├── snapshot_service.py      # 会话快照服务
│   ├── followup_service.py      # 追问建议服务
│   ├── cache_manager.py         # 多级缓存管理
│   ├── llm_budget_manager.py    # LLM 预算管理
│   ├── business_metrics.py      # 业务指标
│   └── batch_process_service.py # 批处理服务
│
├── core/
│   ├── tenant_security.py       # 多租户安全
│   └── rate_limiter.py          # API 限流
│
├── memory_system/
│   └── entity_memory.py         # 实体持久化
│
├── api/v1/endpoints/
│   ├── health.py                # 健康检查
│   └── snapshot.py              # 快照 API
│
└── models/
    ├── session_snapshot.py       # 快照模型
    ├── batch_task.py             # 批处理模型
    └── entity_context.py         # 实体模型
```

### 9.2 配置项变更

```python
# app/core/config.py 新增配置

# 限流配置
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_USER_PER_MINUTE: int = 60
RATE_LIMIT_TENANT_PER_HOUR: int = 10000

# 配额配置
LLM_DAILY_QUOTA_PER_USER: int = 10000
LLM_DAILY_QUOTA_PER_TENANT: int = 100000
QUOTA_WARNING_THRESHOLD: float = 0.8

# 缓存配置
CACHE_L1_MAX_SIZE: int = 1000
CACHE_L1_TTL: int = 60
CACHE_L2_TTL: int = 300

# 快照配置
SNAPSHOT_ENABLED: bool = True
SNAPSHOT_TTL_DAYS: int = 7

# 批量处理配置
BATCH_MAX_CONCURRENCY: int = 10
BATCH_PROGRESS_WS_ENABLED: bool = True
```

### 9.3 数据库变更

```sql
-- 新增表: 实体上下文
CREATE TABLE entity_contexts (
    id VARCHAR(36) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_name VARCHAR(200) NOT NULL,
    description TEXT,
    user_id VARCHAR(36) NOT NULL,
    tenant_id VARCHAR(36) NOT NULL,
    last_mentioned TIMESTAMP NOT NULL,
    mention_count INTEGER DEFAULT 1,
    importance FLOAT DEFAULT 0.5,
    aliases JSON DEFAULT '[]',
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_entity_type (entity_type),
    INDEX idx_user_tenant (user_id, tenant_id),
    INDEX idx_importance (importance),
    INDEX idx_expires (expires_at)
);

-- 新增表: 会话快照
CREATE TABLE session_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(200),
    description TEXT,
    query TEXT NOT NULL,
    partial_response TEXT,
    memory_state JSON,
    tool_calls JSON,
    progress_percent INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    INDEX idx_session (session_id),
    INDEX idx_user (user_id),
    INDEX idx_expires (expires_at)
);

-- 新增表: 批量任务
CREATE TABLE batch_tasks (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    tenant_id VARCHAR(36) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    task_type VARCHAR(50) NOT NULL,
    config JSON,
    status VARCHAR(20) DEFAULT 'pending',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    errors JSON,
    result JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_status (status)
);

-- Message 表新增字段
ALTER TABLE messages ADD COLUMN state VARCHAR(20) DEFAULT 'pending';
ALTER TABLE messages ADD COLUMN partial_content TEXT;
ALTER TABLE messages ADD COLUMN stream_id VARCHAR(36);
```

---

## 文档结束

**版本历史**：

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| v1.0 | 2026-04-04 | Claude | 初始版本 |
| v1.1 | 2026-04-04 | Claude | 智能搜索路由已实现更正 (基于用户反馈) |
| v1.2 | 2026-04-04 | AI Assistant | **重大更新**: 完成第一轮实现情况核查 |
| | | | + 添加实现情况核查结果 (Section 1.4) |
| | | | + 更新改进范围总览图，标记已实现模块 |
| | | | + 添加详细实现验证清单 (Appendix B) |
| | | | + 更新术语表，添加关键技术术语 |
| | | | **关键发现**: 7/12 模块已实现，5个需要增强 |
| | | | - ✅ 多租户隔离: TenantContextMiddleware 完整实现 |
| | | | - ✅ 监控增强: MonitorService 完整实现 |
| | | | - ✅ 智能搜索路由: SmartRouter+IntentAgent 完整实现 |
| | | | - ✅ 记忆系统: 三层记忆+MemoryCache 完整实现 |
| | | | - ✅ 批量处理: AsyncTaskScheduler 完整实现 |
| | | | - 🔶 API限流: 缺少通用中间件 (仅政策采集用) |
| | | | - 🔶 流式稳定性: 缺少专用服务、增量保存、断点续传 |
| | | | - 🔶 追问建议: 缺少LLM生成逻辑 |

```python
"""
app/services/cache_manager.py

多级缓存管理器
L1: 进程内缓存 (内存)
L2: Redis 分布式缓存
L3: 数据库
"""
from typing import Optional, Any, Callable
from functools import wraps
import hashlib
import json
import asyncio
from datetime import datetime, timedelta

class CacheManager:
    """
    多级缓存管理器
    
    特性:
    1. L1 进程内缓存 - 极低延迟，容量有限
    2. L2 Redis 缓存 - 分布式共享，适中延迟
    3. 缓存穿透保护 - 空值缓存
    4. 缓存雪崩保护 - 随机过期时间
    5. 缓存击穿保护 - 分布式锁
    """
    
    def __init__(
        self,
        redis_client,
        l1_max_size: int = 1000,
        l1_ttl: int = 60,  # 秒
    ):
        self.redis = redis_client
        self.l1_cache = {}  # 简单字典实现
        self.l1_timestamps = {}
        self.l1_max_size = l1_max_size
        self.l1_ttl = l1_ttl
        self._lock = asyncio.Lock()
    
    async def get(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[Any]:
        """获取缓存"""
        full_key = f"{namespace}:{key}"
        
        # L1 检查
        if full_key in self.l1_cache:
            if self._is_l1_valid(full_key):
                return self.l1_cache[full_key]
            else:
                del self.l1_cache[full_key]
                del self.l1_timestamps[full_key]
        
        # L2 检查
        value = await self.redis.get(full_key)
        if value:
            data = json.loads(value)
            # 回填 L1
            await self._l1_set(full_key, data)
            return data
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: int = 300,  # 秒
    ):
        """设置缓存"""
        full_key = f"{namespace}:{key}"
        
        # L1
        await self._l1_set(full_key, value)
        
        # L2: 添加随机过期时间防止雪崩
        actual_ttl = ttl + int(asyncio.get_event_loop().time()) % 60
        await self.redis.setex(
            full_key,
            actual_ttl,
            json.dumps(value)
        )
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        namespace: str = "default",
        ttl: int = 300,
        lock_timeout: int = 10,
    ) -> Any:
        """
        获取或设置 (缓存穿透保护)
        
        如果缓存不存在，调用 factory 生成值并缓存
        """
        # 快速路径
        cached = await self.get(key, namespace)
        if cached is not None:
            return cached
        
        # 缓存不存在，需要生成
        cache_key = f"{namespace}:{key}"
        
        # 尝试获取分布式锁 (缓存击穿保护)
        lock_key = f"lock:{cache_key}"
        acquired = await self.redis.set(
            lock_key,
            "1",
            nx=True,
            ex=lock_timeout
        )
        
        if acquired:
            try:
                # 获取锁成功，生成值
                value = await factory()
                
                #