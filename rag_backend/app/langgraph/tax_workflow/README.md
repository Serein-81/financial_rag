# Tax Submission LangGraph Workflow

本模块实现税务提交/税务分析的 LangGraph 状态机。它不是纯线性脚本，也不是让 LLM 自由决定所有步骤的 agent；当前设计是“固定业务骨架 + 条件分支 + 可恢复状态”的工作流，更适合税务这类需要审计、复核和稳定结果的流程。

## 当前入口

文件位置：`app/langgraph/tax_workflow/`

主要入口：

- `TaxSubmissionWorkflow`：工作流类，负责构建、编译和执行 LangGraph。
- `tax_submission_workflow`：模块级默认实例。
- `TaxIntelligenceService`：业务服务层优先调用该工作流，失败或不可用时回退到 legacy workflow。

服务层调用位置：`app/services/tax_intelligence_service.py`

```python
if self.tax_workflow:
    result = await self._execute_langgraph_workflow(request, analysis_id, trace_id)
else:
    result = await self._execute_legacy_workflow(request, analysis_id, trace_id)
```

API 入口：`POST /api/v1/tax-intelligence/analyze`

## 文件说明

```text
tax_workflow/
  state.py        # TaxSubmissionState、状态枚举、Pydantic 数据模型和状态辅助函数
  nodes.py        # 工作流节点：验证、取数、计算、风险评估、人工审核、保存、错误处理
  conditional.py  # 条件路由函数
  graph.py        # LangGraph StateGraph 组装和执行入口
  test_workflow.py
```

## 工作流节点

当前 `graph.py` 注册的节点如下：

1. `validate_submission`：校验租户、用户、年度、税种等输入。
2. `fetch_financial_data`：通过 `FinancialDataQueryTool` 查询本地财务数据。
3. `calculate_taxes`：调用 `TaxIntelligenceService` / `TaxSpecialist` 计算并解释税务结果。
4. `assess_risk`：结合 LLM 分析结果和规则判断风险项。
5. `request_human_review`：高风险时创建人工审核请求。
6. `handle_human_review`：读取审核结果，决定通过或失败。
7. `save_submission`：生成摘要并标记完成。
8. `handle_error`：集中错误收口。

## 路由逻辑

```text
validate_submission
  |-- valid --> fetch_financial_data
  |-- invalid --> handle_error

fetch_financial_data
  |-- has data --> calculate_taxes
  |-- no data --> handle_error

calculate_taxes --> assess_risk

assess_risk
  |-- high_risk_count > 0 --> request_human_review --> handle_human_review
  |-- no high risk --> save_submission

handle_human_review
  |-- approved --> save_submission
  |-- rejected --> handle_error

save_submission
  |-- continue ok --> END
  |-- critical errors --> handle_error

handle_error --> END
```

对应代码在 `conditional.py`：

- `route_after_validation`
- `route_after_financial_data`
- `route_after_risk_assessment`
- `route_after_human_review`
- `check_continue_workflow`

## 直接调用示例

```python
from app.langgraph.tax_workflow import TaxSubmissionWorkflow

workflow = TaxSubmissionWorkflow()

state = await workflow.execute(
    session_id="analysis-001",
    tenant_id="tenant-001",
    user_id="user-001",
    fiscal_year=2026,
    fiscal_period="Q1",
    tax_types=["vat", "income_tax"],
    include_policy_benefits=True,
    include_risk_assessment=True,
)

print(state["current_status"])
print(state["total_tax_burden"])
print(state["overall_risk_score"])
```

## 状态持久化

默认使用 `langgraph.checkpoint.memory.MemorySaver`。调用方可以传入自定义 checkpointer，并通过 `configurable.thread_id` 关联一次可恢复执行。

```python
from langgraph.checkpoint.memory import MemorySaver
from app.langgraph.tax_workflow import TaxSubmissionWorkflow

workflow = TaxSubmissionWorkflow(checkpointer=MemorySaver())
state = await workflow.execute(
    session_id="analysis-001",
    tenant_id="tenant-001",
    user_id="user-001",
    fiscal_year=2026,
    config={"configurable": {"thread_id": "analysis-001"}},
)
```

项目中还存在更通用的 LangGraph、多智能体和任务持久化模块，如 `app/langgraph/`、`app/api/v1/endpoints/langgraph_api.py`、`app/api/v1/endpoints/agent_task.py`，但税务提交工作流当前由 `TaxIntelligenceService` 接入。

## 注意事项

- 当前流程骨架仍在代码中固定，不是配置化 DSL。
- 人工审核节点目前会读取审核队列结果；如果结果未及时返回，代码中存在默认通过逻辑，生产环境需谨慎评估。
- 税额计算中仍有 LLM 结果提取逻辑，关键税额建议优先使用确定性计算工具，LLM 负责解释和风险建议。
- 前端 `TaxSubmissionView.vue` 中仍有模拟工作流进度逻辑，和真实 LangGraph 工作流事件尚未完全统一。
- 文档、日志或源码中的历史乱码不应再复制扩散，新文档统一使用 UTF-8。

## 扩展建议

新增节点：

1. 在 `nodes.py` 实现 `async def xxx_node(state)`。
2. 在 `graph.py` 调用 `workflow.add_node(...)`。
3. 在 `conditional.py` 增加必要的路由函数。
4. 更新 `TaxSubmissionState` 中需要持久化的字段。
5. 增加单元测试或集成测试。

新增税种：

1. 更新 `validate_submission_node` 中的 `valid_tax_types`。
2. 更新 `_get_tax_type_name` 和 `_get_default_tax_rate`。
3. 在 `calculate_taxes_node` 和 `assess_risk_node` 中补充计算/风险逻辑。
4. 确认 `TaxAnalysisRequest` schema 和前端传参一致。

## 测试

```bash
cd rag_backend
python -m app.langgraph.tax_workflow.test_workflow
pytest tests/api/test_tax_workflow_monitor.py
pytest tests/api/test_tax_logic_validator_standalone.py
```

部分测试依赖数据库、LLM 配置或业务测试数据，运行失败时先检查 `.env.example`、数据库连接和模型 API Key。
