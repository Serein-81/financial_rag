from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from app.core import settings
import logging

logger = logging.getLogger(__name__)

# =========================================================
# 1. 创建同步引擎 (用于测试和脚本)
# =========================================================
# 将异步 URL 转换为同步 URL
sync_database_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(
    sync_database_url, 
    echo=False, 
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE
)

# 创建同步 Session 工厂
SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autocommit=False,
    autoflush=False
)

# =========================================================
# 2. 创建异步引擎 (Engine) - 优化用于 PgBouncer
# =========================================================
# 连接池配置说明：
# - pool_size: 基础连接数（PgBouncer 模式下设小一些，让 PgBouncer 处理）
# - max_overflow: 最大溢出连接数
# - pool_recycle: 连接回收时间，避免连接过期
# - pool_pre_ping: 每次使用前检测连接是否有效
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args={
        "server_settings": {
            "statement_timeout": "30000",  # 查询超时 30秒
        },
        "timeout": 30,  # 连接超时 30秒
    }
)

# 记录连接池配置
if settings.PGBOUNCER_ENABLED:
    logger.info(
        f"数据库连接池配置 (PgBouncer {settings.PGBOUNCER_POOL_MODE} 模式): "
        f"pool_size={settings.DB_POOL_SIZE}, "
        f"max_overflow={settings.DB_MAX_OVERFLOW}, "
        f"target={settings.PGBOUNCER_HOST}:{settings.PGBOUNCER_PORT}"
    )
else:
    logger.info(
        f"数据库连接池配置 (直连): "
        f"pool_size={settings.DB_POOL_SIZE}, "
        f"max_overflow={settings.DB_MAX_OVERFLOW}, "
        f"target={settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}"
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
# 4. 简化的依赖注入函数 (Dependency)
# =========================================================
# ⚠️ 重要：PgBouncer Transaction 模式下，不再设置 SET LOCAL
# 租户隔离通过 Repository 层的显式 tenant_id 参数实现
async def get_db():
    """
    获取数据库会话
    
    ⚠️ 注意：
    - 不再设置 SET LOCAL 会话变量
    - 租户隔离通过 Repository 层实现
    - 每个请求获取独立的 session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    """数据库会话上下文管理器

    用于在非 FastAPI 依赖注入的场景下获取数据库会话
    
    ⚠️ 注意：
    - 不再设置 SET LOCAL 会话变量
    - 租户隔离通过 Repository 层实现
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
