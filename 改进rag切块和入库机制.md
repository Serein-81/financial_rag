# 知识库分块与入库机制重构方案 v2

> 基于现有 My_rag 项目基础设施，引入领域感知切片、节点关系体系、元数据扩散注入、实体显式化等能力，系统性提升 RAG 召回精度和上下文完整性。

---

## 目录

1. [现系统分析：保留什么，改什么](#1-现系统分析保留什么改什么)
2. [整体架构设计](#2-整体架构设计)
3. [领域检测器](#3-领域检测器)
4. [ChunkResult 数据类增强](#4-chunkresult-数据类增强)
5. [财务类 Financial：表格孤岛重构 + 树绑定元数据](#5-财务类-financial表格孤岛重构--树绑定元数据)
6. [税务类 Tax：条款级切片 + 生命周期打标](#6-税务类-tax条款级切片--生命周期打标)
7. [法务类 Legal：AST 切分 + 双路实体解析 + 概括存留](#7-法务类-legalast-切分--双路实体解析--概括存留)
8. [默认通用类 General：Markdown 层级 + Auto-Merging](#8-默认通用类-generalmarkdown-层级--auto-merging)
9. [元数据注入器 MetadataInjector：AST 上下文栈](#9-元数据注入器-metadatainjectorast-上下文栈)
   - [9.5 AST 净化器 Sanitizer：防御性编程](#95-ast-净化器-sanitizer防御性编程)
10. [节点关系模型与关系构建器](#10-节点关系模型与关系构建器)
11. [受控并发与批处理：摘要生成](#11-受控并发与批处理摘要生成)
   - [11.4 分布式限流：超越单进程 Semaphore](#114-分布式限流超越单进程-semaphore)
12. [检索层改造：利用 Node Relationships](#12-检索层改造利用-node-relationships)
13. [实施路线图](#13-实施路线图)
   - [Phase 0：评估基建](#157-重新排序后的实施路线图)
14. [风险与缓解措施](#14-风险与缓解措施)
15. [评估系统：Golden Dataset + 自动化 Benchmark](#15-评估系统golden-dataset--自动化-benchmark)

---

## 1. 现系统分析：保留什么，改什么

### 1.1 可以全力保留的现有基础设施

| 模块 | 保留理由 |
|------|----------|
| `FileParserFactory` + 各 `StructuredParser` | 策略模式设计优秀，PDF/Word/Excel/Markdown 解析到位，已输出 `StructuredDocument` 层次结构 |
| `StructuredDocument` / `DocumentBlock` / `DocumentSection` | 已支持 `BlockType.TABLE`, `HEADING`, `PARAGRAPH` 等类型，`TableData` 含表头+行数据，`build_hierarchy()` 构建了完整的标题树 |
| `DocumentChunk` 模型 (`models/chunk.py`) | 已有 `meta_info`(JSONB) 可扩展，`heading_path` 可保留标题层级，`chunk_start/end` 记录位置 |
| `EmbeddingService` 门面+适配器工厂 | 多 Provider 支持完善，单例接口统一，不改 |
| `TenantContextMiddleware` + 各 SQL 租户过滤 | 全局隔离机制成熟，新方案直接沿用 |
| `MinioService` | 对象存储不变 |
| `background_tasks` + `process_document_task()` | 异步处理框架不变，在调度链中插入新步骤 |

### 1.2 需要改造的关键短板

| 短板 | 现状 | 目标 |
|------|------|------|
| 无领域感知 | 所有文档用同一套 chunking 参数 | 根据 domain 调用不同的 ChunkStrategy |
| 无 Node Relationships | `DocumentChunk` 间无关联 | 增加 PARENT / CHILD / PREVIOUS / NEXT / SOURCE 关系 |
| 无元数据扩散 | `meta_info` 只存 chunk_index / source | 注入 domain、年份、季度、公司、币种、税种等 |
| 无时效管理 | 不感知生效/废止日期 | 注入 lifecycle 字段 |
| 无实体替换 | 合同保留"甲方""乙方" | 入库前用双路方案硬替换为真实实体名 |
| 无概括存留 | 父节点不存摘要 | PARENT 节点生成 50 字 Summary，受控并发生成 |
| 检索未利用关系 | `UnifiedRetriever` 只做向量余弦 | 检索时带上 PARENT Summary / PREVIOUS 上下文 |

### 1.3 不复用、不自研的内容

| 项目 | 决策理由 |
|------|----------|
| 不引入新向量数据库 | pgvector 足以支撑所有场景，现有 HNSW 索引不改 |
| 不做全文替换式 LLM 摘要 | 改为双路策略：LLM 只做结构化提取，代码层做执行替换 |
| 不做线性状态机 | 改为 AST 绑定的上下文栈，彻底解决元数据作用域泄漏 |

---

## 2. 整体架构设计

### 2.1 新入库流水线：两阶段解耦架构

**核心设计决断**：将流水线分为"物理切块落库"和"异步充血"两个阶段。所有依赖 LLM 的步骤（实体替换、摘要生成）都放到第二阶段。

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  Phase 1: 物理切块落库 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Upload ──→ Parse ──→ Domain Detection ──→ Domain Chunker ──→ Metadata Injection ──→ Embedding ──→ Storage (status = 'pending_enrichment')
                          │                                              │
                    ┌─────┴─────┐                                  [AST Sanitizer]
                    │           │                                 过滤伪标题 + 修复层级跳跃
              User-specified   LLM/Heuristic Auto-Detect

━━━━━━━━━━━━━━━━━━━━━━━━  Phase 2: 异步充血 (任务队列, 可重试) ━━━━━━━━━━━━━━━━━━━━━━━━━━

DLQ Task ──→ Entity Resolution ──→ Relationship Builder ──→ Summary Generation ──→ Update status = 'ready'
              (legal only)              (all domains)           (legal only)
```

**为什么必须两阶段**：

- **原子失败**：Phase 1 不依赖任何外部 LLM 服务，失败概率极低。切块和向量入库成功后，数据已可被检索
- **Partial Success**：Phase 2 中任何一个 LLM 调用失败（502/429），不会导致 Phase 1 的成果回滚
- **重试友好**：Phase 2 的 LLM 任务通过任务队列反复重试，不会阻塞用户上传

### 2.2 新模块目录结构

```
rag_backend/app/
├── chunkers/                                  # 改造现有目录
│   ├── __init__.py
│   ├── base_chunker.py                        # [改造] ChunkResult 增加字段
│   ├── domain_detector.py                     # [新增] 领域检测器
│   ├── domain_chunker_factory.py              # [新增] 领域切块工厂
│   ├── financial_chunker.py                   # [新增] 财务领域切块策略
│   ├── tax_chunker.py                         # [新增] 税务领域切块策略
│   ├── legal_chunker.py                       # [新增] 法务领域切块策略
│   ├── general_chunker.py                     # [新增] 默认切块策略（含 Auto-Merging）
│   ├── ast_sanitizer.py                       # [新增] AST 净化器：过滤伪标题 + 修复层级跳跃
│   ├── metadata_injector.py                   # [新增] AST 上下文栈元数据注入
│   ├── entity_resolver.py                     # [新增] 双路实体显式化（法务专用）
│   ├── summary_generator.py                   # [新增] 受控并发 PARENT 摘要生成（法务专用）
│   ├── relationship_builder.py                # [新增] 节点关系构建器
│   ├── structured_document_chunker.py         # [保留] 作为 GeneralChunker 的内核组件
│   └── plain_text_chunker.py                  # [保留] 纯文本兜底
├── models/
│   ├── chunk.py                               # [改造] DocumentChunk 增加 domain/node_type/summary/relationships/node_hash 字段
│   ├── document_enrichment_job.py             # [新增] 充血任务表（DLQ 持久化）
│   └── ...其他模型不变
├── tasks/
│   ├── arq_worker.py                          # [保留] ARQ Worker 入口
│   └── arq_tasks.py                           # [改造] 新增 EnrichmentTask（LLM 充血任务）
└── tests/
    └── evaluators/
        ├── test_retrieval_recall.py            # [新增] 召回率自动化评估
        └── golden_dataset/
            ├── documents/                      # [新增] 20 份测试文档
            └── queries.json                    # [新增] 100 条标准测试集
```

### 2.3 文档状态模型与死信队列

**文档级状态**（`Document.processing_state` 枚举值扩展）：

| 状态 | 含义 | 何时设置 |
|------|------|----------|
| `pending` | 刚上传，未开始处理 | 上传完成 |
| `chunking` | Phase 1 进行中 | 开始物理切块 |
| `ready` | Phase 1 完成，可被检索；Phase 2 未开始或已完成 | 切块落库完成 |
| `enriching` | Phase 2 进行中（LLM 实体替换/摘要生成） | 任务队列调度 |
| `enrichment_failed` | Phase 2 部分失败 | LLM 返回 502/429 |
| `failed` | Phase 1 失败 | 切块/向量化异常 |

**核心设计决断**：`ready` 状态在 Phase 1 完成后立即设置。Phase 2 的 `enriching`/`enrichment_failed` 状态对检索透明——用户的检索请求在 `status = 'ready'` 时即可返回结果，无需等待 Phase 2 完成。

**死信队列（DLQ）模型**：`app/models/document_enrichment_job.py`

```python
class EnrichmentJob(Base):
    """
    文档充血任务表（DLQ）

    记录 Phase 2 中失败的 LLM 依赖任务，供定时任务重试。
    与 Document 表解耦：文档本身已经是 'ready' 状态，不影响检索。
    """
    __tablename__ = "enrichment_jobs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    job_type = Column(String(20), nullable=False)       # entity_resolve / summary_generate
    domain = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")       # pending / running / failed / completed

    payload = Column(JSONB, default={})                  # 任务参数（如待处理的 chunk_id 列表）
    error_message = Column(Text, nullable=True)          # 最后一次失败的错误信息
    retry_count = Column(Integer, default=0)             # 已重试次数
    max_retries = Column(Integer, default=5)             # 最大重试次数（超过后标记为 dead）
    next_retry_at = Column(DateTime(timezone=True), nullable=True)  # 下一次重试时间（指数退避）

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

**恢复机制**：

```
定时任务 cron (每 5 分钟):
  1. SELECT * FROM enrichment_jobs
     WHERE status = 'failed' AND retry_count < max_retries AND next_retry_at <= NOW()
  2. 对每条记录：
     a. 推入任务队列
     b. 更新 status = 'running'
     c. 成功 → status = 'completed', 更新 Document 的 enrichment 字段
     d. 失败 → retry_count++, next_retry_at = NOW() + 2^retry_count * 60s (指数退避)
       如果 retry_count >= max_retries → status = 'dead'（需人工介入）
```

**为什么需要 DLQ 而非简单重试**：
- 单次请求可能耗时几分钟（300 个摘要），挂在内存里重试会阻塞 worker
- 指数退避（2^retry * 60s）在 LLM 服务大面积故障时保护 API
- DLQ 记录落库，即使整个服务重启也不丢失待办任务

---

## 3. 领域检测器

### 3.1 文件：`app/chunkers/domain_detector.py`

```python
class DomainDetector:
    """
    领域检测器

    三级策略（从上到下优先级递减）：
    1. 用户上传时选择的 KB category（显式指定，最高优先级）
    2. 文件名启发式匹配
    3. LLM 快速分类（极简 Prompt，单 token 输出）
    """

    # 文件名启发式规则
    FILENAME_PATTERNS = {
        "finance": ["财报", "审计", "财务", "利润表", "资产负债表", "年报", "季报", "营收"],
        "tax": ["税务", "税法", "增值税", "所得税", "发票", "纳税", "申报"],
        "legal": ["合同", "协议", "法务", "条款", "律师", "诉讼", "判决", "裁定"],
    }

    async def detect(
        self,
        filename: str,
        parsed_doc: StructuredDocument,
        kb_category: str | None = None
    ) -> str:
        """
        检测文档领域

        Returns:
            "finance" | "tax" | "legal" | "general"
        """
        # 1. 用户显式指定
        if kb_category and kb_category in ("finance", "tax", "legal", "general"):
            return kb_category

        # 2. 文件名启发式
        for domain, keywords in self.FILENAME_PATTERNS.items():
            if any(kw in filename for kw in keywords):
                return domain

        # 3. LLM 快速分类
        return await self._llm_classify(parsed_doc) or "general"

    async def _llm_classify(self, doc: StructuredDocument) -> str | None:
        """极简 LLM 分类，单 token 输出"""
        preview = doc.to_markdown()[:800]
        prompt = f"""分类以下文档的领域，只输出一个词：
finance - 财务报告、审计、营收数据等
tax - 税务法规、申报流程等
legal - 合同、协议、法律条款等
general - 其他

文档预览：
{preview}

输出：
"""
        try:
            result = await llm_service.get_answer(prompt, [], [])
            result = result.strip().lower()
            if result in ("finance", "tax", "legal"):
                return result
            return "general"
        except Exception:
            return "general"
```

### 3.2 设计要点

- 分类结果写入 `Document.meta_info["domain"]`
- 支持缓存（文档 hash → domain），避免重复调用 LLM
- LLM 失败或超时时默认回退到 `general`，不影响主流程

---

## 4. ChunkResult 数据类增强

### 4.1 文件：`app/chunkers/base_chunker.py`

```python
@dataclass
class ChunkResult:
    """增强后的切块结果（v2）"""
    # ==== 原有字段 ====
    content: str
    start: int
    end: int
    tokens: int
    heading_path: str | None = None
    metadata: dict | None = None

    # ==== 新增字段 ====
    domain: str = "general"                     # finance / tax / legal / general
    node_type: str = "leaf"                     # root / parent / leaf
    chunk_index: int = 0                        # 全局序号
    relationships: dict | None = None           # {"PARENT": "parent_uuid", "CHILDREN": [...], ...}
    summary: str | None = None                  # PARENT 节点摘要（仅 legal domain）
    block_type: str | None = None               # table / paragraph / code / list（源自 DocumentBlock.type）
    entity_map: dict | None = None              # 实体替换映射表（仅 legal domain）
```

---

## 5. 财务类 Financial：表格孤岛重构 + 树绑定元数据

### 5.1 文件：`app/chunkers/financial_chunker.py`

**设计思路**：财务数据的核心矛盾是"文本连续性 vs 表格完整性"。当前系统已能做到 `BlockType.TABLE` 识别，但做的是"按 token 合并"，会把表格和文本合并在一起，或者把大表格切碎。

### 5.2 切块规则

**规则 A：表格级原子化**

```
遇到一个 Table Block：
  ├── 表头行数 ≤ 20 且 总行数 ≤ 200 → 整个表格作为 1 个 Chunk，不做切分
  └── 表头行数 > 20 或 总行数 > 200 → 保留完整表头，按逻辑行组拆分（每 30 行一组）
                                       每组复制表头，称为 Sub-Table
```

注意：如果表格前的解释性文本中含有"单位：万元"等信息，该信息必须注入到表格的 metadata 中。

**规则 B：表格-正文上下文剥离+链接**

```
解析到 Table Block 之前的一段 Paragraph → 此为表格的"上下文前言"
  ├── 正文段落作为 PARENT Node（node_type = "parent"）
  └── 表格作为 CHILD Node（node_type = "leaf"）
  └── PARENT.relationships["CHILDREN"] = [table_node_id1, ...]
  └── CHILD.relationships["PARENT"] = parent_node_id
```

为何不合并？向量检索时，单独匹配表格的行比匹配一个混合了大段文字的 chunk 更精确。检索命中表格时，通过 PARENT 指针可以带回上下文。

### 5.3 实现要点

`FinancialChunker` 不重新实现所有逻辑，而是包装 `StructuredDocumentChunker`：

```python
class FinancialChunker:
    def __init__(self):
        self._inner = StructuredDocumentChunker()

    def chunk(self, structured_doc: StructuredDocument,
              chunk_tokens: int = 800,
              overlap_tokens: int = 80) -> List[ChunkResult]:
        # 1. 用现有 chunker 生成初始块
        raw_chunks = self._inner.chunk_structured_document(
            structured_doc, chunk_tokens, overlap_tokens
        )

        # 2. 表格原子化后处理
        chunks = []
        for chunk in raw_chunks:
            if chunk.metadata.get("block_types") == ["table"]:
                # 表格块 → 按财务规则拆分
                table_chunks = self._split_financial_table(chunk)
                chunks.extend(table_chunks)
            else:
                chunks.append(chunk)

        # 3. 上下文剥离 + 建立关系
        return self._link_context_to_tables(chunks)

    def _split_financial_table(self, chunk: ChunkResult) -> List[ChunkResult]:
        """表格原子化拆分"""
        # 实现略：解析 markdown 表格格式，统计行数
        # 小表 → 保留完整
        # 大表 → 保留表头，每 N 行一组
        ...

    def _link_context_to_tables(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """将表格前方的正文段落设为 PARENT，表格设为 CHILD"""
        # 实现略：扫描 chunk 序列，检测 pattern [text_chunk, table_chunk]
        # 建立 PARENT/CHILDREN 双向关系
        ...
```

### 5.4 Node 示例

```json
{
  "node_id": "fin_table_882",
  "text": "| 研发费用 | 1.2亿 | 1.5亿 (同比+25%) |",
  "metadata": {
    "domain": "finance",
    "year": "2023",
    "quarter": "Q4",
    "company": "字节跳动",
    "currency": "CNY",
    "report_type": "利润表",
    "table_title": "主要财务指标"
  },
  "relationships": {
    "PARENT": "fin_text_881"
  },
  "node_type": "leaf"
}
```

---

## 6. 税务类 Tax：条款级切片 + 生命周期打标

### 6.1 文件：`app/chunkers/tax_chunker.py`

**设计思路**：税务文件是"带有有效期的可执行代码"。切块必须以法条为边界，而不是自然段。

### 6.2 切块规则

```
输入：经过 StructuredParser 解析后的 Markdown 文本
处理流程：
  1. 正则匹配 "第[一二三四五六七八九十百千]+条" / "第\\d+条" / "（[一二三四五六七八九十]+）"
  2. "第一条" 到 "第二条" 之间为一个完整 Clause Node
  3. "第二款" 到 "第三款" 之间为一个 Sub-Clause Node

边界条件：
  - 条款不含子款 → 单 Node，node_type = "leaf"
  - 条款含多款 → 父条款为 PARENT，子款为 CHILD
  - 超过 1024 token 的条款 → 按自然段再次切分但仍标记为同一 Clause 族
```

### 6.3 元数据生命周期提取

```python
# 内嵌在 tax_chunker.py 或独立工具函数

def extract_lifecycle_metadata(full_text: str) -> dict:
    """
    从文档头部提取生命周期元数据

    提取规则：
    - "发文日期：YYYY年MM月DD日" → effective_date
    - "施行日期：YYYY年MM月DD日" → effective_date
    - "废止：YYYY年MM月DD日" / "同时废止" → expiry_date
    - 未明确废止 → expiry_date = "2099-12-31"
    - "增值税" / "企业所得税" / "个人所得税" → tax_type
    - "上海市" / "全国" → region
    """
    metadata = {"expiry_date": "2099-12-31"}

    # 只扫描前 50 行（头部）
    header = "\n".join(full_text.split("\n")[:50])

    # 发文日期 / 施行日期
    for pattern in [r"(发文|施行|公布)日期[：:]\s*(\d{4})[年/](\d{1,2})[月/](\d{1,2})",
                    r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})日起施行"]:
        match = re.search(pattern, header)
        if match:
            metadata["effective_date"] = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
            break

    # 废止日期
    expiry_match = re.search(r"(废止|同时废止|有效期至)[^。]*?(\d{4})[年/](\d{1,2})[月/](\d{1,2})", header)
    if expiry_match:
        metadata["expiry_date"] = f"{expiry_match.group(1)}-{expiry_match.group(2).zfill(2)}-{expiry_match.group(3).zfill(2)}"

    # 税种
    for tax_type in ["增值税", "企业所得税", "个人所得税", "消费税", "关税",
                     "印花税", "房产税", "土地使用税", "契税", "城市维护建设税"]:
        if tax_type in full_text:
            metadata["tax_type"] = tax_type
            break

    # 地域
    for region in ["全国", "北京市", "上海市", "广东省", "浙江省", "江苏省",
                   "深圳市", "广州市"]:
        if region in full_text and "适用" in full_text:
            metadata["region"] = region
            break

    return metadata
```

### 6.4 Node Relationships

```json
{
  "node_id": "tax_clause_102",
  "text": "第三条：高新技术企业减按15%的税率征收企业所得税。",
  "metadata": {
    "domain": "tax",
    "tax_type": "企业所得税",
    "region": "全国",
    "effective_date": "2008-01-01",
    "expiry_date": "2099-12-31"
  },
  "relationships": {
    "PARENT": "tax_doc_005",
    "PREVIOUS": "tax_clause_101",
    "NEXT": "tax_clause_103"
  },
  "node_type": "leaf"
}
```

---

## 7. 法务类 Legal：AST 切分 + 双路实体解析 + 概括存留

### 7.1 文件：`app/chunkers/legal_chunker.py`

**设计思路**：合同是逻辑嵌套树。利用现有的 `StructuredDocument.build_hierarchy()` 层级 + `DocumentBlock.level` 缩进，构建 AST。

### 7.2 切块规则：层级树状切分

```python
class LegalChunker:
    """法务文档 AST 切分器"""

    def chunk(self, structured_doc: StructuredDocument) -> List[ChunkResult]:
        """
        基于 AST 层级切分法律文档

        策略：
        - 叶节点 = 最小不可分割的法律条款
        - 内部节点 = 章节标题，node_type = "parent"
        - 每个内部节点保留其下所有子节点的内容全文（用于摘要生成）
        """
        chunks = []
        self._traverse_sections(
            sections=structured_doc.sections,
            parent_path=[],
            chunks=chunks
        )
        return chunks

    def _traverse_sections(
        self,
        sections: List[DocumentSection],
        parent_path: List[str],
        chunks: List[ChunkResult]
    ):
        """DFS 遍历并生成 chunk"""
        for section in sections:
            current_path = parent_path + [section.heading]
            heading_path = " > ".join(current_path)

            # 为该章节创建 PARENT Node（包含其下所有子节点的全文聚合）
            parent_chunk = ChunkResult(
                content=section.get_full_content(),
                start=0,
                end=0,
                tokens=self._approx_token_len(section.get_full_content()),
                heading_path=heading_path,
                node_type="parent",
                domain="legal",
                metadata={
                    "section_title": section.heading,
                    "section_level": section.level,
                }
            )
            chunks.append(parent_chunk)

            # 为该章节的每个独立条款创建 LEAF Node
            for block in section.blocks:
                if block.type == BlockType.PARAGRAPH and block.content.strip():
                    leaf_chunk = ChunkResult(
                        content=block.content,
                        start=0,
                        end=0,
                        tokens=self._approx_token_len(block.content),
                        heading_path=heading_path,
                        node_type="leaf",
                        domain="legal",
                        metadata={"block_type": "clause"},
                        # 关系：指向 PARENT
                        relationships={"PARENT": parent_chunk.chunk_index}
                    )
                    chunks.append(leaf_chunk)

            # 递归子章节
            if section.subsections:
                self._traverse_sections(section.subsections, current_path, chunks)
```

注意：`PARENT` 节点的 `chunk_index` 需要在调用方（`RelationshipBuilder`）中通过 `id` 关联，这里用 `chunk_index` 做占位，实际存储时替换为数据库生成的 UUID。

### 7.3 实体显式化：双路解析 (Two-Pass Hybrid)

**文件：`app/chunkers/entity_resolver.py`**

**为什么纯正则不行**：真实中文合同中，简称定义变体多达几十种：

```
（以下简称"甲方"）     ✓ 标准格式
（以下简称甲方）        ✓ 省去引号
，简称"乙方"           ✓ 逗号+简称
（即丙方）              ✓ 即
买方（甲方）：XX公司   ✓ 段落内嵌
甲方：XX科技有限公司   ✓ 极简
以下称"丁方"           ✓ 以下称
以下简称为"戊方"       ✓ 以下简称为
```

正则去硬扛这些变体，维护成本极高且召回率断崖式下跌。如果映射表建错，全文替换就全毁了。

**双路方案**：

```
Pass 1 (LLM 结构化提取) ──→ 构建映射字典 {"甲方": "XX科技有限公司"}
Pass 2 (纯 str.replace)  ──→ 对全文 chunk 做字符串替换
```

```python
class EntityResolver:
    """
    法务实体显式化器

    双路策略：
    - LLM 从合同头部提取实体映射表（负责"理解"，容错变体）
    - 纯 str.replace 洗稿所有 chunk（负责"执行"，绝不出幻觉）

    理解能力和执行能力分离，各自的弱点不会叠加。
    """

    # 实体标记模板：替换后的格式为 "XX科技有限公司(原称:甲方)"
    ENTITY_MARKER_TEMPLATE = "{real_name}(原称:{original})"

    async def resolve(
        self,
        structured_doc: StructuredDocument,
        chunks: List[ChunkResult]
    ) -> List[ChunkResult]:
        """
        双路解析主入口
        """
        # Step 1: 提取合同前 20 blocks（或前 3000 字符）
        preamble = self._extract_preamble(structured_doc)
        if not preamble:
            logger.warning("[EntityResolver] 未提取到头文本，跳过")
            return chunks

        # Step 2: LLM 构建字典
        entity_map = await self._extract_entity_map(preamble)
        if not entity_map:
            logger.warning("[EntityResolver] LLM 未提取到实体映射，跳过")
            return chunks

        logger.info(f"[EntityResolver] 提取到 {len(entity_map)} 个映射: {entity_map}")

        # Step 3: 按原始词长度降序排序（避免"甲方"覆盖"甲"）
        sorted_terms = sorted(entity_map.keys(), key=len, reverse=True)

        # Step 4: 对每个 chunk 执行纯字符串替换
        for chunk in chunks:
            for term in sorted_terms:
                real_name = entity_map[term]
                replacement = self.ENTITY_MARKER_TEMPLATE.format(
                    real_name=real_name, original=term
                )
                chunk.content = chunk.content.replace(term, replacement)

        # 将映射表存入文档级 metadata 以便追溯
        chunks[0].entity_map = entity_map if chunks else None
        return chunks

    async def _extract_entity_map(self, preamble: str) -> Dict[str, str]:
        """
        调用 LLM 提取实体映射表

        Prompt 设计要点：
        - 输出必须是纯 JSON，禁止 markdown 代码块
        - 示例驱动，减少幻觉
        - 单次调用，不需要流式
        """
        prompt = f"""你是一个法务文档解析专家。请从以下合同/协议的开头部分，提取所有简称-全称的对应关系。

【规则】
1. 仅提取"简称→全称"映射
2. 注意识别各种写法变体：'（以下简称"甲方"）'、'，简称"乙方"'、'（即丙方）'、段落起始的'买方（甲方）：XX公司'
3. 全称必须是完整的公司名称或个人姓名
4. 如果没有找到任何映射，返回 {{}}

【输出格式】
纯 JSON，不要 markdown 代码块：

{{"甲方": "XX科技有限公司", "乙方": "YY供应链有限公司"}}

【合同开头部分】
{preamble[:3000]}
"""
        try:
            response = await llm_service.get_answer(prompt, [], [])
            response = response.strip()
            # 清理 markdown 代码块标记（如果 LLM 不听话）
            if response.startswith("```"):
                response = response.split("\n", 1)[-1]
                response = response.rsplit("```", 1)[0]
            entity_map = json.loads(response.strip())
            return entity_map if isinstance(entity_map, dict) else {}
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[EntityResolver] LLM 提取失败: {e}")
            return {}

    def _extract_preamble(self, doc: StructuredDocument) -> str:
        """提取合约开头文本：取前 20 个 block 或第一个 section"""
        blocks = doc.raw_blocks[:20] if doc.raw_blocks else []
        if not blocks and doc.sections:
            blocks = doc.sections[0].blocks[:20]
        return "\n".join(b.content for b in blocks if b.content)[:3000]
```

### 7.4 概括存留：受控并发与批处理

此部分在[第 11 节](#11-受控并发与批处理摘要生成)中统一设计。

### 7.5 Node 示例

```json
{
  "node_id": "legal_clause_551",
  "text": "如果 XX科技有限公司(原称:甲方) 未能在规定时间内付款，需支付每日万分之五的违约金。",
  "metadata": {
    "domain": "legal",
    "contract_type": "采购合同",
    "governing_law": "PRC",
    "clause_number": "8.3"
  },
  "relationships": {
    "PARENT": "legal_section_550",
    "SOURCE": "contract_pdf_001"
  },
  "node_type": "leaf"
}
```

PARENT 节点：
```json
{
  "node_id": "legal_section_550",
  "text": "（完整章节原文...）",
  "summary": "规定了逾期付款的违约责任及赔偿标准",
  "node_type": "parent",
  "relationships": {
    "CHILDREN": ["legal_clause_551", "legal_clause_552"]
  }
}
```

---

## 8. 默认通用类 General：Markdown 层级 + Auto-Merging

### 8.1 文件：`app/chunkers/general_chunker.py`

**设计思路**：复用现有 `StructuredDocumentChunker` 的能力，加上 Auto-Merging 策略。

### 8.2 双粒度切块策略

```
输入：StructuredDocument（含完整 heading 层级）
  │
  ├── Step 1: 按 heading 边界切分大块 (Parent Nodes)
  │     目标 1024 token，以标题（H1/H2/H3）为边界
  │     如果两个标题之间超过 1024 token，通过句号软切分
  │
  ├── Step 2: 对大块再切分为小块 (Leaf Nodes)
  │     目标 256 token，以句号/换行为边界
  │     保留 heading_path 继承自父节点
  │
  └── Step 3: 建立 PARENT → CHILDREN 关系
         Leaf.relationships["PARENT"] = parent_node.id
         Parent.relationships["CHILDREN"] = [leaf1.id, leaf2.id, ...]
```

### 8.3 为什么双粒度？

| | Small Leaf (256 tok) | Large Parent (1024 tok) |
|---|---|---|
| **检索精度** | 高 — 语义最浓缩，匹配精准 | 低 — 信息混合 |
| **上下文完整性** | 低 — 可能信息不全 | 高 — 包含完整段落 |
| **用途** | 向量检索匹配 | 命中后作为附加上下文喂给 LLM |

### 8.4 与现有代码的关系

```python
class GeneralChunker:
    def __init__(self):
        self._inner = StructuredDocumentChunker()

    def chunk(self, structured_doc: StructuredDocument,
              chunk_tokens: int = 800,
              overlap_tokens: int = 80) -> List[ChunkResult]:
        # Step 1: 用现有 chunker 生成父块（1024 token 目标）
        parent_chunks = self._inner.chunk_structured_document(
            structured_doc,
            chunk_tokens=chunk_tokens,      # 传入 chunk_tokens（如 1024）
            overlap_tokens=overlap_tokens
        )
        # 标记为 parent
        for c in parent_chunks:
            c.node_type = "parent"

        # Step 2: 对每个父块做细分（256 token 目标）
        leaf_chunks = []
        for parent in parent_chunks:
            leaves = self._split_into_leaves(parent, leaf_tokens=256)
            for leaf in leaves:
                leaf.node_type = "leaf"
                leaf.relationships = {"PARENT": parent.chunk_index}
            leaf_chunks.extend(leaves)

        # Step 3: 建立 PARENT → CHILDREN 反向引用
        parent_to_children = {}
        for leaf in leaf_chunks:
            parent_idx = leaf.relationships["PARENT"]
            parent_to_children.setdefault(parent_idx, []).append(leaf)

        for parent in parent_chunks:
            if parent.chunk_index in parent_to_children:
                child_indices = [
                    c.chunk_index for c in parent_to_children[parent.chunk_index]
                ]
                parent.relationships = {"CHILDREN": child_indices}

        # 返回 LEAF 用于向量入库，PARENT 也保留但只存 summary 不存向量
        return leaf_chunks + parent_chunks
```

---

## 9. 元数据注入器 MetadataInjector：AST 上下文栈

### 9.1 问题背景：线性状态机的作用域泄漏

原方案（v1）的线性状态机在遇到以下场景时会出错：

```
H1 "2023年财务总结"              → 状态机进入 STATE_IN_YEAR (2023)  ✓
├── H2 "收入分析"               → 正确继承 2023
│   └── H3 "产品线收入"         → 正确继承 2023
├── H2 "2022年历史数据对比"     → 状态机切换到 2022             ✓
│   └── H3 "按季度拆分"         → 正确继承 2022
└── H2 "下半年展望"             → 线性状态机认为还在 2022 ❌ 致命！
                                  但实际上应恢复到 2023
```

**根因**：文档是一个树，不是线性列表。线性状态机在进入平行兄弟节点时无法正确恢复父级上下文。

### 9.2 解决方案：AST 绑定的上下文栈 (Context Stack)

**文件：`app/chunkers/metadata_injector.py`**

```python
@dataclass
class ContextFrame:
    """一个标题层级的上下文快照"""
    level: int                       # H1=1, H2=2, H3=3
    heading_text: str                # 该层级的标题原文
    metadata: Dict[str, Any]         # 在该层级提取到的元数据（含从父级继承的）


class ContextStack:
    """
    上下文栈：绑定到 DocumentSection 树深度的栈结构

    核心规则：
    - 进入一个 Section → 从父节点继承元数据 + 在当前 heading 中提取 → Push 新 Frame
    - 离开一个 Section → Pop 该层级 Frame，恢复父级元数据

    关键保证：兄弟节点之间零元数据泄漏。
    """

    def __init__(self):
        self._stack: List[ContextFrame] = []

    def enter_section(self, level: int, heading: str) -> Dict[str, Any]:
        """
        进入一个新章节。

        返回该章节的完整合并元数据（继承 + 当前提取）。
        """
        # 退栈：丢弃所有 level >= 当前 level 的帧
        # （即退出已结束的深层子章节）
        while self._stack and self._stack[-1].level >= level:
            self._stack.pop()

        # 从父级继承元数据
        inherited = {}
        if self._stack:
            inherited = dict(self._stack[-1].metadata)

        # 在当前 heading 中提取新元数据
        extracted = self._extract_from_heading(heading)

        # 合并：extracted 覆盖 inherited（子级覆盖父级同名键）
        merged = {**inherited, **extracted}

        # Push 新帧
        self._stack.append(ContextFrame(
            level=level,
            heading_text=heading,
            metadata=merged
        ))

        return merged

    def get_current_context(self) -> Dict[str, Any]:
        """获取当前栈顶的完整元数据"""
        if not self._stack:
            return {}
        return dict(self._stack[-1].metadata)

    # ======== 内置 heading 提取规则 ========

    HEADING_EXTRACTORS = [
        (r"(\d{4})\s*年", "year"),
        (r"Q([1-4])", "quarter", lambda m: f"Q{m.group(1)}"),
        (r"第([一二三四])季度", "quarter", lambda m: f"Q{self._cn_to_num(m.group(1))}"),
        (r"(利润表|资产负债表|现金流量表|所有者权益变动表)", "report_type"),
        (r"([\u4e00-\u9fa5]{2,10}(?:公司|集团|有限))", "company"),
        (r"(人民币|USD|CNY|美元|欧元|港币)", "currency"),
    ]

    def _extract_from_heading(self, heading: str) -> Dict[str, str]:
        """从标题文本中提取元数据键值对"""
        result = {}
        for pattern, key, *transform in self.HEADING_EXTRACTORS:
            match = re.search(pattern, heading)
            if match:
                value = transform[0](match) if transform else match.group(1)
                result[key] = value
        return result
```

### 9.3 MetadataInjector 集成到流水线

```python
class MetadataInjector:
    """
    元数据注入器：遍历 DocumentSection 树，为每个 ChunkResult 分配正确的元数据

    遍历方式：先序遍历（DFS），与 chunk 生成的顺序一致
    注入时机：chunking 完成之后，embedding 之前
    """

    def inject(
        self,
        structured_doc: StructuredDocument,
        chunks: List[ChunkResult]
    ) -> List[ChunkResult]:
        """
        主入口：为 chunks 注入领域元数据
        """
        context_stack = ContextStack()
        # section_heading → metadata 映射表
        section_metadata: Dict[str, Dict] = {}

        # DFS 遍历树，构建 heading_path → metadata 映射
        self._walk_sections(structured_doc.sections, context_stack, section_metadata)

        # 为每个 chunk 匹配其所在的 section 元数据
        for chunk in chunks:
            if chunk.heading_path and chunk.heading_path in section_metadata:
                # 注入，但保留 chunk 自身 metadata 的优先级
                chunk.metadata = {
                    **section_metadata[chunk.heading_path],
                    **chunk.metadata
                }
            else:
                # 精确路径不匹配 → 最长前缀匹配
                matched = self._longest_prefix_match(chunk.heading_path, section_metadata)
                if matched:
                    chunk.metadata = {
                        **section_metadata[matched],
                        **chunk.metadata
                    }

        return chunks

    def _walk_sections(
        self,
        sections: List[DocumentSection],
        stack: ContextStack,
        output: Dict[str, Dict]
    ):
        """DFS 遍历并构建上下文映射"""
        for section in sections:
            merged = stack.enter_section(section.level, section.heading)
            output[section.heading] = merged

            if section.subsections:
                self._walk_sections(section.subsections, stack, output)

            # 递归返回时不需要显式 pop，ContextStack 在下一个 enter_section 中自动处理

    @staticmethod
    def _longest_prefix_match(
        target: str | None,
        mapping: Dict[str, Any]
    ) -> str | None:
        """查找最长的 heading_path 前缀匹配"""
        if not target:
            return None
        parts = target.split(" > ")
        for i in range(len(parts) - 1, 0, -1):
            prefix = " > ".join(parts[:i])
            if prefix in mapping:
                return prefix
        return None
```

### 9.4 正确的注入效果

```
Document Tree                          Context Stack State                    Chunk 元数据
─────────────────────────────────────────────────────────────────────────────────────────
H1 "2023年财务总结"                  Stack: [{l1: {year:2023}}]               {year:2023}
├── H2 "收入分析"                    Stack: [{l1}, {l2: {year:2023}}]         {year:2023}
│   └── H3 "产品线收入"              Stack: [{l1},{l2},{l3:{year:2023}}]      {year:2023}
├── H2 "2022年历史数据对比"          Pop→{l3}, Pop→{l2} → 恢复 {l1}
│                                    Push: [{l1}, {l2: {year:2022}}]          {year:2022}
│   └── H3 "按季度拆分"              Push: [{l1},{l2(y:2022)},{l3(y:2022)}]  {year:2022,Q1}
└── H2 "下半年展望"                  Pop→{l3}, Pop→{l2} → 恢复 {l1}
                                     Push: [{l1}, {l2: {year:2023}}]          {year:2023} ✓ 正确
```

### 9.5 AST 净化器（Sanitizer）：防御性编程

**问题**：上游 Parser 输出的标题层级不可信赖。真实企业文档中常见：

- **越级跳跃**：H1 下面直接跟 H3，没有 H2
- **伪标题**：正文段落因加粗且居中被误判为 H2，后续几十页的元数据被污染
- **超长标题**：OCR 将整个段落识别为标题

**设计决断**：在 `ContextStack.enter_section()` 之前，对所有 `DocumentSection` 执行一次"降噪清洗"。

```python
# 内嵌在 metadata_injector.py 顶部

class ASTSanitizer:
    """
    AST 净化器：防御性编程，不相信上游 Parser 的层级定义。

    主要工作：
    1. 强制拉平非法层级跳跃（H1→H3 → H1→H2→H3）
    2. 超长标题降级（>50 字符的"标题"强制降级为正文）
    3. 空标题过滤
    """

    MAX_HEADING_CHARS = 50      # 超过此长度的标题视为伪标题

    def sanitize_sections(self, sections: List[DocumentSection]) -> List[DocumentSection]:
        """
        清洗并修复一层的 sections，递归处理 subsections
        """
        if not sections:
            return []

        # 1. 超长标题降级
        sanitized = []
        for sec in sections:
            if len(sec.heading) > self.MAX_HEADING_CHARS:
                # 降级为普通正文段落：保留内容，但标记为非标题
                logger.warning(
                    f"[ASTSanitizer] 超长标题({len(sec.heading)}字符)降级为正文: "
                    f"'{sec.heading[:30]}...'"
                )
                # 该 section 的内容合并到父级或前一个兄弟节点
                continue  # 跳过此 section，其内容通过 blocks 保留
            sanitized.append(sec)

        # 2. 修复层级跳跃
        repaired = self._repair_level_jumps(sanitized)

        # 3. 递归子章节
        for sec in repaired:
            sec.subsections = self.sanitize_sections(sec.subsections)

        return repaired

    def _repair_level_jumps(self, sections: List[DocumentSection]) -> List[DocumentSection]:
        """
        修复非法层级跳跃。

        例：H1 → H3 (缺少 H2)
        修复为：H1 → H2 (level=2) → H3 (level=3)
        即创建一个"隐式父节点"来填补空缺。

        例：H2 → H2 (同层级)
        期望行为：保持同层级，不修复
        """
        if len(sections) <= 1:
            return sections

        repaired = []
        expected_level = sections[0].level  # 第一个 section 的 level 为准

        for sec in sections:
            if sec.level > expected_level + 1:
                # 越级跳跃：插入一个隐式父节点
                logger.info(
                    f"[ASTSanitizer] 修复层级跳跃: level {sec.level} "
                    f"(expected ≤ {expected_level + 1})"
                )
                # 创建隐式章节（heading 从上下文推断）
                implicit = DocumentSection(
                    heading=f"（{sec.heading} 所属章节）",
                    level=expected_level + 1,
                    subsections=[sec]
                )
                repaired.append(implicit)
            else:
                repaired.append(sec)
                # 更新期望层级
                expected_level = max(expected_level, sec.level)

        return repaired
```

**集成方式**：在 `MetadataInjector.inject()` 中，DFS 遍历之前先过 Sanitizer：

```python
class MetadataInjector:
    def inject(self, structured_doc, chunks):
        # [新增] AST 净化
        sanitizer = ASTSanitizer()
        structured_doc.sections = sanitizer.sanitize_sections(structured_doc.sections)

        # 原有的 DFS 遍历
        context_stack = ContextStack()
        # ... 其余逻辑不变 ...
```

### 10.1 DocumentChunk 模型改造

**文件：`app/models/chunk.py`**

```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    # ==== 现有字段 [保留] ====
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    meta_info = Column(JSONB, default={})
    embedding = Column(Vector(1024), nullable=True)
    heading_path = Column(String, nullable=True)
    chunk_start = Column(Integer, nullable=True)
    chunk_end = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    tenant_id = Column(String(50), nullable=True)

    # ==== 新增字段 ====
    domain = Column(String(20), nullable=True, index=True)        # finance/tax/legal/general
    node_type = Column(String(10), nullable=True, index=True)     # root/parent/leaf
    summary = Column(String(500), nullable=True)                  # PARENT 节点摘要（仅 legal）
    relationships = Column(JSONB, default={})                     # {"PARENT": "uuid", "CHILDREN": [...], ...}
    node_hash = Column(String(64), nullable=True, index=True)     # 内容哈希，用于增量更新去重
```

**设计理由**：
- `relationships` 用 JSONB 而非独立关系表：关系类型是动态的（每个 domain 有不同的关系种类），JSONB 查询灵活，避免 JOIN 开销
- `domain` 和 `node_type` 加索引：检索时可能需要按 domain 过滤或按 node_type 排除
- `node_hash` 用于文档更新时检测哪些 chunk 未变化可跳过重新 embedding

### 10.2 关系构建器

**文件：`app/chunkers/relationship_builder.py`**

```python
class RelationshipBuilder:
    """
    节点关系构建器

    在 chunking 全部完成后，根据 domain 建立节点间关系。
    所有 domain 共享一轮遍历即可完成，避免多遍扫描。
    """

    def build(
        self,
        chunks: List[ChunkResult],
        domain: str
    ) -> List[ChunkResult]:
        """
        根据 domain 建立关系

        注意：此时 chunks 中 chunk_index 是临时占位符，
        后续由存储层替换为真实的数据库 UUID。
        """
        if domain == "finance":
            return self._build_finance_relations(chunks)
        elif domain == "tax":
            return self._build_tax_relations(chunks)
        elif domain == "legal":
            return self._build_legal_relations(chunks)
        else:
            return self._build_general_relations(chunks)

    def _build_finance_relations(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """
        财务关系构建：
        扫描 chunk 序列，检测 pattern [text_chunk, table_chunk]
        文本段落作为 PARENT，表格作为 CHILD
        """
        # 实现略：一行遍历，检测前一个 chunk 是纯文本
        # 当前 chunk 是 table → 则建立关系
        ...

    def _build_tax_relations(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """
        税务关系构建：
        按 clause 序号建立 PREVIOUS / NEXT 指针
        """
        # 按 chunk_index 排序
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)
        for i, chunk in enumerate(sorted_chunks):
            if i > 0:
                chunk.relationships["PREVIOUS"] = sorted_chunks[i - 1].chunk_index
            if i < len(sorted_chunks) - 1:
                chunk.relationships["NEXT"] = sorted_chunks[i + 1].chunk_index
        return chunks

    def _build_legal_relations(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """
        法务关系构建：
        - leaf → PARENT 关系（已在 LegalChunker 中建立）
        - PARENT → CHILDREN 反向引用
        """
        parent_to_children = {}
        for chunk in chunks:
            if "PARENT" in (chunk.relationships or {}):
                parent_idx = chunk.relationships["PARENT"]
                parent_to_children.setdefault(parent_idx, []).append(chunk.chunk_index)

        for chunk in chunks:
            if chunk.chunk_index in parent_to_children:
                chunk.relationships["CHILDREN"] = parent_to_children[chunk.chunk_index]
        return chunks

    def _build_general_relations(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """通用关系构建：leaf → PARENT（已在 GeneralChunker 中建立）"""
        # 反向引用已经在 GeneralChunker 中做了
        return chunks
```

### 10.3 关系类型总表（含消费者定位）

| 关系 | 源节点 | 目标节点 | 适用 Domain | 语义 | **消费者** | 是否进入 LLM Prompt |
|------|--------|----------|-------------|------|------------|---------------------|
| `PARENT` | leaf | parent | all | 叶子节点的父级 | **大模型** → 仅取 summary 作为语义锚点 | 是（仅 summary, 50字） |
| `CHILDREN` | parent | [leaf, ...] | all | 父级包含的子节点列表 | **关系构建器** → 仅用于建库时反向引用 | 否 |
| `PREVIOUS` | clause | clause | tax | 前一条法条 | **大模型** → 前后文理解 | 是（截断到 200 字符） |
| `NEXT` | clause | clause | tax | 后一条法条 | **大模型** → 前后文理解 | 是（截断到 200 字符） |
| `SOURCE` | any | document | all | 来源文档引用 | **前端 UI** → 提供"查看原文"链接 | **绝对禁止** |

**关键原则**：
- `SOURCE` 的消费者是前端 UI 和后端溯源逻辑，**不是**大模型。将几万字的原合同全文扔进 Prompt 是对切块工程的彻底否定。
- `PARENT` 的消费者是大模型，但只消费其 50 字 `summary`，绝不允许 PARENT 全文进入 Prompt。
- `CHILDREN` 的消费者仅限入库时的关系构建器，检索阶段用不到。

---

## 11. 受控并发与批处理：摘要生成

### 11.1 文件：`app/chunkers/summary_generator.py`

**痛点**：一份 100 页合同可能产生 300 个 PARENT 节点。逐个 `await llm.generate()` 不仅极慢，还会打满 API rate limit。

### 11.2 设计方案

```python
class SummaryGenerator:
    """
    PARENT 节点摘要生成器

    三层保护：
    1. asyncio.Semaphore 严格控制并发数
    2. Batch Prompt 将多个文本合并为一次 LLM 调用
    3. 超时 + 降级：超时或失败时取原文前 50 字符为兜底
    """

    def __init__(
        self,
        max_concurrency: int = 10,    # 并发上限（适配常见 LLM API 的 rate limit）
        batch_size: int = 5,           # 每个 batch 的文本数
        timeout: float = 10.0,         # 单个 batch 超时
        fallback_chars: int = 50       # 降级截断长度
    ):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batch_size = batch_size
        self._timeout = timeout
        self._fallback_chars = fallback_chars

    async def generate_for_all(
        self,
        parent_chunks: List[ChunkResult]
    ) -> List[ChunkResult]:
        """
        为所有 PARENT 节点生成摘要

        策略：
        - 将 parent_chunks 按 batch_size 分组
        - 每组作为一个 batch request 发送
        - Semaphore 控制全局并发
        """
        if not parent_chunks:
            return parent_chunks

        # 按 batch 分组
        batches = [
            parent_chunks[i:i + self._batch_size]
            for i in range(0, len(parent_chunks), self._batch_size)
        ]

        logger.info(
            f"[SummaryGenerator] 开始为 {len(parent_chunks)} 个节点生成摘要, "
            f"{len(batches)} 个 batch, 并发上限 {self._semaphore._value}"
        )

        # 并发处理所有 batch（Semaphore 限制实际并发数）
        tasks = [self._process_batch(batch) for batch in batches]
        await asyncio.gather(*tasks)

        success_count = sum(1 for c in parent_chunks if c.summary and len(c.summary) > 10)
        logger.info(f"[SummaryGenerator] 完成: {success_count}/{len(parent_chunks)}")

        return parent_chunks

    async def _process_batch(self, batch: List[ChunkResult]):
        """处理一个 batch：受 Semaphore 和 timeout 双重保护"""
        async with self._semaphore:
            try:
                await asyncio.wait_for(
                    self._call_llm_batch(batch),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"[SummaryGenerator] Batch 超时 ({self._timeout}s), "
                    f"回退到截断摘要"
                )
                for chunk in batch:
                    chunk.summary = chunk.content[:self._fallback_chars]
            except Exception as e:
                logger.error(f"[SummaryGenerator] Batch 失败: {e}")
                for chunk in batch:
                    chunk.summary = chunk.content[:self._fallback_chars]

    async def _call_llm_batch(self, batch: List[ChunkResult]):
        """
        一次 LLM 调用生成 batch 内所有文本的摘要

        Batch Prompt 设计：
        - 要求 LLM 按序号输出（便于解析）
        - 每个原文截断到 300 字符（减少 token 消耗）
        - 输出格式：序号|摘要（一行一条，用 | 分隔，解析鲁棒）
        """
        lines = []
        for i, chunk in enumerate(batch, 1):
            content = chunk.content[:300]
            lines.append(f"{i}. {content}")

        prompt = f"""请为以下法律条款各生成一句不超过 50 字的摘要，概括其主要内容或法律义务。
按序号逐行输出，每行格式：序号|摘要

例子：
```
1|规定了逾期付款的违约金计算标准
2|明确了合同解除的条件和程序
```

{chr(10).join(lines)}
"""
        response = await llm_service.get_answer(prompt, [], [])
        self._parse_batch_response(response, batch)

    def _parse_batch_response(self, response: str, batch: List[ChunkResult]):
        """解析 LLM 的 batch 响应"""
        summaries = {}
        for line in response.strip().split("\n"):
            line = line.strip()
            if "|" in line:
                try:
                    idx_str, summary = line.split("|", 1)
                    idx = int(idx_str.strip())
                    summaries[idx] = summary.strip()
                except (ValueError, IndexError):
                    continue

        for i, chunk in enumerate(batch, 1):
            chunk.summary = summaries.get(i, chunk.content[:self._fallback_chars])
```

### 11.3 性能对比

```
无控制：     300 calls × 2s/call = 600s = 10 分钟  ← 可能触发 rate limit
Semaphore:   300 calls ÷ 10 concurrency × 2s = 60s ← 并发受控但调用次数不变
Batch化:     300 ÷ 5 batch_size = 60 次 API 调用
             60 次 ÷ 10 concurrency × 2s = 12s    ← 最优
             总耗时约 12 秒，原方案的 1/50
```

### 11.4 分布式限流：超越单进程 Semaphore

**问题**：`asyncio.Semaphore(10)` 只是**单进程级别**的保护。如果部署在 K8s 上开 5 个 Pod，或者用户批量上传 50 份合同：

```
5 Pods × 10 concurrency = 50 个并发请求 → LLM API 返回 HTTP 429 Too Many Requests → 全部失败
```

**解决方案**：将 LLM 密集型调用挂载到分布式任务队列上，由队列控制全局并发。

```python
# app/tasks/arq_tasks.py

class EnrichmentTask:
    """
    文档充血任务：统一由 ARQ 任务队列调度

    架构定位：
    - FastAPI 后台任务 (background_tasks) 只做 Phase 1（物理切块）
    - Phase 2（LLM 摘要生成）全部由 ARQ worker 执行
    - ARQ Redis 作为全局协调器：无论多少个 Pod，全局并发由 ARQ 控制
    """

    # ARQ 的 max_burst_jobs 控制全局并发（比 asyncio.Semaphore 可靠）
    # 在 Worker 初始化时设置：
    #   redis_settings = RedisSettings(...)
    #   worker = Worker(
    #       conn_settings,
    #       functions=[enrich_parent_summaries],
    #       max_burst_jobs=10,       # 全局最多 10 个并发 LLM 任务
    #       queue_name="llm_enrich"
    #   )

    @staticmethod
    async def enrich_parent_summaries(ctx, document_id: str, parent_chunk_ids: List[str]):
        """
        异步任务：为文档生成 PARENT 摘要

        由 ARQ Worker 从 Redis 队列拉取执行。
        全局只有 max_burst_jobs=10 个槽位，不会超限。
        """
        logger.info(f"[EnrichmentTask] 开始处理 document_id={document_id}, {len(parent_chunk_ids)} nodes")

        # 从数据库加载 parent chunks
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.id.in_([uuid.UUID(pid) for pid in parent_chunk_ids])
                )
            )
            parent_chunks = result.scalars().all()

        # 用已有的 SummaryGenerator 生成摘要
        generator = SummaryGenerator(max_concurrency=5, batch_size=5)
        # 注意：这里的 max_concurrency 是 Batch Prompt 内部的并发，
        # ARQ 的 max_burst_jobs 是全局级别的并发，
        # 两层叠加后最大 LLM 并发 = 10 × 5 = 50 通道
        # 但这 50 个通道共享同一个 Batch Prompt，实际 API 调用次数 = 50 ÷ batch_size = 10 次/秒
        await generator.generate_for_all(parent_chunks)

        # 更新数据库
        async with AsyncSessionLocal() as db:
            for chunk in parent_chunks:
                await db.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.id == chunk.id)
                    .values(summary=chunk.summary)
                )
            # 更新文档充血状态
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(processing_state="ready")
            )
            await db.commit()

        logger.info(f"[EnrichmentTask] document_id={document_id} 摘要生成完成")
```

**为什么 ARQ 比 Celery 更适合本项目**：
- 项目已有 ARQ 基础设施（`app/tasks/arq_worker.py`）
- ARQ 基于 Redis，零依赖
- `max_burst_jobs` 天然支持全局并发控制
- 与 FastAPI 的异步生态完美兼容

**降级路径**：如果 ARQ 不可用（开发环境），回退到本地 `asyncio.Semaphore`：

```python
async def enrich_parent_summaries_fallback(document_id, parent_chunk_ids):
    """开发环境降级：直接在当前进程执行"""
    generator = SummaryGenerator(max_concurrency=10, batch_size=5)
    # Semaphore 继续作为单进程的最后一道防线
    await generator.generate_for_all(parent_chunks)
```

---

## 12. 检索层改造：利用 Node Relationships

### 12.1 核心原则：三种关系的边界定位

在进入具体实现前，必须先确定每种关系类型的消费者及其在检索流程中的角色：

| 关系类型 | 消费者 | 在 Prompt 中的角色 | 内容边界 |
|----------|--------|--------------------|----------|
| **SOURCE** | **前端 UI + 业务溯源** | **绝不进入 LLM Prompt** | 仅作为 API 响应的元数据透传 |
| **PARENT** | **大模型** | **语义锚点**：为孤立的叶子节点提供上下文定位 | 仅取 `summary`(50字)；无 summary 时截断 PARENT.content 前 300 字符 |
| **PREVIOUS/NEXT** | **大模型** | **前后文桥接**：为法条类查询提供相邻条款 | 各取 200 字符，保证不击穿 token 预算 |

**最干净、容错率最高的拼接优先级**：
```
叶子节点原文 > PARENT 摘要 (summary) > PARENT 原文截断 (300字符)
├── SOURCE → 拦截在 Prompt 组装线之外，直接交给 API 响应
└── PREVIOUS/NEXT → 仅在 tax domain 启用，各自 200 字符上限
```

### 12.2 关系展开：Context Assembly（重写）

**改造点：`UnifiedRetriever._combine_context()`**

```python
# ============================================================
# 上下文组装：三种关系各有明确的消费者和内容边界
# - SOURCE → 不进入此函数，在 API 层透传
# - PARENT → 仅 summary 进入 Prompt
# - PREVIOUS/NEXT → 截断后进入 Prompt
# ============================================================

MAX_PARENT_CHARS = 300      # PARENT 全文降级时截断长度
MAX_PREV_NEXT_CHARS = 200   # 相邻条款截断长度

async def _combine_context_with_relationships(
    self,
    rag_results: List[SearchResultItem],
    memory_results: Dict[str, List[MemoryItem]],
    graph_results: Dict[str, Any],
    mode: RouteMode
) -> str:
    """
    在原有合并逻辑基础上，增加关系展开

    关键约束：
    1. SOURCE 关系禁止进入此函数（已在 API 层过滤）
    2. PARENT 仅取出 summary，绝不允许全文进入 Prompt
    3. PARENT 无 summary 则取 content[:300] 作为降级
    """
    context_parts = []

    # [原有逻辑：Memory 部分保持不变]
    if memory_results:
        if memory_results.get("working"):
            working_context = "【当前对话】\n"
            for item in memory_results["working"]:
                working_context += f"{item.role}: {item.content}\n"
            context_parts.append(working_context)
        # ... 其他 memory 部分与原有逻辑一致 ...

    # [重写：RAG 结果的关系展开]
    if rag_results:
        rag_context = "\n<KnowledgeBase>\n"
        for idx, result in enumerate(rag_results[:5], 1):
            # ── Step 1: PARENT summary（语义锚点）──
            # 仅取 summary，绝不要 PARENT 全文
            parent_summary = await self._resolve_parent_summary(result)
            if parent_summary:
                rag_context += f"[章节背景]: {parent_summary}\n"

            # ── Step 2: PREVIOUS/NEXT（仅 tax domain）──
            prev_next = await self._resolve_prev_next(result)
            if prev_next["previous"]:
                rag_context += f"[前一条款]: {prev_next['previous']}\n"

            # ── Step 3: 命中节点原文 ──
            rag_context += f"[具体条款]: {result.content[:500]}\n"

            if prev_next["next"]:
                rag_context += f"[后一条款]: {prev_next['next']}\n"

            rag_context += "\n"

        rag_context += "</KnowledgeBase>\n"
        context_parts.append(rag_context)

    return "\n".join(context_parts)


async def _resolve_parent_summary(self, result: SearchResultItem) -> str | None:
    """
    获取 PARENT 的语义锚点

    优先级：
    1. parent.summary（50 字摘要，最优方案）
    2. parent.content[:MAX_PARENT_CHARS]（降级方案，300 字符截断）
    3. None（连 parent 都不存在）

    绝对不做的事：
    - ❌ 不返回 PARENT 全文
    - ❌ 不将 SOURCE 文档内容混入此处
    """
    chunk_id = result.chunk_id
    chunk = await chunk_repo.get_by_id(chunk_id)
    if not chunk or not chunk.relationships:
        return None

    parent_id = chunk.relationships.get("PARENT")
    if not parent_id:
        return None

    parent = await chunk_repo.get_by_id(parent_id)
    if not parent:
        return None

    # 一级优先级：summary（仅 50 字，Token 消耗极小）
    if parent.summary and len(parent.summary) > 5:
        return parent.summary

    # 二级降级：content 前 300 字符（防止长章节击穿上下文）
    return parent.content[:MAX_PARENT_CHARS]


async def _resolve_prev_next(self, result: SearchResultItem) -> Dict[str, str | None]:
    """
    获取 PREVIOUS/NEXT 相邻条款

    所有内容截断到 MAX_PREV_NEXT_CHARS（200 字符），
    防止相邻条款过长导致 token 超限。
    """
    chunk_id = result.chunk_id
    chunk = await chunk_repo.get_by_id(chunk_id)
    if not chunk or not chunk.relationships:
        return {"previous": None, "next": None}

    prev_id = chunk.relationships.get("PREVIOUS")
    next_id = chunk.relationships.get("NEXT")
    prev_content = None
    next_content = None

    if prev_id:
        prev = await chunk_repo.get_by_id(prev_id)
        if prev:
            prev_content = prev.content[:MAX_PREV_NEXT_CHARS]

    if next_id:
        nxt = await chunk_repo.get_by_id(next_id)
        if nxt:
            next_content = nxt.content[:MAX_PREV_NEXT_CHARS]

    return {"previous": prev_content, "next": next_content}
```

### 12.3 SOURCE 的处理：拦截在 Prompt 之外

**SOURCE 进入 Prompt = 切块工程被否定。** 将几万字的原合同扔进 LLM 上下文，等于没有做 chunking。

正确的 SOURCE 处理路径：

```
检索命中 leaf node
  │
  ├── leaf.content           → 进入 LLM Prompt（核心检索结果）
  ├── PARENT.summary         → 进入 LLM Prompt（语义锚点）
  ├── PREVIOUS/NEXT.content  → 进入 LLM Prompt（前后文桥接）
  │
  └── SOURCE 元数据           → 不进入 Prompt
       ├── source_document_id
       ├── source_filename     ──→ API 响应 → 前端渲染 → "查看原文 [PDF]" 按钮
       └── source_page
```

**实现方式**：在 API 响应（`ChatResponse` / `SearchResultItem`）中增加 `source_document` 字段，由前端自行渲染链接。

```python
# app/schemas/chat.py 改造

class SearchResultItem(BaseModel):
    """搜索结果条目"""
    chunk_id: str
    document_id: str
    score: float
    content: str
    source_file: str
    page_number: int | None = None

    # [新增] SOURCE 元数据（仅透传，不进入 LLM）
    source_document: SourceDocumentMeta | None = None

    # [新增] PARENT 摘要（前端调试/展示用，不强制依赖）
    parent_summary: str | None = None


class SourceDocumentMeta(BaseModel):
    """
    SOURCE 文档元数据

    消费者：前端 UI
    用途：提供给前端的"查看原文"链接，不进入 LLM 上下文
    """
    document_id: str
    filename: str
    file_url: str                     # MinIO 或 CDN 链接
    page_number: int | None = None
    total_pages: int | None = None
```

```python
# 在 chat.py 的流式响应构建中

sources_data = [
    {
        "filename": res.source_file,
        "score": res.score,
        "content": res.content[:200],
        # [新增] SOURCE 元数据透传
        "source_document": {
            "document_id": str(res.document_id),
            "filename": res.source_file,
            "file_url": await minio_service.get_presigned_url(res.source_document_id),
            "page_number": res.page_number,
        }
    }
    for res in rag_results
]
yield f"__SOURCES_EVENT__:{json.dumps(sources_data, ensure_ascii=False)}"
```

### 12.4 领域感知的向量检索

**改造点：`SearchService.search()` 增加可选的 domain 参数**

```python
async def search(
    self,
    query: str,
    top_k: int = 5,
    kb_id: str = None,
    score_threshold: float = 0.6,
    tenant_id: str = None,
    user_id: str = None,
    domain: str = None           # [新增] 领域过滤
) -> List[SearchResultItem]:
    # ... 原有逻辑 ...
    where_clauses = [
        "(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"
    ]
    where_clauses.append("d.tenant_id = :tenant_id")

    # [新增] 领域过滤
    if domain:
        where_clauses.append("c.domain = :domain")
        params["domain"] = domain

    # ... 其余逻辑不变 ...
```

### 12.5 检索时的元数据过滤

增强版检索允许按 JSONB metadata 字段过滤：

```python
# 在 EnhancedSearchService.search_with_callback() 中
# 示例：税务类查询自动带生效日期过滤
if intent.get("domain") == "tax":
    today = datetime.now().strftime("%Y-%m-%d")
    where_clauses.append("""
        (c.meta_info->>'effective_date' IS NULL OR c.meta_info->>'effective_date' <= :today)
        AND (c.meta_info->>'expiry_date' IS NULL OR c.meta_info->>'expiry_date' >= :today)
    """)
    params["today"] = today
```

---

## 13. 实施路线图

### Phase 1：基础建设（预计 3-5 天）

1. 改造 `DocumentChunk` 模型，增加 `domain`, `node_type`, `summary`, `relationships`, `node_hash` 字段
2. 执行 Alembic 迁移
3. 新增 `DomainDetector` 和增强版 `ChunkResult`
4. 新增 `RelationshipBuilder` 基础框架

### Phase 2：领域切块器（预计 5-7 天）

1. 实现 `FinancialChunker` — 表格原子化 + 上下文剥离
2. 实现 `TaxChunker` — 条款级正则切片 + lifecycle 提取
3. 实现 `LegalChunker` — AST 构建
4. 实现 `GeneralChunker` — Auto-Merging 双粒度
5. 实现 `DomainChunkerFactory` — 统一分派入口
6. 集成到 `process_document_task()` 主流程

### Phase 3：元数据与关系系统（预计 4-6 天）

1. 实现 `MetadataInjector` + 完整的 `ContextStack`
2. 实现 `EntityResolver` — 双路实体提取与替换
3. 实现 `SummaryGenerator` — 受控并发 + Batch Prompt
4. 实现 `RelationshipBuilder` 全功能（含所有 domain）
5. 集成到 `process_document_task()` pipeline

### Phase 4：检索增强（预计 3-5 天）

1. 改造 `UnifiedRetriever._combine_context()` 支持关系展开
2. 实现 `_resolve_parent()` 和 `_resolve_prev_next()`
3. 改造 `SearchService.search()` 支持 domain 过滤
4. 可选：按 metadata 过滤（时效日期等）
5. 端到端测试

### Phase 5：测试与验证（预计 3 天）

| 测试项 | 指标 | 方法 |
|--------|------|------|
| 财务表格检索 | 召回率 + 精度 | 用 Golden Dataset (参见 §15) 自动评估 |
| 税务条款时效 | 命中条款是否有效 | 构造含已废止条款的查询，纳入 queries.json |
| 法务实体替换 | 替换准确率 | 对比 LLM 提取结果 vs 人工标注 |
| 通用文档 Auto-Merging | 上下文完整性 | 对比 256 vs 1024 vs merged |
| 并发摘要性能 | 端到端耗时 | 用 300 节点合同压测 |
| **整体回归** | **Recall@5 + MRR** | `python tests/evaluators/test_retrieval_recall.py --report final.json` |

---

## 14. 风险与缓解措施

| 风险 | 风险评估 | 缓解措施 |
|------|----------|----------|
| LLM Summary 延迟导致入库超时（legal domain） | **高** | 降级策略：超时自动 fallback 到 `content[:50]`；离线异步生成摘要 |
| LLM 实体提取 JSON 解析失败（legal domain） | **中** | 解析失败时跳过实体替换，原样入库；日志告警，可人工补录 |
| 表格原子化后 chunk 过大超过 pgvector 限制 | **低** | `Vector(1024)` 的文本内容一般 < 2K tokens；超大表格做 Sub-Table 切分 |
| 关系展开导致检索延迟增加 | **低** | `relationships` 中只有 uuid 指针，`SELECT` 单行极快；可用 `IN()` 批量查询 |
| 旧文档兼容问题（已有 chunk 无 domain 字段） | **低** | `domain IS NULL` 视为 `general`，走旧逻辑；不强制迁移 |
| AST ContextStack 对非标准标题格式误判 | **低** | 不匹配 heading 规则的 section 返回空字典，不注入任何元数据（安全行为） |
| Batch Prompt 中某个文本过长导致上下文超限 | **中** | 每个文本截断到 300 字符；batch_size 动态调整（按总 token 数） |
| 切块参数（256/1024）未经量化验证 | **高** | Phase 0 先建 Golden Dataset + 自动化评估脚本，参数调优后有指标可依 |

---

## 15. 评估系统：Golden Dataset + 自动化 Benchmark

### 15.1 为什么要先做评估

你在通用切块中设定了 256 Token 的小块和 1024 Token 的大块，在财务切块中设定了超过 20 行表格拆分。这些参数目前是"拍脑袋"的。项目上线后，再想调这些参数意味着要全部重新入库——极度痛苦。

**核心原则**：没有量化指标的架构优化 = 蒙眼狂奔。在写任何 chunker 代码之前，先构建评估系统。

### 15.2 Golden Dataset 结构

```
rag_backend/tests/
├── golden_dataset/
│   ├── documents/                    # 测试文档（20 份，覆盖财税法+通用）
│   │   ├── 01_financial_report_2023.pdf
│   │   ├── 02_tax_law_amendment.docx
│   │   ├── 03_legal_contract_100pages.pdf
│   │   ├── 04_hr_handbook.md
│   │   └── ...
│   └── queries.json                  # 100 条测试 question + 标准答案
│
├── evaluators/
│   ├── test_retrieval_recall.py      # 召回率测试脚本
│   └── test_context_assembly.py      # 上下文组装质量测试
```

### 15.3 queries.json 格式

```json
[
  {
    "id": "FIN-001",
    "domain": "finance",
    "question": "2023年第四季度字节跳动的研发费用是多少？",
    "expected_chunks": ["fin_table_882"],
    "expected_metadata": {
      "year": "2023",
      "quarter": "Q4",
      "company": "字节跳动"
    },
    "difficulty": "medium"
  },
  {
    "id": "TAX-015",
    "domain": "tax",
    "question": "高新技术企业的企业所得税税率是多少？",
    "expected_chunks": ["tax_clause_102"],
    "expected_lifecycle": {
      "effective_date": "2008-01-01",
      "expiry_date": "2099-12-31"
    },
    "difficulty": "easy"
  },
  {
    "id": "LEG-023",
    "domain": "legal",
    "question": "如果甲方未按时付款，违约金是多少？",
    "entity_requirements": {
      "should_contain": ["XX科技有限公司"],
      "should_not_contain": ["甲方"]
    },
    "difficulty": "hard"
  },
  {
    "id": "GEN-007",
    "domain": "general",
    "question": "请问员工产假期间的薪资政策是什么？",
    "expected_context": {
      "leaf_text": "员工产假期间，基本工资照发",
      "parent_summary": "假期薪资"
    },
    "difficulty": "easy"
  }
]
```

### 15.4 自动化评估脚本

```python
# tests/evaluators/test_retrieval_recall.py

class RAGEvaluator:
    """
    RAG 检索质量自动化评估

    每次更改切块参数、Embedding 模型或检索策略后，运行此脚本。
    输出评估报告 JSON，对比不同配置下的召回率（Recall@K）。
    """

    METRICS = ["recall@1", "recall@3", "recall@5", "mrr", "ndcg"]

    async def evaluate(self, config: dict) -> Dict[str, float]:
        """
        用 Golden Dataset 评估当前配置

        Args:
            config: {"chunk_tokens": 256, "domain": "finance", ...}

        Returns:
            {"recall@1": 0.85, "recall@3": 0.92, "mrr": 0.88, ...}
        """
        queries = json.loads(open("tests/golden_dataset/queries.json").read())
        results = {metric: [] for metric in self.METRICS}

        for q in queries:
            # 执行检索
            hits = await self._retrieve(q["question"], config)

            # 计算 Recall@K
            expected = set(q["expected_chunks"])
            for k in [1, 3, 5]:
                top_k = set(h[:h["chunk_id"]] for h in hits[:k])
                recall = len(expected & top_k) / len(expected) if expected else 0
                results[f"recall@{k}"].append(recall)

            # 计算 MRR
            for rank, hit in enumerate(hits, 1):
                if hit["chunk_id"] in expected:
                    results["mrr"].append(1.0 / rank)
                    break
            else:
                results["mrr"].append(0.0)

        # 聚合
        return {
            metric: round(sum(values) / len(values), 4)
            for metric, values in results.items()
        }

    async def compare_configs(self, configs: List[Dict]) -> Dict[str, Dict]:
        """对比多种配置"""
        report = {}
        for config in configs:
            tag = f"{config['domain']}_t{config['chunk_tokens']}"
            report[tag] = await self.evaluate(config)
        return report
```

**集成到 CI**：

```yaml
# .github/workflows/rag_eval.yml (示例)
name: RAG Evaluation
on:
  pull_request:
    paths:
      - 'rag_backend/app/chunkers/**'
      - 'rag_backend/app/services/search_service.py'
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run RAG evaluation
        run: python tests/evaluators/test_retrieval_recall.py --report rag_report.json
      - name: Compare with baseline
        run: |
          python tests/evaluators/compare_baseline.py \
            --current rag_report.json \
            --baseline tests/baseline/recall_v1.json \
            --threshold 0.02
```

### 15.5 可引入的第三方评估框架

| 框架 | 用途 | 本项目适用性 |
|------|------|-------------|
| **RAGAS** | 评估 faithfulness, answer_relevancy, context_recall | 适用于最终端到端评估（LLM 回答质量） |
| **TruLens** | 评估 RAG 三元组（Answer, Context, Ground Truth） | 适用于开发调试阶段 |
| **LlamaIndex Evals** | 评估检索 + 响应质量 | 依赖 LlamaIndex，本项目用自定义框架，可选 |

**推荐先用纯 Python 自己写**（如 §15.4 所示），因为：
- Golden Dataset 已经定义了 `expected_chunks`，计算 Recall 无需任何第三方库
- 自定义框架下引入 LlamaIndex Evals 会增加依赖
- RAGAS 和 TruLens 作为 Phase 5 的可选增强

### 15.6 参数调优实验矩阵

在 Phase 0 中，用评估脚本跑一组对照实验，确定参数基线：

| 实验 | 领域 | Leaf Token | Parent Token | Table Split | 预期 Recall@5 |
|------|------|-----------|-------------|-------------|---------------|
| Baseline (现有系统) | all | — | 800 | 不拆分 | TBD |
| Exp-01 | general | 256 | 1024 | N/A | TBD |
| Exp-02 | general | 128 | 512 | N/A | TBD |
| Exp-03 | finance | 256 | 1024 | 20行 | TBD |
| Exp-04 | finance | 256 | 1024 | 50行 | TBD |
| Exp-05 | legal | 256 | 1024 | N/A | TBD |

**最终决策**：只看客观指标。哪个实验的 Recall@5 + MRR 最高，就用哪个参数。不靠感觉。

### 15.7 重新排序后的实施路线图

`Phase 0` 插入在所有 Phase 之前：

```
Phase 0: 评估基建（预计 2 天）
  准备 20 份测试文档 + 100 条 queries.json
  写 test_retrieval_recall.py 自动化脚本
  跑 Baseline 实验，记录当前系统的 Recall 和 MRR
  └→ 每次参数调整后重跑，用数据说话

Phase 1-5: 与原计划一致，但每次 PR 必须附带评估结果
```
