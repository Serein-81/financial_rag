# RAG 后端特性实现总结

## 实现日期: 2026-04-02

## 实现的功能

### 1. ✅ Token 预算动态管理方案 A (tiktoken)

**文件位置**: `app/services/token_budget_manager.py`

**核心功能**:
- 基于 tiktoken 的精确 token 计数
- 动态预算分配和监控
- 多组件预算管理（系统保留、上下文保留、用户可用）
- 实时使用监控和告警机制
- Token 使用历史记录和分析

**主要类和方法**:
```python
TokenBudgetManager
├── count_tokens(text) -> int
├── count_messages_tokens(messages) -> int
├── allocate_budget(component, priority) -> TokenAllocation
├── record_usage(prompt_tokens, completion_tokens)
├── get_remaining_budget() -> int
├── should_warn(tokens_to_add) -> (bool, str)
└── get_statistics() -> Dict
```

**配置参数**:
- `total_budget`: 128000 tokens (GPT-4 上下文窗口)
- `system_reserved`: 2000 tokens (系统提示保留)
- `context_reserved`: 1000 tokens (上下文保留)
- `warning_threshold`: 0.8 (80% 警告阈值)
- `critical_threshold`: 0.95 (95% 严重警告阈值)

**使用示例**:
```python
from app.services.token_budget_manager import token_budget_manager

# 初始化
token_budget = token_budget_manager

# 计数 tokens
tokens = token_budget.count_tokens("用户查询内容")
tokens = token_budget.count_messages_tokens(messages)

# 分配预算
allocation = token_budget.allocate_budget("search_component", priority=3)

# 检查警告
should_warn, message = token_budget.should_warn(5000)

# 获取统计
stats = token_budget.get_statistics()
```

---

### 2. ✅ 意图工具筛选方案 B (LLM)

**文件位置**: `app/services/intent_based_tool_filter.py`

**核心功能**:
- 意图识别：分析用户查询的真实意图
- 工具筛选：根据意图选择最合适的工具
- 意图验证：验证工具选择的合理性
- 意图历史：记录和分析历史意图
- 双重策略：规则匹配 + LLM 深度分析

**意图分类**:
```python
IntentCategory
├── INFORMATION_RETRIEVAL  # 信息检索
├── CALCULATION              # 计算
├── ANALYSIS                 # 分析
├── COMPARISON              # 比较
├── GENERATION              # 生成
├── VALIDATION              # 验证
├── RESEARCH                # 研究
└── GENERAL                 # 通用
```

**主要类和方法**:
```python
IntentBasedToolFilter
├── filter_tools(query, available_tools, use_llm) -> IntentAnalysisResult
├── match_tool_to_intent(tool, intent) -> ToolIntentMatch
├── get_intent_statistics() -> Dict
└── clear_history()

LLMIntentAnalyzer
└── analyze_intent(query, available_tools) -> IntentAnalysisResult

IntentPatternMatcher
├── match_intent(query) -> List[Tuple[IntentCategory, float]]
└── suggest_tools(intents) -> List[str]
```

**使用示例**:
```python
from app.services.intent_based_tool_filter import intent_based_tool_filter

# 筛选工具
result = await intent_based_tool_filter.filter_tools(
    query="帮我计算增值税",
    available_tools=tools,
    use_llm=True
)

print(f"意图: {result.primary_intent.category}")
print(f"选择工具: {result.selected_tools}")
print(f"置信度: {result.confidence}")
```

---

### 3. ✅ 工具失败标记方案 A (基础)

**文件位置**: `app/agent_framework/tools/tool_manager.py`

**核心功能**:
- 失败记录：记录工具失败的详细信息（错误类型、错误消息、上下文）
- 连续失败追踪：跟踪连续失败次数
- 冷却机制：失败后自动进入冷却期
- 自动禁用：连续失败超过阈值自动禁用工具
- 健康检查：定期检查工具健康状态

**主要类和方法**:
```python
ToolManager
├── _record_failure(tool_name, error_type, error_message)
├── _record_success(tool_name)
├── is_tool_available(tool_name) -> bool
├── get_tool_failure_stats(tool_name) -> ToolFailureStats
├── get_all_failure_stats() -> Dict[str, ToolFailureStats]
├── reset_tool_failures(tool_name)
├── enable_tool(tool_name)
├── disable_tool(tool_name, reason)
├── get_healthy_tools() -> List[str]
└── get_tool_health_report() -> Dict
```

