# RAG 机制修改总结

> 基于 `rag_backend/` 项目已有的分块与入库机制，对检索和召回链路进行的系统性重构。
> 参考 LlamaIndex 的 Hybrid Search、RecursiveRetriever、AutoMergingRetriever 等核心机制。

---

## 一、分块与入库机制（Chunking & Ingestion）

### 1.1 四域感知切块器

| 领域 | 切块策略 | 核心能力 |
|------|----------|----------|
| **finance** | `FinancialChunker` | 表格原子化（整表不切碎）、财务指标实体提取（meta_info.metrics）、正文→表格 PARENT/CHILD 关系 |
| **tax** | `TaxChunker` | 条款级正则切片（第X条）、生命周期打标（effective_date/expiry_date/tax_type/region）、PREVIOUS/NEXT 法条链表 |
| **legal** | `LegalChunker` | AST 双层节点（PARENT+LEAF）、章节→条款层级关系、Phase 2 实体替换 |
| **general** | `GeneralChunker` | Auto-Merging 双粒度（256 token LEAF + 1024 token PARENT）、向上坍缩 |

### 1.2 三级领域检测

```
① 用户指定（kb_category）→ ② 文件名关键词（"财报"/"合同"/"税务"）
→ ③ LLM 读前 800 字符分类 → 兜底 general
```

### 1.3 元数据注入（MetadataInjector）

ContextStack 树绑定栈结构，DFS 遍历 DocumentSection 树，在标题中提取 year/quarter/report_type/company/currency 并注入子节点。兄弟节点间零泄漏（Push/Pop 机制）。

### 1.4 AST 净化器（ASTSanitizer）

超长标题降级（>50字符）、越级跳跃修复（H1→H3 自动插入 H2 隐式父节点）。

### 1.5 节点关系体系

| 关系 | 存储方式 | 适用领域 |
|------|----------|----------|
| PARENT/CHILDREN | `relationships` JSONB | all |
| PREVIOUS/NEXT | `relationships` JSONB | tax |
| SOURCE | `relationships` JSONB | legal（前端展示，不进 LLM） |

所有关系存储在同一张 `document_chunks` 表，通过 `domain` 和 `node_type` 列区分。

### 1.6 两阶段架构（Phase 1 + Phase 2）

```
Phase 1: 解析 → 领域检测 → 切块 → 元数据注入 → 关系构建 → 向量化 → status='ready'
Phase 2 (legal only): 实体替换 + 摘要生成（asyncio.ensure_future 后台执行）
```

Phase 1 完成后立即可检索，Phase 2 失败不影响检索。

---

## 二、检索与召回机制（Retrieval & Recall）

### 2.1 完整检索流水线

```
用户查询
  → QueryAnalyzer（域路由 + 条件提取 + 最新意图检测）
  → HybridSearch（Dense pgvector + Sparse tsvector BM25 + RRF 融合）
  → Cross-Encoder Reranker（bge-reranker-v2-m3）
  → MMR 多样性重排
  → Cliff Prune（断崖截断）
  → Temporal Dedup（时序去重，"最新"查询时分组择新）
  → Relationship Expansion（PARENT summary / PREVIOUS/NEXT）
  → Auto-Merging（general 域向上坍缩）
  → Context Assembly（四域多态 Prompt 组装）
```

### 2.2 混合检索（HybridSearchEngine）

| 检索引擎 | 技术 | 职责 |
|----------|------|------|
| Dense | pgvector HNSW + 余弦相似度 | 语义泛化匹配 |
| Sparse | tsvector BM25 + GIN index | 精确字面量匹配 |

**RRF 融合**：`Score = w_dense/(60+rank_dense) + w_sparse/(60+rank_sparse)`

各域权重：

| 域 | w_dense | w_sparse |
|----|---------|----------|
| legal | 0.4 | 0.6 |
| tax | 0.5 | 0.5 |
| finance | 0.3 | 0.7 |
| general | 0.5 | 0.5 |

### 2.3 查询解析器（QueryAnalyzer v3）

- 域路由：关键词评分 → legal/tax/finance
- 条件提取：year/quarter/tax_type/region/metric
- 最新意图检测："最新""现行"等关键词
- 过滤器生成：`build_metadata_filter()` + `build_temporal_filter()`

### 2.4 精排与截断（Reranker + MMR + Cliff Prune）

```
RRF Top-50 → bge-reranker-v2-m3 → Top-20 → MMR → Top-15 → Cliff Prune → Top-3~10
```

- **Reranker**：SiliconFlow bge-reranker-v2-m3 Cross-Encoder
- **MMR**：Maximal Marginal Relevance，lambda=0.6，避免相似 chunk 堆砌
- **Cliff Prune**：从第 3 条开始检测得分断层，Δ>0.15 截断

### 2.5 时序去重（Temporal Dedup）

