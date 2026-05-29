# 项目复现部署指南

> 本文档面向**首次在新机器上复现本项目**的人，按顺序照做即可跑通前后端。
> 最后更新：2026-05-27

---

## 〇、系统架构与端口

后端是一整套 Docker 服务，前端是独立的 Vite 开发服务器（不在 Docker 内）。

| 服务 | 容器名 | 端口（宿主机） | 说明 |
|------|--------|---------------|------|
| PostgreSQL + pgvector | rag_db | 5432 | 主数据库（**必须 pgvector 镜像**） |
| Redis | rag_redis | 6379 | 缓存 / 任务队列 |
| PgBouncer | rag_pgbouncer | 6432 | 连接池（可选） |
| Neo4j | rag_neo4j | 7474 / 7687 | 知识图谱 |
| MinIO | rag_minio | 9000 / 9001 | 对象存储 |
| FastAPI 后端 | rag_backend | 8000 | API 服务 |
| Vue 前端 | （非容器） | 5500 | `npm run dev` |

前端通过 Vite 代理把 `/api/v1/*` 转发到 `http://localhost:8000`。

---

## 一、前置软件

| 软件 | 版本要求 | 验证命令 |
|------|---------|---------|
| Docker Desktop | 最新稳定版 | `docker --version` |
| Docker Compose | v2+（随 Docker Desktop） | `docker-compose version` |
| Node.js | ≥ 18 | `node -v` |
| npm | 随 Node | `npm -v` |
| Git | 任意 | `git --version` |

> Windows 用户：Docker Desktop 需开启 WSL2 后端；确保 Docker 已启动再执行后续命令。

---

## 二、拉取代码

```powershell
git clone <仓库地址> My_rag
cd My_rag
```

目录结构：

```
My_rag/
├── rag_backend/      # FastAPI 后端 + docker-compose.yml
├── rag_frontend/     # Vue3 前端
├── docs/             # 文档
└── SETUP.md          # 本文件
```

---

## 三、配置后端环境变量

```powershell
cd rag_backend
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

用编辑器打开 `.env`，**必须填写以下项**（其余可保持默认）：

```bash
# ---------- 数据库 ----------
POSTGRES_USER=postgres
POSTGRES_PASSWORD=你的数据库密码
POSTGRES_SERVER=db                 # ⚠️ Docker 内部互联用 db，不要写 localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db

# ---------- 安全 ----------
# 32 位以上随机字符串。用户 API Key 加密(G4)依赖它，换了会导致旧密文无法解密
SECRET_KEY=请生成一个32位以上的随机字符串
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ---------- 中间件密码 ----------
REDIS_PASSWORD=你的redis密码
NEO4J_PASSWORD=你的neo4j密码
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=你的minio密码

# ---------- LLM（至少配一个，否则对话/Agent 不可用）----------
LLM_PROVIDER=deepseek              # 可选: qwen / zhipu / openai / claude 等
DEEPSEEK_API_KEY=你的key

# ---------- Embedding（文档入库必需）----------
EMBEDDING_PROVIDER=siliconflow
SILICONFLOW_API_KEY=你的key

# ---------- 知识图谱（可选，但 NEO4J_PASSWORD 要与上面一致）----------
ENABLE_KNOWLEDGE_GRAPH=true
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
```

> 生成随机 SECRET_KEY 的方法（任选其一）：
> ```powershell
> # PowerShell
> -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
> ```
> ```bash
> # bash
> openssl rand -hex 24
> ```

---

## 四、启动后端 Docker 服务

```powershell
# 在 rag_backend 目录下
docker-compose up -d
```

首次启动会拉取镜像（Neo4j 约 600MB，耐心等待）。检查状态：

```powershell
docker-compose ps
```

所有服务应显示 `Up` 且 healthcheck 为 `(healthy)`。查看后端日志确认启动完成：

```powershell
docker-compose logs -f backend
# 看到 "Application startup complete." 即启动成功，Ctrl+C 退出日志查看
```

---

## 五、初始化数据库表 ⚠️ 关键步骤，不可跳过

后端容器的启动脚本**不会自动建表**。需要执行两步：

### 5.1 运行 alembic 迁移（建大部分业务表）

```powershell
docker exec rag_backend alembic upgrade head
```

这会建立 policy / financial / contract / custom_tools / agent_task 等业务表。

### 5.2 建立反馈系统 + 多模态配置的 5 张表

> 这 5 张表（用户反馈、失败案例、改进记录、多模态配置、多模态用量日志）目前**未纳入 alembic 迁移**，必须单独执行下面的脚本建表（幂等，重复执行安全）：

```powershell
docker exec rag_backend python -c @'
import asyncio
from app.db.session import engine
from app.db.base import Base
from app.models import feedback, user_multimodal_config

async def main():
    names = [
        "user_feedback", "failure_cases", "improvement_records",
        "user_multimodal_configs", "user_multimodal_usage_logs",
    ]
    tables = [Base.metadata.tables[n] for n in names]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables, checkfirst=True))
    print("✅ 反馈/多模态 5 张表已建立")

asyncio.run(main())
'@
```

### 5.3 验证表已建立

```powershell
docker exec rag_db psql -U postgres -d rag_db -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'user_feedback%' OR tablename LIKE 'failure_cases%' OR tablename LIKE 'improvement_records%' OR tablename LIKE 'user_multimodal%') ORDER BY tablename;"
```

应输出 5 行：
```
failure_cases
improvement_records
user_feedback
user_multimodal_configs
user_multimodal_usage_logs
```

---

## 六、启动前端

**另开一个终端窗口**：

```powershell
cd My_rag\rag_frontend