**配置参数**:
- `max_consecutive_failures`: 3 (最大连续失败次数)
- `failure_cooldown_minutes`: 5 (失败冷却时间)
- `max_failure_records`: 100 (最大失败记录保留数)

**使用示例**:
```python
# 检查工具是否可用
if tool_manager.is_tool_available("calculate_tax_vat"):
    result = await tool_manager.call_tool("calculate_tax_vat", **params)
else:
    print("工具暂时不可用，使用备选方案")

# 获取工具失败统计
stats = tool_manager.get_tool_failure_stats("calculate_tax_vat")
print(f"连续失败: {stats.consecutive_failures}")
print(f"上次失败: {stats.last_failure_time}")

# 获取健康报告
health_report = tool_manager.get_tool_health_report()
print(f"健康工具数: {health_report['summary']['healthy']}")
```

---

### 4. ✅ pgvector 集成利用

#### 4.1 向量搜索服务

**文件位置**: `app/services/vector_search_service.py`

**核心功能**:
- 向量索引管理（HNSW、IVFFlat）
- 多种距离度量（余弦、欧几里得、点积）
- 元数据过滤
- 混合搜索（向量 + 关键词）
- 查询优化和性能监控

**主要类和方法**:
```python
VectorSearchService
├── create_index(table_name, column_name, index_type)
├── drop_index(table_name, column_name)
├── search(table_name, query_vector, limit, filters)
├── hybrid_search(query, query_vector, limit, filters)
└── get_index_info(table_name)

IndexType (Enum)
├── FLAT      # 暴力搜索
├── IVFFLAT   # 倒排文件索引
└── HNSW      # 分层可导航小世界图

DistanceMetric (Enum)
├── COSINE        # 余弦距离
├── EUCLIDEAN     # 欧几里得距离
└── DOT_PRODUCT   # 点积
```

#### 4.2 向量索引迁移脚本

**文件位置**: `app/migrations/add_vector_indexes.py`

**使用说明**:
```bash
# 运行迁移脚本
python -m app.migrations.add_vector_indexes
```

**功能**:
- 检测现有索引
- 智能推荐索引类型（HNSW/IVFFlat）
- 支持交互式创建
- 自动优化参数设置

---

### 5. ✅ 工具依赖图谱服务

**文件位置**: `app/services/tool_dependency_graph.py`

**核心功能**:
- 工具依赖关系存储（使用 Neo4j）
- 基于调用历史的自动依赖发现
- LLM 分析工具依赖
- 拓扑排序执行规划
- 依赖健康评分

**主要类和方法**:
```python
ToolDependencyGraph
├── initialize()  # 初始化，从 Neo4j 加载依赖
├── add_dependency(tool_name, depends_on, confidence, reason)
├── learn_from_history(call_sequences, tool_schemas)
├── analyze_with_llm(tools)
├── get_dependencies(tool_name) -> Optional[ToolDependency]
├── suggest_execution_order(required_tools) -> List[str]
├── plan_execution(required_tools, max_parallel) -> ExecutionPlan
└── get_tool_health_score(tool_name) -> float

ToolDependencyDiscovery
└── discover_from_history(call_sequences, tool_schemas)

LLMDependencyAnalyzer
└── analyze_dependencies(tools)
```

**依赖发现策略**:
1. 频繁共现：经常一起调用的工具
2. 调用顺序：总是 A 在 B 之前调用
3. 输入输出匹配：A 的输出是 B 的输入

**使用示例**:
```python
# 获取执行顺序
execution_order = tool_dependency_graph.suggest_execution_order(
    ["tool_a", "tool_b", "tool_c"]
)

# 规划执行
plan = tool_dependency_graph.plan_execution(
    required_tools=["search", "calculate", "report"],
    max_parallel=3
)
print(f"执行顺序: {plan.execution_order}")
print(f"并行组: {plan.parallel_groups}")
```

---

## 集成到现有系统

### ToolManager 集成

**修改文件**: `app/agent_framework/tools/tool_manager.py`

