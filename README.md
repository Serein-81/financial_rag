# 企业级 RAG 知识库系统

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
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
│   ├── react_agent.py     # ReAct 推理
│   ├── plan_agent.py      # 规划模式
│   └── reflect_agent.py    # 反思模式
├── llm/            # LLM 适配器
│   ├── base_adapter.py     # 适配器基类
│   ├── zhipu_adapter.py    # 智谱 AI
│   ├── openai_adapter.py   # OpenAI
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
│  │ (Milvus)   │  │  (BM25)    │          │
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
│  │ 智谱 AI  │ │ OpenAI │ │  本地   │ │  MCP    │               │
│  │ GLM-4   │ │ GPT-4   │ │ Ollama  │ │ 工具服务 │               │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈详情

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **后端框架** | FastAPI 0.100+ | 异步高性能 API 框架 |
| **数据库** | PostgreSQL 15+ | 关系型数据存储 |
| **缓存** | Redis 7+ | 会话缓存、频率限制 |
| **向量库** | Milvus / Qdrant | 语义向量检索 |
| **图数据库** | Neo4j | 知识图谱存储 |
| **对象存储** | MinIO | 文档、图片存储 |
| **前端框架** | Vue 3.4+ | 渐进式 JavaScript 框架 |
| **UI 库** | Element Plus | Vue 3 组件库 |
| **状态管理** | Pinia | Vue 3 状态管理 |
| **LLM** | 智谱 AI GLM-4 | 中文优化大语言模型 |
| **向量模型** | Embedding-3 | 文档向量化 |

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
│   └── README.md                # 后端说明
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

## 🚀 快速开始

### 环境要求

| 组件 | 版本要求 |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 15+ |
| Redis | 7+ |
| Milvus/Qdrant | 2.0+ |
| Neo4j | 5.0+ |
| MinIO | latest |

### 方式一：Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/yourusername/your-repo.git
cd your-repo

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

访问 `http://localhost:5173` 即可使用。

### 方式二：本地开发

#### 1. 后端服务

```bash
cd rag_backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境变量
cp .env.example .env
# 编辑 .env 填写必要的 API Key

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 前端服务

```bash
cd rag_frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 `http://localhost:5173` 即可。

#### 3. MCP 服务（可选）

```bash
cd mcp_server

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app/main.py
```

---

## 🔧 配置说明

### 环境变量配置

复制 `.env.example` 为 `.env`，配置以下关键项：

```env
# LLM 配置
LLM_PROVIDER=zhipu
ZHIPU_API_KEY=your_zhipu_api_key

# 数据库配置
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/rag_db

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# 向量库配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 知识图谱配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# 对象存储配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### LLM 模型切换

系统支持多种 LLM 提供商，修改配置即可切换：

```env
# 智谱 AI
LLM_PROVIDER=zhipu
ZHIPU_API_KEY=your_key

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key

# 本地 Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 📖 相关文档

| 文档 | 说明 |
|------|------|
| [后端 README](rag_backend/README.md) | 后端服务详细说明 |
| [前端 README](rag_frontend/README.md) | 前端应用详细说明 |
| [MCP README](mcp_server/README.md) | MCP 工具服务说明 |
| [API 文档](rag_backend/API完整文档_v2.md) | 完整的 API 接口文档 |
| [用户指南](rag_backend/USER_GUIDE.md) | 系统使用指南 |
| [部署指南](rag_backend/DEPLOYMENT_GUIDE.md) | 生产环境部署 |

### 进阶文档

- [多智能体系统设计](rag_backend/MULTI_AGENT_FRAMEWORK_DESIGN.md)
- [Agent 框架详解](rag_backend/INTELLIGENT_AGENT_FRAMEWORK_DESIGN.md)
- [记忆系统设计](rag_backend/HUMAN_MEMORY_SYSTEM_DESIGN.md)
- [知识图谱集成](rag_backend/QUICKSTART_GRAPHRAG.md)
- [LangGraph 集成](rag_backend/LANGGRAPH_INTEGRATION.md)
- [LangSmith 追踪](rag_backend/LANGSMITH_INTEGRATION_GUIDE.md)

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

# 运行单元测试
npm run test

# 运行 E2E 测试
npm run test:e2e
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

- **项目主页**: https://github.com/yourusername/your-repo
- **问题反馈**: https://github.com/yourusername/your-repo/issues

---

<div align="center">

**如果这个项目对你有帮助，请给我们一个 ⭐**

</div>
