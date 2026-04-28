# 企业级 RAG 知识库系统

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)
![Vue.js](https://img.shields.io/badge/Vue.js-3.4+-42b883.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**一个面向财税法务领域的智能问答与知识管理平台**

</div>

---

## 📋 项目概述

本项目是一个**企业级 RAG（检索增强生成）知识库系统**，专注于为企业提供专业的财税法务智能问答服务。系统基于 FastAPI + Vue3 技术栈构建，采用多智能体架构，支持文档上传、智能检索、AI 对话等功能。

### 核心价值

- 🤖 **智能问答** - 基于专业知识库的 AI 对话，支持流式输出
- 📚 **知识管理** - 多知识库管理，文档自动解析与向量化
- 🎯 **专业智能体** - 税务、法律、财务领域专家智能体协作
- 🔍 **语义搜索** - 混合检索 + 知识图谱增强
- 🔐 **企业级安全** - 租户隔离、角色权限、完整审计日志

---

## 🏛️ 项目组成

本项目采用前后端分离架构，包含以下主要模块：

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| **[前端应用](./rag_frontend)** | Vue 3 + TypeScript | 企业级 Web 应用界面，包含完整的用户交互体验 |
| **[后端服务](./rag_backend)** | FastAPI + Python | RESTful API 服务，提供核心业务逻辑和 AI 能力 |
| **[MCP 工具服务](./mcp_server)** | Python | 财税法务领域专用工具接口，支持 MCP 标准协议 |

### 🚀 快速访问

- 📱 **前端界面**：[查看前端 README](./rag_frontend/README.md)
- ⚙️ **后端 API**：[查看后端项目](./rag_backend)
- 🔧 **MCP 服务**：[查看 MCP 服务](./mcp_server)
- 🐳 **Docker 部署**：[docker-compose.yml](./rag_backend/docker-compose.yml)

### 🔎 重点功能入口

- 🧰 **智能体工具构建器**：管理员可在 `/custom-tools` 通过自然语言生成工具规格和代码草稿，发布后的配置型工具可供同企业成员查看和使用。
- 📥 **拉取项目并启动**：执行 `git clone https://github.com/Serein-81/My_rag.git` 后进入 `My_rag/rag_backend`，可用 `docker compose up -d` 快速启动后端依赖与服务；完整步骤见下方“本地快速启动”。

### 💡 前端亮点

前端采用 **Vue 3 + TypeScript** 构建，提供企业级用户体验：

| 功能模块 | 说明 |
|---------|------|
| 🤖 **智能对话** | 单/多智能体对话、群组聊天、流式输出 |
| 🧰 **智能体工具** | 自然语言生成工具、测试入参、发布配置型工具、企业内共享 |
| 💼 **企业管理** | 知识库管理、财务数据、政策服务 |
| 📊 **工作流** | 税务申报、合同审查、安全审计 |
| 🔧 **系统工具** | Agent 监控、意图分类、人机协作 |
| 📈 **数据可视化** | 分析仪表板、实时监控、图表展示 |
| 🎨 **交互体验** | 动画效果、骨架屏、国际化支持 |


## ✨ 核心特性

### 1. 多智能体协作系统

系统采用分层智能体架构，不同领域的问题由对应的专业智能体处理：

```
┌─────────────────────────────────────────────┐
│              用户问题输入                      │
└─────────────────┬───────────────────────────┘
                  ▼
┌─────────────────────────────────────────────┐
│         分诊智能体 (Triage Agent)            │
│    - 分析问题类型和领域                       │
│    - 智能路由到对应专家智能体                   │
└─────────────────┬───────────────────────────┘
                  ▼
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐   ┌────────┐   ┌────────┐
│税务专家 │   │法律专家 │   │财务专家 │
│智能体  │   │智能体   │   │智能体   │
└───┬────┘   └───┬────┘   └───┬────┘
    └─────────────┼─────────────┘
                  ▼
┌─────────────────────────────────────────────┐
│         报告生成智能体 (Report Agent)         │
│    - 整合多智能体答案                         │
│    - 生成结构化报告                           │
└─────────────────────────────────────────────┘
```

**专业能力**：

| 智能体类型 | 职责范围 |
|-----------|---------|
| 分诊智能体 | 问题分类、意图识别、路由决策 |
| 税务专家 | 增值税、企业所得税、个人所得税计算与咨询 |
| 法律专家 | 合同审查、法律条款匹配、风险提示 |
| 财务专家 | 财务指标分析、报表解读、比率计算 |
| 反思智能体 | 答案质量评估、交叉验证、改进建议 |

### 2. 自研轻量级 Agent 框架

不同于 LangChain 的臃肿，我们实现了轻量级的 ReAct Agent 框架：

```python
# 核心架构
app/agent_framework/
├── core/           # Agent 核心实现
│   ├── base_agent.py      # 基类定义
│   ├── agent_wrapper.py   # Agent 包装与统一调用
│   ├── react_agent.py     # ReAct 推理
│   ├── plan_agent.py      # 规划模式
│   ├── reflect_agent.py   # 反思模式
│   └── output_agent.py    # 输出整理
├── llm/            # LLM 适配器
│   ├── base_adapter.py     # 适配器基类
│   ├── openai_adapter.py   # OpenAI
│   ├── zhipu_adapter.py    # 智谱 AI
│   ├── deepseek_adapter.py # DeepSeek
│   ├── qwen_adapter.py     # 通义千问
│   ├── claude_adapter.py   # Claude
│   ├── specialist_llm_router.py # 专家模型路由
│   └── factory.py          # 工厂模式
└── tools/          # 工具管理
    ├── tool_manager.py     # 工具注册
    └── tool_router.py      # 智能路由
```

**设计亮点**：

- 🧠 **ReAct 推理** - 推理与行动交替执行
- 🔧 **工具调用** - 灵活的外部工具集成
- 🔄 **多模式支持** - ReAct / Plan / Reflect 模式切换
- 🎯 **适配器模式** - 零代码切换不同 LLM 提供商

### 3. 混合检索系统

结合多种检索技术，实现精准的知识召回：

```
用户查询
    │
    ▼
┌──────────────────────────────────────────┐
│           混合检索管理器                    │
├──────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐          │
│  │  向量检索   │  │  关键词检索  │          │
│  │ (pgvector) │  │  (BM25/FTS)│          │
│  └─────┬──────┘  └─────┬──────┘          │
│        │               │                  │
│        └─────────┬─────┘                  │
│                  ▼                        │
│        ┌─────────────────┐                │
│        │   RRF 融合排序   │                │
│        └────────┬────────┘                │
│                 ▼                          │
│        ┌─────────────────┐                │
│        │  知识图谱增强    │                │
│        │  (Neo4j)        │                │
│        └─────────────────┘                │
└──────────────────────────────────────────┘
    │
    ▼
精准检索结果
```

当前向量检索主要基于 PostgreSQL + pgvector，结合全文检索、同义词扩展、RRF 融合和可选 MMR/Rerank 进行结果优化。

### 4. 记忆系统

完整的 Agent 记忆体系，支持上下文理解：

| 记忆类型 | 说明 | 持久化 |
|---------|------|--------|
| 工作记忆 | 当前对话上下文 | 内存 |
| 情景记忆 | 对话历史摘要 | PostgreSQL |
| 语义记忆 | 长期知识存储 | Vector DB |
| 关系记忆 | 实体关系图谱 | Neo4j |

### 5. MCP 远程工具服务

提供标准化的财税法务工具调用接口：

- 🧮 **税务计算** - 增值税、所得税、个税计算
- ⚖️ **法律匹配** - 合同条款检查、法规匹配
- 📊 **财务分析** - 比率计算、报表分析
- 🏢 **企业信息** - 企业查询、风险评估

> **说明**：后端项目 `rag_backend/app/mcp/` 已内置上述所有计算/检查类工具的同名实现（通过 `@cloud_tool` 装饰器），agent 默认走进程内直接调用，无需依赖外部 MCP 服务。`mcp_server/` 是独立的 HTTP MCP 工具服务，供外部 MCP 客户端或其他项目通过标准协议调用。如需启用 mcp_server，请确保有可用的云端服务器并在 `.env` 中正确配置 `MCP_MODE` 和 `MCP_SERVER_URL`（见下方云端部署章节）。

---


### 🆕 当前代码能力概览

根据当前代码，系统已经扩展为覆盖 RAG、智能体协作、企业管理、财税工作流和运维观测的一体化平台：

| 能力域 | 当前实现 |
|------|------|
| **认证与企业权限** | 登录/注册、JWT 鉴权、管理员路由、租户上下文中间件、企业用户管理、邀请码管理 |
| **知识库与 RAG** | 文档上传、知识库管理、向量检索、混合检索、查询改写、MMR、知识图谱增强、检索结果缓存 |
| **文档解析** | 文本、Markdown、Word、PDF、Excel、图片解析；支持 OCR、MinerU、Unstructured API 等解析路径 |
| **智能体框架** | ReAct / Plan / Reflect Agent、智能体 LLM 独立配置、工具路由、工具调用追踪、Agent Trace |
| **智能体工具构建器** | 管理员可通过自然语言生成工具规格与代码草稿，支持配置型工具发布、企业内可见、操作日志追踪；生成代码默认仅保存待审核，不直接执行 |
| **多智能体系统** | 意图路由、任务拆解、税务/法务/财务专家、结果合并、报告生成、人机审核、A2A 协议与多传输适配 |
| **财税法务业务** | 税务申报、税务智能分析、政策检索与通知、合同审查、财务数据录入、财务健康监控、企业政策匹配 |
| **协作与实时能力** | 群组聊天、WebSocket 在线状态、SSE 流式响应、工作流事件推送、后台任务状态持久化 |
| **运维与治理** | 请求日志、对话日志、安全监控、限流、熔断器、健康检查、LangSmith 追踪、OpenTelemetry 依赖 |
| **远程工具服务** | 独立 MCP Server，提供税务、法务、财务工具注册、API Key 鉴权、JSON-RPC 风格工具调用 |

### 🧭 当前前端页面入口

前端路由已覆盖下列主要业务页面：

| 路径 | 页面能力 |
|------|------|
| `/` | 主智能对话 |
| `/multi-agent` | 多智能体对话 |
| `/search`、`/documents`、`/knowledge`、`/knowledge/:id` | 搜索、文档、知识库与知识详情 |
| `/knowledge-graph`、`/knowledge-graph-editor` | 知识图谱查看与编辑 |
| `/audit/upload`、`/audit/result/:id` | 多智能体审计上传与结果页 |
| `/tax-submission`、`/tax-intelligence` | 税务申报与税务智能分析 |
| `/policy`、`/policy/:id`、`/policy-search`、`/policy-notifications` | 政策列表、详情、检索与通知 |
| `/financial-health`、`/financial-data-entry`、`/financial-data-list` | 财务健康、财务数据录入与列表 |
| `/contract-review`、`/enterprise-match` | 合同审查与企业政策匹配 |
| `/group-chat`、`/notifications` | 群组聊天与通知中心 |
| `/analytics`、`/agent-center`、`/hitl-approval`、`/intent-debug`、`/security-audit`、`/logs` | 分析、Agent 管理、人机审核、意图调试、安全审计与日志 |
| `/custom-tools` | 智能体工具构建器：自然语言生成工具、发布配置型工具、测试入参、查看企业已发布工具 |
| `/task-management`、`/chat-logs`、`/profile`、`/test-data-guide` | 任务管理、对话日志、个人资料与测试数据指南 |

### 🔌 当前后端 API 分组

后端入口位于 `rag_backend/app/main.py`，当前已注册的主要 API 分组包括：

| API 前缀 | 功能 |
|------|------|
| `/api/v1/auth` | 认证、登录、注册 |
| `/api/v1/documents`、`/api/v1/knowledge`、`/api/v1/search`、`/api/v1/knowledge_graph` | 文档、知识库、搜索、知识图谱 |
| `/api/v1/chat`、`/api/v1/sessions`、`/api/v1/groups`、`/api/v1/ws/groups` | 对话、会话、群聊与 WebSocket |
| `/api/v1/multi-agent`、`/api/v1/human-review`、`/api/v1/agent_trace`、`/api/v1/agent-trace`、`/api/v1/tool_trace`、`/api/v1/tool-trace` | 多智能体、人机审核、Agent/工具追踪 |
| `/api/v1/agents`、`/api/v1/agent-discovery`、`/api/v1/agent-task` | 智能体 LLM 配置、智能体发现与任务状态恢复 |
| `/api/v1/custom-tools` | 自定义智能体工具：生成规格、生成代码草稿、创建、发布、测试执行；管理接口仅管理员可用，企业成员可查看和使用已发布工具 |
| `/api/v1/tax-reports`、`/api/v1/tax-intelligence`、`/api/v1/policy`、`/api/v1/policy-tracking`、`/api/v1/financial-tools-test` | 税务报告、税务智能分析、政策管理、政策追踪、财务工具测试 |
| `/api/v1/financial-health`、`/api/v1/financial-data`、`/api/v1/contract-review` | 财务健康、财务数据管理、合同审查 |
| `/api/v1/enterprise`、`/api/v1/invite-codes`、`/api/v1/tenant-settings` | 企业管理、邀请码、租户设置 |
| `/api/v1/logs`、`/api/v1/chat-logs`、`/api/v1/security`、`/api/v1/rate-limit`、`/api/v1/observability` | 系统日志、对话日志、安全监控、限流管理与可观测性 |
| `/api/v1/workflow*`、`/api/v1/task-manager`、`/api/v1/notifications`、`/api/v1/policy-notifications`、`/api/v1/policy-agent` | 工作流事件、任务管理、通知、政策通知与政策通知智能体 |
| `/api/v1/a2a*`、`/api/v1/circuit-breaker*`、`/api/v1/langsmith` | A2A 协议、熔断器管理与 LangSmith 集成 |
| `/health`、`/health/quick`、`/health/{component}`、`/api/health` | 健康检查与组件级诊断 |

---

## 🔬 技术实现详解

### 1. 智能体设计详解

#### 1.1 ReAct 推理模式

ReAct（Reasoning + Acting）模式是本系统智能体的核心推理范式，它将推理与行动交替执行，使智能体能够像人类一样边思考边行动：

```python
# ReAct 推理循环
while not reached_final_answer:
    # 1. 推理阶段 - 分析当前状态，决定下一步行动
    thought = await llm.think(context, history)
    
    # 2. 行动阶段 - 执行推理决定的动作
    if need_tool:
        action = await execute_tool(thought)
    else:
        action = "final_answer"
    
    # 3. 观察阶段 - 获取行动结果
    observation = await get_observation(action)
    
    # 4. 更新上下文
    context.update(thought, action, observation)
```

**ReAct 模式的优势**：

- ✅ **可解释性** - 每一步推理都有明确的思考过程
- ✅ **可控性** - 可随时干预或修正推理方向
- ✅ **灵活性** - 支持多种工具调用和条件分支
- ✅ **可调试性** - 便于追踪问题出在哪一步

#### 1.2 Plan 规划模式

Plan 模式用于复杂任务的分解和规划，特别适合需要多步骤处理的专业咨询场景：

```
用户问题：某企业重组涉及哪些税务问题？
    │
    ▼
┌─────────────────────────────────────────────┐
│           任务规划阶段                        │
├─────────────────────────────────────────────┤
│  Step 1: 识别企业类型和重组方式               │
│  Step 2: 分析增值税影响                      │
│  Step 3: 分析企业所得税影响                   │
│  Step 4: 分析个人所得税影响（如涉及）         │
│  Step 5: 检查地方性优惠政策                  │
│  Step 6: 生成综合税务建议报告                 │
└─────────────────────────────────────────────┘
    │
    ▼
按计划逐步执行，各步骤可独立也可相互依赖
```

**规划模式的特点**：

- 📋 **结构化分解** - 将复杂问题拆解为可执行的子任务
- 🔗 **依赖管理** - 处理步骤间的数据依赖关系
- 🎯 **目标导向** - 每个子任务都有明确的交付目标
- 🔄 **动态调整** - 根据中间结果调整后续计划

#### 1.3 Reflect 反思模式

Reflect 模式负责答案质量的评估和改进，确保输出的专业性和准确性：

```python
# 反思评估维度
reflection_criteria = {
    "accuracy": "答案的税务/法律计算是否准确",
    "completeness": "是否涵盖了问题的所有关键方面",
    "consistency": "前后逻辑是否一致",
    "safety": "是否包含必要的风险提示和免责声明",
    "clarity": "表达是否清晰易懂"
}

# 反思触发条件
should_reflect = any([
    question.complexity > threshold,
    involves_calculation,
    multiple_domains,
    user_feedback_requested
])
```

**反思机制的作用**：

- 🛡️ **质量保障** - 在最终回答前进行多维度检查
- ⚠️ **风险预警** - 识别可能的法律和税务风险
- 📝 **补充完善** - 自动添加必要的说明和限制条件
- 🔍 **交叉验证** - 用不同方法验证关键结论

#### 1.4 工具集成架构

智能体通过统一的工具接口调用各类外部服务：

```python
# 工具调用协议
class ToolCall(Protocol):
    name: str          # 工具名称
    params: dict       # 输入参数
    result: Any        # 执行结果
    confidence: float  # 结果置信度
    source: str        # 结果来源

# 工具管理器
tool_manager = ToolManager()
tool_manager.register("tax_calculator", TaxCalculator())
tool_manager.register("legal_search", LegalSearchEngine())
tool_manager.register("financial_ratio", FinancialAnalyzer())

# 智能路由选择最合适的工具
selected_tool = tool_manager.route(query_analysis)
```

---

### 2. 记忆模式详解

系统实现了完整的四层记忆体系，模拟人类认知的不同层面：

#### 2.1 工作记忆（Working Memory）

工作记忆是智能体在当前对话中的临时工作空间：

```python
class WorkingMemory:
    def __init__(self, capacity: int = 10):
        self.messages: List[Message] = []      # 对话历史
        self.entities: Dict[str, Entity] = {}   # 当前识别的实体
        self.context_window: List[str] = []    # 滑动上下文窗口
        self.pending_tasks: List[Task] = []    # 待处理任务
    
    def add(self, message: Message):
        self.messages.append(message)
        if len(self.messages) > self.capacity:
            self.messages.pop(0)
    
    def get_relevant(self, query: str, top_k: int = 5) -> List[Message]:
        # 基于语义相似度召回相关内容
        return semantic_search(self.messages, query, top_k)
```

**特点**：

- ⚡ **高速访问** - 存储在内存中，延迟极低
- 🔄 **动态更新** - 根据对话进展实时调整
- 🎯 **聚焦当前** - 专注于当前任务相关的上下文

#### 2.2 情景记忆（Episodic Memory）

情景记忆存储对话历史的压缩摘要，便于快速回顾：

```python
class EpisodicMemory:
    def __init__(self, db: Database):
        self.storage = db
    
    def store_summary(
        self, 
        session_id: str,
        summary: str,
        key_points: List[str],
        sentiment: str,
        topics: List[str]
    ):
        # 自动摘要并存储
        episode = Episode(
            session_id=session_id,
            summary=summary,
            key_points=key_points,
            topics=topics,
            timestamp=datetime.now()
        )
        self.storage.save(episode)
    
    def retrieve_similar(
        self, 
        current_query: str, 
        user_profile: UserProfile
    ) -> List[Episode]:
        # 基于用户画像和查询相似度召回
        return self.storage.search(
            query=current_query,
            filters={
                "user_id": user_profile.id,
                "topics": {"$overlap": current_query.topics}
            }
        )
```

**存储策略**：

- 📦 **自动摘要** - 对话结束后自动生成摘要
- 🏷️ **多维索引** - 支持按主题、情感、时间等维度检索
- 👤 **用户隔离** - 每个用户的情景记忆独立存储
- 🗜️ **定期清理** - 过期或无价值的记忆自动归档

#### 2.3 语义记忆（Semantic Memory）

语义记忆存储长期知识，采用向量数据库实现高效语义检索：

```python
class SemanticMemory:
    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.embedder = EmbeddingModel()
    
    def store_knowledge(
        self,
        content: str,
        metadata: Dict[str, Any],
        knowledge_type: KnowledgeType
    ):
        # 向量化并存储
        vector = self.embedder.encode(content)
        self.store.add(
            id=generate_id(),
            vector=vector,
            content=content,
            metadata={**metadata, "type": knowledge_type}
        )
    
    def query(self, question: str, filters: Dict) -> List[KnowledgeChunk]:
        # 语义检索
        query_vector = self.embedder.encode(question)
        return self.store.search(
            vector=query_vector,
            top_k=10,
            filters=filters,
            include_vectors=False
        )
```

**知识组织**：

- 🧠 **向量化存储** - 使用深度学习模型将文本转为稠密向量
- 🔍 **语义相似度** - 支持基于语义的精准检索
- 🏷️ **元数据过滤** - 支持按来源、时间、类型等过滤
- 🔄 **增量更新** - 支持知识的实时更新和版本管理

#### 2.4 关系记忆（Relational Memory）

关系记忆使用知识图谱存储实体间的复杂关系：

```python
class RelationalMemory:
    def __init__(self, graph_db: Neo4jDatabase):
        self.graph = graph_db
    
    def store_entity(self, entity: Entity):
        # 存储实体节点
        self.graph.create_node(
            label=entity.type,
            properties=entity.to_dict()
        )
    
    def store_relation(self, relation: Relation):
        # 存储关系边
        self.graph.create_relationship(
            from_node=relation.source,
            to_node=relation.target,
            type=relation.type,
            properties=relation.properties
        )
    
    def expand_query(self, entity: str, depth: int = 2) -> Dict:
        # 图谱扩展查询
        return self.graph.traverse(
            start_node=entity,
            depth=depth,
            relations=[
                "税收优惠",
                "适用条件",
                "关联法规"
            ]
        )
```

**图谱能力**：

- 🔗 **关系建模** - 表达实体间的复杂关联关系
- 🚀 **路径发现** - 找出实体间的关联路径
- 📊 **图推理** - 基于图结构的逻辑推理
- 🎯 **上下文增强** - 为检索结果提供关系上下文

#### 2.5 记忆协同机制

四种记忆相互协作，共同支撑智能体的上下文理解能力：

```
用户问题输入
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                 记忆查询阶段                          │
├─────────────────────────────────────────────────────┤
│  1. 工作记忆 → 提取当前对话的实体和上下文             │
│  2. 情景记忆 → 召回该用户历史相似案例                │
│  3. 语义记忆 → 检索相关的专业知识                      │
│  4. 关系记忆 → 扩展概念间的关联信息                   │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                 记忆融合阶段                          │
├─────────────────────────────────────────────────────┤
│  • 权重融合 → 根据相关性分配各记忆的权重              │
│  • 去重合并 → 消除冗余信息，保留核心内容              │
│  • 时序整理 → 按时间顺序组织历史信息                 │
│  • 重要性排序 → 突出关键信息                         │
└─────────────────────────────────────────────────────┘
    │
    ▼
增强后的上下文 → 传递给智能体进行推理
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                 记忆更新阶段                          │
├─────────────────────────────────────────────────────┤
│  • 新实体 → 存入关系记忆                             │
│  • 新知识 → 存入语义记忆                             │
│  • 新经验 → 存入情景记忆                             │
│  • 当前状态 → 更新工作记忆                           │
└─────────────────────────────────────────────────────┘
```

---

### 3. 提示词模块设计

#### 3.1 分层提示词架构

系统采用分层设计的提示词模板，实现专业领域定制：

```python
# 提示词层次结构
prompt_layers = {
    # 第一层：系统基础层 - 定义智能体身份和基本原则
    "system_base": """
    你是一位专业的财税法务顾问助手。
    核心原则：
    1. 提供准确、合规的专业建议
    2. 明确标注风险和限制条件
    3. 引用相关法规条款作为依据
    """,
    
    # 第二层：领域专家层 - 定义具体领域的专业能力
    "domain_expert": {
        "tax": """
        税务专家能力范围：
        - 增值税、企业所得税、个人所得税计算
        - 税务筹划和合规建议
        - 税收优惠政策解读
        """,
        "legal": """
        法律专家能力范围：
        - 合同条款审查和风险提示
        - 法规条文解读和应用
        - 权利义务分析
        """,
        "finance": """
        财务专家能力范围：
        - 财务报表分析和指标计算
        - 财务比率和趋势分析
        - 财务风险评估
        """
    },
    
    # 第三层：任务指令层 - 定义具体任务的执行方式
    "task_instruction": """
    任务类型：{task_type}
    输出格式：{output_format}
    参考资料：{retrieved_context}
    """
}
```

#### 3.2 动态提示词组装

根据对话上下文动态组装最合适的提示词：

```python
class PromptComposer:
    def compose(
        self,
        agent_type: AgentType,
        task: Task,
        context: Context,
        retrieved_knowledge: List[Knowledge]
    ) -> Prompt:
        # 1. 获取基础系统提示
        system_prompt = self.get_system_prompt(agent_type)
        
        # 2. 添加领域特定指令
        domain_prompt = self.get_domain_prompt(agent_type.domain)
        
        # 3. 注入检索到的知识
        knowledge_context = self.format_knowledge(retrieved_knowledge)
        
        # 4. 添加对话历史（摘要形式）
        history_summary = self.summarize_history(context.messages)
        
        # 5. 组装最终提示
        return f"""
        {system_prompt}
        
        {domain_prompt}
        
        参考资料：
        {knowledge_context}
        
        对话历史摘要：
        {history_summary}
        
        当前任务：{task.description}
        """
```

#### 3.3 Few-Shot 示例模板

为复杂任务提供示例参考：

```python
# 税务计算任务的 Few-Shot 示例
tax_calculation_examples = [
    {
        "input": "某企业年销售额500万元，进项税额30万元，应缴纳多少增值税？",
        "reasoning": """
        1. 确定纳税人类型：一般纳税人（销售额>500万）
        2. 适用税率：13%（销售货物）
        3. 计算销项税额：500万 × 13% = 65万
        4. 应纳税额 = 销项税额 - 进项税额 = 65万 - 30万 = 35万
        5. 考虑是否有进项税额转出等特殊情况
        """,
        "output": "应缴纳增值税35万元。\n\n计算依据：《增值税暂行条例》第四条\n备注：以上计算基于一般纳税人13%税率，需根据实际情况核实进项税额抵扣凭证。"
    }
]

# 法律条款匹配任务的 Few-Shot 示例
legal_matching_examples = [
    {
        "input": "合同中约定'定金不得超过合同金额的20%'是否符合规定？",
        "analysis": """
        1. 识别相关法律：《民法典》第五百八十六条
        2. 法条规定：定金不得超过主合同标的额的20%
        3. 条款分析：合同金额的20%与标的额的20%是否一致
        4. 结论判断：条款符合法律规定
        """,
        "output": "该约定符合法律规定。\n\n法律依据：《民法典》第五百八十六条规定，当事人可以约定一方向对方给付定金作为债权的担保。定金不得超过主合同标的额的20%。"
    }
]
```

#### 3.4 Chain-of-Thought 引导

针对复杂问题启用逐步推理模式：

```python
cot_system_prompt = """
当你遇到复杂的税务、法律或财务问题时，请采用链式思考：

1. 问题拆解
   - 这是什么问题类型？
   - 涉及哪些法律/税务条款？
   - 有哪些关键条件需要确认？

2. 条件分析
   - 逐一检查适用条件
   - 识别特殊情况或限制
   - 确定适用税率或标准

3. 方案推导
   - 按逻辑步骤计算或推理
   - 每一步都要有依据
   - 中间结论要明确

4. 综合结论
   - 汇总各部分结论
   - 指出需要注意的风险点
   - 提供可行的建议

请用【思考】标记推理过程，用【结论】标记最终答案。
"""
```

---

### 4. 搜索查询算法详解

#### 4.1 混合检索架构

系统采用多路召回 + 融合排序的混合检索策略：

```python
class HybridRetriever:
    def __init__(self):
        self.vector_retriever = VectorRetriever()
        self.keyword_retriever = KeywordRetriever()
        self.knowledge_graph = KnowledgeGraphRetriever()
        self.fusion_engine = FusionEngine()
    
    async def retrieve(
        self, 
        query: Query,
        top_k: int = 20
    ) -> List[RetrievedChunk]:
        # 1. 查询意图分析
        intent = await self.analyze_intent(query)
        
        # 2. 并行多路召回
        results = await asyncio.gather(
            self.vector_retriever.search(
                query=query.text,
                filters=self.build_filters(intent),
                limit=top_k * 2
            ),
            self.keyword_retriever.search(
                query=query.text,
                filters=self.build_filters(intent),
                limit=top_k * 2
            ),
            self.knowledge_graph.expand(
                entities=self.extract_entities(query.text),
                depth=2
            )
        )
        
        # 3. RRF 融合排序
        fused_results = self.fusion_engine.reciprocal_rank_fusion(
            results,
            k=60  # RRF 融合参数
        )
        
        # 4. 重排序
        reranked = await self.rerank(fused_results, query)
        
        return reranked[:top_k]
```

#### 4.2 向量检索算法

使用稠密向量进行语义级别的相似度匹配：

```python
class VectorRetriever:
    def __init__(self):
        self.embedding_model = EmbeddingModel()
        self.vector_store = MilvusStore()
    
    async def search(
        self,
        query: str,
        filters: Dict,
        limit: int = 20
    ) -> List[VectorResult]:
        # 1. 查询向量化
        query_vector = await self.embedding_model.encode(query)
        
        # 2. 添加查询扩展（可选）
        expanded_queries = await self.expand_query(query)
        expanded_vectors = [
            await self.embedding_model.encode(eq) 
            for eq in expanded_queries
        ]
        
        # 3. 多向量查询融合
        all_vectors = [query_vector] + expanded_vectors
        avg_vector = np.mean(all_vectors, axis=0)
        
        # 4. ANN 近似最近邻搜索
        results = await self.vector_store.search(
            vectors=[avg_vector],
            top_k=limit,
            filters=filters,
            metric_type="COSINE"
        )
        
        return results
```

**向量检索特点**：

- 🔮 **语义理解** - 理解查询的真实含义，而非字面匹配
- 🌐 **跨语言** - 支持中英文混合检索
- 📏 **维度选择** - 1536维 Embedding-3 模型
- ⚡ **ANN 加速** - 使用 HNSW 索引实现毫秒级检索

#### 4.3 BM25 关键词检索

经典的关键词检索算法，基于词频和文档频率：

```python
class KeywordRetriever:
    def __init__(self):
        self.bm25 = BM25Okapi()
        self.index = InvertedIndex()
    
    def search(
        self,
        query: str,
        filters: Dict,
        limit: int = 20
    ) -> List[BM25Result]:
        # 1. 查询分词
        tokens = self.tokenize(query)
        
        # 2. 计算 BM25 分数
        scores = self.bm25.get_scores(tokens)
        
        # 3. 应用过滤器
        filtered_scores = self.apply_filters(scores, filters)
        
        # 4. 排序返回 Top-K
        top_indices = np.argsort(filtered_scores)[::-1][:limit]
        
        return [
            BM25Result(
                doc_id=idx,
                content=self.index.get_doc(idx),
                score=filtered_scores[idx],
                matched_terms=self.get_matched_terms(tokens, idx)
            )
            for idx in top_indices
        ]
```

**BM25 公式**：

$$score(D, Q) = \sum_{i=1}^{n} IDF(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot (1 - b + b \cdot \frac{|D|}{avgdl})}$$

其中：
- $f(q_i, D)$：词项 $q_i$ 在文档 $D$ 中的频率
- $|D|$：文档 $D$ 的长度
- $avgdl$：平均文档长度
- $k_1$, $b$：调参参数（通常 $k_1=1.5$, $b=0.75$）
- $IDF(q_i)$：逆文档频率

#### 4.4 RRF 融合排序

Reciprocal Rank Fusion（倒数排名融合）将多路检索结果综合排序：

```python
def reciprocal_rank_fusion(
    result_lists: List[List[SearchResult]],
    k: int = 60
) -> List[FusedResult]:
    """
    RRF 融合算法
    
    RRF_score(d) = Σ 1/(k + rank_i(d))
    
    其中：
    - k: 融合参数（通常 60）
    - rank_i(d): 文档 d 在第 i 路检索结果中的排名
    """
    scores = defaultdict(float)
    doc_metadata = {}
    
    for result_list in result_lists:
        for rank, result in enumerate(result_list, start=1):
            # 累加 RRF 分数
            scores[result.doc_id] += 1.0 / (k + rank)
            # 记录文档元数据（取最高分数对应的）
            if result.doc_id not in doc_metadata or \
               result.score > scores.get(result.doc_id + "_raw", 0):
                doc_metadata[result.doc_id] = result
    
    # 按 RRF 分数排序
    sorted_docs = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return [
        FusedResult(
            doc_id=doc_id,
            rrf_score=score,
            metadata=doc_metadata[doc_id]
        )
        for doc_id, score in sorted_docs
    ]
```

**RRF 的优势**：

- 🎯 **简单有效** - 无需训练，规则驱动
- ⚖️ **公平融合** - 平衡不同检索方法的优势
- 🛡️ **鲁棒性** - 单路召回差也不影响整体效果
- ⚡ **高效** - 时间复杂度 O(n log n)

#### 4.5 查询改写与扩展

自动优化用户查询，提升召回效果：

```python
class QueryExpander:
    def __init__(self):
        self.llm = LLMAdapter()
        self.synonym_dict = SynonymDictionary()
    
    async def expand(self, query: str) -> ExpandedQuery:
        # 1. 意图识别
        intent = await self.identify_intent(query)
        
        # 2. 同义词扩展
        synonyms = self.synonym_dict.expand(query)
        
        # 3. LLM 生成扩展查询
        llm_expansions = await self.llm.generate(
            prompt=f"请为以下查询生成3个语义相近但表述不同的查询：\n{query}"
        )
        
        # 4. 领域术语标准化
        standardized = self.standardize_terms(query)
        
        return ExpandedQuery(
            original=query,
            intent=intent,
            expanded_terms=synonyms + [standardized],
            alternative_queries=llm_expansions,
            filters=self.extract_filters(query)
        )
```

**扩展策略**：

- 📚 **同义词扩展** - 税务/税收/税金等效词汇
- 🔄 **表述改写** - "如何办理" → "办理流程/步骤/方法"
- 🏷️ **领域归一化** - 统一专业术语表述
- 🎭 **意图分解** - 复杂查询拆分为多个简单查询

#### 4.6 重排序策略

使用交叉编码器对初筛结果进行精细排序：

```python
class Reranker:
    def __init__(self):
        self.cross_encoder = CrossEncoder()
    
    async def rerank(
        self,
        candidates: List[RetrievedChunk],
        query: Query,
        top_k: int = 10
    ) -> List[RerankedChunk]:
        # 1. 构建 Query-Document 对
        pairs = [(query.text, doc.content) for doc in candidates]
        
        # 2. 批量计算相关性分数
        scores = await self.cross_encoder.predict(pairs)
        
        # 3. 结合原始分数和重排分数
        final_scores = []
        for i, doc in enumerate(candidates):
            combined_score = (
                0.3 * doc.original_score +  # 原始召回分数
                0.7 * scores[i]             # 交叉编码器分数
            )
            final_scores.append((combined_score, doc))
        
        # 4. 排序并返回
        final_scores.sort(reverse=True)
        
        return [
            RerankedChunk(
                doc=doc,
                score=score,
                rank=i + 1
            )
            for i, (score, doc) in enumerate(final_scores[:top_k])
        ]
```

**重排序的作用**：

- 🎯 **精度提升** - 交叉编码器比向量检索更精准
- ⚖️ **分数校准** - 结合多信号进行综合评估
- 📊 **多样性控制** - 避免结果过于集中同一来源
- 🏷️ **质量筛选** - 过滤低质量或无关内容

---

## 🏗️ 技术架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户层                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Web 界面   │  │  移动端     │  │  API 调用   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      前端层 (Vue 3)                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Element Plus  │  Pinia  │  Vue Router  │  Tailwind CSS │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端层 (FastAPI)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│  │  API 路由    │ │  业务逻辑    │ │  Agent 框架  │              │
│  │  /api/v1/*  │ │   Services   │ │   Core      │              │
│  └──────────────┘ └──────────────┘ └──────────────┘              │
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│  │  中间件      │ │  权限认证    │ │  日志审计    │              │
│  │ Middleware  │ │   Security   │ │   Logging   │              │
│  └──────────────┘ └──────────────┘ └──────────────┘              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│                        数据层                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │PostgreSQL│ │  Redis  │ │ Milvus  │ │  Neo4j  │ │  MinIO  │     │
│  │ 数据库   │ │  缓存   │ │ 向量库  │ │  图数据库│ │ 对象存储│     │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│                       AI 服务层                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│  │DeepSeek │ │OpenAI等 │ │  本地   │ │  MCP    │               │
│  │ 推荐使用 │ │ 适配器  │ │ Ollama  │ │ 工具服务 │               │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈详情

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **后端框架** | FastAPI 0.128+ | 异步高性能 API 框架 |
| **数据库** | PostgreSQL 16 + pgvector | 关系型数据存储与向量扩展 |
| **缓存** | Redis 7+ | 会话缓存、频率限制 |
| **向量检索** | PostgreSQL pgvector / ChromaDB | 语义向量检索，当前 Docker Compose 默认使用 pgvector |
| **图数据库** | Neo4j | 知识图谱存储 |
| **对象存储** | MinIO | 文档、图片存储 |
| **前端框架** | Vue 3.4+ | 渐进式 JavaScript 框架 |
| **UI 库** | Element Plus | Vue 3 组件库 |
| **状态管理** | Pinia | Vue 3 状态管理 |
| **LLM** | DeepSeek / OpenRouter 兼容接口等 | 当前推荐 DeepSeek，默认配置可走 OpenRouter 兼容接口 |
| **向量模型** | SiliconFlow / 智谱 / OpenAI 等 | 文档向量化，按环境变量选择 |

> 说明：当前项目推荐使用 DeepSeek。代码中也保留了 OpenAI、Claude、智谱、Qwen、MiniMax 等 LLM 适配器，已检查其导入和初始化路径；真实调用仍取决于用户自己的 API Key、Base URL、模型权限和网络环境。

---

## 📁 项目结构

```
My_rag/
├── rag_backend/                 # 后端服务
│   ├── app/
│   │   ├── api/v1/endpoints/    # API 接口
│   │   │   ├── auth.py          # 认证接口
│   │   │   ├── chat.py          # 对话接口
│   │   │   ├── knowledge.py     # 知识库接口
│   │   │   ├── search.py        # 搜索接口
│   │   │   ├── multi_agent.py   # 多智能体接口
│   │   │   └── ...              # 更多接口
│   │   ├── agent_framework/     # Agent 框架
│   │   │   ├── core/            # 核心实现
│   │   │   ├── llm/             # LLM 适配器
│   │   │   └── tools/           # 工具管理
│   │   ├── multi_agent_system/  # 多智能体系统
│   │   │   ├── agents/          # 专家智能体
│   │   │   └── pipeline/        # 数据处理管道
│   │   ├── models/              # 数据模型
│   │   ├── services/            # 业务逻辑
│   │   ├── memory_system/       # 记忆系统
│   │   ├── knowledge_graph/     # 知识图谱
│   │   ├── langgraph/           # LangGraph 集成
│   │   ├── parsers/             # 文档解析器
│   │   └── chunkers/            # 文档分块
│   ├── .env.example             # 环境变量模板
│   ├── requirements.txt         # Python 依赖
│   ├── Dockerfile               # Docker 配置
│   ├── docker-compose.yml       # Docker Compose 配置
│   └── .dockerignore            # Docker 忽略规则
│
├── rag_frontend/                # 前端应用
│   ├── src/
│   │   ├── api/                 # API 调用
│   │   ├── components/          # 公共组件
│   │   ├── views/               # 页面视图
│   │   ├── stores/              # 状态管理 (Pinia)
│   │   ├── router/              # 路由配置
│   │   ├── types/               # TypeScript 类型
│   │   ├── config/              # 应用配置
│   │   ├── locales/             # 国际化资源
│   │   ├── utils/               # 工具函数
│   │   └── composables/          # Vue Composables
│   ├── .env.example             # 环境变量模板
│   ├── package.json             # NPM 依赖
│   ├── vite.config.ts           # Vite 配置
│   ├── tailwind.config.js       # Tailwind CSS 配置
│   ├── nginx.conf              # Nginx 配置 (Docker 部署)
│   ├── Dockerfile              # Docker 配置 (生产环境)
│   └── README.md                # 前端说明
│
├── mcp_server/                  # MCP 工具服务
│   ├── app/
│   │   ├── tools/               # 工具实现
│   │   │   ├── tax_tools.py     # 税务工具
│   │   │   ├── legal_tools.py   # 法律工具
│   │   │   ├── financial_tools.py # 财务工具
│   │   │   └── enterprise_tools.py # 企业工具
│   │   ├── auth/                # 认证模块
│   │   ├── config.py            # 配置
│   │   └── main.py              # 服务入口
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── README.md                    # 项目总览
└── .gitignore                   # Git 忽略规则
```

---

## 🚀 部署架构

本项目采用**混合部署架构**：

```
┌─────────────────────────────────────────────────────────────────┐
│                         本地环境                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Docker Compose                                          │    │
│  │  ├── PostgreSQL (pgvector)  - 向量数据库                  │    │
│  │  ├── Redis                   - 缓存服务                    │    │
│  │  ├── Neo4j                   - 知识图谱                   │    │
│  │  ├── MinIO                   - 对象存储                   │    │
│  │  └── Backend API             - 后端服务 (FastAPI)         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              │ API 端口 8000                     │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
┌────────────────────────────┐  ┌────────────────────────────┐
│        云端环境            │  │       本地环境              │
│  ┌────────────────────┐    │  │  ┌────────────────────┐    │
│  │  MCP Server         │    │  │  │  Frontend (Nginx)  │    │
│  │  (Docker)           │    │  │  │  npm build         │    │    │
│  │  - 税务计算工具     │    │  │  │  端口 80/5173       │    │
│  │  - 法律匹配工具     │    │  │  └────────────────────┘    │
│  │  - 财务分析工具     │    │  │                            │
│  │  - 企业查询工具     │    │  │                            │
│  └────────────────────┘    │  │                            │
└────────────────────────────┘  └────────────────────────────┘
```

### 环境要求

| 环境 | 组件 | 版本要求 |
|------|------|---------|
| **本地** | Docker & Docker Compose | 20.10+ |
| **本地** | Python | 3.11+ |
| **本地** | Node.js | 18+ |
| **云端** | Docker | 20.10+ |
| **云端** | Python | 3.12+ |

---

## 📦 本地部署（Docker）

### 0. 使用 Docker Desktop 复现运行环境

如果你只是想在自己的电脑上复现本项目的运行环境，不需要手动安装 Python 包、Node 包、PostgreSQL、Redis、Neo4j、MinIO 或 OCR 相关系统库。推荐安装 **Docker Desktop**，由 Docker Compose 一次性启动后端和依赖服务。

#### Windows / macOS 准备

1. 安装 Docker Desktop：[https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. 启动 Docker Desktop，等待左下角/状态栏显示 Docker Engine 正在运行。
3. Windows 用户建议开启 WSL 2 后端，并在 Docker Desktop 设置中确认 WSL integration 已启用。
4. 安装 Git，用于克隆代码。

#### 一键启动后端完整依赖

```bash
git clone https://github.com/Serein-81/My_rag.git
cd My_rag/rag_backend

# 首次运行需要创建本地环境变量文件
cp .env.example .env

# 按需编辑 .env，至少填写数据库、Redis、Neo4j 密码和你要使用的大模型 API Key

# 启动 PostgreSQL/pgvector、Redis、PgBouncer、Neo4j、MinIO 和后端服务
docker compose up -d

# 查看容器状态
docker compose ps

# 查看后端日志
docker compose logs -f backend
```

启动成功后访问：

- 后端 API 文档：http://localhost:8000/docs
- 后端健康检查：http://localhost:8000/health
- MinIO 控制台：http://localhost:9001
- Neo4j Browser：http://localhost:7474

停止环境：

```bash
cd My_rag/rag_backend
docker compose down
```

清理本地数据卷/数据目录前请先确认不再需要已有数据。当前 compose 使用 `rag_backend` 目录下的 `postgres_data/`、`redis_data/`、`neo4j_data/`、`minio_data/` 等目录保存数据。

#### 使用已发布的后端镜像（可选）

如果不想在本地重新构建后端镜像，可以拉取 GitHub Container Registry 中发布好的镜像。该镜像由 GitHub Actions 的 **Docker Build** 工作流手动发布，成功发布后会生成以下标签：

- `main`：主分支最新发布镜像
- `latest`：最新发布镜像
- `<commit-sha>`：对应提交的精确镜像

先确认镜像可以匿名拉取：

```bash
docker pull ghcr.io/serein-81/rag-backend:main
```

也可以拉取：

```bash
docker pull ghcr.io/serein-81/rag-backend:latest
```

如果出现 `unauthorized`，说明 GHCR package 还没有公开，或 `Docker Build` 工作流尚未成功发布该标签。此时仍可使用默认的 `docker compose up -d` 在本地构建并运行项目。

要让 Docker Compose 使用这个远端镜像，需要把 `rag_backend/docker-compose.yml` 中 `backend` 服务的 `build:` 配置改为：

```yaml
backend:
  image: ghcr.io/serein-81/rag-backend:main
```

然后再运行：

```bash
docker compose up -d
```

普通复现建议直接使用本仓库默认的 `docker compose up -d`，它会按当前代码在本地构建镜像，更适合调试和二次开发。

### 1. 克隆项目

```bash
git clone https://github.com/Serein-81/My_rag.git
cd My_rag
```

### 2. 配置后端环境变量

```bash
cd rag_backend

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置必要的环境变量
# 至少需要配置：
# - POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
# - REDIS_PASSWORD
# - NEO4J_PASSWORD
# - LLM 提供商的 API Key
```

### 3. 启动基础服务（PostgreSQL, Redis, Neo4j, MinIO, Backend）

```bash
cd rag_backend

# 使用 Docker Compose 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend
```

**Docker Compose 包含的服务：**

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| PostgreSQL | rag_db | 5432 | 向量数据库 |
| Redis | rag_redis | 6379 | 缓存服务 |
| PgBouncer | rag_pgbouncer | 6432 | PostgreSQL 连接池 |
| Neo4j | rag_neo4j | 7474, 7687 | 知识图谱 |
| MinIO | rag_minio | 9000, 9001 | 对象存储 |
| Backend | rag_backend | 8000 | 后端 API |
| Unstructured API | rag_unstructured_api | 8001 | 重型文档解析服务，需 `--profile heavy` 或 `--profile full` |

### 4. 验证后端服务

```bash
# 检查后端健康状态
curl http://localhost:8000/health
curl http://localhost:8000/health/quick

# 访问 API 文档
# http://localhost:8000/docs
```

如只需确认 API 进程是否存活，也可以访问：

```bash
curl http://localhost:8000/api/health
```

### 5. 数据库初始化

首次部署需要执行数据库迁移：

```bash
# 进入后端容器
docker exec -it rag_backend bash

# 运行数据库迁移
alembic upgrade head

# 创建初始超级管理员用户
python -m app.scripts.create_admin --email admin@example.com --password your_password

# 退出容器
exit
```

---

## 🔑 必需 API 密钥配置指南

### 必需密钥（必须配置）

#### 1. LLM 大模型 API

系统支持多种大模型提供商，**推荐优先使用 DeepSeek**。其它供应商适配器已检查导入和初始化路径；真实调用需要根据对应平台的 API Key、Base URL、模型权限和网络环境确认。

| 提供商 | 环境变量 | 获取地址 | 说明 |
|--------|----------|----------|------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | [DeepSeek Platform](https://platform.deepseek.com/) | **推荐使用，当前项目主要验证路径** |
| 智谱 AI | `ZHIPU_API_KEY` | [智谱AI开放平台](https://open.bigmodel.cn/) | 已有适配器，需配置平台密钥 |
| OpenAI | `OPENAI_API_KEY` | [OpenAI Platform](https://platform.openai.com/) | 已有适配器，需配置平台密钥 |
| Claude | `CLAUDE_API_KEY` | [Anthropic Console](https://console.anthropic.com/) | 已有适配器，需配置平台密钥 |
| 硅基流动 | `SILICONFLOW_API_KEY` | [硅基流动](https://siliconflow.cn/) | 主要用于 Embedding/Rerank，也可按需接入模型 |

**推荐配置示例（使用 DeepSeek）：**

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek/deepseek-chat-v3-0324
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

#### 2. 数据库密码

```env
# PostgreSQL
POSTGRES_PASSWORD=your_secure_postgres_password

# Redis
REDIS_PASSWORD=your_secure_redis_password

# Neo4j 图数据库
NEO4J_PASSWORD=your_secure_neo4j_password
```

#### 3. 安全密钥

```env
# JWT 认证密钥（至少32位字符）
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

---

### 可选密钥（根据需要配置）

#### 1. Embedding 向量化 API

用于将文档和查询转换为向量：

```env
# 智谱 AI Embedding（与 LLM 共享密钥）
EMBEDDING_PROVIDER=zhipu
ZHIPU_EMBEDDING_MODEL=embedding-3

# 或使用硅基流动
EMBEDDING_PROVIDER=siliconflow
SILICONFLOW_API_KEY=your_siliconflow_api_key
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
```

#### 2. 天气查询 API（可选）

```env
# 和风天气 API
QWEATHER_API_KEY=your_qweather_api_key
QWEATHER_WEATHER_HOST=your_host
QWEATHER_GEO_HOST=your_host
```
获取地址：[和风天气开发者平台](https://dev.qweather.com/)

#### 3. 地图 API（可选）

```env
# 高德地图 API
GAODE_API_KEY=your_gaode_api_key
```
获取地址：[高德开放平台](https://lbs.amap.com/)

#### 4. 搜索增强 API（可选）

```env
# Tavily 搜索 API
TAVILY_API_KEY=your_tavily_api_key
```
获取地址：[Tavily](https://tavily.com/)

#### 5. 短信服务 API（可选，用于用户注册验证）

```env
# 阿里云短信服务
ALIYUN_ACCESS_KEY_ID=your_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_access_key_secret
ALIYUN_SMS_SIGN_NAME=签名名称
ALIYUN_SMS_TEMPLATE_CODE=SMS_xxx
```

#### 6. LangSmith 追踪（可选，用于调试和分析）

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=financial_rag
```
获取地址：[LangSmith](https://smith.langchain.com/)

---

### MinIO 对象存储配置

MinIO 用于存储上传的文档和文件：

```env
# MinIO 访问凭证（Docker Compose 中已设置默认值）
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# 存储桶名称
MINIO_BUCKET=documents
MINIO_AVATAR_BUCKET=avatars
```

**注意**：生产环境中请务必修改默认的 Access Key 和 Secret Key。

---

### 完整 .env 配置示例

```env
# ==========================================
# 项目基础配置
# ==========================================
PROJECT_NAME="RAG Knowledge Base"

# ==========================================
# 数据库配置 (PostgreSQL)
# ==========================================
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=your_secure_postgres_password
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db

# ==========================================
# 安全配置
# ==========================================
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ==========================================
# LLM 大模型配置（必需）
# ==========================================
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek/deepseek-chat-v3-0324
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ==========================================
# MinIO 对象存储
# ==========================================
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET=documents
MINIO_AVATAR_BUCKET=avatars

# ==========================================
# Redis
# ==========================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_secure_redis_password

# ==========================================
# Neo4j 图数据库
# ==========================================
ENABLE_KNOWLEDGE_GRAPH=false
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_neo4j_password

# ==========================================
# Embedding 向量化
# ==========================================
EMBEDDING_PROVIDER=zhipu
SILICONFLOW_API_KEY=your_siliconflow_api_key_here
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
```

---

## 🔧 云端 MCP 服务部署（Docker）

MCP 服务部署在云端，为后端提供远程工具调用能力。

### 1. 准备云端环境

```bash
# 在云服务器上安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
```

### 2. 上传 MCP 服务代码

```bash
# 在云服务器上创建目录
mkdir -p /opt/mcp_server
cd /opt/mcp_server

# 上传 mcp_server 目录内容
# 可以使用 scp、rsync 或 git clone
scp -r mcp_server/* user@your-cloud-server:/opt/mcp_server/
```

### 3. 配置 MCP 服务

```bash
cd /opt/mcp_server

# 创建环境变量文件
cat > .env << EOF
# MCP 服务配置
MCP_HOST=0.0.0.0
MCP_PORT=8000

# API 认证
MCP_API_KEY=your_mcp_api_key_here
EOF
```

### 4. 构建并启动 MCP 服务

```bash
cd /opt/mcp_server

# 构建 Docker 镜像
docker build -t mcp-server .

# 运行容器
docker run -d \
  --name mcp-server \
  -p 8080:8080 \
  --env-file .env \
  --restart unless-stopped \
  mcp-server

# 查看日志
docker logs -f mcp-server
```

### 5. 验证 MCP 服务

```bash
# 检查服务健康状态
curl http://your-cloud-server:8080/health

# 测试工具调用
curl -X POST http://your-cloud-server:8080/tools/tax_calculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_mcp_api_key_here" \
  -d '{"amount": 300000, "tax_type": "vat_small"}'
```

### 6. 配置后端连接 MCP

在本地 `rag_backend/.env` 中添加：

```env
# MCP 服务地址（云端）
MCP_SERVER_URL=http://your-cloud-server:8080
MCP_API_KEY=your_mcp_api_key_here
```

---

## 🌐 前端部署（npm）

### 方式一：本地开发

```bash
cd rag_frontend

# 安装依赖
npm install

# 复制环境变量
cp .env.example .env
# 编辑 .env 配置 API 地址

# 启动开发服务器
npm run dev

# Vite 默认访问 http://localhost:5173
```

### 方式二：Docker 部署生产环境

```bash
cd rag_frontend

# 复制环境变量并配置生产环境地址
cp .env.example .env
# 编辑 .env：
# VITE_API_BASE_URL=http://your-backend-server:8000

# 构建 Docker 镜像
docker build -t rag-frontend .

# 运行容器
docker run -d \
  --name rag-frontend \
  -p 80:80 \
  --env-file .env \
  --restart unless-stopped \
  rag-frontend

# 访问 http://localhost
```

### 方式三：静态资源部署（npm build）

```bash
cd rag_frontend

# 安装依赖
npm install

# 配置生产环境
cp .env.example .env
# 编辑 .env 配置 API 地址

# 构建生产版本
npm run build

# 上传 dist 目录到 Web 服务器（Nginx/Apache）
scp -r dist/* user@your-server:/var/www/html/
```

**Nginx 配置示例：**

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/html;
    index index.html;

    location /api/ {
        proxy_pass http://your-backend-server:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 🔧 配置说明

### 本地后端环境变量

复制 `rag_backend/.env.example` 为 `rag_backend/.env`，配置以下关键项：

```env
# ==========================
# 数据库配置 (本地 Docker)
# ==========================
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=rag_db
POSTGRES_PORT=5432

# ==========================
# Redis 配置 (本地 Docker)
# ==========================
REDIS_PASSWORD=your_redis_password
REDIS_PORT=6379
REDIS_DB=0

# ==========================
# Neo4j 配置 (本地 Docker)
# ==========================
NEO4J_PASSWORD=your_neo4j_password

# ==========================
# LLM 配置
# ==========================
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_MODEL=deepseek/deepseek-chat-v3-0324
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ==========================
# MCP 服务配置 (云端)
# ==========================
# MCP_MODE=auto   # auto=本地进程内+云端(默认); local=仅本地 mcp_server; cloud=仅云端
# MCP_LOCAL_URL=http://127.0.0.1:8001  # 仅 MCP_MODE=local 时使用
MCP_SERVER_URL=http://your-cloud-server:8080
MCP_API_KEY=your_mcp_api_key
```

### 前端环境变量

复制 `rag_frontend/.env.example` 为 `rag_frontend/.env`：

```env
# API 地址（指向本地后端）
VITE_API_BASE_URL=http://localhost:8000

# 如果前后端分开部署，修改为实际地址：
# VITE_API_BASE_URL=http://your-backend-server:8000
```

---

## ✅ 部署检查清单

### 环境准备
- [ ] Docker 和 Docker Compose 已安装（版本 20.10+）
- [ ] Git 已安装
- [ ] 代码已克隆到本地

### 后端配置
- [ ] 已复制 `rag_backend/.env.example` 为 `.env`
- [ ] `SECRET_KEY` 已配置（至少32位字符）
- [ ] 数据库密码已配置（PostgreSQL、Redis）
- [ ] **LLM API Key 已配置**（至少一种大模型）
- [ ] 数据库迁移已执行（`alembic upgrade head`）
- [ ] 初始管理员用户已创建

### Docker 服务状态
- [ ] PostgreSQL 服务运行正常（端口 5432）
- [ ] Redis 服务运行正常（端口 6379）
- [ ] Neo4j 服务运行正常（端口 7474, 7687）
- [ ] MinIO 服务运行正常（端口 9000, 9001）
- [ ] 后端 API 服务运行正常（端口 8000）

### 验证访问
- [ ] 后端 API 可访问： http://localhost:8000/docs
- [ ] MinIO Web 控制台可访问： http://localhost:9001 （账号：minioadmin）
- [ ] Neo4j Web 控制台可访问： http://localhost:7474
- [ ] 健康检查接口正常：`curl http://localhost:8000/health/quick`

### 功能测试
- [ ] 用户注册/登录功能正常
- [ ] 知识库创建成功
- [ ] 文档上传功能正常
- [ ] 文档检索功能正常
- [ ] AI 对话功能正常
- [ ] 多智能体协作正常

### 生产环境额外检查
- [ ] 已修改 MinIO 默认密码
- [ ] 已配置 HTTPS/SSL 证书
- [ ] 防火墙已正确配置
- [ ] 数据库已配置定期备份
- [ ] 日志系统已配置

### LLM 模型切换

当前推荐使用 DeepSeek。系统代码中保留多种 LLM 提供商适配器，已检查导入和初始化路径；切换到其它供应商时，请确认对应平台的 API Key、Base URL、模型权限和网络环境。

```env
# DeepSeek（推荐，当前主要验证路径）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL=deepseek/deepseek-chat-v3-0324
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key

# Claude
LLM_PROVIDER=claude
CLAUDE_API_KEY=your_key

# 智谱 AI
LLM_PROVIDER=zhipu
ZHIPU_API_KEY=your_key

# 本地 Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 🔧 常见问题排查

### 数据库连接失败
```bash
# 检查 PostgreSQL 容器状态
docker compose ps db

# 查看 PostgreSQL 日志
docker compose logs db

# 测试数据库连接
docker exec -it rag_db psql -U rag_user -d rag_db -c "SELECT 1;"
```

### 后端启动失败
```bash
# 查看后端日志
docker compose logs backend

# 常见原因：
# 1. .env 文件未配置或配置错误
# 2. 数据库未启动或连接失败
# 3. API Key 配置错误
```

### MinIO 无法访问
```bash
# 检查 MinIO 容器状态
docker compose ps minio

# 验证 MinIO 健康状态
docker exec -it rag_minio mc ready local
```

### API 认证问题
```bash
# 确认 SECRET_KEY 已配置
grep SECRET_KEY rag_backend/.env

# 重启后端服务
docker compose restart backend
```

---

## 📖 相关文档

### 核心文档

| 文档 | 说明 |
|------|------|
| [前端 README](rag_frontend/README.md) | 前端应用详细说明 |
| [MCP README](mcp_server/README.md) | MCP 工具服务说明 |
| [Agent 框架说明](rag_backend/app/agent_framework/README.md) | Agent 框架设计文档 |
| [记忆系统说明](rag_backend/app/memory_system/README.md) | 记忆系统设计文档 |

### 项目文档

| 文档 | 说明 |
|------|------|
| [项目介绍文档](rag_backend/项目介绍文档.md) | 项目整体介绍 |
| [多智能体实施方案](rag_backend/财税法务多智能体实施方案.md) | 多智能体系统实施方案 |
| [问题与解决方案](rag_backend/项目开发中遇到的问题和解决方案.md) | 开发中遇到的问题记录 |

### 进阶文档

- [多智能体协作系统设计](rag_backend/mass_/COLLABORATION_SYSTEM_DESIGN.md)
- [MCP 架构设计](rag_backend/mass_/MCP_ARCHITECTURE_DESIGN.md)
- [人类记忆系统设计](rag_backend/app/memory_system/HUMAN_MEMORY_SYSTEM.md)
- [知识图谱使用指南](rag_backend/知识图谱使用指南.md)
- [OCR 集成指南](rag_backend/OCR_INTEGRATION_GUIDE.md)
- [日志系统集成指南](rag_backend/日志系统集成指南.md)

---

## 🎯 核心模块说明

### Agent 框架

自研的轻量级 Agent 框架，支持多种推理模式：

```python
from app.agent_framework.core.react_agent import ReActAgent

# 创建 Agent
agent = ReActAgent(
    name="税务专家",
    tools=[calculate_tax, search_regulations],
    llm_adapter=zhipu_adapter
)

# 执行推理
result = await agent.run("小规模纳税人季度销售额30万，增值税如何计算？")
```

### 工具系统

灵活的外部工具集成机制：

```python
from app.agent_framework.tools.hybrid_manager import HybridToolManager

# 注册自定义工具
manager = HybridToolManager()
manager.register_custom_tool(my_tool)
manager.register_langchain_tool(langchain_tool)
```

### 检索增强

混合检索 + 知识图谱增强：

```python
from app.services.hybrid_search import HybridSearchService

searcher = HybridSearchService()
results = await searcher.search(
    query="企业所得税优惠政策",
    top_k=10,
    enable_knowledge_graph=True
)
```

---

## 🧪 测试

### 后端测试

```bash
cd rag_backend

# 运行所有测试
pytest

# 运行指定模块测试
pytest tests/api/test_chat.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

### 前端测试

```bash
cd rag_frontend

# 当前 package.json 提供的脚本
npm run dev
npm run build
npm run preview

# 类型检查可直接调用本地 vue-tsc
npx vue-tsc --noEmit
```

---

## 📝 API 示例

### 聊天对话

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "企业所得税税率是多少？",
    "session_id": "xxx",
    "knowledge_base_ids": ["kb_001"]
  }'
```

### 文档上传

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf" \
  -F "knowledge_base_id=kb_001"
```

### 语义搜索

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "研发费用加计扣除条件",
    "top_k": 5
  }'
```

---

## 🛡️ 安全特性

- 🔐 **JWT 认证** - Token 过期机制
- 🏢 **租户隔离** - 数据完全隔离
- 👥 **角色权限** - RBAC 权限控制
- 📋 **审计日志** - 完整操作记录
- 🔒 **敏感信息加密** - 密码、密钥加密存储
- 🚫 **频率限制** - API 频率限制防护

---

## 🚦 HITL（Human-In-The-Loop）人工介入系统

### 📖 概述

HITL（Human-In-The-Loop）是一种 **AI 安全机制**，用于在高风险操作执行前，需要人工审批确认的场景。当用户通过 AI 助手发起涉及敏感操作的请求时，系统会自动暂停并等待管理员审批。

### 🎯 核心功能

| 功能 | 说明 |
|------|------|
| **风险检测** | 自动识别高风险 AI 操作 |
| **审批工作流** | 创建审批请求，等待管理员处理 |
| **实时通知** | 通过 WebSocket 推送通知给管理员 |
| **审计日志** | 记录所有高风险操作和审批决策 |

### 🔍 检测的10种高风险行为

| 行为类型 | 触发关键词 | 风险级别 |
|---------|----------|---------|
| **批量删除** | 批量删除、删除全部、清空、删除所有 | 🔴 高 |
| **敏感数据导出** | 导出敏感数据、导出全部数据、下载敏感信息 | 🔴 高 |
| **系统配置修改** | 修改系统配置、系统设置、配置变更 | 🔴 高 |
| **大额费用审批** | 大额审批、高额费用、巨额支出 | 🔴 高 |
| **税务申报** | 税务申报、纳税申报、报税 | 🟡 中 |
| **合同生成** | 生成合同、创建合同、合同模板 | 🟡 中 |
| **审计请求** | 审计请求、合规检查、合规审计 | 🟡 中 |
| **用户权限变更** | 修改权限、变更角色、用户权限 | 🟡 中 |
| **批量数据修改** | 批量修改、批量更新、批量编辑 | 🟡 中 |
| **外部数据共享** | 外部共享、数据外发、导出到外部 | 🔴 高 |

### 📊 风险级别判定

| 级别 | 阈值 | 处理方式 |
|------|------|---------|
| 🟢 LOW | 0-0.3 | 无需审批，正常执行 |
| 🟡 MEDIUM | 0.3-0.6 | 创建审批，通知管理员 |
| 🔴 HIGH | 0.6-0.8 | 创建审批，通知管理员，标记高优先级 |
| ⚫ CRITICAL | >0.8 | 创建审批，通知所有管理员，强制阻断 |

### 🔄 工作流程

```
用户输入 → AI意图识别 → 风险检测
                         │
                         ▼
              ┌─────────────────────┐
              │  风险级别判定        │
              └─────────────────────┘
                    │         │
           LOW     │         │  MEDIUM/HIGH/CRITICAL
            │      │         │
            ▼      │         ▼
      正常执行      │   创建HITL审批
                    │         │
                    │         ▼
                    │   通知所有管理员
                    │         │
                    │         ▼
                    │   等待审批 (批准/拒绝)
                    │         │
                    │    ┌────┴────┐
                    │    │         │
                    │ 批准       拒绝
                    │    │         │
                    │    ▼         ▼
                    │  执行   返回拒绝原因
```

### 📂 核心组件

#### 1. 管理员通知服务 (`app/services/admin_notification_service.py`)

```python
class AdminNotificationService:
    """管理员通知服务"""
    
    async def detect_risk_level(self, user_query: str) -> tuple[RiskLevel, List[HighRiskBehavior]]:
        """检测用户查询的风险级别"""
        
    async def create_hitl_request(self, ...) -> Dict[str, Any]:
        """创建HITL审批请求"""
        
    async def notify_admins(self, tenant_id: str, notification_type: str, title: str, message: str):
        """通知所有管理员"""
        
    async def handle_high_risk_operation(self, user_id: str, tenant_id: str, ...) -> Dict[str, Any]:
        """处理高风险操作的主要入口"""
```

#### 2. HITL API 端点 (`app/api/v1/endpoints/multi_agent.py`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/multi-agent/hitl/pending` | GET | 获取待审批的HITL请求 |
| `/api/v1/multi-agent/hitl/history` | GET | 获取审批历史记录 |
| `/api/v1/multi-agent/hitl/approve` | POST | 创建HITL审批请求 |
| `/api/v1/multi-agent/hitl/{approval_id}/review` | POST | 审核/批准/拒绝审批请求 |
| `/api/v1/multi-agent/rbac/roles` | GET | 获取用户角色列表 |
| `/api/v1/multi-agent/rbac/policies` | GET | 获取RBAC策略列表 |

### 💻 使用示例

#### 1. 前端 HITL 审批界面

访问 `/hitl-approval` 查看待审批请求：

```vue
<template>
  <div class="hitl-approval">
    <el-table :data="pendingApprovals">
      <el-table-column prop="user_id" label="申请人" />
      <el-table-column prop="risk_level" label="风险级别" />
      <el-table-column prop="operation" label="操作类型" />
      <el-table-column prop="created_at" label="申请时间" />
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button @click="approve(row)">批准</el-button>
          <el-button @click="reject(row)">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
```

#### 2. API 调用示例

```bash
# 获取待审批请求
curl -X GET http://localhost:8000/api/v1/multi-agent/hitl/pending \
  -H "Authorization: Bearer $TOKEN"

# 批准审批请求
curl -X POST http://localhost:8000/api/v1/multi-agent/hitl/{approval_id}/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "notes": "审批通过"
  }'
```

### 🔧 配置说明

#### 风险关键词配置

在 `app/services/admin_notification_service.py` 中配置：

```python
RISK_KEYWORDS = {
    HighRiskBehavior.BULK_DELETE: ["批量删除", "删除全部", "清空"],
    HighRiskBehavior.SENSITIVE_DATA_EXPORT: ["导出敏感数据", "导出全部数据"],
    # 添加更多风险关键词...
}
```

#### 风险阈值配置

```python
RISK_THRESHOLDS = {
    RiskLevel.LOW: 0.0,
    RiskLevel.MEDIUM: 0.3,
    RiskLevel.HIGH: 0.6,
    RiskLevel.CRITICAL: 0.8,
}
```

### 📱 通知机制

#### 1. WebSocket 实时推送

管理员登录后，通过 WebSocket 接收实时通知：

```javascript
// 前端 WebSocket 连接
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/groups/{group_id}?token=YOUR_JWT');

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  if (notification.type === 'hitl_approval_required') {
    showNotification(notification.title, notification.message);
  }
};
```

#### 2. Redis 消息队列

支持离线通知存储，通过 Redis 队列管理：

```python
# 通知存储到 Redis
notification_key = f"notification:admin:{tenant_id}"
redis.client.lpush(notification_key, json.dumps(notification))
redis.client.expire(notification_key, 604800)  # 7天过期
```

### 🎨 设计亮点

1. **智能检测** - 基于关键词和上下文分析，自动识别高风险操作
2. **多层防护** - 风险检测 + 审批机制 + 实时通知 + 审计日志
3. **无缝集成** - 已集成到多智能体编排系统，无需修改前端
4. **灵活扩展** - 易于添加新的风险检测规则和审批流程
5. **实时通知** - WebSocket + Redis 双重通知机制

### 📈 未来扩展方向

- [ ] 支持自定义风险检测规则
- [ ] 添加机器学习模型进行风险预测
- [ ] 支持多级审批流程
- [ ] 集成邮件/短信通知
- [ ] 添加操作超时自动处理机制

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)

---

## 📬 联系方式

- 负责人：陈
- 邮箱：chenjh8181@gmail.com


---

<div align="center">

**如果这个项目对你有帮助，请给我们一个 ⭐**

</div>
