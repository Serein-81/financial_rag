# 🐳 Docker 完整部署指南

## 📋 更新内容

### 🆕 新增服务和配置

1. **Redis 服务** - 缓存和会话管理
2. **后端服务** - 包含三大高级特性的完整后端
3. **自动迁移** - 容器启动时自动创建高级特性表
4. **健康检查** - 所有服务的健康状态监控
5. **环境变量** - 完整的配置管理

### 📁 新增文件

- ✅ `docker-compose.yml` - 更新了完整的服务配置
- ✅ `Dockerfile` - 后端服务的容器构建文件
- ✅ `docker-entrypoint.sh` - 容器启动脚本
- ✅ `migrations/docker_migration.py` - Docker 专用迁移脚本
- ✅ `.env` - Docker 环境配置文件

---

## 🚀 快速部署

### 1. 检查配置文件

确保 `.env` 文件配置正确：

```bash
# 检查关键配置
cat .env | grep -E "(POSTGRES_SERVER|REDIS_HOST|MINIO_ENDPOINT)"
```

**预期输出：**
```
POSTGRES_SERVER=db
REDIS_HOST=redis
MINIO_ENDPOINT=minio:9000
```

### 2. 构建和启动服务

```bash
# 构建并启动所有服务
docker-compose up --build -d

# 查看服务状态
docker-compose ps
```

**预期输出：**
```
NAME          IMAGE                    STATUS                    PORTS
rag_backend   rag_backend-backend      Up (healthy)             0.0.0.0:8000->8000/tcp
rag_db        pgvector/pgvector:pg16   Up (healthy)             0.0.0.0:5432->5432/tcp
rag_minio     quay.io/minio/minio      Up (healthy)             0.0.0.0:9000-9001->9000-9001/tcp
rag_redis     redis:7-alpine           Up (healthy)             0.0.0.0:6379->6379/tcp
```

### 3. 查看启动日志

```bash
# 查看后端服务日志
docker-compose logs -f backend
```

**预期日志：**
```
🐳 RAG Backend 容器启动中...
⏳ 等待数据库服务启动...
✅ 数据库连接成功
🔄 运行数据库迁移...
📊 创建 Agent 追踪表...
✅ Agent 追踪表创建成功
🔧 创建工具调用追踪表...
✅ 工具调用追踪表创建成功
🤖 创建 Prompt 优化表...
✅ Prompt 优化表创建成功
📑 创建索引...
✅ 索引创建成功
🎉 所有高级特性数据库表创建完成！
🌱 插入示例数据...
✅ 示例数据插入成功
✅ Docker 环境数据库迁移完成！
🚀 启动 FastAPI 应用...
```

### 4. 验证部署

```bash
# 检查 API 健康状态
curl http://localhost:8000/

# 访问 API 文档
open http://localhost:8000/docs
```

---

## 🔍 服务详情

### 📊 服务架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Database      │
│   (Vue.js)      │◄──►│   (FastAPI)     │◄──►│  (PostgreSQL)   │
│   Port: 3000    │    │   Port: 8000    │    │   Port: 5432    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │     Redis       │    │     MinIO       │
                       │   (Cache)       │    │ (Object Store)  │
                       │   Port: 6379    │    │   Port: 9000    │
                       └─────────────────┘    └─────────────────┘
```

### 🗄️ 数据库表结构

**高级特性表 (6张)：**

1. **agent_traces** - Agent 执行追踪主表
   - 记录每次 Agent 执行的基本信息
   - 包含执行统计和状态

2. **agent_steps** - Agent 执行步骤详情表
   - 记录 Thought → Action → Observation 流程
   - 支持工具调用信息记录

3. **tool_call_traces** - 工具调用追踪表
   - 支持嵌套调用追踪
   - 性能分析和调用链构建

4. **prompt_templates** - Prompt 模板管理表
   - 版本控制和模板管理
   - 支持 A/B 测试

5. **prompt_executions** - Prompt 执行记录表
   - 性能指标收集
   - 自动评分和用户反馈

6. **prompt_ab_tests** - A/B 测试管理表
   - 流量分配和结果分析
   - 自动决策支持

### 🌐 API 端点

**新增的 API 标签：**

1. **Agent Trace** (3个端点)
   - `GET /api/v1/agent_trace/traces/{session_id}` - 获取会话追踪
   - `GET /api/v1/agent_trace/traces/{trace_id}/steps` - 获取执行步骤
   - `GET /api/v1/agent_trace/traces/{trace_id}/visualization` - 可视化数据

2. **Tool Trace** (3个端点)
   - `GET /api/v1/tool_trace/tool_calls/{trace_id}` - 获取工具调用
   - `GET /api/v1/tool_trace/tool_calls/{trace_id}/chain` - 获取调用链
   - `GET /api/v1/tool_trace/tool_stats` - 获取工具统计

3. **Prompt Optimization** (12个端点)
   - 模板管理：创建、查询、更新模板
   - 执行记录：记录和分析执行结果
   - A/B 测试：创建、管理、分析测试
   - 性能分析：模板比较和优化建议

---

## 🧪 功能测试

### 1. 测试 Agent 追踪

```bash
# 进入后端容器
docker exec -it rag_backend bash

