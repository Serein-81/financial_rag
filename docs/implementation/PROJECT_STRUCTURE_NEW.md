# RAG Backend 新增功能项目结构

## 📁 项目结构

```
d:\Python\Codebase\My_rag\rag_backend\app\
├── 📁 middleware/                           # 中间件
│   └── rate_limit_middleware.py           # API限流中间件 ⭐ (P0-1)
│
├── 📁 services/                            # 业务服务层
│   ├── streaming_service.py              # 流式服务稳定性增强 ⭐ (P0-2)
│   ├── snapshot_service.py                # 会话快照服务 ⭐ (P2-1)
│   ├── suggestion_service.py              # 追问建议服务 ⭐ (P2-2)
│   └── health_service.py                  # 健康检查服务 ⭐ (P2-3)
│
├── 📁 api/v1/endpoints/                   # API端点
│   ├── rate_limit.py                      # 限流管理API
│   ├── streaming.py                       # 流式管理API
│   ├── snapshot.py                         # 快照管理API
│   └── suggestion.py                       # 建议生成API
│
├── 📁 core/
│   └── config.py                          # 配置文件（已更新）
│
└── main.py                                # 主应用（已更新）
```

## ✨ 功能概览

### 🔴 P0-1: API通用限流中间件
**文件**: `app/middleware/rate_limit_middleware.py`

**核心功能**:
- ✅ 滑动窗口算法限流
- ✅ 多级限流：全局 < 租户 < 用户 < API Key
- ✅ HTTP 429 标准响应
- ✅ 优雅降级
- ✅ 异步并发安全

**配置项**:
```python
RATE_LIMIT_ENABLED = True
RATE_LIMIT_STRATEGY = "sliding_window"
RATE_LIMIT_GLOBAL_REQUESTS = 100
RATE_LIMIT_GLOBAL_WINDOW = 60
```

**API端点**:
- `GET /api/v1/rate-limit/stats` - 获取限流统计
- `POST /api/v1/rate-limit/reset/{key}` - 重置限流计数
- `POST /api/v1/rate-limit/cleanup` - 清理过期数据

### 🔴 P0-2: 流式稳定性增强
**文件**: `app/services/streaming_service.py`

**核心功能**:
- ✅ 增量保存检查点
- ✅ 断点续传
- ✅ 进度追踪
- ✅ 取消功能
- ✅ 优雅关闭

**关键类**:
- `StreamState` - 流状态枚举
- `StreamProgress` - 流进度信息
- `StreamCheckpoint` - 检查点数据
- `StreamingService` - 流式服务（全局单例）

**API端点**:
- `POST /api/v1/streaming/chat` - 带稳定性的流式聊天
- `GET /api/v1/streaming/progress/{stream_id}` - 获取进度
- `POST /api/v1/streaming/resume/{stream_id}` - 恢复流
- `GET /api/v1/streaming/active` - 列出活跃流
- `POST /api/v1/streaming/{stream_id}/cancel` - 取消流
- `POST /api/v1/streaming/cleanup` - 清理过期流
- `GET /api/v1/streaming/stats` - 获取统计

### 🟡 P2-1: 会话快照API
**文件**: `app/services/snapshot_service.py`

**核心功能**:
- ✅ 三种快照类型：MANUAL, AUTO, SYSTEM
- ✅ 快照创建和恢复
- ✅ 快照对比（diff）
- ✅ 过期快照清理
- ✅ 存储指标追踪

**关键类**:
- `SnapshotType` - 快照类型枚举
- `SnapshotDiff` - 快照差异
- `SessionSnapshot` - 快照数据模型
- `SnapshotService` - 快照服务

**API端点**:
- `POST /api/v1/snapshot/` - 创建快照
- `GET /api/v1/snapshot/` - 列出快照
- `GET /api/v1/snapshot/{id}` - 获取快照
- `DELETE /api/v1/snapshot/{id}` - 删除快照
- `POST /api/v1/snapshot/{id}/restore` - 恢复快照
- `POST /api/v1/snapshot/compare` - 对比快照
- `POST /api/v1/snapshot/cleanup` - 清理过期快照
- `GET /api/v1/snapshot/stats` - 获取统计

