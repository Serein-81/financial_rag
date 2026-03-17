# 运维手册

## 📋 目录

- [日常维护](#日常维护)
- [监控指标](#监控指标)
- [故障排查](#故障排查)
- [备份恢复](#备份恢复)
- [性能调优](#性能调优)
- [安全管理](#安全管理)

---

## 日常维护

### 1. 服务状态检查

**每日检查清单**:

```bash
# 1. 检查系统健康状态
python health_check.py

# 2. 检查 Docker 容器状态
docker-compose ps

# 3. 检查磁盘空间
df -h

# 4. 检查内存使用
free -h

# 5. 查看最近的错误日志
tail -n 100 logs/error.log
```

### 2. 日志管理

**日志位置**:
- 应用日志: `logs/app.log`
- 错误日志: `logs/error.log`
- 访问日志: `logs/access.log`
- 审计日志: 数据库 `tenant_audit_logs` 表

**日志轮转配置**:

```bash
# 每天轮转，保留 30 天
/var/log/rag/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
}
```

### 3. 数据库维护

**每周任务**:

```sql
-- 1. 分析表统计信息
ANALYZE;

-- 2. 清理过期数据（根据业务需求）
DELETE FROM tenant_audit_logs 
WHERE created_at < NOW() - INTERVAL '90 days';

-- 3. 重建索引（如需要）
REINDEX DATABASE rag_db;

-- 4. 检查数据库大小
SELECT pg_size_pretty(pg_database_size('rag_db'));
```

### 4. 存储清理

**MinIO 存储管理**:

```bash
# 查看存储使用情况
mc du minio/rag-documents

# 清理临时文件（根据业务规则）
# 示例：删除 90 天前的临时文件
mc rm --recursive --force --older-than 90d minio/rag-documents/temp/
```

---

## 监控指标

### 1. 系统指标

**关键指标**:

| 指标 | 正常范围 | 告警阈值 |
|------|---------|---------|
| CPU 使用率 | < 70% | > 85% |
| 内存使用率 | < 80% | > 90% |
| 磁盘使用率 | < 80% | > 90% |
| 网络延迟 | < 50ms | > 200ms |

**监控脚本**:

```python
# monitor_system.py
import psutil

def check_system_health():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    alerts = []
    if cpu > 85:
        alerts.append(f"CPU 使用率过高: {cpu}%")
    if memory > 90:
        alerts.append(f"内存使用率过高: {memory}%")
    if disk > 90:
        alerts.append(f"磁盘使用率过高: {disk}%")
    
    return alerts
```

### 2. 应用指标

**关键指标**:

| 指标 | 正常范围 | 告警阈值 |
|------|---------|---------|
| API 响应时间 | < 200ms | > 1000ms |
| 错误率 | < 1% | > 5% |
| 并发连接数 | < 100 | > 500 |
| 队列长度 | < 10 | > 50 |

**监控查询**:

```sql
-- 查看最近 1 小时的 API 调用统计
SELECT 
    endpoint,
    COUNT(*) as total_calls,
    AVG(response_time) as avg_response_time,
    MAX(response_time) as max_response_time,
    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
FROM api_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY endpoint
ORDER BY total_calls DESC;
```

### 3. 业务指标

**关键指标**:

| 指标 | 说明 |
|------|------|
| 日活跃用户数 | 每日登录的唯一用户数 |
| 审查任务数 | 每日创建的审查任务数 |
| 文档上传数 | 每日上传的文档数 |
| 平均处理时间 | 审查任务的平均完成时间 |

---

## 故障排查

### 1. 服务无法启动

**症状**: 应用启动失败或立即退出

**排查步骤**:

1. 检查配置文件
```bash
# 验证 .env 文件
cat .env | grep -v "^#" | grep -v "^$"
```

2. 检查依赖服务
```bash
# 检查 PostgreSQL
psql -h localhost -U user -d rag_db -c "SELECT 1"

# 检查 MinIO
mc admin info minio
```

3. 查看错误日志
```bash
tail -n 100 logs/error.log
```

4. 检查端口占用
```bash
# Windows
netstat -ano | findstr :8000

# Linux
lsof -i :8000
```

### 2. 数据库连接失败

**症状**: `sqlalchemy.exc.OperationalError`

**解决方案**:

1. 检查数据库服务
```bash
docker-compose ps postgres
```

2. 检查连接配置
```bash
echo $DATABASE_URL
```

3. 测试连接
```python
from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL)
conn = engine.connect()
print("连接成功")
```

4. 检查连接池
```sql
-- 查看当前连接数
SELECT count(*) FROM pg_stat_activity;

-- 查看最大连接数
SHOW max_connections;
```

### 3. 内存泄漏

**症状**: 内存使用持续增长

**排查步骤**:

1. 监控内存使用
```python
import psutil
import time

while True:
    mem = psutil.virtual_memory()
    print(f"内存使用: {mem.percent}%")
    time.sleep(60)
```

2. 使用内存分析工具
```bash
pip install memory_profiler
python -m memory_profiler app/main.py
```

3. 检查对象引用
```python
import gc
import sys

# 查看对象数量
print(len(gc.get_objects()))

# 查看最大的对象
import objgraph
objgraph.show_most_common_types(limit=10)
```

### 4. 性能下降

**症状**: API 响应时间变长

**排查步骤**:

1. 检查数据库查询
```sql
-- 查看慢查询
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

2. 检查索引使用
```sql
-- 查看未使用的索引
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0;
```

3. 分析 API 性能
```bash
# 使用 ab 进行压力测试
ab -n 1000 -c 10 http://localhost:8000/api/v1/health
```

---

## 备份恢复

### 1. 数据库备份

**自动备份脚本**:

```bash
#!/bin/bash
# backup_database.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/rag_db_$DATE.sql"

# 创建备份
pg_dump -h localhost -U user rag_db > $BACKUP_FILE

# 压缩备份
gzip $BACKUP_FILE

# 删除 30 天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "备份完成: $BACKUP_FILE.gz"
```

**定时任务**:

```bash
# 每天凌晨 2 点执行备份
0 2 * * * /path/to/backup_database.sh
```

### 2. 数据库恢复

```bash
# 恢复备份
gunzip -c /backups/postgres/rag_db_20240316_020000.sql.gz | \
psql -h localhost -U user rag_db
```

### 3. MinIO 备份

```bash
# 备份 MinIO 数据
mc mirror minio/rag-documents /backups/minio/rag-documents

# 恢复 MinIO 数据
mc mirror /backups/minio/rag-documents minio/rag-documents
```

### 4. 配置备份

```bash
# 备份配置文件
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
    .env \
    docker-compose.yml \
    app/core/config.py
```

---

## 性能调优

### 1. 数据库优化

**连接池配置**:

```python
# app/db/session.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # 连接池大小
    max_overflow=10,       # 最大溢出连接
    pool_timeout=30,       # 连接超时
    pool_recycle=3600      # 连接回收时间
)
```

**索引优化**:

```sql
-- 添加常用查询的索引
CREATE INDEX idx_documents_tenant_id ON documents(tenant_id);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_audit_logs_created_at ON tenant_audit_logs(created_at);
```

### 2. 缓存策略

**Redis 缓存配置**:

```python
# 缓存热点数据
from app.services.redis_service import RedisService

redis = RedisService()

# 缓存知识库信息（1小时）
redis.set(f"kb:{kb_id}", kb_data, ex=3600)

# 缓存搜索结果（10分钟）
redis.set(f"search:{query_hash}", results, ex=600)
```

### 3. 并发优化

**异步处理**:

```python
# 使用异步任务处理耗时操作
from celery import Celery

celery = Celery('tasks', broker='redis://localhost:6379/0')

@celery.task
def process_document(document_id):
    # 异步处理文档
    pass
```

---

## 安全管理

### 1. 访问控制

**定期审查**:
- 检查用户权限
- 审查 API 访问日志
- 更新访问控制列表

### 2. 密钥管理

**密钥轮换**:

```bash
# 每季度更新密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 更新 .env 文件
# 重启服务
docker-compose restart
```

### 3. 安全扫描

**定期扫描**:

```bash
# 扫描依赖漏洞
pip-audit

# 扫描 Docker 镜像
docker scan rag-backend:latest
```

---

## 告警配置

### 1. 邮件告警

```python
# alert_service.py
import smtplib
from email.mime.text import MIMEText

def send_alert(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = f"[RAG System Alert] {subject}"
    msg['From'] = "alerts@example.com"
    msg['To'] = "admin@example.com"
    
    with smtplib.SMTP('smtp.example.com', 587) as server:
        server.starttls()
        server.login("user", "password")
        server.send_message(msg)
```

### 2. 告警规则

- CPU 使用率 > 85% 持续 5 分钟
- 内存使用率 > 90% 持续 5 分钟
- 磁盘使用率 > 90%
- API 错误率 > 5% 持续 10 分钟
- 数据库连接失败

---

**更新时间**: 2024-03-16  
**版本**: 1.0.0