# 运行测试脚本
python test_features_simple.py
```

### 2. 测试 API 接口

```bash
# 测试 Agent 追踪 API
curl -X POST "http://localhost:8000/api/v1/agent_trace/traces" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "ReAct",
    "user_query": "Docker 测试查询"
  }'

# 测试 Prompt 模板 API
curl -X GET "http://localhost:8000/api/v1/prompt/templates"
```

### 3. 查看示例数据

```bash
# 连接数据库
docker exec -it rag_db psql -U postgres -d rag_db

# 查看 Prompt 模板
SELECT name, version, agent_type, description FROM prompt_templates;
```

---

## 🔧 运维管理

### 📊 监控命令

```bash
# 查看所有服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f backend
docker-compose logs -f db
docker-compose logs -f redis
docker-compose logs -f minio

# 查看资源使用
docker stats
```

### 🔄 重启服务

```bash
# 重启单个服务
docker-compose restart backend

# 重启所有服务
docker-compose restart

# 重新构建并启动
docker-compose up --build -d
```

### 🗄️ 数据备份

```bash
# 备份数据库
docker exec rag_db pg_dump -U postgres rag_db > backup.sql

# 备份 MinIO 数据
docker cp rag_minio:/data ./minio_backup

# 备份 Redis 数据
docker exec rag_redis redis-cli BGSAVE
```

### 🧹 清理资源

```bash
# 停止所有服务
docker-compose down

# 清理数据卷（谨慎使用）
docker-compose down -v

# 清理镜像
docker system prune -a
```

---

## 🚨 故障排除

### 1. 后端服务启动失败

**症状：** 后端容器反复重启

**排查：**
```bash
# 查看详细日志
docker-compose logs backend

# 检查健康状态
docker-compose ps
```

**常见原因：**
- 数据库连接失败
- 环境变量配置错误
- 端口冲突

### 2. 数据库迁移失败

**症状：** 迁移脚本报错

**排查：**
```bash
# 手动运行迁移
docker exec -it rag_backend python migrations/docker_migration.py

# 检查数据库连接
docker exec -it rag_backend python -c "
import asyncio
from migrations.docker_migration import wait_for_db
asyncio.run(wait_for_db())
"
```

### 3. API 接口异常

**症状：** 新增 API 返回 404 或 500

**排查：**
```bash
# 检查路由注册
docker exec -it rag_backend python -c "
from app.main import app
print([route.path for route in app.routes])
"

# 检查数据库表
docker exec -it rag_db psql -U postgres -d rag_db -c "
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE '%trace%' OR table_name LIKE '%prompt%';
"
```

---

## 🎯 性能优化

### 📈 推荐配置

**生产环境 docker-compose.yml 调整：**

```yaml
# 添加资源限制
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
    
  db:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 🔧 数据库优化

```sql
-- 在数据库中执行
-- 分析表统计信息
ANALYZE agent_traces;
ANALYZE agent_steps;
ANALYZE tool_call_traces;

-- 查看索引使用情况
SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch 
FROM pg_stat_user_indexes 
WHERE schemaname = 'public';
```

---

## 🎉 部署成功验证

### ✅ 成功标志

当你看到以下内容时，说明部署成功：

1. **所有服务健康** - `docker-compose ps` 显示所有服务为 `Up (healthy)`
2. **API 文档可访问** - http://localhost:8000/docs 显示完整 API
3. **新增 API 标签** - 可以看到 Agent Trace、Tool Trace、Prompt Optimization
4. **数据库表完整** - 6张高级特性表全部创建
5. **示例数据存在** - 可以查询到预置的 Prompt 模板

### 🎯 最终测试

```bash
# 完整功能测试
curl -s http://localhost:8000/docs | grep -E "(Agent Trace|Tool Trace|Prompt Optimization)"

# 数据库表验证
docker exec -it rag_db psql -U postgres -d rag_db -c "
SELECT COUNT(*) as table_count 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('agent_traces', 'agent_steps', 'tool_call_traces', 'prompt_templates', 'prompt_executions', 'prompt_ab_tests');
"
```

**预期结果：** table_count = 6

---

## 🎊 恭喜！

你已经成功部署了包含三大高级特性的企业级 RAG 系统！

### 🌟 你现在拥有：

- ✅ **完整的微服务架构** - 4个服务协同工作
- ✅ **企业级可观测性** - Agent 决策追踪和工具调用分析
- ✅ **数据驱动优化** - Prompt 性能分析和 A/B 测试
- ✅ **自动化部署** - 一键启动，自动迁移
- ✅ **健康监控** - 完整的服务健康检查
- ✅ **生产就绪** - 容器化部署，易于扩展

### 🚀 下一步：

1. **前端集成** - 将新功能集成到 Vue.js 前端
2. **监控面板** - 创建实时监控仪表板
3. **性能调优** - 根据实际使用情况优化配置
4. **扩展功能** - 添加更多高级特性

**准备好展示你的企业级 Agent 平台了吗？** 🎯