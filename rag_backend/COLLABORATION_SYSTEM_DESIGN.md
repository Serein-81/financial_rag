# 多智能体协作系统设计

## 概述

本项目实现了一个基于认知科学的智能审计系统，采用多智能体协作架构，整合了财税法务领域的专业知识和智能决策能力。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           多智能体协作系统架构                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────────┐                                                         │
│    │   用户请求    │                                                         │
│    └──────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│    ┌──────────────┐                                                         │
│    │  前台 Agent   │ ← IntentAgent                                          │
│    │ (接待/分流)   │   - 用户意图识别                                        │
│    └──────┬───────┘   - 复杂度评估                                          │
│           │         - 路由策略选择                                          │
│           ▼                                                                 │
│    ┌──────────────┐                                                         │
│    │   协调器     │ ← AgentCoordinator                                       │
│    │ (任务编排)   │   - 任务分解                                            │
│    └──────┬───────┘   - Agent 协调                                          │
│           │         - 结果整合                                              │
│     ┌─────┴─────┐                                                           │
│     │           │                                                           │
│     ▼           ▼                                                           │
│  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐                                │
│  │ 税务 │   │ 财务 │   │ 法律 │   │ 报告 │                                │
│  │专家  │   │专家  │   │专家  │   │生成器 │                                │
│  └──────┘   └──────┘   └──────┘   └──────┘                                │
│     │           │           │           │                                  │
│     └───────────┴─────┬─────┴───────────┘                                  │
│                       │                                                    │
│                       ▼                                                    │
│    ┌──────────────────────────────────────────┐                             │
│    │              冲突检测 & 合并              │                             │
│    │           ConflictDetector              │                             │
│    │           ResultMerger                 │                             │
│    └──────────────────────────────────────────┘                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 前台 Agent (ReceptionistAgent)

负责用户交互的第一层处理：

```python
from app.multi_agent_system import ReceptionistAgent

agent = ReceptionistAgent(llm=llm)
result = await agent.process("分析某公司的税务风险")
```

**职责**：
- 用户接待和信息收集
- 意图初步识别
- 复杂度评估
- 路由决策

### 2. 意图 Agent (IntentAgent)

智能路由的核心组件：

```python
from app.multi_agent_system import IntentAgent, IntentCategory, ComplexityLevel

intent_agent = IntentAgent(llm=llm)
analysis = await intent_agent.analyze_intent(user_query)

# 分析结果
print(analysis.category)  # IntentCategory.TAX | LEGAL | FINANCE | COMPREHENSIVE
print(analysis.complexity)  # ComplexityLevel.SIMPLE | MODERATE | COMPLEX
print(analysis.routing_strategy)  # RoutingStrategy.SINGLE | SEQUENTIAL | PARALLEL
```

### 3. 税务专家 Agent (TaxSpecialist)

处理税务相关分析：

```python
from app.multi_agent_system import TaxSpecialist

tax_agent = TaxSpecialist(llm=llm, mcp_factory=mcp_factory)
result = await tax_agent.analyze_tax_risk(document, context)
```

### 4. 法律专家 Agent (LegalSpecialist)

处理法律合规分析：

```python
from app.multi_agent_system import LegalSpecialist

legal_agent = LegalSpecialist(llm=llm, mcp_factory=mcp_factory)
result = await legal_agent.analyze_compliance(document, context)
```

### 5. 财务专家 Agent (FinanceSpecialist)

处理财务数据分析：

```python
from app.multi_agent_system import FinanceSpecialist

finance_agent = FinanceSpecialist(llm=llm, mcp_factory=mcp_factory)
result = await finance_agent.analyze_financial(document, context)
```

### 6. 协调器 (AgentCoordinator)

管理多 Agent 协作的核心：

```python
from app.multi_agent_system import AgentCoordinator

coordinator = AgentCoordinator(
    llm=llm,
    mcp_factory=mcp_factory,
    enable_conflict_detection=True
)

result = await coordinator.process(request)
```

### 7. 任务分解器 (TaskDecomposer)

将复杂任务分解为可执行的子任务：

```python
from app.multi_agent_system import TaskDecomposer, DocumentType, AuditPriority

decomposer = TaskDecomposer(llm=llm)
tasks = await decomposer.decompose(
    task="全面审计某公司2023年度财税情况",
    document_type=DocumentType.MIXED,
    priority=AuditPriority.HIGH
)
```

## Agent 间通信

### 消息总线 (MessageBus)

