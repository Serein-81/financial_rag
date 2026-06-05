# LangGraph 编排层

基于 **LangGraph StateGraph** 的多智能体编排工作流，负责宏观调度：意图路由、检索质量闭环（CRAG）、单/多专家分发、结果聚合、忠实度校验与反思重试。微观执行（Function Calling 工具循环）由 `app/multi_agent_system/agents/` 承担。

## 目录速览

```text
langgraph/
  graph.py                 # MultiAgentWorkflowBuilder：节点/边装配与编译
  state.py                 # AgentState（Pydantic 模型，含累加通道）
  nodes.py                 # 各节点函数工厂
  conditional.py           # 条件边路由函数（委托 multi_agent_system/routing/unified_router）
  agentic_rag_nodes.py     # Agentic RAG 规划-检索-评估节点
  agentic_rag_state.py     # Agentic RAG 状态定义
  postgres_saver.py        # 自定义 Postgres 业务快照（非 LangGraph 原生接口）
  persistences.py          # Redis/Postgres/Memory 自定义 checkpointer（未被 compile 使用）
  monitoring.py            # LangSmithMonitor（需 LANGCHAIN_API_KEY，否则静默禁用）
  tax_workflow/            # 税务申报子工作流（独立 StateGraph）
```

## 主工作流拓扑

```
START → receptionist → intent
   ├─ trivial ──────────────────────────→ direct_answer → END
   ├─ human_review（置信度 <0.5）→ END（interrupt）
   ▼
rag_retrieval → retrieval_grader ──score<0.6 且 iterations<2──→ query_rewriter ─┐
   ▲                                                                            │
   └────────────────────────────────────────────────────────────────────────────┘
   │ proceed
   ▼
single_specialist_router ──────→ finance/tax/legal/report_specialist ─┐
multi_specialist_router（并行 Send 分发多专家）──────────────────────────┤
   ▼                                                                  │
aggregator ←──────────────────────────────────────────────────────────┘
   ▼
faithfulness_checker ──score<0.7 且 regen<1──→ regenerate_aggregator → aggregator
   │ proceed
   ▼
reflection（enable_reflection 可关）
   ├─ EXCELLENT/GOOD（≥0.8）→ final_answer → END
   ├─ ACCEPTABLE → final_answer_with_suggestions → END
   ├─ POOR 且 retry_count<3 → retry → single_specialist_router（重做）
   └─ 重试超限 / needs_human → human_review → END（interrupt_before 拦截）
```

## AgentState 关键字段（state.py）

| 分组 | 字段（默认值） |
|---|---|
| 累加通道 | `rag_context`、`specialist_results`、`messages`、`activated_skills`（`Annotated[..., operator.add]`） |
| 意图路由 | `intent`、`intent_confidence`、`routing_strategy`、`target_specialists`、`complexity` |
| CRAG 闭环 | `retrieval_quality_score`、`missing_aspects`、`retrieval_iterations=0`、`max_retrieval_iterations=2`、`rewritten_query` |
| 忠实度 | `faithfulness_score`、`unfaithful_sentences`、`regenerate_count=0`、`max_regenerate_count=1` |
| 重试 | `retry_count=0`、`max_retries=3`、`max_iterations=10` |
| 反思 | `reflection_result`、`needs_human_review`、`enable_reflection` |

## 关键阈值汇总

| 环节 | 阈值 | 位置 |
|---|---|---|
| 检索质量重检索 | score < 0.6，最多 2 轮改写 | `route_after_grader` |
| 忠实度重生成 | score < 0.7，最多 1 轮 | `route_after_faithfulness` |
| 反思质量达标 | overall ≥ 0.6（`QualityReviewFunction.quality_threshold`） | `prompts/llm_functions/quality_review_function.py` |
| 反思重试 | `retry_count < max_retries=3`，超限转人工 | `retry` 节点 + lambda 条件边 |
| 意图低置信转人工 | confidence < 0.5 | `unified_router.route_by_intent_result` |

## Checkpoint 持久化的真实现状 ⚠️

`compile()` 会尝试用 `LangGraphPostgresSaver`，但该类**未实现** LangGraph 原生 `BaseCheckpointSaver` 接口（缺 `aget_tuple/aput/get_next_version`），`isinstance` 检查失败后**降级为 `MemorySaver`**（进程内、重启丢失）。`invoke()` 中手动调用的 `postgres_saver.put_checkpoint` 仅为业务层快照，与 LangGraph 线程恢复机制无关。`persistences.py` 中的三个自定义 checkpointer 同样不兼容原生接口且未被使用。如需真正的断点续传，需补齐原生接口实现。

## Agentic RAG（`agentic_rag_nodes.py`）

由 `services/agent_service.py::_agentic_retrieve()` 驱动的多轮自适应检索循环：

```
planner.plan（首轮原查询，后续按评估改写）
  → unified_retriever.retrieve
  → evaluator.evaluate
       ├─ overall ≥ 0.7        → 充分，停止
       ├─ overall < 0.2        → 短路停止（知识库基本无相关内容，避免空转）
       └─ 否则改写继续（默认 max_iterations=3）
```

LLM 评估失败时自动降级为规则评估。

## tax_workflow/ 子工作流

`TaxSubmissionWorkflow`（`TaxSubmissionState` TypedDict，硬编码 `MemorySaver`），线性拓扑：

```
validate_submission → fetch_financial_data → calculate_taxes → assess_risk
  ├─ 高风险数 >0 → request_human_review →（approved → save_submission / rejected → handle_error）
  └─ 无高风险 → save_submission → END
```

风险规则示例：增值税进项占比 >80% 触发 medium；企业所得税有效税率 <15% 触发 high；高风险 >2 个时审核优先级 HIGH。通过 `TaxIntelligenceService` 复用 tax_specialist。

## 与相邻模块的关系

- 条件边逻辑共享自 `app/multi_agent_system/routing/unified_router.py`。
- 专家节点内部调用 `app/multi_agent_system/agents/`（原生 Function Calling）。
- 被 `api/v1/endpoints/langgraph_api.py`（存在但未注册到 main.py）、`chat.py`、`multi_agent.py` 等使用。
- `monitoring.py` 集成 LangSmith；环境变量 `LANGSMITH_TRACING` / `LANGCHAIN_API_KEY` 控制。
