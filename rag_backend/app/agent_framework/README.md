# Agent Framework

后端自研 Agent 框架，负责把 LLM 适配器、工具系统、推理模式、结果合成和追踪能力组织成统一的业务智能体运行层。**不依赖 LangChain 核心**（仅提供可选兼容层）。当前项目中，多智能体编排主要位于 `app/multi_agent_system/`，本目录提供可复用的基础 Agent、LLM adapter 和工具抽象。

## 当前定位

- `core/` 提供基础 Agent 运行模式，包括 `BaseAgent`、`ReActAgent`、`PlanAgent`、`ReflectAgent`。
- `llm/` 提供统一 LLM adapter 接口和 12 家供应商实现（见下表）。
- `tools/` 提供工具注册、调用、工具链、工具路由、LangChain 兼容层，以及财务、税务、法务、文档检索等业务工具。
- `components/` 提供 `ResultSynthesizer`，用于多来源结果合成。
- `routing/` 提供 LLM 驱动的工具路由能力。
- `tokens/` 提供 token 追踪和预算管理。

## Agent 核心类（core/）

| 类 | 继承 | 默认迭代上限 | 主循环 |
|---|---|---|---|
| `BaseAgent` | ABC | `max_iterations=10` | 抽象 `run()` / `stream_run()`；提供 `call_tool()`、提示词加载（优先 `app/prompts/agents/{name}/system.md`）、技能注入 `inject_skill_context()` |
| `ReActAgent` | BaseAgent | 10 | 思考→行动→观察循环，文本协议解析工具调用；`stream_run()` 真流式输出 Final Answer |
| `PlanAgent` | BaseAgent | 10（`max_steps=10`） | `_make_plan()` → `_execute_plan()` → `_complete_task()` 三阶段，无迭代循环 |
| `ReflectAgent` | BaseAgent | 5（`max_reflections=2`） | 初始回答 → 反思-改进循环，遇 `需要改进: No` 提前退出 |

另有 `AgentWrapper` / `AgentResponseValidator`（`agent_wrapper.py`）作为容错包装层。

### ReActAgent 防失控机制（关键阈值）

| 机制 | 实现 | 阈值 |
|---|---|---|
| 语义循环检测 | `_check_loop_detection()`（EmbeddingService 余弦相似度，比较最近 3 轮） | 相似度阈值 0.8（构造参数） |
| 精确去重 | 同 action+input+thought 的 MD5 哈希比对 | 完全相同即重复 |
| 连续失败计数 | `_check_consecutive_failures()`（结果含"错误/失败/未找到"等） | `max_consecutive_failures=3` |
| 强制终止 | `_should_force_final_answer()` | 循环相似度 >0.95 / 连续失败 ≥3 / 达迭代上限，任一触发 |
| 答案去重 | `_is_answer_duplicate_with_streamed()` / `_remove_duplicate_full_text()` | 相似度 0.85 |
| 历史窗口 | `_update_history()` | 各保留最近 5 条 |
| 降级方案 | 嵌入失败时 `_calculate_similarity()` 用 Jaccard 3-gram 字符串相似度 | — |

> 说明：**原生 OpenAI Function Calling 的多轮工具循环**实现在编排层 `app/multi_agent_system/agents/base_specialist.py`（`max_tool_rounds=5`，`asyncio.gather` 并行执行 tool_calls）；本框架的 `ReActAgent` 走文本协议解析路径，两者并存、各有适用场景。

## 目录速览

