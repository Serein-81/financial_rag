# A2A Transport Layer 使用指南

## 概述

A2A 传输层为多智能体系统提供统一的通信抽象，支持：
- **本地传输**：复用 message_bus，同进程 Agent 间通信（零网络开销）
- **HTTP 传输**：跨服务通信，RESTful API
- **自动选择**：根据 Agent 位置自动选择最优传输方式
- **流式事件**：支持 SSE 流式接收任务事件
- **广播消息**：向所有本地 Agent 广播消息
- **健康检查**：实时监控传输层健康状态

## 架构

```
┌─────────────────────────────────────────┐
│          Transport Manager              │
│  (自动选择 + 统一接口 + Agent 注册)       │
└────────┬───────────────┬───────────────┘
         │               │
    ┌────▼────┐     ┌────▼────┐
    │ Local   │     │  HTTP   │
    │Transport│     │Transport│
    └────┬────┘     └────┬────┘
         │               │
    ┌────▼────┐     ┌────▼────┐
    │message_ │     │ httpx   │
    │  bus    │     │ Client  │
    └─────────┘     └─────────┘
```

## 快速开始

### 1. 初始化传输管理器

```python
from app.a2a_protocol import get_transport_manager, shutdown_transport_manager

async def main():
    # 获取传输管理器单例
    transport = await get_transport_manager()
    
    # 初始化（传入 message_bus）
    await transport.initialize(message_bus)
    
    # 注册本地 Agent
    transport.register_local_agent("assistant", assistant_agent)
    
    # 注册远程 Agent
    transport.register_remote_agent(
        "cloud_agent",
        url="http://cloud-service:8000/a2a/v1"
    )
    
    # 使用完毕关闭
    await transport.shutdown()
```

### 2. 单例模式使用（推荐）

```python
from app.a2a_protocol import get_transport_manager, shutdown_transport_manager

# 获取全局单例
manager = await get_transport_manager()

# 使用
await manager.send_message(
    to_agent="assistant",
    message={"content": "Hello"}
)

# 程序结束时关闭
await shutdown_transport_manager()
```

## 核心功能

### 1. 发送消息

```python
# 自动选择传输方式（本地 vs HTTP）
result = await transport.send_message(
    to_agent="assistant",
    message={"content": "Hello, how are you?"},
    tenant_id="tenant_123",
    wait_for_response=True  # 等待响应
)

# 或者发送通知（单向，不等待响应）
await transport.send_message(
    to_agent="assistant",
    message={"event": "update", "data": {...}},
    tenant_id="tenant_123",
    wait_for_response=False
)
```

### 2. 流式接收（SSE）

```python
# 订阅任务事件流
async for event in transport.stream_task_events(
    to_agent="assistant",
    task_id="task_123",
    tenant_id="tenant_123"
):
    print(f"Received event: {event}")
    
    # 事件示例：
    # {"type": "status", "data": {"status": "running"}}
    # {"type": "data", "data": {"result": "..."}}
    # {"type": "done", "data": {"success": true}}
```

### 3. 广播消息

```python
# 向所有本地 Agent 广播消息
result = await transport.broadcast(
    message={"event": "system_update"},
    tenant_id="tenant_123",
    exclude_agents=["problematic_agent"]  # 可选：排除某些 Agent
)

print(f"广播给 {result['total']} 个 Agent")
for agent_name, agent_result in result['results'].items():
    print(f"  {agent_name}: {agent_result}")
```

### 4. 事件订阅

```python
# 订阅特定类型的事件
async def my_callback(event):
    print(f"Received event: {event}")

subscription_id = await transport.subscribe_events(
    agent="assistant",
    event_types=["task_complete", "error"],
    callback=my_callback,
    tenant_id="tenant_123"
)

print(f"Subscribed with ID: {subscription_id}")
```

### 5. 健康检查

```python
# 检查所有传输的健康状态
health = await transport.health_check_all()

print(f"Manager: {'✅' if health['manager'] else '❌'}")
print(f"Local Transport: {'✅' if health['local'] else '❌'}")

print("Remote Agents:")
for name, status in health['remote'].items():
    print(f"  {name}: {'✅' if status else '❌'}")
```

### 6. Agent 位置查询

```python
from app.a2a_protocol.transports.manager import AgentLocation

location = transport.get_agent_location("assistant")

if location == AgentLocation.LOCAL:
    print("Agent 在本地")
elif location == AgentLocation.REMOTE:
    print("Agent 在远程")
else:
    print("Agent 位置未知")
```

## RESTful API

### 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/a2a/v1/health` | 健康检查 |
| POST | `/a2a/v1/tasks/send` | 发送任务 |
| GET | `/a2a/v1/tasks/{task_id}` | 获取任务状态 |
| POST | `/a2a/v1/tasks/{task_id}/cancel` | 取消任务 |
| GET | `/a2a/v1/tasks/{task_id}/subscribe` | 订阅任务事件（SSE） |
| POST | `/a2a/v1/notifications` | 发送通知 |
| POST | `/a2a/v1/subscriptions` | 创建订阅 |
| DELETE | `/a2a/v1/subscriptions/{id}` | 删除订阅 |
| GET | `/a2a/v1/agents` | 列出所有 Agent |
| POST | `/a2a/v1/agents/register` | 注册 Agent |

### 请求示例

#### 发送任务
```bash
curl -X POST http://localhost:8000/a2a/v1/tasks/send \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant_123" \
  -d '{
    "message": {
      "content": "Hello",
      "metadata": {"agent_name": "assistant"}
    }
  }'
```

#### SSE 流式订阅
```bash
curl -N http://localhost:8000/a2a/v1/tasks/task_123/subscribe \
  -H "X-Tenant-ID: tenant_123"
```

