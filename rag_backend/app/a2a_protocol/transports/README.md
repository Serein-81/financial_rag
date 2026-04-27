# A2A Transport Layer

A2A transport 层为多智能体系统提供统一通信抽象，让同进程、本地 LangGraph 状态、HTTP 远程服务之间的 Agent 调用可以通过一致接口完成。它位于 `app/a2a_protocol/transports/`，上层由 A2A 协议、dispatcher、orchestrator node 和多智能体系统使用。

## 当前能力

- `LocalAgentTransport`：复用本地 message bus，同进程 Agent 间通信。
- `HttpAgentTransport`：通过 HTTP 调用远程 Agent 或远程 A2A 服务。
- `LangGraphTransport`：基于 LangGraph state / blackboard 的传输方式，用于图状态内的任务交接。
- `TransportManager`：注册本地/远程 Agent，统一发送消息、广播、订阅和健康检查。
- `TransportStrategyFactory`：根据场景创建 LOCAL、HTTP、GRAPH_STATE 等策略。

## 文件说明

```text
transports/
  base.py                # TransportConfig、TransportType、AgentTransport、TransportError
  strategy.py            # TransportMode、TransportStrategy、TransportEnvelope
  local_transport.py     # 本地 message_bus transport
  http_transport.py      # HTTP transport
  langgraph_transport.py # LangGraph state/blackboard transport
  manager.py             # TransportManager 单例和 agent registry
  factory.py             # 策略工厂、agent cards prompt helper、task bus context
```

## 主要导出

`app.a2a_protocol.transports.__init__` 当前导出：

- `TransportConfig`
- `TransportType`
- `AgentTransport`
- `TransportError`
- `TransportMode`
- `TransportStrategy`
- `TransportEnvelope`
- `LangGraphTransport`
- `StateBlackboard`
- `LocalAgentTransport`
- `HttpAgentTransport`
- `TransportManager`
- `get_transport_manager`
- `shutdown_transport_manager`
- `TransportStrategyFactory`
- `get_transport_factory`
- `create_default_strategy`
- `build_prompt_with_agent_cards`
- `A2ATaskBusContext`

## 基本用法

```python
from app.a2a_protocol.transports import get_transport_manager, shutdown_transport_manager

manager = await get_transport_manager()
await manager.initialize(message_bus)

manager.register_local_agent("tax_agent", tax_agent)
manager.register_remote_agent(
    "policy_agent",
    url="http://policy-service:8000/api/v1/a2a/v1"
)

result = await manager.send_message(
    to_agent="tax_agent",
    message={"content": "分析企业所得税风险"},
    tenant_id="tenant-001",
    wait_for_response=True,
)

await shutdown_transport_manager()
```

## 策略选择

`factory.py` 中提供策略工厂，适合在编排层按部署形态选择通信方式：

- `LOCAL`：同进程、低延迟，适合单体部署。
- `HTTP`：跨服务调用，适合拆分部署或云端 Agent。
- `GRAPH_STATE`：在 LangGraph 工作流中通过 state/blackboard 交接。

实际策略命名以 `TransportMode` 和 `TransportType` 枚举为准。

## API 路径

主应用注册了两套 A2A 路由：

```python
app.include_router(a2a_router, prefix="/api/v1", tags=["A2A Protocol"])
app.include_router(a2a_v1_router, prefix="/api/v1", tags=["A2A Protocol v1"])
```

因此 v1 接口通常位于：

```text
/api/v1/a2a/v1/...
```

旧版接口位于：

```text
/api/v1/a2a/...
```

具体端点以 `app/api/v1/endpoints/a2a_v1.py` 和 `app/api/v1/endpoints/a2a_protocol.py` 为准。

## 多租户与安全

调用 transport 时应显式传入 `tenant_id`。HTTP transport 会把租户上下文带到请求中，用于服务端权限校验、租户隔离和审计。不要在跨租户调用中复用无租户上下文的 manager 状态。

## 维护建议

- 新增 transport 时继承 `AgentTransport`，实现连接、断开、发送消息、通知、事件流和健康检查。
- 新增策略时优先扩展 `TransportStrategyFactory`，不要让上层业务直接判断底层协议细节。
- 长任务建议通过事件流或任务状态查询返回进度，不要阻塞 HTTP 请求。
- 跨服务调用必须处理超时、重试、认证、租户头和错误码。
- 调试通信问题时先查 `TransportManager` registry，再查目标 Agent location 和 health check。

## 简单排障

```python
stats = manager.get_statistics()
print(stats)

location = manager.get_agent_location("tax_agent")
print(location)

health = await manager.health_check_all()
print(health)
```

如果 HTTP 远程 Agent 不可用，优先确认目标 URL、鉴权头、`tenant_id` 传递和服务端 `/health` 状态。
