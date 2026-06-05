# Knowledge Graph（类型约束的知识图谱提取管线）

面向财税法务领域的实体/关系提取与 Neo4j 入库。区别于通用 NER：**预设类型白名单 + 规则预提取 + LLM 补全 + 置信度过滤**，从源头抑制幻觉。

## 目录速览

```text
knowledge_graph/
  kg_types.py              # EntityType（21 种）/ RelationType（24 种）及描述字典
  entity_extractor.py      # 两阶段实体提取（规则 → LLM 补全）
  relation_extractor.py    # 关系提取（source/target 必须在已提取实体中）
  coreference_resolver.py  # 指代消解（ENABLE_COREFERENCE_RESOLUTION）
  neo4j_manager.py         # Neo4j 连接 + UNWIND 批量写入 + 多标签数据模型
```

## 类型体系（kg_types.py）

**21 种实体类型**：

| 分组 | 类型 |
|---|---|
| 主体（3） | COMPANY、PERSON、DEPARTMENT |
| 财务（4） | FINANCIAL_METRIC、FINANCIAL_REPORT、ACCOUNT、BUDGET |
| 税务（4） | TAX_TYPE、TAX_POLICY、TAX_RATE、TAX_EXEMPTION |
| 法务（4） | CONTRACT、LEGAL_CASE、REGULATION、CLAUSE |
| 通用（6） | PRODUCT、SERVICE、LOCATION、DATE_PERIOD、EVENT、TECHNOLOGY |

**24 种关系类型**：公司/人事 10 种（WORKS_AT、MANAGED_BY、OWNS、INVESTED_IN…）、财务 3 种（HAS_METRIC、REPORTED_IN、AUDITED_BY）、税务 4 种（SUBJECT_TO、HAS_RATE、ELIGIBLE_FOR、CLAIMED）、法务 5 种（SIGNED、GOVERNS、VIOLATES、CONTAINS_CLAUSE、EFFECTIVE_PERIOD）、通用 4 种（LOCATED_AT、PRODUCES、USES、RELATED_TO）。

## 提取流程

```
文本
 │
 ├─ 阶段一：规则预提取 _pre_extract_by_rules()（8 类）
 │    DATE_PERIOD（\d{4}年…）、TAX_RATE（百分数）、TAX_TYPE（10 税种字典）、
 │    CONTRACT/CLAUSE（正则+前缀剥离）、LOCATION（省市）、FINANCIAL_METRIC（指标+金额对）、
 │    COMPANY（已知公司字典）
 │    规则命中 → 直接返回，跳过 LLM
 │
 ├─ 阶段二：LLM 补全（仅当规则未提取到任何实体时触发）
 │    提示词限定 21 种类型白名单，含置信度评分与消歧
 │
 ├─ 校验：类型白名单（VALID_ENTITY_TYPES）→ 必填字段 → 置信度 ≥ ENTITY_CONFIDENCE_THRESHOLD(0.7) → 消歧名替换
 │
 └─ 关系提取：只传 Top 10 核心实体；source/target 必须在实体列表中；类型须在 VALID_RELATION_TYPES
```

所有 LLM 调用带 120 秒超时保护。

## Neo4j 数据模型（neo4j_manager.py）

```cypher
// 多标签：基础 :Entity + 领域标签（ENTITY_TYPE_LABEL_MAP 共 21 种）
(:Entity:Company  {name, type: "COMPANY",  unique_key: "{tenant_id}_{name}_{type}", tenant_id})
(:Entity:TaxType  {name, type: "TAX_TYPE", ...})

// 关系统一为 :RELATED，语义类型存在属性 r.type 上
(:Entity)-[:RELATED {type: "SUBJECT_TO"}]->(:Entity)

// 记忆节点
(:Memory {content, user_id, tenant_id, importance})-[:CONTAINS]->(:Entity)
```

- 查询时 `MATCH (e:Entity)` 向后兼容，`MATCH (c:Company)` 类型限定高效遍历；语义关系需 `WHERE r.type='WORKS_AT'`（非原生关系类型）。
- **批量写入**：`batch_create_entities()` 按类型分组 UNWIND MERGE；`batch_create_relations()` 单次 UNWIND，一次网络往返替代 N 次。
- **多租户软隔离**：所有查询附加 `(e.tenant_id IS NULL OR e.tenant_id = $tenant_id)`。

## 检索侧配合

- `services/graphrag_service.py`：向量检索（top_k×2 候选）→ 从 chunk 元数据提取实体 → Cypher 图遍历（深度 2、上限 20 节点）→ 文档片段+实体+关系拼接 → 可选 Rerank → Top-K。
- 查询阶段实体提取用 **jieba 分词**（毫秒级，无 LLM）。
- 知识图谱编辑器（前端 `/knowledge-graph-editor`）支持子图加载、增删实体/关系、JSON 导入导出、批量保存回 Neo4j。

## 相关配置（.env）

```env
ENABLE_KNOWLEDGE_GRAPH=true        # config.py 默认 true；docker-compose/.env.example 默认 false
ENABLE_ENTITY_EXTRACTION=true
ENABLE_RELATION_EXTRACTION=true
ENABLE_COREFERENCE_RESOLUTION=true
ENTITY_CONFIDENCE_THRESHOLD=0.7
ENABLE_DEFERRED_GRAPH_EXTRACTION=true   # 延迟提取（入库后后台跑图谱）
NEO4J_URI=bolt://localhost:7687
```
