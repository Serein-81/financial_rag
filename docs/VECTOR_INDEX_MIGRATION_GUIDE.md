# Docker 环境向量索引迁移指南

## 📋 概述

本指南说明如何在 Docker 环境中为 `semantic_memories` 表创建 pgvector 向量索引。

## 🎯 索引类型选择

### HNSW 索引（Hierarchical Navigable Small World）
- ✅ 查询速度最快
- ✅ 适合 < 100k 数据量
- ⚠️ 内存占用较高
- ⚠️ 构建时间较长

### IVFFlat 索引（Inverted File Flat）
- ✅ 适合 > 100k 数据量
- ✅ 内存占用较低
- ✅ 构建速度快
- ⚠️ 查询速度中等

## 🚀 自动迁移（推荐）

容器启动时**自动**运行索引创建：

```bash
# 重启容器即可自动创建索引
docker-compose down
docker-compose up -d
```

查看日志：
```bash
docker-compose logs -f backend
```

如果看到类似输出，说明索引创建成功：
```
📊 检查并创建向量索引...
向量索引自动创建脚本
============================================================
当前数据量: 12345
✅ 向量索引已存在或创建成功
```

## 🔧 手动迁移

### 方式 1：交互式创建（推荐用于首次设置）

```bash
# 进入后端容器
docker exec -it rag_backend bash

# 运行交互式脚本
python -m app.migrations.add_vector_indexes_docker
```

按照提示选择：
1. 选择索引类型（HNSW/IVFFlat）
2. 设置参数（m, ef_construction 等）
3. 确认执行

### 方式 2：自动创建（无需交互）

```bash
docker exec -it rag_backend python -m app.migrations.auto_create_vector_index
```

自动根据数据量选择最佳索引类型：
- 数据量 < 100k → HNSW
- 数据量 >= 100k → IVFFlat

### 方式 3：直接执行 SQL

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
CREATE INDEX IF NOT EXISTS semantic_memories_embedding_hnsw
ON semantic_memories 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
"
```

## 📊 验证索引创建

### 检查索引是否存在

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'semantic_memories'
AND indexdef LIKE '%embedding%';
"
```

预期输出：
```
indexname                      | indexdef
-------------------------------|------------------------------------------------
semantic_memories_embedding_hnsw | CREATE INDEX semantic_memories_embedding_hnsw ...
```

### 检查索引大小

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
SELECT pg_size_pretty(pg_relation_size('semantic_memories_embedding_hnsw'));
"
```

### 验证索引是否被使用

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
EXPLAIN SELECT * FROM semantic_memories 
ORDER BY embedding <=> '[0,0,0,...]'::vector LIMIT 10;
"
```

如果看到 `Hnsw Scan` 或 `Bitmap Index Scan`，说明索引正在工作。

## 🔄 索引维护

### 重建索引（如果性能下降）

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
REINDEX INDEX semantic_memories_embedding_hnsw;
"
```

### 更新统计信息

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
ANALYZE semantic_memories;
"
```

### 删除索引

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
DROP INDEX IF EXISTS semantic_memories_embedding_hnsw;
"
```

## ⚙️ 参数调优

### HNSW 参数

| 参数 | 默认值 | 说明 | 调整建议 |
|------|--------|------|----------|
| m | 16 | 每个节点的连接数 | 数据量大时增加（32-64） |
| ef_construction | 64 | 构建时的搜索范围 | 数据量大时增加（128-256） |

### IVFFlat 参数

| 参数 | 默认值 | 说明 | 调整建议 |
|------|--------|------|----------|
| lists | 100 | 聚类数量 | 数据量/1000 左右 |

### 示例：高性能配置

```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
CREATE INDEX IF NOT EXISTS semantic_memories_embedding_hnsw
ON semantic_memories 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);
"
```

## ❓ 常见问题

### Q: 索引创建很慢怎么办？

A: 
- HNSW 索引构建是单线程的，可能需要较长时间
- 对于大数据集，建议使用 IVFFlat
- 可以先创建 IVFFlat 索引，之后再迁移到 HNSW

### Q: 内存不足怎么办？

A:
- 减少 HNSW 的 m 参数值
- 使用 IVFFlat 替代 HNSW
- 增加 Docker 容器内存限制

### Q: 索引创建失败？

A:
- 确保 pgvector 扩展已安装：
  ```bash
  docker exec -it rag_db psql -U rag_user -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
  ```
- 确保 embedding 列存在且类型为 vector

### Q: 如何查看当前索引状态？

A:
```bash
docker exec -it rag_db psql -U rag_user -d rag_db -c "
SELECT 
    indexrelname AS index_name,
    idx_scan AS scan_count,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes 
WHERE relname = 'semantic_memories';
"
```

## 📝 脚本文件说明

| 文件 | 用途 |
|------|------|
| `app/migrations/add_vector_indexes.py` | 本地开发环境使用 |
| `app/migrations/add_vector_indexes_docker.py` | Docker 交互式创建 |
| `app/migrations/auto_create_vector_index.py` | Docker 自动创建 |

## 🔗 相关文档

- [特性实现总结](./FEATURE_IMPLEMENTATION_SUMMARY.md)
- [pgvector 官方文档](https://github.com/pgvector/pgvector)
- [HNSW 索引文档](https://github.com/pgvector/pgvector#hnsw)