## 多租户安全穿透

所有 API 都支持 `X-Tenant-ID` Header，用于：

1. **租户隔离**：确保租户只能访问自己的数据
2. **权限穿透**：JWT Token 中的 tenant_id 会自动传递
3. **审计日志**：记录每个租户的操作

```python
# 传输层自动处理租户穿透
result = await transport.send_message(
    to_agent="assistant",
    message={"content": "Hello"},
    tenant_id="tenant_123"  # 自动添加到 HTTP Header
)

# 在 HTTP 传输中会自动转换为：
# Headers: {"X-Tenant-ID": "tenant_123"}
```

## 性能对比

| 传输方式 | 延迟 | 吞吐 | 适用场景 |
|---------|------|------|---------|
| Local (message_bus) | < 1ms | 极高 | 同进程、本地部署 |
| HTTP | 10-50ms | 高 | 跨服务、云端部署 |

### 性能优化建议

1. **优先本地**：同节点的 Agent 使用本地传输
2. **批量消息**：多条消息批量发送减少网络开销
3. **连接池**：HTTP 传输使用连接池复用连接
4. **异步非阻塞**：所有 I/O 操作使用 async/await

## 错误处理

```python
from app.a2a_protocol import TransportError

try:
    result = await transport.send_message(
        to_agent="unknown_agent",
        message={"content": "test"}
    )
except TransportError as e:
    print(f"Error code: {e.code}")
    print(f"Error message: {e.message}")
    print(f"Error details: {e.details}")
except (OSError, IOError) as e:
    print(f"Network error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## 最佳实践

### 1. 使用单例模式

```python
# 推荐：使用全局单例
transport = await get_transport_manager()

# 不推荐：频繁创建新实例
transport = TransportManager()
```

### 2. 注册 Agent 时提供 URL

```python
# 推荐：注册时提供完整 URL
transport.register_remote_agent(
    "cloud_assistant",
    url="http://cloud-service:8000/a2a/v1"
)

# 不推荐：不提供 URL
transport.register_remote_agent("cloud_assistant", url=None)
```

### 3. 使用上下文管理器管理生命周期

```python
# 推荐：使用单例并确保关闭
manager = await get_transport_manager()
try:
    # 使用 manager
    pass
finally:
    await shutdown_transport_manager()
```

### 4. 监控健康状态

```python
# 定期检查健康状态
health = await transport.health_check_all()
if not health["manager"]:
    print("Transport Manager 不健康")
    print(f"Local: {health['local']}")
    print(f"Remote: {health['remote']}")
```

### 5. 使用广播功能

```python
# 系统更新时广播给所有 Agent
await transport.broadcast(
    message={
        "type": "config_update",
        "data": {"new_config": {...}}
    },
    tenant_id="system",
    exclude_agents=[]  # 可排除不需要接收的 Agent
)
```

### 6. 流式事件处理

```python
# 处理长时间运行的任务
async for event in transport.stream_task_events(
    to_agent="long_running_agent",
    task_id="task_123",
    tenant_id="tenant_123"
):
    event_type = event.get("type")
    
    if event_type == "progress":
        print(f"进度: {event['data']['progress']}%")
    elif event_type == "data":
        process_data(event['data'])
    elif event_type == "done":
        print("任务完成")
        break
```

## 故障排除

### 1. 消息发送失败

```python
# 检查 Agent 是否注册
stats = transport.get_statistics()
if "target_agent" not in stats["registry"]:
    print("Agent 未注册")

# 检查 Agent 位置
location = transport.get_agent_location("target_agent")
print(f"Agent 位置: {location}")
```

### 2. SSE 连接断开

```python
# 检查网络连接
import httpx
async with httpx.AsyncClient() as client:
    try:
        response = await client.get("http://target:8000/health")
        print("目标服务正常")
    except Exception as e:
        print(f"目标服务不可达: {e}")
```

### 3. 租户隔离失败

```python
# 检查 Header 是否传递
print(f"Request headers: {request.headers}")
# 确保 X-Tenant-ID 存在
```

### 4. 本地传输未初始化

```python
# 确保先初始化
if transport._local_transport is None:
    await transport.initialize(message_bus)
```

## 扩展开发

### 自定义传输

```python
from app.a2a_protocol.transports import AgentTransport, TransportConfig, TransportType

class CustomAgentTransport(AgentTransport):
    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._connection = None
    
    async def connect(self):
        # 实现连接逻辑
        self._connection = await self._create_connection()
    
    async def disconnect(self):
        # 实现断开逻辑
        if self._connection:
            await self._connection.close()
    
    async def send_message(self, to_agent, message, tenant_id=None):
        # 实现发送消息
        pass
    
    async def send_notification(self, to_agent, message, tenant_id=None):
        # 实现发送通知
        pass
    
    async def stream_events(self, task_id, tenant_id=None):
        # 实现流式事件
        yield {}
    
    async def subscribe(self, agent, event_types, callback, tenant_id=None):
        # 实现订阅
        pass
    
    async def health_check(self) -> bool:
        # 实现健康检查
        return True
```

## 总结

A2A 传输层提供：

- ✅ 统一抽象：无需关心底层实现
- ✅ 自动选择：本地 vs HTTP 自动选择
- ✅ 零代码复用：复用 message_bus
- ✅ 多租户支持：安全穿透
- ✅ 高性能：本地传输微秒级响应
- ✅ 流式事件：SSE 支持长时间任务
- ✅ 广播功能：向所有 Agent 广播消息
- ✅ 健康检查：实时监控状态
- ✅ 易扩展：支持自定义传输

