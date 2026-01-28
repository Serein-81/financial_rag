from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine

# ➕ 1. 导入 Base (我们的模型基类)
from app.db.base import Base
# ➕ 2. 必须导入 models 里的文件！
# 只有导入了 document，SQLAlchemy 才知道 "哦，原来有一个叫 Document 的子类要建表"
# 如果不导入这行，Base.metadata 里面是空的，就不会建表。
from app.models import document
from app.api.v1.endpoints import document as document_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.PROJECT_NAME} 正在启动...")

    # --- 🟢 自动建表逻辑 (Magic Happens Here) ---
    print("正在检查并自动创建数据库表...")
    try:
        async with engine.begin() as conn:
            # run_sync: 因为 create_all 是同步方法，所以在异步里要这样运行
            await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库表结构同步完成！")
    except Exception as e:
        print(f"❌ 自动建表失败: {e}")
    # ----------------------------------------------

    print("正在尝试连接数据库...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print(f"✅ 数据库连接成功！地址: {settings.POSTGRES_SERVER}")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

    yield

    print(f"🛑 {settings.PROJECT_NAME} 正在关闭...")
    await engine.dispose()


# ... 下面的代码保持不变 ...
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(document_router.router, prefix="/api/v1/documents", tags=["Documents"])


@app.get("/")
def root():
    return {"message": "RAG Backend is Running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)