```python
from app.multi_agent_system import MessageBus, MessageType, AgentMessage

# 创建消息总线
bus = MessageBus()

# 发布消息
await bus.publish(AgentMessage(
    type=MessageType.TASK_REQUEST,
    sender="coordinator",
    receiver="tax_specialist",
    content={"task_id": "xxx", "data": "..."}
))

# 订阅消息
async for message in bus.subscribe(agent_id="tax_specialist"):
    print(f"收到消息: {message.content}")
```

## 协作流程

### 标准流程

```
1. 请求进入 → ReceptionistAgent 接待
2. 意图分析 → IntentAgent 识别意图和复杂度
3. 任务分解 → TaskDecomposer 分解任务
4. Agent 执行 → 税务/法律/财务 Agent 并行/串行执行
5. 结果合并 → ResultMerger 整合结果
6. 冲突检测 → ConflictDetector 检测并解决冲突
7. 报告生成 → ReportGenerator 生成最终报告
```

### 路由策略

| 策略 | 适用场景 | 执行方式 |
|------|---------|---------|
| SINGLE | 单一领域简单问题 | 单个 Agent 执行 |
| SEQUENTIAL | 跨领域顺序问题 | 按顺序调用多个 Agent |
| PARALLEL | 独立多领域问题 | 并行调用多个 Agent |
| HYBRID | 复杂综合问题 | 组合多种策略 |

## 状态管理

```python
from app.multi_agent_system import AuditState, create_initial_state

state = create_initial_state(
    request_id="req_001",
    user_id="user_001",
    audit_type=AuditType.COMPREHENSIVE
)

# 状态流转
state = await agent.process(state)
```

## 冲突检测与解决

```python
from app.multi_agent_system import ConflictDetector, Conflict

detector = ConflictDetector(llm=llm)
conflicts = await detector.detect_conflicts(results)

for conflict in conflicts:
    print(f"冲突类型: {conflict.conflict_type}")
    print(f"冲突描述: {conflict.description}")
    print(f"解决建议: {conflict.resolution_suggestion}")
```

## 配置参数

### 环境变量

```bash
# Agent 配置
MAX_PARALLEL_AGENTS=3
AGENT_TIMEOUT=30
ENABLE_CONFLICT_DETECTION=True

# MCP 配置
MCP_MODE=cloud
MCP_SERVER_URL=http://your-cloud-server:8080
```

### Agent 配置文件

```python
# app/multi_agent_system/tax_rules_config.py
TAX_RULES_CONFIG = {
    "risk_thresholds": {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    },
    "expertise_areas": [
        "企业所得税",
        "增值税",
        "个人所得税",
        "国际税收"
    ]
}
```

## 扩展开发

### 添加新的专家 Agent

1. 继承 `BaseSpecialistAgent`：

```python
from app.multi_agent_system import BaseSpecialistAgent

class CustomSpecialist(BaseSpecialistAgent):
    async def _analyze_impl(self, task: str, context: dict) -> dict:
        # 实现自定义分析逻辑
        return {"result": "..."}
```

2. 注册到协调器：

```python
coordinator.register_agent("custom", CustomSpecialist(llm=llm))
```

### 添加新的工具

```python
from app.multi_agent_system.tools import BaseTool

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "自定义工具"

    async def execute(self, params: dict) -> dict:
        return {"result": "..."}
```

## 性能优化

### 并行执行

```python
# 启用并行执行
result = await coordinator.process(
    request,
    parallel_execution=True,
    max_parallel=3
)
```

### 缓存策略

```python
# 启用结果缓存
coordinator = AgentCoordinator(
    llm=llm,
    cache_enabled=True,
    cache_ttl=3600
)
```

## 测试

```bash
# 运行多智能体系统测试
pytest tests/test_multi_agent_system/ -v

# 运行特定 Agent 测试
pytest tests/test_multi_agent_system/test_tax_specialist.py -v
```

## 常见问题

### Q: 如何调试 Agent 协作流程？

启用详细日志：

```python
import logging
logging.getLogger("multi_agent_system").setLevel(logging.DEBUG)
```

### Q: 如何添加新的意图分类？

修改 `IntentCategory` 枚举和 `IntentAgent._classify_intent` 方法。

### Q: MCP 服务不可用时如何处理？

系统会自动降级到本地模式或跳过 MCP 调用，具体见 `MCP_ARCHITECTURE_DESIGN.md`。

## 相关文档

- [MCP 架构设计](./MCP_ARCHITECTURE_DESIGN.md)
- [人类记忆系统设计](./rag_backend/app/memory_system/HUMAN_MEMORY_SYSTEM.md)
- [知识图谱使用指南](./知识图谱使用指南.md)
