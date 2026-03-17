# 部署指南

## 📋 目录

- [环境要求](#环境要求)
- [依赖安装](#依赖安装)
- [配置说明](#配置说明)
- [数据库初始化](#数据库初始化)
- [启动步骤](#启动步骤)
- [健康检查](#健康检查)
- [常见问题](#常见问题)

---

## 环境要求

### 硬件要求

- CPU: 4核心及以上
- 内存: 8GB 及以上（推荐 16GB）
- 磁盘: 50GB 及以上可用空间

### 软件要求

- 操作系统: Windows 10/11, Linux (Ubuntu 20.04+), macOS
- Python: 3.9 或更高版本
- Docker: 20.10 或更高版本（用于依赖服务）
- Docker Compose: 1.29 或更高版本

### 依赖服务

- PostgreSQL: 14 或更高版本
- MinIO: 最新稳定版
- Neo4j: 5.x（可选，用于知识图谱）
- Redis: 6.x（可选，用于缓存）

---

## 依赖安装

### 1. 安装 Python 依赖

```bash
cd rag_backend
pip install -r requirements.txt
```

### 2. 启动 Docker 服务

```bash
# 启动所有依赖服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

服务端口：
- PostgreSQL: 5432
- MinIO: 9000 (API), 9001 (Console)
- Neo4j: 7474 (HTTP), 7687 (Bolt)
- Redis: 6379

---

## 配置说明

### 1. 环境变量配置

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下关键参数：

```ini
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/rag_db

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=rag-documents

# Neo4j 配置（可选）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Redis 配置（可选）
REDIS_URL=redis://localhost:6379/0

# LLM 配置
ZHIPUAI_API_KEY=your_api_key_here

# 安全配置
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_here
```

### 2. 生成密钥

```python
# 生成 SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 生成 JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 数据库初始化

### 1. 创建数据库

```sql
CREATE DATABASE rag_db;
```

### 2. 运行迁移脚本

```bash
# 运行所有迁移
python migrations/phase0_migration.sql
python migrations/add_knowledge_graph_tables.py
python migrations/add_agent_trace.py
# ... 其他迁移脚本
```

或使用自动化脚本：

```bash
python setup_database.py
```

### 3. 创建 Neo4j 索引（如果使用知识图谱）

```bash
python create_neo4j_indexes.py
```

---

## 启动步骤

### 方式 1: 直接启动（开发环境）

```bash
# 启动 FastAPI 应用
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 方式 2: 使用 Docker（生产环境）

```bash
# 构建镜像
docker build -t rag-backend:latest .

# 运行容器
docker run -d \
  --name rag-backend \
  -p 8000:8000 \
  --env-file .env \
  rag-backend:latest
```

### 方式 3: 使用部署脚本

Windows:
```bash
deploy.bat
```

Linux/macOS:
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 健康检查

### 1. 运行健康检查脚本

```bash
python health_check.py
```

输出示例：
```
✓ PostgreSQL 连接正常
✓ MinIO 连接正常
⚠ Neo4j 连接失败 (可选服务)
✓ Redis 连接正常
✓ LLM 配置完整
✓ 文件系统结构正常

总体状态: 良好 - 核心服务正常
```

### 2. API 健康检查

```bash
curl http://localhost:8000/health
```

响应：
```json
{
  "status": "healthy",
  "timestamp": "2024-03-16T10:00:00Z",
  "services": {
    "database": "ok",
    "storage": "ok"
  }
}
```

### 3. 查看 API 文档

访问: http://localhost:8000/docs

---

## 常见问题

### Q1: 数据库连接失败

**问题**: `sqlalchemy.exc.OperationalError: could not connect to server`

**解决方案**:
1. 检查 PostgreSQL 是否运行: `docker-compose ps`
2. 检查数据库配置: `.env` 中的 `DATABASE_URL`
3. 检查防火墙设置

### Q2: MinIO 连接失败

**问题**: `S3Error: Access Denied`

**解决方案**:
1. 检查 MinIO 凭证: `MINIO_ACCESS_KEY` 和 `MINIO_SECRET_KEY`
2. 检查 bucket 是否存在
3. 运行: `python fix_minio_policy.py`

### Q3: LLM API 调用失败

**问题**: `AuthenticationError: Invalid API key`

**解决方案**:
1. 检查 API Key: `.env` 中的 `ZHIPUAI_API_KEY`
2. 验证 API Key 是否有效
3. 检查网络连接

### Q4: 内存不足

**问题**: 系统运行缓慢或崩溃

**解决方案**:
1. 增加系统内存
2. 调整 Docker 内存限制
3. 优化并发配置

### Q5: 端口冲突

**问题**: `Address already in use`

**解决方案**:
1. 检查端口占用: `netstat -ano | findstr :8000`
2. 修改端口配置
3. 停止冲突的服务

---

## 生产环境建议

### 1. 安全配置

- 使用强密码和密钥
- 启用 HTTPS
- 配置防火墙规则
- 定期更新依赖

### 2. 性能优化

- 使用生产级数据库配置
- 启用数据库连接池
- 配置缓存策略
- 使用 CDN 加速静态资源

### 3. 监控和日志

- 配置日志收集（如 ELK）
- 设置性能监控（如 Prometheus）
- 配置告警规则
- 定期备份数据

### 4. 高可用性

- 使用负载均衡
- 配置数据库主从复制
- 实施容器编排（如 Kubernetes）
- 设置自动故障转移

---

## 下一步

- 阅读 [API 文档](API_DOCUMENTATION.md)
- 查看 [运维手册](OPERATIONS_MANUAL.md)
- 参考 [用户指南](USER_GUIDE.md)

---

**更新时间**: 2024-03-16  
**版本**: 1.0.0
