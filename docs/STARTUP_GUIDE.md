# RAG Backend 新功能启动指南

## 🚀 快速启动

### 1. 启动服务

```bash
cd d:\Python\Codebase\My_rag\rag_backend
python -m app.main
```

服务将在 http://localhost:8000 启动

### 2. 访问API文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 3. 验证新功能

```bash
cd d:\Python\Codebase\My_rag\rag_backend
python verify_features.py
```

## 📚 API使用指南

### 1️⃣ API限流中间件 (P0-1)

**自动生效**，无需额外配置。

**默认限流规则**:
- 全局：100 请求 / 60秒
- 聊天API：30 请求 / 60秒
- 搜索API：60 请求 / 60秒

**手动管理**:
```bash
# 查看限流统计
curl -X GET "http://localhost:8000/api/v1/rate-limit/stats"

# 重置特定限流
curl -X POST "http://localhost:8000/api/v1/rate-limit/reset/user_123"
```

### 2️⃣ 流式稳定性增强 (P0-2)

**使用带稳定性的流式聊天**:
```bash
curl -X POST "http://localhost:8000/api/v1/streaming/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是Python?",
    "top_k": 5
  }'
```

**查询进度**:
```bash
curl -X GET "http://localhost:8000/api/v1/streaming/progress/{stream_id}"
```

**恢复流**:
```bash
curl -X POST "http://localhost:8000/api/v1/streaming/resume/{stream_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "继续",
    "top_k": 5
  }'
```

### 3️⃣ 会话快照API (P2-1)

**创建快照**:
```bash
curl -X POST "http://localhost:8000/api/v1/snapshot/" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "snapshot_type": "MANUAL",
    "description": "重要决策点"
  }'
```

**列出快照**:
```bash
curl -X GET "http://localhost:8000/api/v1/snapshot/?session_id=session_123"
```

**恢复快照**:
```bash
curl -X POST "http://localhost:8000/api/v1/snapshot/{snapshot_id}/restore"
```

**对比快照**:
```bash
curl -X POST "http://localhost:8000/api/v1/snapshot/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_a_id": "snapshot_1",
    "snapshot_b_id": "snapshot_2"
  }'
```

### 4️⃣ 追问建议生成 (P2-2)

**生成建议**:
```bash
curl -X POST "http://localhost:8000/api/v1/suggestion/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "conversation_history": [
      {"role": "user", "content": "什么是机器学习?"},
      {"role": "assistant", "content": "机器学习是..."}
    ],
    "types": ["DEEPEN", "EXAMPLE"],
    "count": 3
  }'
```

**获取建议类型说明**:
```bash
curl -X GET "http://localhost:8000/api/v1/suggestion/types"
```

**快速建议**:
```bash
curl -X POST "http://localhost:8000/api/v1/suggestion/quick" \
  -H "Content-Type: application/json" \
  -d '{
    "current_content": "Python是一种高级编程语言"
  }'
```

### 5️⃣ 健康检查 (P2-3)

**简单检查**:
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

**详细检查**:
```bash
curl -X GET "http://localhost:8000/api/v1/health/detailed"
```

**检查特定组件**:
```bash
curl -X GET "http://localhost:8000/api/v1/health/components/database"
curl -X GET "http://localhost:8000/api/v1/health/components/redis"
```

## ⚙️ 配置指南

### 修改限流配置

编辑 `app/core/config.py`:

```python
# 启用/禁用限流
RATE_LIMIT_ENABLED = True

# 选择策略：sliding_window, token_bucket, fixed_window
RATE_LIMIT_STRATEGY = "sliding_window"

# 全局限流
RATE_LIMIT_GLOBAL_REQUESTS = 100
RATE_LIMIT_GLOBAL_WINDOW = 60

# 自定义端点限流
# 在 RateLimitMiddleware.ENDPOINT_TIERS 中添加
```

### 修改流式服务配置

编辑 `app/services/streaming_service.py`:

```python
# 检查点保存间隔
CHECKPOINT_INTERVAL = 5  # 每5个chunk保存一次

# 流过期时间（秒）
STREAM_EXPIRY = 3600  # 1小时

# 检查点过期时间（秒）
CHECKPOINT_EXPIRY = 86400  # 24小时
```

### 修改快照配置

编辑 `app/services/snapshot_service.py`:

```python
# 快照过期时间（秒）
SNAPSHOT_EXPIRY = 604800  # 7天

# 最大快照数
MAX_SNAPSHOTS_PER_SESSION = 50
```

## 🧪 测试指南

### 运行验证脚本

```bash
cd d:\Python\Codebase\My_rag\rag_backend
python verify_features.py
```

### 手动测试API

1. 启动服务
2. 打开 http://localhost:8000/docs
3. 找到对应的API端点
4. 点击 "Try it out"
5. 填写参数并执行

## 🔍 监控和调试

### 查看日志

```bash
# 限流日志
grep "rate_limit" logs/app.log

# 流式日志
grep "streaming" logs/app.log

# 快照日志
grep "snapshot" logs/app.log
```

### 统计信息

```bash
# 所有服务的统计
curl http://localhost:8000/api/v1/rate-limit/stats
curl http://localhost:8000/api/v1/streaming/stats
curl http://localhost:8000/api/v1/snapshot/stats
curl http://localhost:8000/api/v1/suggestion/stats
```

## 📊 性能考虑

### 限流
- 内存使用：每1000个限流键约占用 1MB
- 建议使用Redis后端以支持分布式部署

### 流式服务
- 每个活跃流约占用 10-50KB 内存
- 建议设置合理的过期时间

### 快照
- 每个快照约占用 1-10KB 内存
- 建议定期清理过期快照

## 🐛 故障排查

### 问题：限流未生效
1. 检查 `RATE_LIMIT_ENABLED = True`
2. 检查日志中是否有错误
3. 验证中间件是否正确注册

### 问题：流式进度查询失败
1. 检查流ID是否正确
2. 检查流是否已过期
3. 查看流式服务日志

### 问题：快照创建失败
1. 检查数据库连接
2. 验证会话ID是否存在
3. 检查磁盘空间

### 问题：建议生成失败
1. 检查LLM服务是否可用
2. 验证对话历史格式
3. 查看建议服务日志

## 📞 获取帮助

- 查看详细文档: `PROJECT_STRUCTURE_NEW.md`
- 查看实现总结: `IMPLEMENTATION_SUMMARY.md`
- 查看源代码注释
- 使用 Swagger UI: http://localhost:8000/docs

## ✅ 下一步

1. 运行验证脚本确认功能正常
2. 根据需要调整配置
3. 集成到你的应用
4. 设置监控和告警
5. 定期检查统计信息

---

**祝你使用愉快！** 🎉
