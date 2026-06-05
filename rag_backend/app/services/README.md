# Services（业务服务层）

100+ 服务文件，覆盖检索、对话、智能体、财税法务业务、政策采集与基础设施。本 README 重点说明**检索链路**与服务地图。

## 检索链路（两条并存）

### 主链路：UnifiedRetriever（unified_retriever.py）

```
查询
 → Step 1  query_analyzer.analyze()            查询解析
 → Step 2  元数据过滤 + 时效过滤（tax 域）
 → Step 3  hybrid_search_engine.search()       Dense(pgvector) + Sparse(BM25) → RRF 融合
 → Step 4  rerank_service.rerank()             SiliconFlow API，pool_k = max(20, final_k×2)
 → Step 4.5 _mmr_rerank()                      MMR 多样性，lambda=0.6（批量向量纯内存计算）
 → Step 4.6 cliff_prune()                      断崖裁剪：cliff_threshold=0.15，min_results=3
 → Step 5  temporal_dedup()                    时序去重
 → Step 6  _enrich_results()                   知识图谱关系展开（ENABLE_KNOWLEDGE_GRAPH）
 → Step 6.5 auto_merge()                       Auto-Merging 父块展开（仅 general 域）
 → Step 7  context_assembler.assemble()        按域多态组装 Prompt
```

### 旧链路：HybridSearchService（hybrid_search_service.py）

三路 RRF（向量 + 同义词扩展向量 + PostgreSQL 全文），`rrf_k=60`，无 MMR/Cliff Prune，保留兼容。

> 注意：两条链路 MMR lambda 不一致 —— unified 硬编码 0.6，enhanced_search/query_optimizer 走 `MMR_LAMBDA` 环境变量（默认 0.9）。

### 三种检索模式（chat 侧 `retrieval_method` 参数）

| 模式 | 链路 |
|---|---|
| `simple` | UnifiedRetriever 单轮 |
| `graphrag` | `graphrag_service.py`：向量候选 → 实体提取 → Neo4j 图遍历（深度 2）→ 合并 → 可选 Rerank |
| `agentic` | `agent_service._agentic_retrieve()`：规划→检索→评估循环，充分阈值 0.7，**短路阈值 0.2**（整体分过低立即停止），默认最多 3 轮 |

### Embedding 与 Rerank

- `embedding_service.py` + `embedding_factory.py` + `adapters/`：zhipu / openai / ollama / siliconflow 四类提供商；**全局维度固定 1024**（`system_config_service.EMBEDDING_DIM`，数据库列 `Vector(1024)`），模型配置中心保存前做维度强校验。
- `rerank_service.py`：SiliconFlow Rerank API（默认 `Pro/BAAI/bge-reranker-v2-m3`），开关 `ENABLE_RERANK` 且需 `SILICONFLOW_API_KEY`；`RERANK_TOP_K=10`、`RERANK_SCORE_THRESHOLD=0.5`。
- 二者均支持 `reload()` 热重载：DB 配置覆盖 → `.env` 兜底，保存后无需重启容器。

### 查询优化

- `query_optimizer` / `enhanced_search_service`：LLM 改写生成 2 个变体（`ENABLE_QUERY_REWRITE`，默认 true）、HyDE（`ENABLE_HYDE`，默认 false）。
- `synonym_service.py`：财税领域同义词扩展（最多取 5 个）。

## 上下文与对话

| 服务 | 职责 |
|---|---|
| `context_optimizer.py` | **三级压缩**：L1 删除冗余 → L2 工具 JSON 转单行摘要 → L3 滚动摘要（LLM）。阈值 deepseek 100K / 默认 80K，L3 目标 60K。被 FinanceSpecialist 每轮 chat 前调用 |
| `agent_service.py` | 智能体服务入口（单例）；`reset_agent_service()` 热重载；`chat_stream()` SSE 流式 |
| `streaming_service.py` | 流式稳定性框架：StreamState/StreamProgress、断点续传、增量保存 |
| `snapshot_service.py` | 会话快照保存与恢复 |
| `agent_service_langchain.py` | ⚠️ 已废弃，仅向后兼容 |

## 业务服务地图（节选）

| 域 | 服务 |
|---|---|
| 税务 | `tax_intelligence_service`（智能分析）、`tax_report_service`、`tax_file_validator` |
| 财务 | `financial_health_service`（异常检测/预警）、`financial_data_service`、`invoice/`（认知/计算/风险/人工审核触发四件套） |
| 法务 | `contract_review_service`（条款提取 + 风险评估 + 政策 RAG） |
| 政策 | `policy_service`、`policy_retrieval_service`、`policy_tracking_service`、`policy_notification_service`、`policy_crawler_service`、`policy_collector/`（API/RSS/Sitemap/HTML 四源采集 + robots.txt + 限速） |
| 基础设施 | `minio_service`（对象存储）、`file_service`（解析门面）、`redis_service`、`email_service`、`sms_service`（阿里云）、`pii_anonymizer`（身份证/手机号/银行卡脱敏）、`tavily_service`（联网搜索） |
| 观测 | `agent_tracer`、`tool_call_tracer`、`workflow_event_service`、`health_service` |

## 子目录

- `adapters/`：Embedding 适配器（siliconflow/zhipu/openai/ollama）。
- `ocr_adapters/`：OCR 适配器（paddleocr/tesseract/mineru/unstructured），详见 `app/parsers/README.md`。
- `policy_collector/`：政策采集器 + robots 检查 + 限速器。
- `invoice/`：发票识别、计算引擎、风险判断、人工审核触发。
