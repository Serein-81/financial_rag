# LangSmith 集成指南

## 概述

本项目已实现 AgentTracer 与 LangSmith 的双写集成，既保留了本地数据库追踪（业务必需），又添加了 LangSmith 追踪（LLM 调试）。

## 架构设计

### 双写模式

```
Agent 执行 → AgentTracer
              ├── 本地数据库（agent_traces 表）
              │   └── 业务必需：会话管理、审计、查询
              └── LangSmith（可选）
                  └── LLM 调试：性能分析、Prompt 优化
```

### 核心组件

1. **AgentTracer** (`app/services/agent_tracer.py`)
   - 本地追踪服务
   - 自动检测并集成 LangSmith
   - 双写能力

2. **LangSmithTracer** (`app/langsmith_integration.py`)
   - LangSmith 客户端封装
   - 支持 Agent、LLM、Tool 三种追踪
   - 上下文管理器支持

## 配置方法

### 1. 环境变量配置

在 `.env` 文件中添加：

```bash
# LangSmith 追踪配置
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=financial_rag
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

**提示**：可以参考 `.env.example` 文件。

### 2. 前端配置

在前端 `.env` 文件中添加：

```bash
VITE_LANGSMITH_PROJECT=financial_rag
```

## 使用方法

### 方式一：自动追踪（推荐）

现有的 Agent 代码已经集成了自动追踪，无需额外修改：

```python
from app.services.agent_tracer import agent_tracer

# Agent 执行时自动追踪
result = await agent_tracer.start_trace(
    agent_type="ReAct",
    user_query="用户查询内容",
    session_id="session-id"  # 可选
)

# 添加步骤
await agent_tracer.add_step(
    trace_id=result,
    step_number=1,
    step_type="thought",
    content="思考内容"
)

# 结束追踪
await agent_tracer.end_trace(
    trace_id=result,
    final_answer="最终答案",
    success=True
)
```

### 方式二：手动追踪

如果需要追踪特定的 LLM 调用或工具调用：

```python
from app.langsmith_integration import get_tracer

tracer = get_tracer()

# 追踪 LLM 调用
tracer.trace_llm_call(
    model_name="MiniMax",
    prompt="用户问题",
    response="模型回答",
    token_usage={"prompt": 100, "completion": 50, "total": 150}
)

# 追踪工具调用
tracer.trace_tool_call(
    tool_name="search_kb",
    arguments={"query": "人工智能"},
    result="搜索结果"
)
```

### 方式三：Agent Run 追踪

使用上下文管理器追踪完整的 Agent 执行：

```python
from app.langsmith_integration import get_tracer

tracer = get_tracer()

with tracer.trace_agent_run(
    agent_name="FinanceSpecialist",
    agent_type="specialist",
    user_query="用户查询",
    session_id="session-id"
) as run_id:
    # Agent 执行逻辑
    pass
    # 添加步骤
    tracer.add_agent_step(
        parent_run_id=run_id,
        step_type="thought",
        content="思考内容"
    )
```

## 测试验证

运行集成测试：

```bash
cd rag_backend
python test_langsmith_integration.py
```

测试结果应显示：

```
✅ 本地数据库写入: 正常工作
✅ LangSmith 写入: 启用/未启用（取决于环境变量配置）
```

## 查看追踪数据

### 本地数据库

访问 Agent 追踪页面：`/agent-trace`

- 查看追踪列表
- 查看追踪详情
- 流程可视化

### LangSmith

点击页面右上角的 **LangSmith** 按钮，跳转到 LangSmith 官网查看：

- Agent 执行链路
- LLM 调用详情
- Token 使用量
- 执行时间统计
- Prompt 模板

## 功能对比

| 功能 | 本地追踪 | LangSmith |
|------|---------|-----------|
| 会话管理 | ✅ | ❌ |
| 审计日志 | ✅ | ❌ |
| 业务查询 | ✅ | ❌ |
| LLM 调试 | ❌ | ✅ |
| Prompt 优化 | ❌ | ✅ |
| 性能分析 | ❌ | ✅ |
| 团队协作 | ❌ | ✅ |

## 常见问题

### Q1: LangSmith 未启用，但追踪正常？

这是正常现象。AgentTracer 默认只写入本地数据库，只有配置了环境变量后才会同时写入 LangSmith。

### Q2: 如何临时禁用 LangSmith？

设置环境变量：

```bash
LANGSMITH_TRACING=false
```

### Q3: LangSmith 追踪失败会影响业务吗？

不会。AgentTracer 实现了容错机制，LangSmith 写入失败只会记录警告日志，不影响本地数据库写入和 Agent 正常执行。

### Q4: 如何查看 LangSmith 配置状态？

```python
from app.langsmith_integration import get_langsmith_config

config = get_langsmith_config()
print(config)
```

输出示例：

```python
{
    "api_key": "lsv2_pt_xxxx",  # 已隐藏
    "project": "financial_rag",
    "endpoint": "https://api.smith.langchain.com",
    "tracing": True,
    "enabled": True
}
```

## 性能考虑

- LangSmith 写入是异步的，不阻塞 Agent 执行
- 本地数据库使用异步 SQLAlchemy
- 建议在高并发场景下监控 LangSmith API 限流

## 后续优化

计划中的优化方向：

1. 支持更细粒度的追踪开关
2. 添加追踪数据的压缩和批量上传
3. 支持自定义 metadata 和 tags
4. 集成 LangSmith 的评估功能
5. 添加缓存机制减少 API 调用

## 参考资料

- [LangSmith 官方文档](https://docs.smith.langchain.com/)
- [LangSmith Python SDK](https://python.langchain.com/docs/langsmith)
- 项目内部文档：`docs/业务集成方案_智能体深度应用.md`
