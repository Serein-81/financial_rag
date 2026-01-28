from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core import settings

# =========================================================
# 1. 创建异步引擎 (Engine)
# =========================================================
# 这是一个连接池对象。它不会马上连接数据库，只有当真正有请求时才会建立连接。
# echo=True 表示会在控制台打印出每一条生成的 SQL 语句，方便你调试代码。
# (生产环境通常会把 echo 设为 False)
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# =========================================================
# 2. 创建 Session 工厂 (SessionLocal)
# =========================================================
# 我们不能直接用 engine 查数据，必须用 Session。
# 这个工厂负责源源不断地生产 Session 对象。
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # 防止提交后属性过期，异步编程中通常设为 False
)

# =========================================================
# 3. 定义依赖注入函数 (Dependency)
# =========================================================
# 这是 FastAPI 最核心的用法。
# 以后在写 API 接口时，只需要写 `db: AsyncSession = Depends(get_db)`
# FastAPI 就会自动帮你执行下面的逻辑：
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            # yield 相当于“借出”这个 session 给接口用
            yield session
        finally:
            # 无论接口代码有没有报错，这里都会执行
            # 相当于“归还”连接，关闭 session，防止数据库连接数爆满
            await session.close()