# 自定义 Agent 框架

一个功能丰富、可扩展的 Agent 实现框架，支持多种推理模式、多智能体协作和专业智能体调度。

## 🎯 设计目标

- **多模式支持**: ReAct、Plan-and-Solve、Reflect、Output Review 等多种推理模式
- **多智能体协作**: Agent Orchestrator 协调多个专业智能体
- **多 LLM 支持**: 统一的适配器接口，支持 14+ 种大模型提供商
- **灵活工具系统**: 支持函数工具、工具链、混合执行
- **生产级质量**: 错误处理、令牌追踪、预算管理

## 📁 目录结构

```
agent_framework/
├── __init__.py                 # 框架入口，导出核心类和函数
├── core/                       # 核心 Agent 实现
│   ├── __init__.py
│   ├── base_agent.py          # Agent 抽象基类
│   ├── react_agent.py         # ReAct 模式实现
│   ├── reflect_agent.py       # Reflect 模式实现
│   ├── output_agent.py        # 输出质量审查智能体
│   ├── reviewed_agent.py      # 带审查的 ReAct Agent
│   ├── report_agent.py        # 报表生成专用智能体
│   ├── plan_agent.py          # 规划执行智能体
│   └── agent_orchestrator.py  # 多智能体调度器
├── llm/                        # LLM 适配器
│   ├── __init__.py
│   ├── base_adapter.py        # 适配器抽象基类
│   ├── factory.py             # 适配器工厂
│   ├── agent_adapter_factory.py  # Agent 专用适配器工厂
│   ├── agent_llm_config.py   # Agent LLM 配置
│   ├── specialist_llm_router.py   # 专家路由
│   ├── model_policies.py     # 模型策略管理
│   ├── token_utils.py        # Token 计算工具
│   ├── errors.py             # 错误定义和分类
│   ├── notifications.py      # 通知管理
│   ├── zhipu_adapter.py      # 智谱 AI 适配器
│   ├── openai_adapter.py     # OpenAI 适配器
│   ├── gpt_adapter.py        # GPT 适配器（别名）
│   ├── claude_adapter.py     # Anthropic Claude 适配器
│   ├── qwen_adapter.py       # 通义千问适配器
│   ├── deepseek_adapter.py    # DeepSeek 适配器
│   ├── minimax_adapter.py     # MiniMax 适配器
│   ├── baichuan_adapter.py   # 百川适配器
│   ├── xinference_adapter.py  # Xinference 适配器
│   ├── huggingface_adapter.py # HuggingFace 适配器
│   └── modelscope_adapter.py  # ModelScope 适配器
├── tools/                      # 工具系统
│   ├── __init__.py
│   ├── tool_manager.py        # 工具管理器
│   ├── agent_tool_registry.py # Agent 专用工具注册
│   ├── base.py               # 工具基类
│   ├── langchain_compat.py   # LangChain 兼容层
│   ├── tool_chain.py         # 工具链执行
│   ├── tool_router.py        # 工具路由
│   ├── hybrid_manager.py     # 混合工具管理器
│   └── financial_data_tools.py # 金融数据工具
├── routing/                    # 路由模块
│   ├── __init__.py
│   └── llm_tool_router.py     # LLM/工具路由
└── tokens/                     # Token 管理
    ├── __init__.py
    ├── token_tracker.py       # Token 追踪器
    └── budget_manager.py      # 预算管理器
```

## 🚀 快速开始

### 1. 基本使用

```python
from app.agent_framework import ReActAgent, ToolManager, create_llm_adapter

# 初始化组件
llm_adapter = create_llm_adapter()  # 使用配置的默认提供商
tool_manager = ToolManager()
agent = ReActAgent(llm_adapter, tool_manager)

# 执行对话
answer = await agent.run("你好，今天天气怎么样？")
print(answer)
```

### 2. 使用 Agent Orchestrator（推荐）

```python
from app.agent_framework import orchestrator, TaskType

# 注册所有智能体
orchestrator.register_all_agents()

# 自动选择合适的智能体
result = await orchestrator.execute("帮我生成一份销售报表")

# 流式输出
async for chunk in orchestrator.execute_stream("分析这个月的财务数据"):
    print(chunk, end="", flush=True)
```

### 3. 注册工具

```python
# 注册普通函数
tool_manager.register_function(
    name="get_weather",
    func=get_weather,
    description="查询城市天气"
)

# 注册工具链
from app.agent_framework.tools import ToolChain, ChainStep, ChainStepType

chain = ToolChain(name="data_pipeline")
chain.add_step(ChainStep(
    name="fetch",
    tool_name="fetch_data",
    step_type=ChainStepType.SEQUENTIAL
))
chain.add_step(ChainStep(
    name="process",
    tool_name="process_data",
    step_type=ChainStepType.SEQUENTIAL
))
```

### 4. 多 LLM 支持