copy .env.example .env        # 默认空配置即可（走 Vite 代理到 8000）

npm install                   # 首次安装依赖

npm run dev                   # 启动开发服务器
```

启动成功后访问：**http://localhost:5500**

---

## 七、验证部署

1. 浏览器打开 http://localhost:5500
2. 注册一个账号并登录
3. 打开浏览器 F12 → Network，确认 `/api/v1/*` 请求返回 200
4. 逐项验证核心功能：

| 功能 | 操作 | 期望 |
|------|------|------|
| 对话 | 进入对话页，选知识库，发消息 | 流式返回回答 |
| 检索模式 | 输入框上方齿轮按钮 → 切换 simple/graphrag/agentic | 保存后发消息生效 |
| 反馈 | AI 回答下方点 👍/👎/⭐/💬 | `POST /api/v1/feedbacks` 返回 200 |
| 多模态配置 | 侧栏「个人偏好 → 多模态配置」 | 修改保存返回 200 |
| 多模态用量 | 侧栏「数据与监控 → 多模态用量」 | 统计卡片正常 |
| 反馈管理(admin) | 侧栏「数据与监控 → 反馈管理」 | 列表 + 统计卡片 |
| 失败分析(admin) | 侧栏「数据与监控 → 失败分析」 | 类型分布 + 案例卡片 |

---

## 八、替代方案：用 SQL 快照快速建表

如果不想跑 alembic + 手动建表（第五步），可以让**已有环境的人导出数据库快照**，新机器直接导入。

### 8.1 在已有环境导出（只导结构，推荐）

```powershell
# 只导表结构（干净、无敏感数据、可分享）
docker exec rag_db pg_dump -U postgres -d rag_db --schema-only --no-owner --no-privileges > schema.sql

# 如需连测试数据一起导（⚠️ 含密码 hash / 加密 API Key / 租户数据，切勿提交 Git）
docker exec rag_db pg_dump -U postgres -d rag_db --no-owner --no-privileges > full_dump.sql
```

### 8.2 新机器导入

新机器仍需先起数据库容器（**必须是 pgvector 镜像**，schema.sql 里含 `CREATE EXTENSION vector`）：

```powershell
cd rag_backend
docker-compose up -d db redis neo4j minio

# 导入 SQL（命令行方式）
docker exec -i rag_db psql -U postgres -d rag_db < schema.sql

# 或用 Navicat 连接 localhost:5432 (postgres / 密码 / rag_db) 运行 schema.sql

# 再起后端
docker-compose up -d backend
```

> 用了 SQL 快照后，**第五步可整步跳过**（表已经全部建好，含那 5 张表）。

---

## 九、服务管理常用命令

```powershell
# 在 rag_backend 目录下

docker-compose ps                      # 查看服务状态
docker-compose logs -f backend         # 实时后端日志
docker-compose restart backend         # 重启后端（改了挂载代码后）
docker-compose up -d --build backend   # 改了 Dockerfile/依赖后重建
docker-compose stop                    # 停止全部（保留容器）
docker-compose down                    # 停止并删除容器（数据卷保留）

# ⚠️ docker-compose down -v 会删除数据卷（清空数据库），慎用
```

可选重型组件（文档解析增强）：

```powershell
docker-compose --profile heavy up -d   # 加 unstructured-api
docker-compose --profile full up -d    # 全部可选服务
```

---

## 十、常见问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 后端反复重启 | `.env` 缺必填项 / SECRET_KEY 空 | 检查第三步必填项 |
| `relation "xxx" does not exist` | 表没建 | 执行第五步（5.1 + 5.2） |
| `CREATE EXTENSION vector` 失败 | PG 不是 pgvector 镜像 | 用 `pgvector/pgvector:pg16`（compose 默认已是） |
| 前端 `/api/v1/...` 404 | 后端没起 / 路由没注册 | `docker-compose logs backend` 查启动是否成功 |
| 前端 `/api/v1/...` 500 + `AsyncSession has no attribute query` | 后端用了旧代码 | `docker-compose restart backend` 重启 |
| 8000 端口被占用 | 其他进程占用 | `netstat -ano \| findstr :8000` 找 PID，`taskkill /PID <pid> /F` |
| 5500 端口被占用 | 其他进程占用 | 改 `rag_frontend/vite.config.ts` 的 `server.port` |
| 对话报 LLM 错误 | 没配 API Key | 检查 `.env` 的 `LLM_PROVIDER` 对应 key |
| 文档入库失败 | 没配 Embedding | 检查 `EMBEDDING_PROVIDER` 对应 key |

---

## 十一、最小可跑清单（TL;DR）

```powershell
# 后端
cd rag_backend
copy .env.example .env          # 然后编辑填必填项
docker-compose up -d
docker exec rag_backend alembic upgrade head
docker exec rag_backend python -c @'
import asyncio
from app.db.session import engine
from app.db.base import Base
from app.models import feedback, user_multimodal_config
async def main():
    names=["user_feedback","failure_cases","improvement_records","user_multimodal_configs","user_multimodal_usage_logs"]
    tables=[Base.metadata.tables[n] for n in names]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables, checkfirst=True))
    print("ok")
asyncio.run(main())
'@

# 前端（另开窗口）
cd ..\rag_frontend
copy .env.example .env
npm install
npm run dev
# 访问 http://localhost:5500
```