```text
agent_framework/
  core/
    base_agent.py
    react_agent.py
    plan_agent.py
    reflect_agent.py
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

结果质量整合统一使用 `ResultSynthesizer` 和多智能体系统中的报告/审查组件；旧的 `OutputAgent` 兼容包装已移除。

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
- `tool_router.py` / `routing/llm_tool_router.py`：根据意图选择工具（LLM 选择失败时降级为六类关键词打分）。
- `hybrid_manager.py`：CHAIN（工具链）/ AGENT（ReAct）/ HYBRID（先链后 Agent）三种执行模式。
- `langchain_compat.py`：把项目工具暴露成 LangChain 风格接口。

关键机制：

- **自动注册**：`decorators.py` 的 `@auto_register_tool(name, description, category, timeout=30)` 自动提取函数签名生成 metadata；`scanner.py` 启动时递归扫描 `app/tools`、`app/skills` 等目录动态导入（跳过 `_` 前缀与 test 文件）。
- **解析兼容**：`ToolManager.parse_tool_call_from_text()` 支持 5 种文本格式（MCP JSON、Action/Action Input、内联函数调用、MiniMax XML、中文格式）。
- **失败熔断**：工具连续失败 3 次进入冷却期（默认 5 分钟），期间跳过调用。
- **MCP 工具注入**：`agent_tool_registry.initialize_tool_manager()` 统一注册 MCP 工具（`app/mcp/`，27 本地 + 10 云端）、9 个领域确定性计算工具与代码解释器。

## LLM 适配器

LLM 通过统一 adapter 接口接入。业务代码应优先通过 `LLMAdapterFactory` 或 Agent 专用配置创建 adapter，而不是直接散落实例化供应商 SDK。

### 支持的 12 家 Provider（`llm/factory.py`）

| provider 值 | 适配器 | 说明 |
|---|---|---|
| `deepseek` | `DeepSeekAdapter` | 直连或经 OpenRouter，**推荐** |
| `qwen` | `QwenAdapter` | 通义千问 |
| `zhipu` | `ZhipuAdapter` | 智谱 AI |
| `openai` | `OpenAIAdapter` | OpenAI |
| `claude` | `ClaudeAdapter` | Anthropic |
| `gpt` | `GPTAdapter` | OpenRouter 兼容端点 |
| `minimax` | `MiniMaxAdapter` | MiniMax |
| `baichuan` | `BaiChuanAdapter` | 百川 |
| `xinference` | `XinferenceAdapter` | 本地部署 |
| `huggingface` | `HuggingFaceAdapter` | HuggingFace |
| `modelscope` | `ModelScopeAdapter` | 魔搭 |
| `ollama` | 复用 `DeepSeekAdapter` | 本地 Ollama（OpenAI 兼容端点，保留 Function Calling） |

### 接口约定（`base_adapter.py`）

- 抽象方法：`generate(prompt, temperature=0.1, max_tokens=None)`、`stream_generate(...)`、`_chat(messages, ...)`
- 基类已实现：`chat(system, history, ...)`（内置最多 `LLM_MAX_RETRIES=5` 次重试）、`bind_tools(toolcall_session, tools)`
- `specialist_llm_router.py`：按 `AgentType`（CHAT/GREETING/FINANCE/TAX/LEGAL/…）路由到不同 provider，支持**租户级覆盖**（读取 `TenantSettings.extra_settings.llm_config`）
- `errors.py`：12 种 `LLMErrorCode` + 关键词分类器；`model_policies.py`：模型系列特殊策略（如 o1/o3 不支持自定义 temperature）；`notifications.py`：截断提示追加

```python
from app.agent_framework.llm.factory import LLMAdapterFactory

adapter = LLMAdapterFactory.create_adapter("deepseek")
response = await adapter.generate("你好，介绍一下你的能力。")
```

配置来源主要在 `app/core/config.py` 和 `.env`（`LLM_PROVIDER` / `LLM_PROVIDER_DEFAULT` / `LLM_PROVIDER_SPECIALIST` + 各家 API Key），也可经模型配置中心（DB 配置覆盖 `.env` 兜底）。

## Token 预算（tokens/）

- `TokenTracker`：基于 tiktoken（`cl100k_base`）精确计数；`count_messages_tokens()` 按 ChatML 每条 +4 token 开销；`truncate_to_tokens()` / `split_by_tokens()` 截断与分块；降级估算为中文字符/2 + 其他/4。
- `BudgetManager`：组件级预算分配。`BudgetConfig` 默认 `total_budget=128000`、系统提示 4000、响应预留 4000、警告阈值 0.8、临界阈值 0.95；支持 FIXED/DYNAMIC/PRIORITY/ADAPTIVE 四种策略与组件间预算转移。
- 多轮对话的**三级压缩**（去冗余 → JSON 摘要 → 滚动摘要）在 `app/services/context_optimizer.py`，与本目录的预算管理互补。

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
