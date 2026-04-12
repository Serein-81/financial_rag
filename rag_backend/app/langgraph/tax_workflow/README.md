# 税务提交工作流实现文档

## 概述

本文档描述了基于 LangGraph 的税务提交工作流实现。该工作流替代了原有的线性硬编码流程，提供了更灵活、可维护、可观测的税务处理能力。

## 核心特性

### 1. 状态管理
- **TaxSubmissionState**: 完整的状态定义，包含所有税务提交流程的数据
- **SubmissionStatus**: 清晰的状态枚举，追踪工作流执行进度
- **ValidationResult**: 验证结果模型，包含错误和警告

### 2. 工作流节点

#### 2.1 validate_submission_node
- 验证输入数据的完整性和合法性
- 支持三种验证级别：严格、正常、宽松
- 返回详细的验证错误和警告信息

#### 2.2 fetch_financial_data_node
- 使用 LangChain 工具从本地 PostgreSQL 数据库获取财务数据
- 支持增值税和企业所得税数据的获取
- 处理数据缺失情况并生成警告

#### 2.3 calculate_taxes_node
- 使用 MCP 云端工具执行税务计算
- 支持多种税种：增值税、企业所得税、个人所得税等
- 计算总税负和税负率

#### 2.4 assess_risk_node
- 自动识别税务风险项
- 风险分级：高、中、低
- 基于业务规则的风险检测

#### 2.5 request_human_review_node
- 检测到高风险项时触发人工审核
- 自动创建审核请求并添加到队列
- 支持优先级设置

#### 2.6 handle_human_review_node
- 处理人工审核结果
- 支持审核通过/拒绝
- 提供默认通过机制（当审核结果未及时返回时）

#### 2.7 save_submission_node
- 保存税务分析结果
- 生成执行摘要
- 标记工作流完成

#### 2.8 handle_error_node
- 集中处理工作流中的错误
- 生成错误摘要
- 确保工作流优雅结束

### 3. 条件路由

#### 3.1 route_after_validation
验证后根据结果路由：
- 验证通过 → fetch_financial_data
- 验证失败 → handle_error

#### 3.2 route_after_financial_data
财务数据获取后路由：
- 数据获取成功 → calculate_taxes
- 数据获取失败 → handle_error

#### 3.3 route_after_risk_assessment
风险评估后路由：
- 有高风险项 → request_human_review
- 无高风险项 → save_submission

#### 3.4 route_after_human_review
人工审核后路由：
- 审核通过 → save_submission
- 审核拒绝 → handle_error

### 4. 工具分层策略

#### LangChain 工具（本地数据库访问）
- **FinancialDataQueryTool**: 直接访问 PostgreSQL 数据库
- 优点：高性能、低延迟、支持复杂查询
- 使用场景：需要查询本地项目财务数据时

#### MCP 工具（云端服务）
- **VATCalculatorTool**: 增值税计算
- **CorporateIncomeTaxTool**: 企业所得税计算
- **PersonalIncomeTaxTool**: 个人所得税计算
- 优点：集中管理、版本控制、易于扩展
- 使用场景：需要调用云端计算服务时

## 使用方法

### 方式一：直接使用工作流

```python
from app.langgraph.tax_workflow import TaxSubmissionWorkflow

workflow = TaxSubmissionWorkflow()

result = await workflow.execute(
    session_id="session_001",
    tenant_id="tenant_001",
    user_id="user_001",
    fiscal_year=2024,
    fiscal_period="Q4",
    tax_types=["vat", "income_tax"],
    include_policy_benefits=True,
    include_risk_assessment=True
)

print(f"总税负: ¥{result['total_tax_burden']:,.2f}")
print(f"风险评分: {result['overall_risk_score']}")
```

### 方式二：通过 TaxIntelligenceService

```python
from app.services.tax_intelligence_service import TaxIntelligenceService

service = TaxIntelligenceService()

request = TaxAnalysisRequest(
    analysis_type=TaxAnalysisType.COMPREHENSIVE,
    fiscal_year=2024,
    tax_types=["vat", "income_tax"],
    include_policy_benefits=True,
    include_risk_assessment=True
)

result = await service.execute_analysis_workflow(request)
```

## 工作流图

