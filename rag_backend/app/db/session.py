from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from app.core import settings

# =========================================================
# 1. 创建同步引擎 (用于测试和脚本)
# =========================================================
# 将异步 URL 转换为同步 URL
sync_database_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_database_url, echo=False, pool_pre_ping=True)

# 创建同步 Session 工厂
SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autocommit=False,
    autoflush=False
)

# =========================================================
# 2. 创建异步引擎 (Engine)
# =========================================================
# 这是一个连接池对象。它不会马上连接数据库，只有当真正有请求时才会建立连接。
# echo=True 表示会在控制台打印出每一条生成的 SQL 语句，方便你调试代码。
# (生产环境通常会把 echo 设为 False)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    connect_args={
        "server_settings": {
            "statement_timeout": "30000",  # 查询超时 30秒
        },
        "timeout": 30,  # 连接超时 30秒
    }
)

# =========================================================
# 3. 创建异步 Session 工厂 (SessionLocal)
# =========================================================
# 我们不能直接用 engine 查数据，必须用 Session。
# 这个工厂负责源源不断地生产 Session 对象。
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # 防止提交后属性过期，异步编程中通常设为 False
)

# =========================================================
# 4. 定义依赖注入函数 (Dependency)
# =========================================================
# 这是 FastAPI 最核心的用法。
# 以后在写 API 接口时，只需要写 `db: AsyncSession = Depends(get_db)`
# FastAPI 就会自动帮你执行下面的逻辑：
async def get_db():
    async with AsyncSessionLocal() as session:
        # yield 相当于"借出"这个 session 给接口用
        # async with 上下文管理器会自动处理 session 的关闭
        yield session


@asynccontextmanager
async def get_db_context():
    """数据库会话上下文管理器

    用于在非 FastAPI 依赖注入的场景下获取数据库会话
    """
    async with AsyncSessionLocal() as session:
        yield session