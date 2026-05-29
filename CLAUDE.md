# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A RAG (Retrieval-Augmented Generation) knowledge base platform for financial, tax, and legal domains. The system features a **dual-layer agent architecture**: LangGraph for orchestration (macro-level scheduling) and a self-built framework for execution (micro-level ReAct loops).

**Stack**: FastAPI + Vue 3 + PostgreSQL (pgvector) + Neo4j + Redis + MinIO

## Essential Commands

### Backend (rag_backend/)

**Development**:
```bash
# Start dependencies
cd rag_backend
docker-compose up -d db redis neo4j minio pgbouncer

# Run dev server (auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Testing**:
```bash
# Run all unit tests
pytest

# Run specific test file
pytest tests/unit/test_adaptive_chunker.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run integration tests (requires running services)
pytest tests/integration/
```

**Linting** (uses Ruff via pyproject.toml):
```bash
ruff check .           # Check
ruff check --fix .     # Auto-fix
ruff format .          # Format
```

**Full Stack with Docker**:
```bash
cd rag_backend
cp .env.example .env
# Edit .env with API keys and settings
docker-compose up -d                    # Core services
docker-compose --profile heavy up -d    # + Unstructured parser
docker-compose --profile full up -d     # All services
```

### Frontend (rag_frontend/)

```bash
npm run dev      # Dev server at localhost:5500
npm run build    # Production build → dist/
npm run preview  # Preview production build
```

## Architecture

### Dual-Layer Agent System

**Layer 1: LangGraph StateGraph (Orchestration)**
- Path: `rag_backend/app/langgraph/`
- State machine workflow with persistent checkpoints (PostgreSQL)
- Nodes: receptionist → intent router → specialist selector → reflection → synthesizer
- Handles: Which expert to use, retry logic, result merging
- Files: `graph.py` (workflow builder), `state.py` (AgentState), `nodes.py`, `conditional.py`

**Layer 2: Self-Built Agent Framework (Execution)**
- Path: `rag_backend/app/agent_framework/core/`
- Three agent types: `ReActAgent` (reason-action-observe), `PlanAgent` (plan-execute), `ReflectAgent` (reflection loop)
- Features: Loop detection, semantic deduplication, early stopping, token budget management
- Native OpenAI Function Calling (no regex parsing)
- Max iterations: 5-10 rounds configurable
- Files: `react_agent.py`, `plan_agent.py`, `reflect_agent.py`, `base_agent.py`

### LLM Provider System

**Factory Pattern**: Zero-code switching between 10+ providers
- Path: `rag_backend/app/agent_framework/llm/factory.py`
- Supported: DeepSeek, Qwen, Zhipu, OpenAI, Claude, GPT (OpenRouter), MiniMax, Xinference, Ollama, etc.
- Config: Set `LLM_PROVIDER` in `.env` + corresponding API key
- Specialist routing: `LLM_PROVIDER_DEFAULT` for general agents, `LLM_PROVIDER_SPECIALIST` for expert agents
- Files: `factory.py`, `*_adapter.py` (per provider), `specialist_llm_router.py`

### Tool System

**Auto-Registration via Decorators**:
```python
# In app/tools/ or app/agent_framework/tools/
@auto_register_tool(
    name="calculate_tax",
    description="Calculate enterprise income tax",
    category="tax"
)
async def calculate_tax(income: float, rate: float = 0.25) -> float:
    return income * rate
```
- Files: `agent_framework/tools/decorators.py` (decorator), `scanner.py` (auto-discovery)
- Tools auto-discovered at startup via `ToolManager`
- Hybrid mode: Supports MCP tools (cloud/local) + native tools

### Domain-Specific Chunkers

**15+ Specialized Document Processors**:
- Path: `rag_backend/app/chunkers/`
- `FinancialChunker`: Table atomization, metric extraction, PARENT/CHILD relations
- `TaxChunker`: Clause-level regex splitting, lifecycle tagging, PREVIOUS/NEXT chains
- `LegalChunker`: AST parsing with chapter (PARENT) + article (LEAF) nodes
- `GeneralChunker`: Auto-merging dual granularity (256-token + 1024-token context)
- `AdaptiveChunker`: Domain router selecting appropriate chunker
- Files: `adaptive_chunker.py`, `financial_chunker.py`, `tax_chunker.py`, `legal_chunker.py`

### Knowledge Graph Pipeline

**Type-Constrained Extraction**:
- Path: `rag_backend/app/knowledge_graph/`
- Two-stage: Rule-based pre-extraction (60%+) → LLM completion (complex cases)
- Four-layer validation: Type whitelist (21 entity types) → Confidence ≥0.7 → Relation source verification → Neo4j
- Files: `entity_extractor.py`, `relation_extractor.py`, `graph_builder.py`
- Neo4j connection: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in `.env`

### Hybrid Retrieval Chain

```
Query → Dense (pgvector HNSW) + Sparse (BM25 tsvector)
      → RRF fusion → Cross-Encoder Reranker → MMR diversity
      → Cliff Prune → Relation expansion → Prompt assembly
