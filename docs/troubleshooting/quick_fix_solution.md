# 🔧 快速修复：增加连接池和优化超时

## 问题根因
请求在中间件阶段挂起，可能是因为数据库连接池被耗尽。

## 修复步骤

### 步骤 1：修改数据库连接池配置

编辑文件: `rag_backend/app/db/session.py`

将：
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,        # ← 当前
    max_overflow=20,     # ← 当前
    pool_timeout=30,     # ← 当前
    ...
)
```

改为：
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,        # ← 增加
    max_overflow=30,     # ← 增加
    pool_timeout=10,     # ← 减少，方便快速失败
    ...
)
```

### 步骤 2：添加中间件超时

编辑文件: `rag_backend/app/middleware/tenant_middleware.py`

在 `get_user_tenant_id` 方法中添加超时：

```python
async def get_user_tenant_id(self, user_id: str) -> str:
    """从数据库查询用户的 tenant_id"""
    import asyncio
    
    try:
        async with asyncio.timeout(5):  # ← 添加 5 秒超时
            async with AsyncSessionLocal() as session:
                ...
    except asyncio.TimeoutError:
        logger.error("获取 tenant_id 超时")
        return None
```

### 步骤 3：重新构建 Docker 容器

```bash
cd rag_backend
docker-compose up -d --build
docker logs -f rag_backend
```

### 步骤 4：测试上传

1. 刷新浏览器
2. 尝试上传文件
3. 观察 Network 面板

---

## 备选方案：如果以上都不工作

尝试完全重启所有服务：

```bash
cd rag_backend
docker-compose down
docker-compose up -d
docker logs -f rag_backend
```

等待 30 秒让所有服务完全启动，然后再测试上传。