```python
from app.agent_framework import (
    create_llm_adapter,
    get_supported_providers,
    get_current_provider
)

# 获取支持的提供商
providers = get_supported_providers()
print(f"支持的提供商: {providers}")

# 创建特定提供商的适配器
zhipu = create_llm_adapter(provider="zhipu")
claude = create_llm_adapter(provider="claude")
qwen = create_llm_adapter(provider="qwen")
```

## 🧠 Agent 类型

### 1. ReAct Agent

**核心思想**: 思考-行动-观察的循环

```python
from app.agent_framework import ReActAgent

agent = ReActAgent(
    llm_adapter=llm_adapter,
    tool_manager=tool_manager,
    max_iterations=10,
    timeout=300.0
)
```

### 2. Output Agent（输出审查）

**核心思想**: 对输出进行质量审查和改进

```python
from app.agent_framework import OutputAgent, output_agent

# 独立使用
output_agent_instance = OutputAgent(llm_adapter)
result = await output_agent_instance.review_output(
    original_output="生成的报表内容",
    context="用户请求生成销售报表"
)

# 或使用便捷函数
reviewed = await output_agent.review_and_improve(
    content="待审查内容",
    task_type="report"
)
```

### 3. Reviewed Agent（带审查的 ReAct）

**核心思想**: ReAct 执行后自动进行输出审查

```python
from app.agent_framework import create_reviewed_agent

agent = create_reviewed_agent(
    llm_adapter=llm_adapter,
    tool_manager=tool_manager,
    review_threshold=0.7  # 质量阈值
)
result = await agent.run("复杂的多步骤任务")
```

### 4. Report Agent（报表生成）

**核心思想**: 专门优化报表生成的智能体

```python
from app.agent_framework import ReportAgent, report_agent

# 独立使用
report_agent_instance = ReportAgent(llm_adapter)
result = await report_agent_instance.generate_report(
    report_type="sales",
    time_range="2024-Q1",
    data={"sales_data": [...]}
)

# 或使用便捷函数
report = await report_agent.generate(
    type="financial",
    period="monthly",
    include_charts=True
)
```

### 5. Agent Orchestrator（多智能体调度）

**核心思想**: 自动选择和协调多个专业智能体

```python
from app.agent_framework import AgentOrchestrator, TaskType, TaskContext

orchestrator = AgentOrchestrator()

# 注册所有内置智能体
orchestrator.register_all_agents()

# 自动识别任务类型并选择合适的智能体
context = TaskContext(
    user_input="帮我生成一份销售报表并分析趋势",
    requires_report=True,
    requires_data=True
)

result = await orchestrator.execute_task(context)
```

## 🤖 LLM 适配器

### 支持的提供商

| 提供商 | 适配器类 | 状态 | 备注 |
|--------|----------|------|------|
| 智谱 AI | `ZhipuAdapter` | ✅ 已实现 | 默认 |
| OpenAI | `OpenAIAdapter` | ✅ 已实现 | |
| GPT | `GPTAdapter` | ✅ 已实现 | OpenAI 别名 |
| Claude | `ClaudeAdapter` | ✅ 已实现 | Anthropic |
| 通义千问 | `QwenAdapter` | ✅ 已实现 | 阿里云 |
| DeepSeek | `DeepSeekAdapter` | ✅ 已实现 | |
| MiniMax | `MiniMaxAdapter` | ✅ 已实现 | |
| 百川 | `BaiChuanAdapter` | ✅ 已实现 | |
| Xinference | `XinferenceAdapter` | ✅ 已实现 | 本地部署 |
| HuggingFace | `HuggingFaceAdapter` | ✅ 已实现 | |
| ModelScope | `ModelScopeAdapter` | ✅ 已实现 | 魔搭 |

### 使用示例

```python
# 工厂模式创建适配器
adapter = create_llm_adapter(
    provider="zhipu",
    model_name="glm-4-flash",
    temperature=0.7
)

# 非流式生成
response = await adapter.generate("你好")

# 流式生成
async for chunk in adapter.stream_generate("请介绍一下人工智能"):
    print(chunk, end="")
```

## 🛠️ 工具系统

### ToolManager（工具管理器）

```python
from app.agent_framework import ToolManager

manager = ToolManager()

# 注册函数工具
manager.register_function(
    name="calculator",
    func=lambda expr: eval(expr),
    description="执行数学计算"
)

# 调用工具
result = await manager.call_tool("calculator", expression="2+3")

# 获取工具描述（用于 LLM）
tools_description = manager.get_tools_description()
```

### HybridToolManager（混合管理器）

```python
from app.agent_framework.tools import HybridToolManager, ExecutionMode

hybrid = HybridToolManager()

# 并行执行多个工具
results = await hybrid.execute_parallel(
    tools=["fetch_data", "fetch_weather", "fetch_news"],
    params=[{}, {"city": "北京"}, {}]
)

# 顺序执行工具链
result = await hybrid.execute_chain(
    tools=["validate", "transform", "load"],
    initial_data=data
)
```

### ToolChain（工具链）