检测 "最新"/"现行" 意图，按 heading_path 或 content 前缀分组，组内按 effective_date/year 降序，每组只保留最新版本。

### 2.6 关系展开（Relationship Expansion）

| 域 | 展开策略 | 数据源 |
|----|----------|--------|
| legal | PARENT.summary（50字摘要，Phase 2 未完成时 content[:300]） | relationships.PARENT |
| tax | PREVIOUS content[:200] + NEXT content[:200] | relationships.PREVIOUS/NEXT |
| finance | PARENT content[:300]（表格上下文） | relationships.PARENT |
| general | Auto-Merging 向上坍缩（≥2 碎片指向同一 PARENT 时替换） | relationships.PARENT |

### 2.7 多态 Prompt 组装（ContextAssembler）

按域模板组装：

```
legal:  [法务条款]
          【章节主旨】: {summary}
          【具体条款】: {content}

tax:    [税法规定]
          【前一条款】: {prev}
          【核心命中】: {content}
          【后一条款】: {next}

finance: [财务报表]
          【表头语境】: {parent_context}
          【核心表格】: {table_content}
```

---

## 三、PDF 解析引擎（混合解析方案）

### 3.1 三级自适应降级

```
① pymupdf4llm（本地，200MB，<2秒/100页）
   → 文字型 PDF，含 Markdown 表格识别

② unstructured-api OCR（Docker，需外网下载模型）
   → 扫描件，通过 host.docker.internal:7890 走 VPN 代理

③ PyMuPDF 启发式解析（无条件兜底）
   → 任何时候不崩溃
```

### 3.2 自适应判定

pymupdf4llm 提取字符 < 文件大小 × 8% → 判定为扫描件 → 触发 unstructured OCR。

---

## 四、基础设施与可观测性

### 4.1 数据库连接池

```
DB_POOL_SIZE: 5 → 10
DB_MAX_OVERFLOW: 5 → 20
DB_POOL_TIMEOUT: 30 → 60
```

### 4.2 关键新增模块

| 文件 | 功能 |
|------|------|
| `services/hybrid_search.py` | HybridSearchEngine（Dense + BM25 + RRF + temporal_dedup + auto_merge） |
| `services/cliff_pruner.py` | 断崖截断算法 |
| `services/context_assembler.py` | 四域多态 Prompt 组装 |
| `services/query_analyzer.py` | 域路由 + 条件提取 + 最新意图检测 |
| `chunkers/financial_chunker.py` | 财务指标实体提取（v2） |
| `chunkers/metadata_injector.py` | ContextStack 树绑定元数据注入 |
| `chunkers/entity_resolver.py` | 双路实体替换（LLM 提取 + str.replace） |
| `chunkers/summary_generator.py` | 受控并发摘要生成（Batch Prompt） |
| `parsers/structured_pdf_parser.py` | 三级自适应 PDF 解析 |

### 4.3 评估系统

**RAGAS 评估结果**（18 道跨领域题 / DeepSeek 裁判）：

| 指标 | 分数 | 含义 |
|------|------|------|
| context_recall | **0.89** | 检索系统能召回到正确文档 |
| context_precision | **0.79** | 召回的 chunk 中大部分相关 |
| faithfulness | **0.75** | LLM 答案忠于上下文，幻觉可控 |

---

## 五、文件变更清单

### 新增文件（12 个）

```
rag_backend/app/services/hybrid_search.py
rag_backend/app/services/cliff_pruner.py
rag_backend/app/services/context_assembler.py
rag_backend/app/services/query_analyzer.py（重写）
rag_backend/app/chunkers/financial_chunker.py（增强）
rag_backend/app/chunkers/metadata_injector.py
rag_backend/app/chunkers/entity_resolver.py
rag_backend/app/chunkers/summary_generator.py
rag_backend/app/parsers/structured_pdf_parser.py（重写）
rag_backend/app/models/document_enrichment_job.py
rag_backend/app/prompts/chunkers/domain_classify_prompt.md
rag_backend/app/prompts/chunkers/entity_resolve_prompt.md
rag_backend/app/prompts/chunkers/summary_generate_prompt.md
rag_backend/migrations/add_content_tsvector.py
```

### 改造文件（10 个）

```
rag_backend/app/services/search_service.py（bm25_search + jsonb_array_filter）
rag_backend/app/services/unified_retriever.py（集成新链路 + MMR）
rag_backend/app/api/v1/endpoints/knowledge.py（两阶段架构）
rag_backend/app/models/chunk.py（新增 domain/node_type/relationships 列）
rag_backend/app/core/config.py（连接池配置）
rag_backend/app/chunkers/__init__.py（新模块导出）
rag_backend/app/models/__init__.py（EnrichmentJob 导出）
rag_backend/app/services/__init__.py（service 导出）
rag_backend/docker-compose.yml（unstructured-api 代理 + mem_limit）
rag_backend/requirements.txt（pymupdf4llm）
```
