# RAG 知识库系统 — 财税法务智能协作平台

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688?logo=fastapi)
![Vue.js](https://img.shields.io/badge/Vue_3-3.4+-42b883?logo=vue.js)
![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-FF6F00)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-336791?logo=postgresql)
![Neo4j](https://img.shields.io/badge/Neo4j-5.15-4581C3?logo=neo4j)
![Docker](https://img.shields.io/badge/Docker-24+-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

**自研 Agent 框架 · 多智能体 LangGraph 编排 · 知识图谱增强 · 12 家 LLM 全适配**

[设计亮点](#-设计亮点) · [系统架构](#-系统架构) · [核心特性](#-核心特性详解) · [部署](#-本地部署docker) · [API](#-后端-api-分组)

</div>

---

## 📋 项目概述

本项目是一套**面向财税法务专业领域的 RAG（Retrieval-Augmented Generation）知识库平台**，围绕"检索增强 + 多智能体协作 + 知识图谱"三大核心能力构建。

系统采用 **FastAPI + Vue 3** 前后端分离架构，后端 200+ 源文件、50 个 API 路由模块、100+ 业务服务文件。核心模块包括自研的 **ReAct/Plan/Reflect Agent 框架**、基于 **LangGraph StateGraph** 的多专家并行编排引擎（含 CRAG 检索自校正与忠实度校验闭环）、**领域感知的文档解析/分块体系**（财务/税务/法务/通用四领域自适应路由）、以及带类型约束的 **Neo4j 知识图谱提取管线**。支持 DeepSeek / OpenAI / Claude / 智谱 / Qwen / Ollama 等 12 家大模型厂商，通过工厂模式实现零代码切换。

### 核心能力矩阵

| 能力维度 | 技术实现 | 关键指标 |
|----------|----------|----------|
| **智能问答** | RAG + ReAct Agent + 原生 Function Calling | 支持 SSE 流式、断线恢复、异步轮询 |
| **知识管理** | 6 类结构化解析器 + 9 种分块器（领域自适应路由） + 自动向量化 | 财务/税务/法务/通用四领域自适应 |
| **专业智能体** | 自研框架 + LangGraph 编排 + 多专家并行 | 37 个 MCP 工具（27 本地 + 10 云端），专家最多 5 轮工具循环 |
| **混合检索** | Dense(pgvector) + Sparse(BM25) → RRF → Rerank | Context Recall 0.89, Precision 0.79 |
| **知识图谱** | Neo4j + 领域类型约束实体/关系提取 | 21 种实体类型 + 24 种关系类型 |
| **企业级安全** | 多租户隔离 + RBAC + HITL 人工审核 + 熔断 | JWT 黑名单、10 类高风险行为检测 |

### 架构特点 — 为什么这样设计

| 设计选择 | 常规方案 | 我们的方案 | 设计意图 |
|----------|----------|------------|----------|
| **Agent 执行** | LangChain Agent | **自研 ReAct/Plan/Reflect 框架** | 轻量可控，摆脱 LangChain 臃肿依赖 |
| **Agent 编排** | 硬编码 if-else | **LangGraph StateGraph 状态机** | 可视化流程 + CRAG 检索自校正 + 忠实度校验闭环 |
| **工具调用** | LLM 输出 JSON → 正则解析 | **OpenAI tools 参数 → 结构化 tool_calls** | API 级可靠性，杜绝解析失败 |
| **文档处理** | 通用固定窗口分块 | **领域感知自适应分块 + AST/表格原子化** | 专业文档结构不丢失 |
| **LLM 接入** | 单一厂商绑定 | **适配器工厂模式，10+ 厂商零代码切换** | 不被任何厂商锁定 |
| **知识图谱** | 通用 NER | **类型约束 LLM 提取 + 正则预筛 + 四层校验** | 杜绝幻觉，精确可控 |
| **上下文管理** | 简单截断 | **三级压缩：去冗余 → JSON 摘要 → 滚动压缩** | 多轮对话不溢出 |
| **多租户隔离** | SET LOCAL / RLS | **ContextVar 传播 + Repository 层显式过滤** | PgBouncer 兼容，无数据库绑定 |

---

## 🎯 设计亮点

### 双 Agent 框架架构

系统独有**两层 Agent 架构**，兼顾编排灵活性与执行可控性：

```
LangGraph 状态机（编排层）          专家执行层（multi_agent_system + agent_framework）
┌────────────────────────┐       ┌──────────────────────────────┐
│ Intent Router           │       │ Specialist Agents            │
│   → 三级降级路由         │       │   → 原生 Function Calling    │
│ CRAG 检索闭环           │       │   → 最多 5 轮并行工具循环      │
│   → 评分→改写→重检索     │  ──→  │ ReActAgent（自研框架）        │
│ Faithfulness Checker    │       │   → 推理-行动-观察循环        │
│   → 逐句校验→重生成      │       │   → 循环检测+语义去重+提前终止 │
│ Reflection Gate         │       │ ContextOptimizer             │
│   → 质量审查 + 重试(≤3)  │       │   → 三级压缩防 Context 溢出   │
│ Aggregator/Synthesizer  │       │ Token 预算（tiktoken 精确计数）│
└────────────────────────┘       └──────────────────────────────┘
```

**为什么需要两层？** LangGraph 负责宏观调度（选哪个专家、检索质量是否达标、要不要反思），专家执行层负责微观执行（Function Calling 工具循环、循环检测、上下文压缩）。这种分层避免了 LangChain 的臃肿，同时保留了灵活的状态机编排能力。

### 原生 Function Calling — 彻底告别正则解析

| 演进阶段 | 工具调用方式 | 可靠性 |
|---------|-------------|--------|
| ~~旧方案~~ | LLM 输出 JSON 文本 → 正则匹配 → 提取参数 | ❌ 格式不稳定，频繁失败 |
| **当前方案** | API `tools` 参数传入定义 → 结构化 `tool_calls` 返回 | ✅ API 级保证 |
| **多轮循环** | `max_tool_rounds=5`，每轮都传 tools，多个 `tool_calls` 经 `asyncio.gather` 并行执行 | ✅ 自主决策停止 |

> 实现位置：`multi_agent_system/agents/base_specialist.py`（编排层专家走原生 Function Calling）。自研框架中的 `ReActAgent` 保留文本协议解析路径，并配套语义循环检测/连续失败计数等防护，供独立 Agent 场景使用。

### 领域感知文档处理 — 分块器体系

`DomainDetector` 三级路由（用户指定 → 文件名启发 → LLM 分类）自动选择领域分块器，配套 AST 净化、元数据注入、实体消解、摘要生成、关系构建五个管道组件：

| 领域 | 分块器 | 核心技术 |
|------|--------|----------|
| **财务** | `FinancialChunker` | 表格原子化（不切碎），指标实体提取，正文↔表格 PARENT/CHILD |
| **税务** | `TaxChunker` | 条款级正则（按「第X条」），生命周期打标，PREVIOUS/NEXT 链 |
| **法务** | `LegalChunker` | AST 双层节点（章节 PARENT + 条款 LEAF），异步实体替换 |
| **通用** | `GeneralChunker` | Auto-Merging 双粒度（256-token 精准 + 1024-token 上下文展开） |
| **兜底/语义** | `AdaptiveChunker` / `PropositionChunker` | LLM 语义边界切分 / 原子命题提取，另有 Markdown、纯文本、结构化文档三种基础策略 |

### 知识图谱 — 类型约束的提取管线

区别于通用 NER，系统预设 21 种实体类型 + 24 种关系类型，采用**两阶段提取 + 多层校验**：

```
文本 → 规则预提取(60%+) → LLM 补全(复杂) → 类型白名单 → 置信度≥0.7 → 关系源验证 → Neo4j
      ↑ 正则+字典          ↑ 仅规则未覆盖    ↑ 21种限定    ↑ 自动过滤     ↑ source须存在
```

### 混合检索链路

```
查询 → Dense(pgvector HNSW) + Sparse(BM25 tsvector)
     → RRF 融合 → Cross-Encoder Reranker → MMR 多样性
     → Cliff Prune → 关系展开 → Prompt 组装
```

**RAGAS 评估**（跨财务/税务/法务，DeepSeek 裁判）：Context Recall **0.89** | Precision **0.79** | Faithfulness **0.75**

### Agent Skill 系统

受 Claude Code Skills 规范启发的自研框架，三级渐进加载（元数据 → SKILL.md → scripts/references），域范围隔离（`skills/{finance,tax,legal,public}/`），内置 7 个技能。**Skills ≠ Tools**：Tools 是原子 API 调用，Skills 是包含引导流程的完整业务工作流。

---

## 🏛️ 项目组成

本项目采用前后端分离架构，包含以下主要模块：

<details>
<summary>📋 项目组成（点击展开）</summary>

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| **[前端应用](./rag_frontend)** | Vue 3 + TypeScript | 企业级 Web 应用界面，包含完整的用户交互体验 |
| **[后端服务](./rag_backend)** | FastAPI + Python | RESTful API 服务，提供核心业务逻辑和 AI 能力 |
| **[MCP 工具服务](./mcp_server)** | Python | 财税法务领域专用工具接口，支持 MCP 标准协议（可扩展功能，需云端服务器） |

</details>

### 🚀 快速访问

- 📱 **前端界面**：[查看前端 README](./rag_frontend/README.md)
- ⚙️ **后端 API**：[查看后端项目](./rag_backend)
- 🔧 **MCP 服务**：[查看 MCP 服务](./mcp_server)

### 🐳 直接拉取 Docker 镜像

```bash
docker pull ghcr.io/serein-81/rag-backend:latest
```

详细部署方式见下方 Docker Compose 章节。

### 🔎 重点功能入口

- ⚙️ **模型配置中心**：管理员可在 `/settings/models` 一页配置三类模型——对话（按租户·主对话/金融/税务/法务专家）/ 向量（部署级·维度强校验保护索引）/ 重排（部署级·启用开关）；本地 Ollama 一等公民、不改 `.env`、附带使用概览（各企业当前生效模型 + 最近对话实际模型 + 各模型调用次数）。
- 🧰 **智能体工具构建器**：管理员可在 `/custom-tools` 通过自然语言生成工具规格和代码草稿，发布后的配置型工具可供同企业成员查看和使用。
- 🕸️ **知识图谱编辑器**：用户可在 `/knowledge-graph-editor` 加载中心实体子图，增删实体与关系，导入/导出 JSON 图谱，并将编辑结果保存回 Neo4j。
- 📥 **拉取项目并启动**：执行 `git clone https://github.com/Serein-81/financial_rag.git` 后进入 `financial_rag/rag_backend`，可用 `docker compose up -d` 快速启动后端依赖与服务；完整步骤见下方“本地快速启动”。

### 💡 前端亮点

前端采用 **Vue 3 + TypeScript** 构建，提供企业级用户体验：

<details>
<summary>💡 前端功能亮点（点击展开）</summary>

| 功能模块 | 说明 |
|---------|------|
| 🤖 **智能对话** | 单/多智能体对话、群组聊天、流式输出 |
| 🧰 **智能体工具** | 自然语言生成工具规格、生成代码草稿、测试入参、发布配置型工具、企业内共享 |
| 🕸️ **知识图谱编辑** | D3 可视化图谱、中心实体探索、实体/关系编辑、JSON 导入导出、Neo4j 保存 |
| 💼 **企业管理** | 知识库管理、财务数据、政策服务 |
| 📊 **工作流** | 税务申报、合同审查、安全审计 |
| 🔧 **系统工具** | Agent 监控、意图分类、人机协作 |
| 📈 **数据可视化** | 分析仪表板、实时监控、图表展示 |
| 🎨 **交互体验** | 动画效果、骨架屏、国际化支持 |

</details>


## ✨ 核心特性

### 1. 多智能体协作系统（LangGraph 状态机）

系统基于 **LangGraph StateGraph** 构建，采用"意图路由 + 并行专家 + 结果合成"的流水线架构：

```
用户输入
    │
    ▼
┌─────────────────┐
│   Receptionist   │  ← 日志/追踪初始化
└────────┬────────┘
         ▼
┌─────────────────┐
│   Intent Router  │  ← 三级分类：正则 → 规则 → LLM
│                  │     输出：意图 + 复杂度 + 所需专家
└────────┬────────┘
         │ trivial → Direct Answer ──────────────────────┐
         ▼                                               │
┌──────────────────────────────┐                         │
│ RAG Retrieval → Grader(CRAG) │ ← 评分 <0.6 →           │
│   Query Rewriter ←───────────│   改写查询重新检索        │
└────────┬─────────────────────┘   (最多 2 轮)            │
         ▼                                               │
    ┌────┴────┐                                          │
    │         │                                          │
    ▼         ▼                                          │
┌────────┐ ┌──────────────────────────┐                  │
│ 单专家  │ │ 多专家并行                │                  │
│ (简单)  │ │ finance / tax / legal /  │                  │
└───┬────┘ │ report （Send 并行分发）  │                  │
    │      └────┬────┬────┬───────────┘                  │
    │           └────┴────┘                              │
    │               ▼                                    │
    │      ┌─────────────────┐                           │
    │      │   Aggregator     │ ← 多专家结果合并           │
    │      └───────┬─────────┘                           │
    ▼              ▼                                     │
┌──────────────────────────────┐                         │
│ Faithfulness Checker          │ ← 逐句核对引用，<0.7      │
│   → Regenerate (最多 1 轮)    │   触发重新生成            │
└────────┬─────────────────────┘                         │
         ▼                                               │
┌────────────────┐  POOR → Retry(≤3) → 重回专家           │
│ Reflection 质量 │  超限 → Human Review (interrupt)       │
│ 审查（可开关）   │                                        │
└───────┬────────┘                                       │
        ▼                                                ▼
┌─────────────────────────────────────────────────────────┐
│   Final Answer  ← SSE 流式 / 异步轮询                     │
└─────────────────────────────────────────────────────────┘
```

**关键流程**：

| 步骤 | 组件 | 说明 |
|------|------|------|
| ① 意图路由 | `IntentRouterAgent` | 三级降级：正则(问候等速通) → 规则(关键词匹配，置信度≥0.9跳过LLM) → LLM分类(置信度≤0.7回退规则结果) |
| ② 检索质量闭环 (CRAG) | `RetrievalGrader` + `QueryRewriter` | 检索结果评分 <0.6 时自动改写查询并重新检索，最多 2 轮 |
| ③ 专家路由 | `route_by_specialists` / 并行 Send | 单专家直达；多专家经 `multi_specialist_router` 并行分发到 finance/tax/legal/report |
| ④ 工具调用 | native function calling | 通过 OpenAI 兼容 `tools` 参数传入，LLM 返回结构化 `tool_calls`，**无需文本正则解析** |
| ⑤ 多轮循环 | `max_tool_rounds=5` | 每轮携带 `tools` 参数，多个 tool_calls 并行执行，LLM 可反复调用工具直到直接回答 |
| ⑥ 结果合并 | `Aggregator` / `ResultSynthesizer` | 多专家场景自动合并，单专家直接返回 |
| ⑦ 忠实度校验 | `FaithfulnessChecker` | 逐句核对回答与检索上下文，评分 <0.7 触发重新生成（最多 1 轮） |
| ⑧ 质量审查 | `QualityReviewFunction` | LLM 评估准确性/完整性/逻辑性，POOR 触发重试（最多3次），超限转人工审核（interrupt） |

**可用工具**（MCP 双模式注册，共 37 个：27 本地 `@local_tool` + 10 云端 `@cloud_tool`）：

- **财务**: `get_financial_overview`（获取财务概览摘要）、`query_financial_data`（查询明细）等
- **税务/法务/通用**: 税务计算、法规合规、企业查询、天气/地图/网络搜索等
- **时间锚点**: `get_current_time_and_context`（时间相关查询必须调用）
- 另有 6 个知识库检索工具（LangChain `@tool`）与数据库中动态加载的自定义工具

### 2. 自研轻量级 Agent 框架 + 原生函数调用

不同于 LangChain 的臃肿，我们实现了轻量级的 Agent 框架：**ReAct/Plan/Reflect 推理引擎** + **12 家 LLM 适配器层**（工厂模式零代码切换）+ **工具管理器**（注册与智能路由），整个框架不依赖 LangChain，便于定制和调试。

**设计亮点**：

- 🧠 **ReAct 推理** - 推理与行动交替执行（`ReActAgent` 默认最多 10 轮，内置语义循环检测 + 连续失败计数 + 提前终止）
- 🔧 **原生函数调用** - 编排层专家通过 API `tools` 参数调用，非文本正则解析
- 🔄 **多轮工具循环** - 专家最多 5 轮（`max_tool_rounds=5`），LLM 自主决策何时直接回答
- 🎯 **适配器模式** - 12 家 LLM 提供商零代码切换（`llm/factory.py`）

### 3. Agent Skill 系统（技术亮点）

> 受 Anthropic Claude Code Skills 规范启发，自研了一套轻量级的 Agent Skill 框架，实现 **LLM 能力的可插拔扩展**。

#### 核心设计

| 维度 | 实现 |
|------|------|
| **渐进式加载** | 三级加载：Level 1 元数据（~100 tokens）→ Level 2 SKILL.md 正文（按需加载）→ Level 3 scripts/references（隔离执行） |
| **域范围目录** | `skills/{domain}/{skill_name}/` 结构，domain 自动推断（finance/tax/legal/public），公有技能跨域可见 |
| **模板变量注入** | `{skill_descriptions}` 通过 `format_domain_skill_descriptions()` 动态渲染到 Agent system prompt 中 |
| **意图-技能匹配** | intent_router 识别 domain → skill_dispatch LangGraph 节点匹配技能 → inject_skill_context() 注入正文 |
| **运行时守卫** | `_is_meta_question()` 跳过 RAG/反思/数据查询；`_sanitize_llm_text()` 后处理 JSON 输出 |
| **LLM 驱动执行** | 不硬编码工具调用，通过 API `tools` 参数传递工具定义，LLM 返回结构化 `tool_calls`；多轮循环直到直接回答 |

#### 7 个内置技能（`rag_backend/skills/{domain}/`）

| 技能 | 归属 | 功能 |
|------|------|------|
| `financial-data-entry` | Finance | 财务数据录入校验与提交（validate_entry.py + submit_entry.py） |
| `corporate-tax-check` | Tax | 企业所得税合规检查 |
| `vat-calculation` | Tax | 增值税计算 |
| `legal-compliance-search` | Legal | 法规合规检索与匹配（Tavily） |
| `tax-law-research` | Legal | 联网搜索最新税务法律知识（Tavily fallback） |
| `policy-crawl` | Public | 爬取政府政策到本地 + 企业匹配 + SSE 通知 |
| `enterprise-profile` | Public | 企业画像信息整理 |

> 另在 `app/prompts/skills/` 下维护 8 个提示词型技能模板（enterprise_knowledge_search、web_research、policy_impact_analysis 等），与 SKILL.md 技能包属不同层次。

**设计原则**：Skills ≠ Tools。Tools 是基础 API 调用，Skills 是复杂业务工作流（如数据录入引导、合规搜索匹配）。Skill 通过 `SKILL.md` 定义流程步骤，scripts/ 执行 LLM 不擅长的精确计算，references/ 提供按需加载的领域知识。

### 4. 上下文优化器（Context Optimizer）

多轮工具调用时，消息列表快速增长（每轮 +1 assistant + M 条 tool result）。为防 context window 溢出，实现了三级压缩：

```
每次 chat() 前检查消息总 token 数
    │
    ├── < 阈值 → 正常发送
    │
    └── > 阈值 → 触发三级压缩:
         │
         ├─ Level 1: 删除冗余（始终执行，零成本）
         │    - 移除空 content 的 assistant 消息
         │    - 合并重复 system 消息
         │
         ├─ Level 2: 工具 JSON → 单行摘要（始终执行，零成本）
         │    原始: {"status":"success","data":{...},"fiscal_year":2024}
         │    压缩: status=success | fy=2024 | 营收=42,918,130.00 | 利润率=37.42%
         │    压缩比: 5:1 ~ 10:1
         │
         └─ Level 3: 多轮滚动摘要（仅超阈值触发，安全网）
              - 将最早的 N 轮 (assistant + tool) 打包为 system(summary)
              - 保留首次 system prompt + 最新用户问题
```

**设计要点**：阈值按模型自适应（deepseek 系列 100K，默认 80K）；Level 1/2 零成本、Level 3 需 LLM 摘要，日常查询不触发；另配套 tiktoken 精确计数与组件级 Token 预算管理。

> 📖 实现与参数详见 [services/README.md](rag_backend/app/services/README.md) 与 [agent_framework/README.md](rag_backend/app/agent_framework/README.md)。

### 5. 混合检索系统

向量检索（pgvector）+ 关键词检索（BM25/FTS）→ RRF 融合 → 知识图谱增强（Neo4j），结合同义词扩展和可选 MMR/Rerank 优化结果。完整链路图见[设计亮点](#-设计亮点)，算法细节见[技术实现详解](#5-搜索查询算法详解)。

#### 智能对话的三种检索模式

智能对话页（右侧「检索设置」抽屉）可按需切换三种检索策略，对应后端 `retrieval_method` 参数 `simple / graphrag / agentic`：

| 模式 | 前端名称 | 链路 | 特点 | 适用场景 |
|---|---|---|---|---|
| `simple` | **简单向量** | Dense(pgvector) + Sparse(BM25) → RRF →（可选 Rerank/MMR）| 速度最快、开销最低、单轮检索 | 一般查询、关键词明确、对时延敏感 |
| `graphrag` | **GraphRAG（图谱增强）** | 在 simple 基础上融合 Neo4j 知识图谱（实体/关系扩展）| 准确度高，能利用实体间关系 | 涉及多实体关系的查询（"A 和 B 是什么关系"、上下游/合作/股东等）|
| `agentic` | **Agentic RAG** | Agent 自主多轮：规划 → 检索 → 评估 →（不足则改写再检索）→ 聚合 | 最智能，多轮自适应；支持**前置短路**（结果分极低时提前停止，避免无意义轮次）| 复杂、多步推理、需要逐步补全信息的查询 |

> 说明：
> - `agentic` 模式额外支持「最大迭代轮数」配置；当某一轮整体评估分低于阈值（默认 0.2，视为知识库基本无相关内容）时**自动短路停止**，对真正相关的企业问题无影响。
> - 三种模式均可叠加「启用知识图谱扩展」「Rerank」「Top K」等检索设置。
> - MMR 多样性重排采用**批量向量计算**（一次性算好候选向量后纯内存计算），避免逐条网络请求带来的高时延。

### 6. 记忆系统

完整的 Agent 记忆体系（`MemoryManager` 统一调度的**三层记忆**），支持上下文理解：

<details>
<summary>🧠 记忆类型说明（点击展开）</summary>

| 记忆类型 | 说明 | 持久化 | 检索方式 |
|---------|------|--------|---------|
| 工作记忆 | 当前对话上下文（默认 50 条，30 分钟过期） | 内存 FIFO | 全量返回 |
| 情景记忆 | 对话历史摘要（准入过滤闲聊/错误响应） | PostgreSQL + pgvector(1024) | 向量相似度×0.7 + 时间衰减×0.3 |
| 语义记忆 | 长期知识/用户事实（importance≥0.8 才写入） | PostgreSQL + pgvector(1024) | 向量检索 + 可选图谱混合检索 |

> 实体关系沉淀由**知识图谱（Neo4j）**承担，作为语义记忆的图谱增强路径，不是独立的第四层记忆。另有 Redis 旁路缓存（空值缓存防穿透 / per-key 锁防击穿 / 随机 TTL 防雪崩）。

</details>

### 7. MCP 工具服务（可扩展功能）

> 🚧 **说明**：MCP 工具服务是一项**可选的可扩展功能**，部署需要一台独立的云端服务器。后端项目 `rag_backend/app/mcp/` 已内置所有计算/检查类工具的同名实现（通过 `@cloud_tool` 装饰器），Agent 默认通过进程内直接调用，**无需依赖外部 MCP 服务**，开箱即用。
>
> `mcp_server/` 是独立的 HTTP MCP 工具服务，供外部 MCP 客户端或其他项目通过标准协议调用。如果你有可用的云端服务器且希望启用远程 MCP 能力，请在 `.env` 中配置 `MCP_MODE` 和 `MCP_SERVER_URL`（详见文档末尾可扩展功能章节）。
>
> **推荐方式**：对于绝大多数用户，直接使用内置的进程内工具调用即可，无需额外部署。MCP 远程服务仅用于需要跨项目共享工具调用的高级场景。

---

### 8. 模型配置中心（管理员可视化配置）

> **不改 `.env`、不向普通用户暴露密钥**。管理员在一个页面里管掉对话/向量/重排三类模型，保存即生效；普通用户透明继承企业设置、看不到入口也访问不了配置 API。

入口：`/settings/models`（管理员可见，`requiresAdmin` 路由守卫 + 后端 `require_admin_user` 双重保护）。

#### 三类模型 · 职责分明

| 分类 | 作用域 | 存储位置 | 关键约束 |
|---|---|---|---|
| **对话模型** | **按租户（企业）** | `tenant_settings.extra_settings.llm_config` | 主对话 + 金融/税务/法务专家可分别配置；不同租户互不影响 |
| **向量模型（Embedding）** | **部署级** | `system_settings.embedding_config` | **维度强校验**：保存前实际编码取维度，必须等于主检索维度（1024），否则后端拒绝——保护已建索引不被破坏 |
| **重排模型（Rerank）** | **部署级** | `system_settings.rerank_config` | 启用开关 + Top K；关闭则检索直接用融合排序结果，跳过重排 |

> 为何对话按租户、向量/重排部署级？因 `chunk.embedding=Vector(1024)` 维度固定共享 + 服务为全局单例，向量/重排无法真正按租户各用各的；对话无此约束。

#### 体验要点

- **本地 Ollama 一等公民**：对话复用 `DeepSeekAdapter` 走 OpenAI 兼容端点（保留 Function Calling，工具调用不丢），向量走 Ollama 原生 `/api/embeddings`；前端「检测本地模型」自动列出已 `ollama pull` 的模型。Docker 部署时 Base URL 用 `host.docker.internal:11434/v1`。
- **测试连接 / 维度守卫 / 说明详情**：每页保存前可一键发最小请求验证；向量保存额外做维度校验；右上角「说明详情」抽屉详尽介绍各字段含义。
- **使用概览**：管理员一页看到各企业 × 各角色当前生效模型 + 最近一次对话**实际使用的模型** + 各模型调用次数——数据来自 `agent_traces.model_name` 真实落库（写入在 ReAct 路径执行）。
- **DB 覆盖 → `.env` 兜底**：任何未配置项自动回退到服务端 `.env`，**前端永不回写 `.env`**；DB 读失败也异常兜底回退，不会打断现网检索。
- **热重载**：保存后调用 `embedding_service.reload()` / `rerank_service.reload()` / `reset_agent_service()`，下一次调用按新配置重建，**无需重启容器**。

#### 主要 API（均管理员鉴权）

- `GET/POST /api/v1/agents/llm-config*` — 对话模型（按租户）CRUD + `/test-connection` + `/ollama/models`
- `GET/PUT /api/v1/agents/llm-config/embedding` + `/embedding/test` + `/embedding/catalog` — 向量（部署级）
- `GET/PUT /api/v1/agents/llm-config/rerank` + `/rerank/test` + `/rerank/catalog` — 重排（部署级）
- `GET /api/v1/agents/llm-config/usage-overview` — 使用概览（各企业生效模型 + 调用统计）
- `GET /api/v1/agents/supported-providers` — 对话提供商目录（自动注入 `.env` 当前在用模型并置顶）

---


### 🆕 当前代码能力概览

根据当前代码，系统已经扩展为覆盖 RAG、智能体协作、企业管理、财税工作流和运维观测的一体化平台：

<details>
<summary>🆕 当前代码能力概览（点击展开）</summary>

| 能力域 | 当前实现 |
|------|------|
| **认证与企业权限** | 登录/注册、JWT 鉴权、管理员路由、租户上下文中间件、企业用户管理、邀请码管理 |
| **知识库与 RAG** | 文档上传、知识库管理、向量检索、混合检索、查询改写、MMR、知识图谱增强、检索结果缓存 |
| **文档解析** | 文本、Markdown、Word、PDF、Excel、图片解析；支持 OCR、MinerU、Unstructured API 等解析路径 |
| **智能体框架** | ReAct / Plan / Reflect Agent、智能体 LLM 独立配置、工具路由、工具调用追踪、Agent Trace |
| **模型配置中心** | 管理员可视化配置三类模型：对话（按租户·主对话/金融/税务/法务专家）+ 向量（部署级·维度强校验保护索引）+ 重排（部署级·启用开关）；本地 Ollama 一等公民；不改 `.env`；保存即生效；使用概览（各企业生效模型 + 最近对话实际模型 + 各模型调用次数） |
| **智能体工具构建器** | 管理员可通过自然语言生成工具规格与代码草稿，支持 `echo`、`http`、`rag_query`、`python_code` 等工具类型，提供 Schema 预览、测试入参生成、发布注册、企业内可见、操作日志追踪；生成代码默认仅保存待审核，不直接执行 |
| **知识图谱编辑器** | 支持中心实体子图加载、实体类型筛选、节点/关系新增删除、连接高亮、缩放适屏、JSON 导入导出，以及批量保存编辑快照到 Neo4j |
| **多智能体系统** | LangGraph 状态机编排、意图路由(三级降级)、多专家并行、原生函数调用(多轮循环)、ResultSynthesizer 合并、质量审查(Reflection)、SSE 流式响应、异步轮询(进度持久化) |
| **财税法务业务** | 税务申报、税务智能分析、政策检索与通知、合同审查、财务数据录入、财务健康监控、企业政策匹配 |
| **协作与实时能力** | 群组聊天、WebSocket 在线状态、SSE 流式响应、工作流事件推送、后台任务状态持久化 |
| **运维与治理** | 请求日志、对话日志、安全监控、限流、熔断器、健康检查、LangSmith 追踪、OpenTelemetry 依赖 |
| **远程工具服务** | 独立 MCP Server（可选可扩展），提供税务、法务、财务工具注册、API Key 鉴权、JSON-RPC 风格工具调用 |

</details>

### 🧭 当前前端页面入口

前端路由已覆盖下列主要业务页面：

<details>
<summary>🧭 当前前端页面入口（点击展开）</summary>

| 路径 | 页面能力 |
|------|------|
| `/` | 主智能对话 |
| `/multi-agent` | 多智能体对话 |
| `/search`、`/documents`、`/knowledge`、`/knowledge/:id` | 搜索、文档、知识库与知识详情 |
| `/knowledge-graph`、`/knowledge-graph-editor` | 知识图谱查看与编辑：实体检索、子图探索、节点/关系维护、JSON 导入导出 |
| `/audit/upload`、`/audit/result/:id` | 多智能体审计上传与结果页 |
| `/tax-submission`、`/tax-intelligence` | 税务申报与税务智能分析 |
| `/policy`、`/policy/:id`、`/policy-notifications` | 政策列表、详情与通知（`/policy-search` 已重定向至 `/policy`） |
| `/financial-health`、`/financial-data-entry`、`/financial-data-list` | 财务健康、财务数据录入与列表 |
| `/contract-review`、`/enterprise-match` | 合同审查与企业政策匹配 |
| `/group-chat`、`/notifications` | 群组聊天与通知中心 |
| `/analytics`、`/agent-center`、`/hitl-approval`、`/intent-debug`、`/security-audit`、`/logs` | 分析、Agent 管理、人机审核、意图调试、安全审计与日志 |
| `/settings/models` | 模型配置中心（管理员）：对话（按租户）/ 向量（部署级·维度守卫）/ 重排（部署级·开关）+ 本地 Ollama 检测 + 测试连接 + 使用概览 |
| `/custom-tools` | 智能体工具构建器：自然语言生成规格与代码草稿、发布配置型工具、测试入参、查看企业已发布工具 |
| `/task-management`、`/chat-logs`、`/profile`、`/test-data-guide` | 任务管理、对话日志、个人资料与测试数据指南 |
| `/settings/multimodal`、`/multimodal-usage` | 多模态配置与用量 |
| `/feedback-management`、`/failure-analysis` | 反馈管理与失败案例分析（管理员） |

</details>

### 🔌 当前后端 API 分组

后端入口位于 `rag_backend/app/main.py`，当前已注册的主要 API 分组包括：

<details>
<summary>🔌 后端 API 分组（点击展开）</summary>

| API 前缀 | 功能 |
|------|------|
| `/api/v1/auth` | 认证、登录、注册 |
| `/api/v1/documents`、`/api/v1/knowledge`、`/api/v1/search`、`/api/v1/knowledge_graph` | 文档、知识库、搜索、知识图谱 |
| `/api/v1/chat`、`/api/v1/sessions`、`/api/v1/groups`、`/api/v1/ws/groups` | 对话、会话、群聊与 WebSocket |
| `/api/v1/multi-agent`、`/api/v1/human-review`、`/api/v1/agent_trace`、`/api/v1/agent-trace`、`/api/v1/tool_trace`、`/api/v1/tool-trace` | 多智能体、人机审核、Agent/工具追踪 |
| `/api/v1/agents`、`/api/v1/agents/llm-config/*`、`/api/v1/agent-discovery`、`/api/v1/agent-task` | 智能体路由、**模型配置中心**（管理员：对话/向量/重排 CRUD + 测试连接 + Ollama 检测 + 使用概览）、智能体发现、任务状态恢复 |
| `/api/v1/custom-tools` | 自定义智能体工具：生成规格、生成代码草稿、创建、发布、测试执行；管理接口仅管理员可用，企业成员可查看和使用已发布工具 |
| `/api/v1/tax-reports`、`/api/v1/tax-intelligence`、`/api/v1/policy`、`/api/v1/policy-tracking`、`/api/v1/financial-tools-test` | 税务报告、税务智能分析、政策管理、政策追踪、财务工具测试 |
| `/api/v1/financial-health`、`/api/v1/financial-data`、`/api/v1/contract-review` | 财务健康、财务数据管理、合同审查 |
| `/api/v1/enterprise`、`/api/v1/invite-codes`、`/api/v1/tenant-settings` | 企业管理、邀请码、租户设置 |
| `/api/v1/logs`、`/api/v1/chat-logs`、`/api/v1/security`、`/api/v1/rate-limit`、`/api/v1/observability` | 系统日志、对话日志、安全监控、限流管理与可观测性 |
| `/api/v1/workflow*`、`/api/v1/task-manager`、`/api/v1/notifications`、`/api/v1/policy-notifications`、`/api/v1/policy-agent` | 工作流事件、任务管理、通知、政策通知与政策通知智能体 |
| `/api/v1/a2a*`、`/api/v1/circuit-breaker*`、`/api/v1/langsmith` | A2A 协议、熔断器管理与 LangSmith 集成 |
| `/api/v1/memory`、`/api/v1/prompt`、`/api/v1/audit`、`/api/v1/feedback`、`/api/v1/multimodal` | 记忆系统、Prompt 优化、多智能体审计、用户反馈、多模态配置 |
| 流式增强（streaming/snapshot/suggestion） | 流式断点续传、会话快照、问题建议 |
| `/health`、`/health/quick`、`/health/{component}`、`/api/health` | 健康检查与组件级诊断 |

</details>

---

## 🔬 技术实现详解

> 本章展示各核心模块的设计思路与技术方案；类名、函数级实现与完整参数表收录在各模块 README（见[相关文档](#-相关文档)）。

### 1. 智能体设计详解

#### 1.1 ReAct 推理模式

ReAct（Reasoning + Acting）是本系统智能体的核心推理范式，将推理与行动交替执行，使智能体像人类一样边思考边行动：

> ReAct 推理引擎通过 **推理 → 行动 → 观察 → 更新** 的四阶段循环实现智能决策。推理阶段由 LLM 分析当前上下文并决定下一步操作，行动阶段执行工具调用获取外部数据，观察阶段收集执行结果，最后更新上下文继续下一轮推理，直到得出最终答案。同时内置**三重防失控机制**：语义循环检测（嵌入相似度比对最近几轮思考）、连续工具失败计数、强制提前终止。

**ReAct 模式的优势**：

- ✅ **可解释性** - 每一步推理都有明确的思考过程
- ✅ **可控性** - 可随时干预或修正推理方向，循环/失败自动熔断
- ✅ **灵活性** - 支持多种工具调用和条件分支
- ✅ **可调试性** - 全程 Agent Trace 落库，便于追踪问题出在哪一步

#### 1.2 Plan 规划模式

复杂任务先分解后执行，适合多步骤专业咨询。例如「企业重组涉及哪些税务问题」会被拆解为：识别重组方式 → 增值税/企业所得税/个税影响逐项分析 → 检查地方优惠 → 生成综合建议。特点：📋 结构化分解 · 🔗 步骤间依赖管理 · 🎯 目标导向交付 · 🔄 根据中间结果动态调整

#### 1.3 Reflect 反思模式

Reflect 模式负责答案质量的评估和改进，确保输出的专业性和准确性：

> 反思机制从 **准确性、完整性、一致性、安全性、清晰度** 五个维度对智能体的回答进行质量评估。当问题复杂度超出阈值或涉及计算类、多领域交叉等场景时，自动触发反思流程，进行交叉验证和补充完善。在 LangGraph 编排层，质量不达标会触发重试（最多 3 次），仍不达标则转人工审核。

#### 1.4 工具集成架构

> 智能体通过统一的工具调用协议与外部服务交互，协议定义工具名称、输入参数、执行结果、置信度和结果来源等标准字段。工具管理器负责注册和路由：装饰器自动注册 + 启动扫描发现，支持税务计算器、法律检索引擎、财务分析器等工具热插拔；智能路由组件根据查询分析自动选择工具，并内置失败熔断（连续失败进入冷却期）。

> 📖 类继承关系、迭代上限、防失控阈值、12 家 LLM 适配器详见 [agent_framework/README.md](rag_backend/app/agent_framework/README.md)；专家的原生 Function Calling 工具循环详见 [multi_agent_system/README.md](rag_backend/app/multi_agent_system/README.md)。

---

### 2. 记忆体系详解

三层记忆（工作/情景/语义，分层表见[核心特性 · 记忆系统](#6-记忆系统)）由 `MemoryManager` 统一调度，查询时四路并发召回（工作上下文 / 历史相似案例 / 专业知识 / 图谱关联）→ 权重融合去重 → 注入推理；推理后新实体入图谱、新知识入语义、新经验入情景。

**四大特色机制**：

- **智能准入** - 闲聊、错误响应不入库；重要性评估（意图关键词 / 重要话题 / 话题频次三路加成）决定是否沉淀为长期记忆
- **混合召回** - 情景记忆按"向量相似度 + 时间衰减 + 重要性"加权；语义记忆可叠加图检索扩展关联知识
- **缓存防御** - Redis 旁路缓存自带空值缓存防穿透、per-key 锁防击穿、随机 TTL 防雪崩
- **用户画像** - 自动从对话提取 facts / preferences / corrections 三类用户记忆，注入 System Prompt

> 📖 各层容量/阈值/打分公式与缓存机制详见 [memory_system/README.md](rag_backend/app/memory_system/README.md)。

---

### 3. 领域知识图谱提取机制

系统采用 **领域类型约束 + 规则/LLM 混合提取 + 多层校验** 的专用提取管线，区别于通用 NER 或纯 LLM 方案。

**实体类型定义** — 面向财税法务领域预设 21 种实体类型：

| 领域 | 实体类型 |
|------|---------|
| **主体** | COMPANY（公司）、PERSON（人物）、DEPARTMENT（部门） |
| **财务** | FINANCIAL_METRIC（财务指标）、FINANCIAL_REPORT（报表）、ACCOUNT（账户）、BUDGET（预算） |
| **税务** | TAX_TYPE（税种）、TAX_RATE（税率）、TAX_POLICY（税收政策）、TAX_EXEMPTION（税收优惠） |
| **法务** | CONTRACT（合同）、CLAUSE（条款）、REGULATION（法规）、LEGAL_CASE（案件） |
| **通用** | PRODUCT（产品）、SERVICE（服务）、LOCATION（地点）、DATE_PERIOD（日期）、EVENT（事件）、TECHNOLOGY（技术） |

**关系类型定义** — 预设 24 种有向关系类型，涵盖公司治理（10 种）、财务（3 种）、税务（4 种）、法务（5 种）、通用（4 种）：`WORKS_AT`、`SIGNED`、`SUBJECT_TO`、`HAS_METRIC`、`OWNS`、`COMPETES_WITH`、`CONTAINS_CLAUSE` 等。

**两阶段提取流程**：

```
文本 → 阶段一：规则预提取 → 阶段二：LLM 补全（可选）→ 关系提取 → Neo4j 入库
        │                         │
        ├ DATE_PERIOD（正则匹配）    ├ 仅当规则未提取到时触发
        ├ TAX_RATE（正则匹配）       ├ 受 21 种类型约束，不可编造
        ├ COMPANY（公司字典）        └ 含置信度评分 + 消歧
        ├ CONTRACT/CLAUSE（正则）
        └ FINANCIAL_METRIC（正则）
```

**多层校验**：类型白名单（提示词限定 + 返回结果二次过滤）→ 置信度 ≥0.7 → 关系 source/target 必须存在于已提取实体（防幻觉）。

**工程优化**：规则预提取覆盖 60%+ 简单实体，LLM 仅补复杂场景；关系提取只传 Top 10 核心实体；LLM 调用 120s 超时保护；Neo4j **UNWIND 批量写入**（一次往返替代 N 次）；查询阶段实体提取用 jieba 分词（毫秒级、零 LLM）。

**Neo4j 数据模型** — 多标签设计（`(:Entity:Company)`），既兼容 `MATCH (e:Entity)` 旧查询，又支持 `MATCH (c:Company)` 类型限定的高效遍历；所有查询附加租户软隔离条件。

> 📖 完整类型枚举、规则正则清单、Cypher 模型与批量写入实现详见 [knowledge_graph/README.md](rag_backend/app/knowledge_graph/README.md)。

---

### 4. 提示词模块设计

**分层提示词架构** — 三层叠加组装，实现专业领域定制：

> **系统基础层**定义智能体身份和核心原则（准确性、合规性、法规引用）；**领域专家层**为税务、法律、财务分别定制专业能力描述；**任务指令层**注入任务类型、输出格式和检索到的参考资料。

**动态提示词组装** — 五步自动化流程：获取角色系统提示 → 注入领域专业指令 → 嵌入检索知识片段 → 压缩插入对话历史摘要 → 组装最终提示交给 LLM。

**Few-Shot 示例模板** — 为复杂任务嵌入典型问答范例：税务计算给出「销售额 → 纳税人类型 → 适用税率 → 销项税额 → 应纳税额」完整推理链；法律分析给出「识别相关法律 → 法条原文 → 对照分析 → 结论判断 → 风险提示」分析框架。

**Chain-of-Thought 引导** — 复杂问题按「问题拆解 → 条件分析 → 方案推导 → 综合结论」链式思考，以【思考】/【结论】标记区分推理过程与最终答案，提升可追溯性。

**工程化管理** — 提示词以 YAML + Markdown 文件维护（`app/prompts/agents/{agent}/system.md`，9 个 Agent 目录 + 8 个提示词型技能模板），支持 Jinja2 变量注入（如 `{skill_descriptions}`），**改提示词不改代码**。

---

### 5. 搜索查询算法详解

#### 5.1 混合检索架构

> 混合检索器采用 **意图分析 → 并行多路召回 → RRF 融合 → 重排序** 的四阶段流水线：分析查询意图后，并行从向量检索、关键词检索、知识图谱三条路径召回候选，RRF 合并排序，最后交叉编码器精排输出 Top-K。

#### 5.2 向量检索

> 查询文本经 Embedding 模型编码为 **1024 维**稠密向量（数据库列固定 `Vector(1024)`，模型配置中心保存前做维度强校验以保护已建索引），HNSW 近似最近邻索引实现毫秒级语义匹配，支持查询扩展（多个相似查询取平均向量提升召回）与元数据过滤。

- 🔮 **语义理解** - 理解查询真实含义而非字面匹配，支持中英文混合
- 📏 **维度约束** - 全局 1024 维，SiliconFlow bge-m3 / 智谱 embedding-3 / OpenAI / Ollama 四类提供商可选
- ⚡ **ANN 加速** - HNSW 索引毫秒级检索

#### 5.3 BM25 + RRF 融合

BM25（PostgreSQL tsvector 全文索引）与向量检索互补——BM25 管精确词汇匹配，向量管语义理解。多路结果用 **RRF（倒数排名融合）**合并：$RRF\_score(d) = \sum_i \frac{1}{k + rank_i(d)}$（k=60），无需训练、单路召回劣化不拖垮整体。

#### 5.4 查询改写与扩展

> 查询扩展器通过 **意图识别 → 同义词扩展 → LLM 生成替代查询 → 领域术语标准化** 四步优化原始查询：同义词字典覆盖财税领域等效词汇（税务/税收/税金），LLM 生成语义相近表述（"如何办理" → "办理流程/步骤/方法"），多个扩展查询融合提升召回覆盖面；另支持可选 HyDE。

#### 5.5 重排序与后处理

> 重排序器调用 SiliconFlow Rerank API（`Pro/BAAI/bge-reranker-v2-m3` 交叉编码器）对候选集配对批量打分，精排筛选 Top-K 并过滤低分结果。之后依次叠加：**MMR 多样性重排**（批量向量纯内存计算，避免逐条网络请求）→ **Cliff Prune 断崖裁剪**（相关性分数骤降处截断，宁缺毋滥）→ 时序去重 → 知识图谱关系展开 → Auto-Merging 父块展开。

> 📖 各环节函数与默认参数（RRF k 值、MMR λ、Cliff 阈值、Agentic 短路阈值、两条检索链路差异）详见 [services/README.md](rag_backend/app/services/README.md)。

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
│  │PostgreSQL│ │  Redis  │ │PostgreSQL│ │  Neo4j  │ │  MinIO  │     │
│  │ 主数据库  │ │  缓存   │ │+pgvector │ │ 图数据库 │ │ 对象存储│     │
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

### 异步设计机制

后端以 FastAPI/asyncio 为核心，数据库访问使用 SQLAlchemy `AsyncSession` 和 `asyncpg`，外部 HTTP/LLM 调用优先使用异步客户端，避免在请求处理中长时间占用事件循环。

系统中的长生命周期任务由 `BackgroundTaskManager` 统一托管，例如在线状态清理和 ARQ Worker。应用启动时注册任务，关闭时先发送停止信号，再统一取消并等待后台任务退出，避免后台任务异常静默丢失或服务退出时残留未完成任务。

流式对话走真正的 async generator 链路：检索完成后调用 LLM 的异步流式接口，再通过 SSE 返回前端。流式 chunk 会被归一化为统一的 `delta` 结构，以兼容 OpenAI、DeepSeek、Qwen 等不同适配器的返回格式。

多智能体和 A2A 协作通过 `asyncio.gather`、`Semaphore` 和任务状态队列控制并发。A2A 任务会记录真实的 asyncio task，取消任务时不仅更新业务状态，也会取消底层执行任务，并通过队列推送最新状态。

对于仍需调用同步库的场景，例如同步工具函数、部分文件/OCR/存储操作，代码会尽量使用 `asyncio.to_thread()` 或 executor 放到线程中执行，减少阻塞主事件循环的风险。

### 技术栈详情

<details>
<summary>🛠️ 技术栈详情（点击展开）</summary>

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **后端框架** | FastAPI 0.128+ | 异步高性能 API 框架 |
| **数据库** | PostgreSQL 16 + pgvector | 关系型数据存储与向量扩展 |
| **缓存** | Redis 7+ | 会话缓存、频率限制 |
| **向量检索** | PostgreSQL pgvector (HNSW/IVFFlat) | 语义向量检索，Docker Compose 默认使用 pgvector |
| **图数据库** | Neo4j | 知识图谱存储 |
| **对象存储** | MinIO | 文档、图片存储 |
| **前端框架** | Vue 3.4+ | 渐进式 JavaScript 框架 |
| **UI 库** | Element Plus | Vue 3 组件库 |
| **状态管理** | Pinia | Vue 3 状态管理 |
| **LLM** | DeepSeek / OpenRouter 兼容接口等 | 当前推荐 DeepSeek，默认配置可走 OpenRouter 兼容接口 |
| **向量模型** | SiliconFlow / 智谱 / OpenAI 等 | 文档向量化，按环境变量选择 |

> 说明：当前项目推荐使用 DeepSeek。代码中也保留了 OpenAI、Claude、智谱、Qwen、MiniMax 等 LLM 适配器，已检查其导入和初始化路径；真实调用仍取决于用户自己的 API Key、Base URL、模型权限和网络环境。

</details>

---

## 📁 项目结构

```
financial_rag/
├── rag_backend/                       # 后端服务 (200+ 源文件)
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口，50+ Router，lifespan 管理
│   │   ├── core/                      # 配置、JWT、异常体系、资源管理
│   │   ├── db/                        # AsyncSession 工厂、PgBouncer 双引擎
│   │   ├── api/
│   │   │   ├── deps.py               # DI 注入链 (get_db → get_user → 租户验证)
│   │   │   └── v1/endpoints/         # 50+ 路由模块
│   │   │       ├── auth.py, chat.py, document.py   # 核心 CRUD
│   │   │       ├── search.py, knowledge.py         # 检索与知识管理
│   │   │       ├── multi_agent.py, group_chat.py   # 多智能体 + 群聊
│   │   │       ├── tax_report.py, financial_health.py  # 财税业务
│   │   │       └── workflow.py, security.py, ...   # 工作流 + 运维
│   │   ├── models/                    # 42 个 ORM 模型 (User, Document, Chunk 等)
│   │   ├── schemas/                   # Pydantic 验证模型
│   │   ├── repositories/              # 仓储层 (BaseRepository 自动注入租户过滤)
│   │   ├── services/                  # 100+ 业务服务 → 详见 services/README.md
│   │   │   ├── unified_retriever.py   # 主检索链路 (RRF→Rerank→MMR→Cliff Prune→关系展开)
│   │   │   ├── hybrid_search_service.py # 三路 RRF 混合检索（旧链路）
│   │   │   ├── context_optimizer.py   # 三级上下文压缩
│   │   │   ├── agent_service.py       # 智能体服务入口 (单例+热重载)
│   │   │   ├── graphrag_service.py    # GraphRAG 图谱增强检索
│   │   │   ├── invoice/               # 发票识别/计算/风险评估
│   │   │   └── policy_collector/      # 政策采集爬虫 (+ robots.txt + 限速)
│   │   ├── agent_framework/           # ▸ 自研 Agent 执行框架 ◂ → README.md
│   │   │   ├── core/                  # BaseAgent, ReActAgent, PlanAgent, ReflectAgent
│   │   │   ├── llm/                   # 12 家 LLM 适配器 (工厂模式)
│   │   │   ├── tools/                 # 工具管理器、路由、链式调用
│   │   │   └── tokens/                # TokenTracker + BudgetManager
│   │   ├── multi_agent_system/        # ▸ 多智能体编排系统 ◂ → README.md
│   │   │   ├── orchestrator.py        # 核心编排器
│   │   │   ├── coordinator.py         # 审计审查协调器
│   │   │   ├── agents/                # 专家 Agent (原生 Function Calling, 5 轮工具循环)
│   │   │   ├── routing/               # 统一请求路由
│   │   │   └── config/                # Agent 能力 YAML 定义
│   │   ├── langgraph/                 # ▸ LangGraph 工作流 ◂ → README.md
│   │   │   ├── graph.py               # StateGraph 构建与编译 (CRAG+忠实度+反思闭环)
│   │   │   ├── agentic_rag_nodes.py   # Agentic RAG 规划-检索-评估循环
│   │   │   └── tax_workflow/          # 税务申报子工作流
│   │   ├── a2a_protocol/              # ▸ Agent 间通信协议 (A2A v0.2.5) ◂
│   │   │   ├── transports/            # HTTP / Local / LangGraph 传输
│   │   │   └── registry.py            # Agent 注册发现 (/.well-known/agent.json)
│   │   ├── knowledge_graph/           # ▸ 知识图谱提取管线 ◂ → README.md
│   │   ├── chunkers/                  # 领域感知分块器体系 → README.md
│   │   ├── parsers/                   # 多格式结构化解析器 → README.md
│   │   ├── memory_system/             # 三层记忆体系 → README.md
│   │   ├── mcp/                       # MCP 工具 (27 本地 + 10 云端, stdio/http 双模式)
│   │   ├── prompts/                   # YAML + Markdown 提示词模板体系
│   │   │   ├── agents/{react,plan,tax,finance,legal,...}/
│   │   │   └── skills/                # 8 个提示词型技能模板
│   │   ├── skills/                    # Skill 框架 (注册/加载/匹配/执行)
│   │   ├── middleware/                # 租户上下文/日志/限流 中间件
│   │   ├── observability/             # 链路追踪 + 指标 + 日志
│   │   ├── security/、tasks/、workflow/、state/  # 安全、定时任务、工作流、状态
│   │   └── utils/、config/、migrations/
│   ├── skills/                        # 7 个内置技能包 (SKILL.md, 按 finance/tax/legal/public 分域)
│   ├── tests/                         # 70+ 测试文件 (unit ~35 / integration ~33 / agent_system)
│   ├── docker-compose.yml             # 7 服务容器编排 (DB/Redis/PgBouncer/Neo4j/MinIO/Backend)
│   ├── Dockerfile                     # 多阶段构建 (builder → runner, 非 root)
│   └── requirements.txt               # 170+ 依赖
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
│  │  - 税务计算工具     │    │  │  │  端口 80/5500       │    │
│  │  - 法律匹配工具     │    │  │  └────────────────────┘    │
│  │  - 财务分析工具     │    │  │                            │
│  │  - 企业查询工具     │    │  │                            │
│  └────────────────────┘    │  │                            │
└────────────────────────────┘  └────────────────────────────┘
```

### 环境要求

<details>
<summary>💻 环境要求（点击展开）</summary>

| 环境 | 组件 | 版本要求 |
|------|------|---------|
| **本地** | Docker & Docker Compose | 20.10+ |
| **本地** | Python | 3.11+ |
| **本地** | Node.js | 18+ |
| **云端** | Docker | 20.10+ |
| **云端** | Python | 3.12+ |

</details>

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
git clone https://github.com/Serein-81/financial_rag.git
cd financial_rag/rag_backend

# 首次运行需要创建本地环境变量文件
cp .env.example .env

# 按需编辑 .env，至少填写数据库、Redis、Neo4j 密码和你要使用的大模型 API Key

# 渲染 PgBouncer 配置（从 *.template 生成实际 ini，注入 POSTGRES_PASSWORD）
# 注意：实际 ini 文件已加入 .gitignore，不渲染会导致 pgbouncer 容器启动失败
python docker/render_pgbouncer.py

# 启动 PostgreSQL/pgvector、Redis、PgBouncer、Neo4j、MinIO 和后端服务
docker compose up -d

# 查看容器状态
docker compose ps

# 查看后端日志
docker compose logs -f backend
```

> 💡 **重型图像/扫描件解析服务可以先不拉取**。`unstructured-api`（内含 YOLOX + Detectron2 版面分析模型，镜像体积数 GB、运行需 2-3GB 内存）已被放入 `heavy`/`full` profile，**默认的 `docker compose up -d` 不会拉取也不会启动它**，不影响文字型 PDF/Word/Excel 的正常解析（PDF 自动走 pymupdf4llm → PyMuPDF 启发式降级链）。
>
> 后续需要高质量扫描件 OCR 时再启用：
>
> ```bash
> docker compose --profile heavy up -d        # 拉取并启动 unstructured-api（端口 8001）
> ```
>
> 并在 `.env` 中设置 `ENABLE_UNSTRUCTURED_PARSER=true`（如有需要再配 `UNSTRUCTURED_API_URL`，容器内默认 `http://unstructured-api:8000`），然后 `docker compose restart backend`。

启动成功后访问：

- 后端 API 文档：http://localhost:8000/docs
- 后端健康检查：http://localhost:8000/health
- MinIO 控制台：http://localhost:9001
- Neo4j Browser：http://localhost:7474

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

停止环境：

```bash
cd financial_rag/rag_backend
docker compose down
```

清理本地数据卷/数据目录前请先确认不再需要已有数据。当前 compose 使用 `rag_backend` 目录下的 `postgres_data/`、`redis_data/`、`neo4j_data/`、`minio_data/` 等目录保存数据。

### 1. 克隆项目

```bash
git clone https://github.com/Serein-81/financial_rag.git
cd financial_rag
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

# 渲染 PgBouncer 配置模板（首次运行必做，详见上文「一键启动」）
python docker/render_pgbouncer.py

# 使用 Docker Compose 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend
```

**Docker Compose 包含的服务：**

<details>
<summary>🐳 Docker Compose 包含的服务（点击展开）</summary>

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| PostgreSQL | rag_db | 5432 | 向量数据库 |
| Redis | rag_redis | 6379 | 缓存服务 |
| PgBouncer | rag_pgbouncer | 6432 | PostgreSQL 连接池 |
| Neo4j | rag_neo4j | 7474, 7687 | 知识图谱 |
| MinIO | rag_minio | 9000, 9001 | 对象存储 |
| Backend | rag_backend | 8000 | 后端 API |
| Unstructured API | rag_unstructured_api | 8001 | ⚠️ 重型图像/扫描件解析（YOLOX+Detectron2，镜像数 GB、需 2-3GB 内存）。**默认不拉取不启动**，首次部署可跳过；需要时 `--profile heavy` 启用并设 `ENABLE_UNSTRUCTURED_PARSER=true` |

</details>

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

> ⚠️ **必做步骤**。`docker compose up -d` 只起空容器，不建表；不做这一步后端接口会全部 500。

**推荐方式 · 一键导入完整 schema（最快最稳）**

仓库根目录提供了完整的 PostgreSQL schema 导出 `530.sql`（140+ 表，含所有枚举、索引、外键），首次部署直接导入即可：

```bash
# 在仓库根目录执行（-U / -d 替换为你 .env 中的 POSTGRES_USER / POSTGRES_DB，下同）
docker cp 530.sql rag_db:/tmp/530.sql
docker exec -it rag_db psql -U rag_user -d rag_db -f /tmp/530.sql
```

**增量迁移 · Alembic（仅用于后续 schema 演进）**

> ⚠️ `alembic/versions/` 中的迁移是**增量补丁**（从政策表起步，共 18 个版本），**不能**从零建出全部核心表。首次部署请务必用上面的 `530.sql`；之后在开发分支上做 schema 演进时再用 alembic：

```bash
docker exec -it rag_backend alembic upgrade head
```

**创建初始管理员账号**

两种方式任选其一：

方式 A · 前端注册页（推荐）：启动前端后访问 `/register`，选择**企业管理员注册**（无需验证码），填写邮箱、用户名、密码（≥6 位）、真实姓名、企业名称即可，注册成功自动获得管理员权限并分配企业租户。

方式 B · 直接调用注册接口：

```bash
curl -X POST http://localhost:8000/api/v1/auth/register/admin \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "username": "admin",
    "password": "your_password",
    "full_name": "系统管理员",
    "company_name": "示例企业"
  }'
```

> 接口返回 JWT Token 即创建成功；`email`、`username`、`password`、`full_name`、`company_name` 为必填字段。

---

## 🔑 必需 API 密钥配置指南

### 必需密钥（必须配置）

#### 1. LLM 大模型 API

系统支持多种大模型提供商，**推荐优先使用 DeepSeek**。其它供应商适配器已检查导入和初始化路径；真实调用需要根据对应平台的 API Key、Base URL、模型权限和网络环境确认。

<details>
<summary>🔑 必需密钥：LLM 大模型 API（点击展开）</summary>

| 提供商 | 环境变量 | 获取地址 | 说明 |
|--------|----------|----------|------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | [DeepSeek Platform](https://platform.deepseek.com/) | **推荐使用，当前项目主要验证路径** |
| 智谱 AI | `ZHIPU_API_KEY` | [智谱AI开放平台](https://open.bigmodel.cn/) | 已有适配器，需配置平台密钥 |
| OpenAI | `OPENAI_API_KEY` | [OpenAI Platform](https://platform.openai.com/) | 已有适配器，需配置平台密钥 |
| Claude | `CLAUDE_API_KEY` | [Anthropic Console](https://console.anthropic.com/) | 已有适配器，需配置平台密钥 |
| 硅基流动 | `SILICONFLOW_API_KEY` | [硅基流动](https://siliconflow.cn/) | 主要用于 Embedding/Rerank，也可按需接入模型 |

</details>

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

# 开发服务器固定端口 5500（vite.config.ts 中 strictPort: true）
# 访问 http://localhost:5500
# /api 与 /ws-api 请求已由 Vite 代理到 http://localhost:8000，无需额外配置
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

## 🔧 可扩展功能：云端 MCP 服务部署

> ⚠️ **说明**：MCP 远程工具服务是一项**可选的可扩展功能**，部署需要一台拥有公网 IP 的云端服务器。**对于绝大多数用户，推荐使用本地的进程内工具调用方式**（项目默认开箱即用，无需额外配置）。
>
> 以下内容适用于需要跨项目共享工具调用的高级场景。如果你没有云端服务器或不需要远程 MCP 能力，可以跳过此章节。

### 1. 准备云端环境

在云服务器上安装 Docker：
```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
```

### 2. 上传 MCP 服务代码

```bash
mkdir -p /opt/mcp_server && cd /opt/mcp_server
# 上传 mcp_server 目录内容（可用 scp、rsync 或 git clone）
scp -r mcp_server/* user@your-cloud-server:/opt/mcp_server/
```

### 3. 配置并构建 MCP 服务

创建环境变量文件（填写 API Key）后构建并运行：

```bash
cd /opt/mcp_server
cat > .env << 'EOF'
MCP_HOST=0.0.0.0
MCP_PORT=8080
MCP_API_KEY=your_mcp_api_key_here
EOF

docker build -t mcp-server .
docker run -d --name mcp-server -p 8080:8080 --env-file .env --restart unless-stopped mcp-server
```

> ⚠️ `MCP_PORT` 必须与端口映射保持一致（代码中 `config.py` 的默认端口是 5000，因此 `.env` 里要**显式**设置 `MCP_PORT=8080`，与 `-p 8080:8080` 对应），否则容器内监听端口与映射端口不一致会导致无法访问。

### 4. 验证服务

```bash
curl http://your-cloud-server:8080/health
```

### 5. 配置后端连接

在本地 `rag_backend/.env` 中添加：

```env
# 如需启用云端 MCP 模式
# MCP_MODE=cloud
MCP_SERVER_URL=http://your-cloud-server:8080
MCP_API_KEY=your_mcp_api_key_here
```

> 💡 **提示**：再次强调，后端 Agent 默认走进程内直接调用内置工具实现，MCP 远程服务仅在需要跨项目共享工具调用时才有配置价值。

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
- [ ] 已渲染 PgBouncer 配置（`python docker/render_pgbouncer.py`）
- [ ] 数据库已初始化（首次部署导入根目录 `530.sql`；alembic 仅用于后续增量迁移）
- [ ] 初始管理员已创建（前端注册页「企业管理员注册」或 `POST /api/v1/auth/register/admin`）

### Docker 服务状态
- [ ] PostgreSQL 服务运行正常（端口 5432）
- [ ] Redis 服务运行正常（端口 6379）
- [ ] Neo4j 服务运行正常（端口 7474, 7687）
- [ ] MinIO 服务运行正常（端口 9000, 9001）
- [ ] 后端 API 服务运行正常（端口 8000）
- [ ] （可选）`rag_unstructured_api` 未启动属正常 —— 重型图像解析服务默认不拉取，按需 `--profile heavy` 启用

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

<details>
<summary>📖 核心文档（点击展开）</summary>

| 文档 | 说明 |
|------|------|
| [前端 README](rag_frontend/README.md) | 前端应用详细说明 |
| [MCP README](mcp_server/README.md) | MCP 工具服务说明 |
| [Agent 框架](rag_backend/app/agent_framework/README.md) | 自研 Agent 框架（核心类/适配器/工具/Token 预算） |
| [LangGraph 编排](rag_backend/app/langgraph/README.md) | 状态机工作流（节点拓扑/CRAG/反思闭环） |
| [多智能体系统](rag_backend/app/multi_agent_system/README.md) | 专家 Agent / 意图路由 / 审计协调器 |
| [分块器体系](rag_backend/app/chunkers/README.md) | 领域感知分块管线 |
| [解析器体系](rag_backend/app/parsers/README.md) | 多格式结构化解析与 OCR 降级链 |
| [知识图谱](rag_backend/app/knowledge_graph/README.md) | 实体/关系提取管线与 Neo4j 数据模型 |
| [服务层](rag_backend/app/services/README.md) | 检索链路与业务服务地图 |
| [记忆系统](rag_backend/app/memory_system/README.md) | 三层记忆体系设计文档 |
| [Skill 技能包](rag_backend/skills/README.md) | 7 个内置技能与三级加载机制 |

</details>

### 项目文档

<details>
<summary>📄 项目文档（点击展开）</summary>

| 文档 | 说明 |
|------|------|
| [项目介绍文档](rag_backend/项目介绍文档.md) | 项目整体介绍 |
| [多智能体实施方案](rag_backend/财税法务多智能体实施方案.md) | 多智能体系统实施方案 |
| [问题与解决方案](rag_backend/项目开发中遇到的问题和解决方案.md) | 开发中遇到的问题记录 |

</details>

### 进阶文档

- [多智能体协作系统设计](rag_backend/mass_/COLLABORATION_SYSTEM_DESIGN.md)
- [MCP 架构设计](rag_backend/mass_/MCP_ARCHITECTURE_DESIGN.md)
- [人类记忆系统设计](rag_backend/app/memory_system/HUMAN_MEMORY_SYSTEM.md)
- [知识图谱使用指南](rag_backend/知识图谱使用指南.md)
- [OCR 集成指南](rag_backend/OCR_INTEGRATION_GUIDE.md)
- [日志系统集成指南](rag_backend/日志系统集成指南.md)

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

所有 API 均采用 RESTful 风格设计，使用 JWT Bearer Token 进行身份认证。主要端点包括：
- **POST /api/v1/chat** — 发送消息到智能体对话会话，支持指定知识库范围
- **POST /api/v1/documents/upload** — 上传文档到知识库，系统自动解析和向量化
- **POST /api/v1/search** — 对知识库进行语义搜索，返回相关文档片段

完整的 API 文档通过 Swagger UI 在 `http://localhost:8000/docs` 提供交互式浏览和测试。

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

<details>
<summary>🎯 核心功能（点击展开）</summary>

| 功能 | 说明 |
|------|------|
| **风险检测** | 自动识别高风险 AI 操作 |
| **审批工作流** | 创建审批请求，等待管理员处理 |
| **实时通知** | 通过 WebSocket 推送通知给管理员 |
| **审计日志** | 记录所有高风险操作和审批决策 |

</details>

### 🔍 检测的10种高风险行为

<details>
<summary>🔍 检测的10种高风险行为（点击展开）</summary>

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

</details>

### 📊 风险级别判定

<details>
<summary>📊 风险级别判定（点击展开）</summary>

| 级别 | 阈值 | 处理方式 |
|------|------|---------|
| 🟢 LOW | 0-0.3 | 无需审批，正常执行 |
| 🟡 MEDIUM | 0.3-0.6 | 创建审批，通知管理员 |
| 🔴 HIGH | 0.6-0.8 | 创建审批，通知管理员，标记高优先级 |
| ⚫ CRITICAL | >0.8 | 创建审批，通知所有管理员，强制阻断 |

</details>

### 🔄 工作流程与入口

```
用户输入 → AI 意图识别 → 风险检测 → LOW：正常执行
                                  └→ MEDIUM/HIGH/CRITICAL：创建审批 → WebSocket 通知管理员
                                       → 批准：继续执行 / 拒绝：返回原因（CRITICAL 强制阻断）
```

- **审批入口**：前端 `/hitl-approval` 页面（申请人、风险级别、操作类型一览，可直接批准/拒绝）；API 位于 `/api/v1/multi-agent/hitl/*`（pending / history / approve / review）+ RBAC 角色策略查询
- **通知机制**：WebSocket 实时推送 + Redis 队列离线存储（7 天过期），管理员上线可拉取历史通知
- **设计特点**：关键词+上下文双路检测 · 风险检测/审批/通知/审计日志多层防护 · 已集成进多智能体编排，规则可扩展

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

## 🚀 未来改进方向

### 1. Agent Harness 基础设施完善（对标行业标准）

参考 **Harness / Hermes Agent** 架构，当前项目的 Harness 能力对标与待建设项：

| Harness 核心模块 | 当前状态 | 待建设 |
|----------------|---------|--------|
| 编排循环引擎 | ✅ LangGraph StateGraph（CRAG + 忠实度 + 反思闭环） | LangGraph 原生 Checkpointer 接口适配（当前编译降级为 MemorySaver，Postgres 仅做业务快照） |
| 工具调用框架 | ✅ 原生 Function Calling + MCP 双模式注册 | — |
| 记忆管理系统 | ✅ 工作/情景/语义三级记忆 | 跨会话记忆召回优化 |
| 上下文优化器 | ✅ `services/context_optimizer.py` 三级压缩 | 扩展到 Finance 之外的多轮工具专家 |
| **安全护栏模块** | ⚠️ 租户隔离 + JWT + HITL 风险检测 | Agent 级输入/输出过滤、注入检测、合规校验 |
| 可观测系统 | ✅ LangSmith + Agent Trace | — |
| 错误处理与容错 | ✅ 熔断器 + 超时回退 | — |
| **技能学习闭环** | ❌ 无 | **从执行经验自动生成 Skills**（Hermes 核心能力） |

**重点建设方向**：

- **LangGraph 原生持久化** — 现有 `LangGraphPostgresSaver` 未实现 LangGraph `BaseCheckpointSaver` 接口，`compile()` 实际降级为内存 checkpoint；需补齐 `aget_tuple/aput` 等接口实现真正的断点续传
- **Agent 安全护栏** — 对 Agent 输入输出做内容安全检测，防止提示词注入、敏感数据泄露
- **技能学习闭环** — Hermes Agent 能自动从执行经验中生成可复用的 Skills 文档。计划引入类似的机制：Agent 完成任务后自动提取成功模式，生成 Skill 描述，注册到 SkillRegistry

### 2. A2A 协议集成（分布式 Agent 通信）

系统已预留 **Google Agent-to-Agent (A2A) 协议**接口，包含 `HybridDispatcher`、`AgentRegistry`、`A2AServer/A2AClient` 和 `LangGraphTransport` 等基础设施，支持将智能体扩展为分布式部署。

**目标场景**：
- 将税务、法务、财务专家拆分为独立服务，部署在不同机器上
- 通过 A2A 协议的 HTTP/JSON-RPC 实现跨服务智能体通信
- 支持异构技术栈的智能体（不同语言、不同框架）统一接入
- 利用 `HybridDispatcher` 实现本地调用与远程调用的自动降级

### 3. 知识图谱增强检索

- 将 Neo4j 知识图谱深度集成到 RAG 检索链路中
- 支持基于实体关系的多跳推理查询
- 图谱问答（GraphQA）增强复杂关系类问题的回答准确率

### 4. 多模态 Agent 能力

- 支持图片/表格/PDF 等多模态输入的智能理解
- Agent 可调用 OCR、图表分析等视觉工具

### 5. 持续学习与反馈闭环

- 用户对回答的评分/纠错反馈自动入库
- 定期用真实反馈微调提示词和检索策略
- 构建评估数据集，自动化回归测试

---

## 📬 联系方式

- 负责人：陈
- 邮箱：chenjh8181@gmail.com


---

<div align="center">

**如果这个项目对你有帮助，请给我们一个 ⭐**

</div>