```python
from app.agent_framework.tools import ToolChain, ChainStep, ChainStepType

chain = ToolChain(name="data_processing")
chain.add_step(ChainStep(
    name="fetch",
    tool_name="fetch_data",
    params={"source": "database"},
    step_type=ChainStepType.SEQUENTIAL
))
chain.add_step(ChainStep(
    name="transform",
    tool_name="transform_data",
    step_type=ChainStepType.SEQUENTIAL
))

result = await chain.execute(input_data)
```

## 📊 令牌管理

### Token Tracker

```python
from app.agent_framework.tokens import TokenTracker

tracker = TokenTracker()

# 追踪使用量
tracker.track(
    model="glm-4",
    prompt_tokens=100,
    completion_tokens=200
)

# 获取统计
stats = tracker.get_stats()
print(f"总 Token: {stats['total_tokens']}")
```

### Budget Manager

```python
from app.agent_framework.tokens import BudgetManager

budget = BudgetManager(monthly_limit=10000)

# 检查预算
can_proceed = budget.check_budget(
    tenant_id="tenant_123",
    estimated_tokens=500
)

if can_proceed:
    # 执行操作
    pass
else:
    # 超出预算
    print("月度预算已用完")
```

## 🛣️ 发展路线

### 已完成 ✅

- [x] BaseAgent 抽象基类
- [x] ReActAgent 实现
- [x] Reflect Agent
- [x] Output Agent（输出审查）
- [x] Reviewed Agent（带审查的 ReAct）
- [x] Report Agent（报表生成）
- [x] Agent Orchestrator（多智能体调度）
- [x] ToolManager 工具管理器
- [x] ToolChain 工具链
- [x] HybridToolManager 混合管理器
- [x] LangChain 兼容层
- [x] LLM 适配器工厂
- [x] 多 LLM 适配器（14+ 个）
- [x] Token 追踪器
- [x] 预算管理器
- [x] 错误处理和分类
- [x] 模型策略管理

### 进行中 🚧

- [ ] Plan Agent（更完善的规划）
- [ ] 负载均衡优化
- [ ] 性能监控增强

### 计划中 📋

- [ ] 更多 LLM 适配器
- [ ] 工具调用并发优化
- [ ] 分布式智能体支持
- [ ] 更丰富的监控面板

## 🔄 与 LangChain 对比

| 特性 | 自定义框架 | LangChain |
|------|-----------|-----------|
| 代码复杂度 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 复杂 |
| 学习价值 | ⭐⭐⭐⭐⭐ 很高 | ⭐⭐ 一般 |
| 可控性 | ⭐⭐⭐⭐⭐ 完全可控 | ⭐⭐ 黑盒较多 |
| 功能完整性 | ⭐⭐⭐⭐⭐ 丰富 | ⭐⭐⭐⭐⭐ 功能丰富 |
| 多智能体 | ⭐⭐⭐⭐⭐ 原生支持 | ⭐⭐⭐ 需要扩展 |
| 多 LLM 支持 | ⭐⭐⭐⭐⭐ 14+ 提供商 | ⭐⭐⭐⭐ 较多 |
| 性能 | ⭐⭐⭐⭐ 轻量高效 | ⭐⭐⭐ 较重 |
| 生产就绪 | ⭐⭐⭐⭐⭐ 是 | ⭐⭐⭐⭐ 是 |

## 🧪 测试

```bash
cd rag_backend
python test_custom_agent.py
```

测试内容：
- 基本功能初始化
- 简单问答（不需要工具）
- 工具调用（天气查询等）
- 流式输出
- 工具管理器功能
- 多智能体协作
- 输出审查功能
- 报表生成

## 📄 许可证

MIT License - 详见 LICENSE 文件

## 🙋‍♂️ 常见问题

### Q: 为什么要自己实现 Agent 框架？
A: 为了深入理解 Agent 的工作原理，提高代码的可控性，减少对外部框架的依赖，并且针对业务场景（金融数据、多智能体）进行深度优化。

### Q: 支持哪些大模型？
A: 目前支持 14+ 种主流大模型提供商，包括智谱 AI、OpenAI、Claude、通义千问、DeepSeek、MiniMax、百川等。

### Q: 如何选择使用哪个 LLM？
A: 使用 `create_llm_adapter(provider="provider_name")` 工厂函数，可以轻松切换不同的提供商。

### Q: 如何添加新的 Agent 模式？
A: 继承 `BaseAgent` 类，实现 `run` 和 `stream_run` 方法即可。

### Q: 如何添加新的 LLM 适配器？
A: 继承 `BaseLLMAdapter` 类，实现 `generate` 和 `stream_generate` 方法，然后在 `factory.py` 中注册。

### Q: Agent Orchestrator 如何工作？
A: 它会自动分析用户输入，识别任务类型（如报表、数据查询、对话等），然后选择最合适的专业智能体处理，并支持多智能体协作。

### Q: 如何调试 Agent 执行过程？
A: 查看 `agent.execution_log` 获取详细的执行日志，或使用 `get_execution_summary()` 获取摘要。
