# Memory System

后端记忆系统为 RAG 和多智能体对话提供可控的上下文管理能力。它不是 LangChain Memory 的简单封装，而是项目内自研的分层记忆模块，面向企业财税法务问答中的长期偏好、会话上下文、事实沉淀和模型上下文预算控制。

## 当前定位

记忆系统位于 `app/memory_system/`，主要服务于：

- 对话上下文构建和压缩。
- 用户偏好、历史事实和业务线索的沉淀。
- 工作记忆、情景记忆、语义记忆的分层管理。
- 大模型上下文窗口预算控制。
- 高价值信息提取、缓存和存储层调度。

## 目录速览

```text
memory_system/
  base_memory.py              # MemoryItem 和基础记忆抽象
  working_memory.py           # 短期工作记忆
  episodic_memory.py          # 会话/事件级情景记忆
  semantic_memory.py          # 长期语义记忆
  memory_manager.py           # 统一记忆管理入口
  context_builder.py          # 面向 LLM 的上下文构建
  memory_cache.py             # 记忆缓存
  model_context_manager.py    # 模型上下文预算与裁剪
  storage_tier_scheduler.py   # 存储层迁移/调度
  user_memory_extractor.py    # 从对话中提取用户记忆
```

## 分层模型

```text
用户输入 / Agent 输出
        |
        v
MemoryManager
        |
        +-- WorkingMemory   短期上下文，适合当前轮和最近几轮对话
        +-- EpisodicMemory  会话事件和历史任务片段
        +-- SemanticMemory  稳定事实、偏好、业务背景和长期知识
        |
        v
ContextBuilder / ModelContextManager
        |
        v
LLM prompt context
```

## 关键参数与机制（与代码同步）

| 层 | 容量/阈值 | 持久化 | 检索打分 |
|---|---|---|---|
| WorkingMemory | 默认 50 条，30 分钟过期，FIFO | 内存 | 全量返回 |
| EpisodicMemory | 100 条；准入过滤（闲聊/错误响应/<3 字不写入） | PostgreSQL `episodic_memories` + pgvector(1024) | 向量相似度×0.7 + 时间衰减×0.3，乘重要性权重 |
| SemanticMemory | 1000 条；`importance ≥ 0.8` 才写入；0.9 相似度去重合并 | PostgreSQL `semantic_memories` + pgvector(1024) | 向量检索 + 可选图谱混合检索（HybridRetriever） |

- **重要性评估** `_evaluate_importance()`：意图关键词（"记住/重要"）→ ≥0.9；重要话题（健康/财务/偏好等）→ ≥0.85；同话题出现 ≥3 次 → ≥0.88。
- **Redis 旁路缓存** `memory_cache.py`：Key 格式 `{prefix}{session_id}:{memory_type}`，TTL 默认 1800s；三重防御 —— 空值缓存（60s）防穿透、per-key asyncio.Lock 防击穿、±10% 随机 TTL 防雪崩。
- **用户记忆提取** `user_memory_extractor.py`：从对话提取 facts / preferences / corrections 三类，写入语义记忆（`extraction_type` 区分），可注入 System Prompt。
- **实体关系**：由 Neo4j 知识图谱承担（`app/knowledge_graph/`），是语义记忆的图谱增强路径，**不是独立的第四层记忆**。

## 主要导出

`app.memory_system.__init__` 当前导出：

- `BaseMemory`
- `MemoryItem`
- `WorkingMemory`
- `EpisodicMemory`
- `SemanticMemory`
- `MemoryManager`

## 基本用法

```python
from app.memory_system import MemoryManager

memory = MemoryManager(session_id="session-001", user_id="user-001")

await memory.add_message("user", "我们公司主要做软件服务，关注企业所得税优惠。")
await memory.add_message("assistant", "我会优先关注软件企业相关优惠政策。")

context = await memory.get_formatted_context("本季度有哪些税务风险？")
history = memory.get_context_for_llm()
```

## 与服务层的关系

记忆系统通常不会直接暴露给前端，而是被以下模块间接使用：

- `app/services/agent_service.py`
- `app/services/hybrid_agent_service.py`
- `app/api/v1/endpoints/memory.py`
- 多智能体对话和群聊相关服务

`model_context_manager.py` 还会参与更大的上下文预算治理，避免 RAG 内容、历史消息和工具结果把模型上下文撑爆。

## API 入口

主应用在 `app/main.py` 中注册：

```python
app.include_router(memory.router, prefix="/api/v1/memory", tags=["Memory System"])
```

具体接口以 `app/api/v1/endpoints/memory.py` 为准。

## 维护建议

- 短期对话只放入 `WorkingMemory`，不要把所有消息都塞进长期记忆。
- 只有稳定、可复用、低敏感的信息才应进入 `SemanticMemory`。
- 涉及个人信息、企业敏感数据时，应先经过权限和脱敏策略。
- 修改上下文裁剪策略后，需要验证长对话、RAG 检索和工具结果混合场景。
- 如果新增持久化字段，记得同步模型、迁移和 API 序列化逻辑。

## 测试建议

```bash
cd rag_backend
pytest tests/unit/test_memory_system.py
pytest tests/unit/test_memory_validation.py
pytest tests/unit/test_enhanced_context_builder.py
pytest tests/integration/test_memory_integration.py
```

部分测试可能依赖数据库或外部服务配置，运行前请检查 `.env.example` 中的数据库、Redis 和模型配置。
