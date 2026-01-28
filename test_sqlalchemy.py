import asyncio
from typing import Optional
from sqlalchemy import String, select, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ==========================================
# 第一部分：数据库配置 (核心改动点)
# ==========================================

# 格式：postgresql+asyncpg://用户名:密码@地址:端口/数据库名
# 示例：用户名 postgres, 本地 localhost, 端口 5432, 库名 rag_db
DATABASE_URL = "postgresql+asyncpg://postgres:REDACTED_PG_PASSWORD@127.0.0.1:5432/rag_db"

# 创建异步引擎
# echo=True 会打印 SQL 日志，生产环境建议关闭
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=5,  # 连接池大小：保持5个连接
    max_overflow=10  # 临时激增时，允许额外再创建10个连接
)

# 创建会话工厂
# expire_on_commit=False 是异步编程必须的，防止提交后属性过期导致重新触发IO报错
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ==========================================
# 第二部分：定义模型 (和 SQLite 一模一样)
# ==========================================

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    # PostgreSQL 的主键通常是 SERIAL 或 IDENTITY，SQLAlchemy 会自动处理
    id: Mapped[int] = mapped_column(primary_key=True)

    # String 对应 PostgreSQL 的 VARCHAR
    name: Mapped[str] = mapped_column(String(50))

    # Optional[int] 对应 PostgreSQL 的 INTEGER (NULLABLE)
    age: Mapped[Optional[int]] = mapped_column()

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name}, age={self.age})"


# ==========================================
# 第三部分：业务逻辑 (CRUD)
# ==========================================

async def main():
    # 1. 建表 (DDL 操作)
    # 注意：异步引擎执行同步的 metadata 操作需要用 run_sync
    # 这会在数据库里创建 "users" 表 (如果不存在的话)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 开启一个会话 (Session) 进行操作
    async with AsyncSessionLocal() as session:
        # --- 新增 (Create) ---
        print("\n=== 新增用户 ===")
        user1 = User(name="Postgres用户", age=30)
        user2 = User(name="测试员", age=25)

        session.add_all([user1, user2])
        await session.commit()  # 提交事务

        # 刷新数据，因为数据库生成了 id，我们需要把它读回内存
        await session.refresh(user1)
        await session.refresh(user2)
        print(f"写入成功: {user1}, {user2}")

        # --- 查询 (Read) ---
        print("\n=== 查询用户 ===")
        # 构造 SQL 语句
        stmt = select(User).where(User.name == "Postgres用户")
        result = await session.execute(stmt)

        # scalar_one_or_none()：只要一个结果，如果没有返回None，如果有多个报错
        user_obj = result.scalar_one_or_none()
        print(f"查到数据: {user_obj}")

        # --- 修改 (Update) ---
        print("\n=== 修改用户 ===")
        if user_obj:
            user_obj.age = 88  # 这里的修改还在内存里
            await session.commit()  # 提交到数据库
            print(f"修改成功，当前年龄: {user_obj.age}")

        # --- 删除 (Delete) ---
        print("\n=== 删除用户 ===")
        # 也是先构造语句，再执行
        stmt_del = delete(User).where(User.name == "测试员")
        await session.execute(stmt_del)
        await session.commit()
        print("删除操作完成")

    # 3. 关闭引擎 (通常在程序退出时执行)
    await engine.dispose()


if __name__ == "__main__":
    # Windows 用户可能需要设置 loop policy，但在 Python 3.8+ 通常不需要了
    asyncio.run(main())