### 🟡 P2-2: 追问建议生成服务
**文件**: `app/services/suggestion_service.py`

**核心功能**:
- ✅ 8种建议类型
- ✅ 上下文分析
- ✅ 置信度评分
- ✅ 快速建议生成
- ✅ 会话级别建议

**8种建议类型**:
1. **DEEPEN** - 深入探讨
2. **EXPAND** - 扩展话题
3. **COMPARE** - 对比分析
4. **EXAMPLE** - 实例案例
5. **CONSEQUENCE** - 结果影响
6. **CAUSE** - 原因背景
7. **DIFFERENCE** - 区别探讨
8. **SUMMARY** - 总结概括

**API端点**:
- `POST /api/v1/suggestion/generate` - 生成建议
- `GET /api/v1/suggestion/session/{id}` - 获取会话建议
- `POST /api/v1/suggestion/quick` - 快速建议
- `GET /api/v1/suggestion/types` - 获取建议类型
- `GET /api/v1/suggestion/stats` - 获取统计

### 🟢 P2-3: 完善健康检查端点
**文件**: `app/services/health_service.py`

**核心功能**:
- ✅ 7个组件健康检查
- ✅ 3种健康级别：basic, standard, detailed
- ✅ 响应缓存
- ✅ 延迟追踪
- ✅ 健康历史记录

**检查的组件**:
1. **database** - PostgreSQL数据库
2. **redis** - Redis缓存
3. **llm_service** - LLM服务
4. **storage** - 存储服务
5. **vector_store** - 向量存储
6. **mcp_services** - MCP服务
7. **rate_limiter** - 限流器

**API端点**:
- `GET /api/v1/health` - 简单健康检查
- `GET /api/v1/health/detailed` - 详细健康检查
- `GET /api/v1/health/components/{component}` - 单组件检查
- `GET /api/v1/health/ready` - 就绪检查
- `GET /api/v1/health/live` - 存活检查

## 🔧 使用示例

### 1. 限流中间件使用
```python
# 无需手动调用，自动拦截所有请求
# 配置在 config.py 中的 RATE_LIMIT_* 配置项
```

### 2. 流式服务使用
```python
from app.services.streaming_service import streaming_service

stream_id = await streaming_service.create_stream(
    session_id="session_123",
    metadata={"user_id": "user_1"}
)

async for chunk in streaming_service.stream_with_save(stream_id, generator):
    print(chunk)
```

### 3. 会话快照使用
```python
from app.services.snapshot_service import snapshot_service

snapshot_id = await snapshot_service.create_snapshot(
    session_id="session_123",
    snapshot_type=SnapshotType.MANUAL,
    description="关键决策点"
)

restored = await snapshot_service.restore_snapshot(snapshot_id)
```

### 4. 追问建议使用
```python
from app.services.suggestion_service import suggestion_service

suggestions = await suggestion_service.generate_suggestions(
    session_id="session_123",
    conversation_history=history,
    types=[SuggestionType.DEEPEN, SuggestionType.EXAMPLE],
    count=3
)
```

### 5. 健康检查使用
```python
from app.services.health_service import health_service

# 详细健康检查
report = await health_service.check_detailed()

# 快速检查（仅关键组件）
quick = await health_service.check_quick()
```

## 📊 统计和监控

所有服务都提供统计端点：

```bash
# 限流统计
GET /api/v1/rate-limit/stats

# 流式统计
GET /api/v1/streaming/stats

# 快照统计
GET /api/v1/snapshot/stats

# 建议统计
GET /api/v1/suggestion/stats

# 健康检查
GET /api/v1/health/detailed
```

## 🚀 启动验证

```bash
cd d:\Python\Codebase\My_rag\rag_backend
python -m app.main
```

所有新增功能将在应用启动时自动注册和初始化。

## ⚙️ 依赖项

所有新增功能都使用标准库或已存在的依赖：
- ✅ asyncio（异步支持）
- ✅ logging（日志）
- ✅ dataclasses（数据结构）
- ✅ datetime（时间处理）
- ✅ contextvars（上下文隔离）
- ✅ 已存在的数据库和缓存连接

无需额外安装依赖。