**新增功能**:
1. 调用历史记录
2. 依赖图谱集成
3. 执行顺序规划
4. 依赖分析

**新增方法**:
```python
ToolManager
├── get_execution_order(required_tools) -> List[str]
├── plan_execution(required_tools, max_parallel) -> Dict
├── learn_dependencies()
├── finish_sequence()
├── get_current_sequence() -> List[str]
├── get_call_history() -> List[List[str]]
├── get_tool_dependencies(tool_name) -> Optional[List[str]]
├── get_all_dependencies() -> Dict[str, List[str]]
├── analyze_dependencies_with_llm(tools)
├── get_dependency_health_score(tool_name) -> float
└── get_dependency_report() -> Dict
```

### LLM Tool Router 集成

**修改文件**: `app/agent_framework/routing/llm_tool_router.py`

**修改内容**:
```python
# 从硬编码改为使用依赖图谱服务
def get_tool_relationships(self) -> Dict[str, List[str]]:
    relationships = tool_dependency_graph.get_all_dependencies()
    
    if not relationships:
        # 回退到默认依赖
        relationships = {...}
    
    return relationships
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    RAG Backend System                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐ │
│  │    Tool      │   │   Intent     │   │   Token    │ │
│  │  Manager     │   │    Filter    │   │   Budget    │ │
│  │              │   │              │   │   Manager   │ │
│  └──────┬───────┘   └──────┬───────┘   └──────┬─────┘ │
│         │                   │                   │        │
│         └───────────┬───────┴───────────────────┘        │
│                     │                                    │
│         ┌───────────▼───────────┐                        │
│         │  Tool Dependency      │                        │
│         │      Graph             │                        │
│         │                        │                        │
│         │  ┌──────────────────┐  │                        │
│         │  │     Neo4j       │  │                        │
│         │  │  (Dependencies) │  │                        │
│         │  └──────────────────┘  │                        │
│         │                        │                        │
│         │  ┌──────────────────┐  │                        │
│         │  │   PostgreSQL     │  │                        │
│         │  │   (pgvector)     │  │                        │
│         │  └──────────────────┘  │                        │
│         └────────────────────────┘                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 文件清单

### 新增文件
- `app/services/token_budget_manager.py` - Token 预算管理器
- `app/services/intent_based_tool_filter.py` - 意图工具筛选器
- `app/services/tool_dependency_graph.py` - 工具依赖图谱
- `app/services/vector_search_service.py` - 向量搜索服务
- `app/migrations/add_vector_indexes.py` - 向量索引迁移脚本（同步版本）

### 修改文件
- `app/agent_framework/tools/tool_manager.py` - 集成依赖图谱和失败标记
- `app/agent_framework/routing/llm_tool_router.py` - 使用依赖图谱服务

---

## 下一步计划

### 可选增强功能
1. **Token 预算管理**:
   - 添加基于 LLM 的智能压缩建议
   - 实现上下文窗口动态调整

2. **意图工具筛选**:
   - 扩展意图分类体系
   - 添加意图置信度校准机制

3. **工具失败标记**:
   - 添加失败原因聚类分析
   - 实现自动恢复机制

4. **pgvector 集成**:
   - 实现增量索引更新
   - 添加查询性能监控面板

5. **工具依赖图谱**:
   - 添加依赖冲突检测
   - 实现依赖变更通知机制

---

## 注意事项

### Windows 环境
迁移脚本已修改为同步版本，避免 asyncpg 在 Windows 上的事件循环问题。

### Neo4j 依赖
工具依赖图谱需要 Neo4j 数据库。如需启用，请在 `app/knowledge_graph/neo4j_manager.py` 中配置连接信息。

### tiktoken 安装
```bash
pip install tiktoken
```

### pgvector 扩展
确保 PostgreSQL 已安装 pgvector 扩展：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 总结

本次实现完成了以下 4 个核心功能：

1. ✅ **Token 预算动态管理**：使用 tiktoken 实现精确计数和预算控制
2. ✅ **意图工具筛选**：结合规则匹配和 LLM 分析的智能筛选
3. ✅ **工具失败标记**：完善的失败追踪和自动恢复机制
4. ✅ **pgvector 集成**：优化的向量索引和搜索服务

所有功能都已集成到现有的工具管理器中，并提供了完整的 API 接口。
