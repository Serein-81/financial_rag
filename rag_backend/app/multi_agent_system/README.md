# Multi-Agent System（专家执行层）

面向财税法务业务的专家 Agent 与编排组件。LangGraph（`app/langgraph/`）负责宏观调度，本模块负责**微观执行**：意图识别、专家推理、原生 Function Calling 工具循环、审计协调与报告生成。

## 目录速览

```text
multi_agent_system/
  orchestrator.py              # 编排器（对话主路径之一）
  coordinator.py               # AgentCoordinator：审计(audit)编排器（不走 LangGraph）
  agent_capability_registry.py # 能力注册表（读取 config/agent_capabilities.yaml）
  evidence_validator.py        # 审计证据校验
  report_templates.py          # 审计报告模板
  message_bus.py               # 进程内 Pub/Sub
  agents/
    intent_router_agent.py     # 意图路由（三级降级）
    base_specialist.py         # 专家基类：原生 Function Calling 多轮工具循环
    finance_specialist.py      # 财务专家（含 ContextOptimizer 三级压缩）
    tax_specialist.py          # 税务专家
    legal_specialist.py        # 法务专家
    orchestrator_agent.py      # 编排 Agent
  routing/
    unified_router.py          # 统一路由纯函数（同时供 LangGraph 条件边使用）
  config/
    agent_capabilities.yaml    # 4 类 Agent 能力与关键词定义
  pipeline/                    # 审计报告流水线组件
```

## 意图路由：三级降级（intent_router_agent.py）

```
Level 0  正则速通      _is_simple_greeting()：问候/感谢/帮助/配置查询/技能查询，命中直接返回
Level 1  规则分类      _classify_intent_rule_based()：多词组合(置信度0.9) → 单关键词(0.8)
                      规则置信度 ≥ 0.9 → 跳过 LLM
Level 2  LLM 分类     _classify_intent_llm()：
                      · LLM 返回通用意图且规则置信度 ≥0.8 → 回退规则结果
                      · LLM 置信度 ≤ confidence_threshold(默认0.7) 且低于规则 → 回退规则结果
```

下游路由阈值：意图置信度 <0.5 转人工审核（`unified_router`）；能力匹配 `min_confidence` 默认 0.5~0.6。

## 专家工具循环：原生 Function Calling（base_specialist.py）

这是项目中"告别正则解析"的核心实现：

- 通过 OpenAI 兼容 `tools` 参数传入工具定义，LLM 返回结构化 `tool_calls`；
- `max_tool_rounds=5`：`for _round in range(max_tool_rounds + 1)`，最后一轮不再携带 tools 强制收敛；
- 单轮多个 `tool_calls` 经 `asyncio.gather` **并行执行**；
- `finish_reason == "stop"` 或无 tool_calls 时结束循环；
- `FinanceSpecialist` 在每次 chat 前调用 `ContextOptimizer`（`app/services/context_optimizer.py`）做三级压缩，防止多轮工具结果撑爆上下文。

## 能力注册表（config/agent_capabilities.yaml）

| agent_type | agent_id | 领域数 | 说明 |
|---|---|---|---|
| finance | finance_specialist_001 | 8 | 财务/投资/融资/报表/现金流等高权重关键词 |
| tax | tax_specialist_001 | 6 | 税务/申报/抵扣/发票/退税等 |
| legal | legal_specialist_001 | 5 | 法律/合同/条款/合规/诉讼等 |
| general | general_assistant_001 | 1 | 兜底，priority=10（最低） |

路由配置：`default_confidence_threshold: 0.5`，`max_specialists_per_request: 3`。

## 审计编排器（coordinator.py）

`AgentCoordinator.audit()` 是 `/api/v1/audit` 的核心：**手动调度**（不依赖 LangGraph StateGraph）finance/tax/legal 专家对上传材料并行审查，`ReworkController(max_rework_count=2)` 控制返工，下游经 `evidence_validator` 校验证据、`report_templates` + `pipeline/` 生成结构化审计报告。

## 与相邻模块的关系

- `routing/unified_router.py` 的 `route_by_intent_result` / `route_by_blackboard_state` 被 `app/langgraph/conditional.py` 直接 import 作为条件边。
- 专家 Agent 的 LLM 由 `agent_framework/llm/specialist_llm_router.py` 按 AgentType 分发（支持租户级模型覆盖）。
- 工具来自 `app/mcp/`（27 本地 + 10 云端）与 `app/tools/`（6 个知识库检索工具）。
- 被 `endpoints/chat.py`、`multi_agent.py`、`audit.py` 调用。