```
┌─────────────────┐
│ validate_submission │
└────────┬────────┘
         │
    ┌────┴────┐
    │  验证结果  │
    └────┬────┘
         │
    通过 │ 失败
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────────┐  ┌──────────┐
│ fetch_   │  │ handle_  │
│ financial│  │ error    │
│ _data    │  └────┬─────┘
└────┬─────┘       │
     │         ┌────┴────┐
 成功 │ 失败    │    END   │
┌────┴────┐   └──────────┘
│        │
▼        ▼
┌─────────────────┐
│ calculate_taxes │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ assess_risk     │
└────────┬────────┘
         │
    ┌────┴────┐
    │ 风险评估  │
    └────┬────┘
         │
  有风险 │ 无风险
┌────┴────┐    ┌──────────────┐
│request_ │    │save_submission│
│human_   │    └────┬─────────┘
│review   │         │
└────┬─────┘         │
     │          ┌────┴────┐
     ▼          │  END    │
┌─────────────────┐└────────┘
│handle_human_    │
│review           │
└────┬────────────┘
     │
通过 │拒绝
┌────┴────┐    ┌──────────┐
▼         ▼    │handle_   │
┌──────────────┐│error     │
│save_submission│└────┬─────┘
└────┬─────────┘    │
     │          ┌────┴────┐
     └──────────│  END    │
                └─────────┘
```

## 集成说明

### 与现有系统集成

1. **保持 API 兼容性**
   - TaxIntelligenceService 的所有公共方法保持不变
   - API 端点无需修改
   - 现有调用方无感知

2. **渐进式迁移**
   - 默认启用 LangGraph 工作流
   - 如果工作流初始化失败，自动回退到原有流程
   - 通过 `tax_workflow` 属性检查是否使用新工作流

3. **监控和追踪**
   - 集成现有的 AgentTracer
   - 支持 LangGraph 内置的状态持久化
   - 可中断恢复

### 状态持久化

使用 MemorySaver 实现状态持久化：

```python
from langgraph.checkpoint.memory import MemorySaver
from app.langgraph.tax_workflow import TaxSubmissionWorkflow

checkpointer = MemorySaver()
workflow = TaxSubmissionWorkflow(checkpointer=checkpointer)

# 可以中断后恢复
result = await workflow.execute(..., config={"configurable": {"thread_id": "session_id"}})
```

## 测试

运行测试：

```bash
cd rag_backend
python -m app.langgraph.tax_workflow.test_workflow
```

## 性能考虑

1. **异步执行**
   - 所有节点函数都是异步的
   - 支持并发执行
   - 最大化 I/O 效率

2. **错误处理**
   - 完善的异常捕获
   - 优雅的错误恢复
   - 详细的日志记录

3. **可观测性**
   - 完整的日志追踪
   - 状态变更记录
   - 性能指标收集

## 扩展性

### 添加新税种

1. 在 `calculate_taxes_node` 中添加处理逻辑
2. 在 `assess_risk_node` 中添加风险规则
3. 更新状态定义

### 添加新节点

1. 实现节点函数
2. 添加条件路由
3. 更新工作流图

### 自定义验证规则

在 `validate_submission_node` 中添加新的验证逻辑：

```python
async def validate_submission_node(state: TaxSubmissionState) -> TaxSubmissionState:
    # 现有验证逻辑
    ...
    
    # 添加自定义验证
    if custom_validation(state):
        errors.append("自定义验证失败")
    
    return state
```

## 最佳实践

1. **状态管理**
   - 保持状态简洁，只存储必要数据
   - 使用 Pydantic 模型进行数据验证
   - 避免在状态中存储大对象

2. **错误处理**
   - 区分可恢复和不可恢复错误
   - 提供有意义的错误消息
   - 记录完整的错误上下文

3. **日志记录**
   - 使用结构化日志
   - 记录关键决策点
   - 包含足够的上下文信息

4. **性能优化**
   - 避免在节点中进行复杂计算
   - 使用异步 I/O 操作
   - 合理设置超时时间

## 故障排查

### 工作流初始化失败

检查：
1. LangGraph 依赖是否正确安装
2. 状态模型定义是否正确
3. 节点函数签名是否匹配

### 节点执行失败

检查：
1. 日志中的具体错误信息
2. 输入状态是否包含必要字段
3. 外部服务是否可用

### 状态持久化问题

检查：
1. MemorySaver 是否正确初始化
2. thread_id 是否唯一
3. checkpointer 配置是否正确

## 未来改进

1. **支持更多验证规则**
2. **添加性能监控**
3. **实现工作流版本控制**
4. **支持工作流可视化**
5. **添加 A/B 测试能力**

## 相关文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 工具文档](https://python.langchain.com/docs/modules/agents/tools/)
- [项目工具架构](./TOOL_ARCHITECTURE.md)