```
- Path: `rag_backend/app/services/hybrid_search_service.py`
- Config: `ENABLE_HYBRID_RETRIEVAL=true`, `ENABLE_RERANK=true`, `RERANK_TOP_K=10` in `.env`

### Multi-Tenancy

**ContextVar Propagation + Repository Filtering**:
- Middleware: `app/middleware/tenant_middleware.py` sets `tenant_id` in ContextVar
- Repositories: `app/repositories/base.py` explicitly filters by `tenant_id`
- Pattern: No database-level RLS, compatible with PgBouncer transaction mode
- Files: `middleware/tenant_middleware.py`, `repositories/base.py`

### API Structure

50+ FastAPI routers in `rag_backend/app/api/v1/endpoints/`:
- **Core**: `auth.py`, `chat.py` (SSE streaming), `search.py`, `documents.py`
- **Knowledge**: `knowledge.py`, `knowledge_graph.py`, `memory.py`
- **Agents**: `multi_agent.py`, `agent_trace.py`, `tool_trace.py`, `custom_tools.py`
- **Business**: `tax_reports.py`, `financial_health.py`, `contract_review.py`, `policy.py`
- **Enterprise**: `enterprise.py`, `tenant_settings.py`, `invite_codes.py`

### Database Layer

**Models** (`app/models/`):
- Documents: `document.py`, `chunk.py`, `structured_document.py`
- Knowledge: `knowledge_base.py`, `semantic_memory.py`, `episodic_memory.py`
- Agents: `agent_trace.py`, `tool_trace.py`, `agent_task.py`
- Business: `tax_report.py`, `financial_health.py`, `contract_review.py`

**Repositories** (`app/repositories/`):
- Pattern: Async SQLAlchemy + explicit tenant filtering
- Base: `base.py` (AbstractRepository with tenant_id injection)
- Session: `app/db/session.py` (AsyncSession, PgBouncer-compatible)

## Configuration

### Environment Variables

**Location**: `rag_backend/.env` (copy from `.env.example`)

**Critical Settings**:
```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<set_password>
POSTGRES_SERVER=localhost  # or 'db' in Docker Compose
POSTGRES_PORT=5432
POSTGRES_DB=rag_db

# PgBouncer (optional, for high concurrency)
PGBOUNCER_ENABLED=false
PGBOUNCER_POOL_MODE=transaction

# Security
SECRET_KEY=<32+ random chars>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM Provider (10+ options)
LLM_PROVIDER=deepseek  # or: qwen, zhipu, gpt, openai, claude, etc.
LLM_PROVIDER_DEFAULT=  # For general agents (falls back to LLM_PROVIDER)
LLM_PROVIDER_SPECIALIST=  # For expert agents (falls back to DEFAULT)
AGENT_MODE=react  # or: plan, reflect

# API Keys (fill based on LLM_PROVIDER)
DEEPSEEK_API_KEY=<key>
QWEN_API_KEY=<key>
ZHIPU_API_KEY=<key>
OPENAI_API_KEY=<key>
GPT_API_KEY=<openrouter_key>

# Embedding & Rerank
EMBEDDING_PROVIDER=siliconflow  # or: zhipu, openai, ollama
SILICONFLOW_API_KEY=<key>
ENABLE_RERANK=true
RERANK_TOP_K=10

# Knowledge Graph
ENABLE_KNOWLEDGE_GRAPH=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>

