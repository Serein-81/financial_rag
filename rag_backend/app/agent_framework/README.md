# Agent Framework

后端自研 Agent 框架，负责把 LLM 适配器、工具系统、推理模式、结果合成和追踪能力组织成统一的业务智能体运行层。当前项目中，多智能体编排主要位于 `app/multi_agent_system/`，本目录提供可复用的基础 Agent、LLM adapter 和工具抽象。

## 当前定位

- `core/` 提供基础 Agent 运行模式，包括 `BaseAgent`、`ReActAgent`、`PlanAgent`、`ReflectAgent` 和兼容保留的 `OutputAgent`。
- `llm/` 提供统一 LLM adapter 接口和多供应商实现，包括智谱、OpenAI/GPT、Claude、Qwen、DeepSeek、MiniMax、百川、Xinference、HuggingFace、ModelScope 等。
- `tools/` 提供工具注册、调用、工具链、工具路由、LangChain 兼容层，以及财务、税务、法务、文档检索等业务工具。
- `components/` 提供 `ResultSynthesizer`，用于多来源结果合成。
- `routing/` 提供 LLM 驱动的工具路由能力。
- `tokens/` 提供 token 追踪和预算管理。

## 目录速览

```text
agent_framework/
  core/
    base_agent.py
    react_agent.py
    plan_agent.py
    reflect_agent.py
    output_agent.py
    agent_wrapper.py
  llm/
    base_adapter.py
    factory.py
    agent_adapter_factory.py
    agent_llm_config.py
    specialist_llm_router.py
    *_adapter.py
  tools/
    tool_manager.py
    base.py
    agent_tool_registry.py
    tool_chain.py
    tool_router.py
    hybrid_manager.py
    langchain_compat.py
    financial_data_tools.py
    financial_analysis_tools.py
    tax_compliance_tools.py
    legal_compliance_tools.py
    legal_enhanced_tools.py
    document_retrieval_tools.py
  components/
    result_synthesizer.py
  routing/
    llm_tool_router.py
  tokens/
    token_tracker.py
    budget_manager.py
```

## 主要导出

`app.agent_framework.__init__` 当前导出：

- `BaseAgent`
- `ReActAgent`
- `PlanAgent`
- `ReflectAgent`
- `ResultSynthesizer`
- `ReportAgent` / `ReportGenerator`
- `report_agent` / `report_generator`
- `ToolManager`
- `ZhipuAdapter`

`OutputAgent` 仍在 `core/output_agent.py` 中保留，但不再作为推荐入口；新的结果质量整合优先使用 `ResultSynthesizer` 和多智能体系统中的报告/审查组件。

## 基本用法

```python
from app.agent_framework import ReActAgent, ToolManager
from app.agent_framework.llm.factory import LLMAdapterFactory

llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
tool_manager = ToolManager()

agent = ReActAgent(
    llm_adapter=llm_adapter,
    tool_manager=tool_manager,
    agent_name="react"
)

result = await agent.run("请帮我分析这份企业所得税风险。")
```

## 工具系统

`ToolManager` 是大多数 Agent 的工具入口，支持注册普通函数、调用内置业务工具、记录工具执行信息，并与 `tool_call_tracer`、`agent_tracer` 等可观测能力协作。

```python
from app.agent_framework.tools.tool_manager import ToolManager

manager = ToolManager()

manager.register_function(
    name="echo",
    func=lambda text: {"text": text},
    description="返回输入文本"
)

result = await manager.call_tool("echo", text="hello")
```

复杂任务可以使用：

- `tool_chain.py`：按顺序或组合方式执行工具链。
- `tool_router.py` / `routing/llm_tool_router.py`：根据意图选择工具。
- `hybrid_manager.py`：兼容本地工具、LangChain 工具和混合执行。
- `langchain_compat.py`：把项目工具暴露成 LangChain 风格接口。

## LLM 适配器

LLM 通过统一 adapter 接口接入。业务代码应优先通过 `LLMAdapterFactory` 或 Agent 专用配置创建 adapter，而不是直接散落实例化供应商 SDK。

```python
from app.agent_framework.llm.factory import LLMAdapterFactory

adapter = LLMAdapterFactory.create_adapter("zhipu")
response = await adapter.generate("你好，介绍一下你的能力。")
```

配置来源主要在 `app/core/config.py` 和 `.env`，其中包含各供应商 API Key、模型名、超时和开关。

## 与多智能体系统的关系

本目录是“基础设施层”。面向业务的专家 Agent 和编排器在：

- `app/multi_agent_system/agents/`
- `app/multi_agent_system/orchestrator.py`
- `app/services/agent_service.py`
- `app/services/hybrid_agent_service.py`

财税法务问答、税务分析、政策通知和报告生成会组合使用本目录中的 `ReActAgent`、`ToolManager`、LLM adapter、业务工具和追踪组件。

## 可观测性

近期代码已加强 Agent/工具追踪链路，相关模块包括：

- `app/services/agent_tracer.py`
- `app/services/tool_call_tracer.py`
- `app/models/agent_trace.py`
- `app/models/tool_trace.py`
- `app/repositories/agent_trace.py`
- `app/repositories/tool_trace.py`
- `app/observability/`

API 层同时提供 `agent_trace` / `agent-trace`、`tool_trace` / `tool-trace` 的兼容路径。

## 测试建议

当前测试集中在 `rag_backend/tests/` 下，常用命令：

```bash
cd rag_backend
pytest tests/unit/test_trace_improvements.py
pytest tests/agent_system
```

如果修改 LLM adapter 或工具调用链，建议同步跑相关 `agent_system`、`integration` 或 `api` 测试。部分测试依赖数据库、Redis、外部模型或环境变量，需要按 `.env.example` 配置。

## 维护提示

- 新增 Agent 模式时，优先继承 `BaseAgent`，并保持 `run` / 流式接口行为一致。
- 新增 LLM 供应商时，继承 `BaseLLMAdapter`，再接入 `llm/factory.py`。
- 新增业务工具时，优先放入 `tools/` 或 `app/mcp/`，并通过 `ToolManager` 或统一 MCP 工具管理器暴露。
- 不建议在 Agent 中直接写数据库或网络访问逻辑；应封装成工具或 service，便于追踪、测试和权限控制。