# Storage
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=<password>
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<password>
```

### Docker Services

**Compose file**: `rag_backend/docker-compose.yml`

Services:
- `db`: PostgreSQL 16 + pgvector (port 5432)
- `redis`: Redis 7 (port 6379)
- `neo4j`: Neo4j 5.15 (ports 7474 web, 7687 bolt)
- `minio`: MinIO object storage (ports 9000, 9001)
- `pgbouncer`: Connection pooler (port 6432)
- `backend`: FastAPI app (port 8000)
- `unstructured-api`: Document parser (port 8001, profile: heavy)

## Development Workflows

### Adding a New Tool

1. Create function in `app/tools/` or `app/agent_framework/tools/`
2. Add `@auto_register_tool` decorator with metadata
3. Tool auto-discovered on startup via `scanner.py`
4. Available to agents through `ToolManager`

### Adding a New Agent

1. Create agent class in `app/agent_framework/core/`
2. Inherit from `BaseAgent`, `ReActAgent`, or `PlanAgent`
3. Create prompt template in `app/prompts/agents/{agent_name}/system.md`
4. Register in agent registry (`app/agent_framework/registry/`)
5. Use in LangGraph workflow (`langgraph/nodes.py`) or standalone

### Switching LLM Providers

1. Set `LLM_PROVIDER=<provider>` in `.env`
2. Set corresponding API key (e.g., `DEEPSEEK_API_KEY`)
3. Restart backend
4. No code changes required (factory pattern handles routing)

### Adding API Endpoints

1. Create router in `app/api/v1/endpoints/<name>.py`
2. Use `APIRouter` with prefix and tags
3. Include in `app/api/v1/router.py`
4. Follow existing auth/tenant patterns

### Running Tests

**Unit Tests** (default):
```bash
pytest                                    # All unit tests
pytest tests/unit/test_graphrag_service.py  # Specific file
pytest -k "test_react"                    # Pattern matching
```

**Integration Tests** (requires services):
```bash
docker-compose up -d db redis neo4j  # Start dependencies
pytest tests/integration/
```

**Test Configuration**:
- File: `rag_backend/pytest.ini`
- Test paths: `tests/unit/` (default)
- Async mode: auto
- UTF-8 encoding enforced in `conftest.py`

## Key Implementation Notes

### Agent Prompt Templates

- Location: `app/prompts/agents/{agent_name}/system.md`
- Structured markdown with sections: Role, Tools, Examples, Rules
- Loaded at agent initialization
- Supports Jinja2 templating for dynamic context

### Token Budget & Context Compression

**Three-level compression** (in `agent_framework/tokens/`):
1. Deduplication: Remove redundant messages
2. JSON summarization: Compress tool outputs to summaries
3. Rolling compression: LLM-based compression when approaching limit
- Max context: Configurable per provider (e.g., 128k for DeepSeek)
- Budget tracking: Per agent instance

### Memory System

**Three types** (in `app/models/`):
- **Working Memory**: Current conversation context (in-memory)
- **Episodic Memory**: Historical conversation summaries (PostgreSQL)
- **Semantic Memory**: Extracted facts and knowledge (PostgreSQL + vector search)
- Config: `ENABLE_MEMORY_SYSTEM=true` in `.env`

### SSE Streaming

**Chat endpoint** (`api/v1/endpoints/chat.py`):
- Server-Sent Events for real-time streaming
- Disconnect recovery: Resume from last message
- Token refresh: Automatic JWT renewal
- WebSocket alternative: Group chat (`api/v1/endpoints/group_chat.py`)

### Observability

**Tracing** (in `app/models/`):
- `agent_trace.py`: Agent execution logs (intent, plan, results, latency)
- `tool_trace.py`: Tool call logs (arguments, outputs, errors)
- Database persistence for audit and replay
- Optional LangSmith integration: `LANGSMITH_TRACING=true`

## Important Files

### Backend
- `rag_backend/app/main.py`: FastAPI app entry point
- `rag_backend/app/core/config.py`: Pydantic settings (from .env)
- `rag_backend/docker-compose.yml`: Full stack orchestration
- `rag_backend/pyproject.toml`: Ruff linting config
- `rag_backend/pytest.ini`: Pytest configuration
- `rag_backend/.env.example`: Environment variable template

### Frontend
- `rag_frontend/src/main.ts`: Vue app entry point
- `rag_frontend/src/router/index.ts`: Vue Router config (40+ routes)
- `rag_frontend/src/api/index.ts`: API client layer
- `rag_frontend/package.json`: Build scripts and dependencies
- `rag_frontend/vite.config.ts`: Vite configuration

## Common Pitfalls

1. **PgBouncer Transaction Mode**: Do not use `SET LOCAL` or PostgreSQL Row-Level Security (RLS). Use ContextVar + explicit filtering.
2. **Async Context**: Always use `AsyncSession` and `await` for database operations.
3. **Tenant Isolation**: Every repository query must include `tenant_id` filtering (handled in base repository).
4. **Tool Registration**: Functions must be async (`async def`) for auto-registration to work.
5. **LLM Switching**: Ensure API key is set when changing `LLM_PROVIDER`, or requests will fail.
6. **Neo4j Memory**: Default heap is 512M; increase for large graphs via `NEO4J_dbms_memory_heap_max__size`.
7. **Test Isolation**: Integration tests require `docker-compose up -d` for db/redis/neo4j before running.
