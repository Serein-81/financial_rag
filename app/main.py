from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text  # 用于写测试用的 SQL 语句
from app.core.config import settings
from app.db.session import engine


# =========================================================
# 1. 生命周期管理器 (Lifespan)
# =========================================================
# 这是一个新概念。它的作用是管理 App "从启动到关闭" 这段时间里要做的事。
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 🟢 启动阶段 (Startup) ---
    print(f"🚀 {settings.PROJECT_NAME} 正在启动...")

    print("正在尝试连接数据库...")
    try:
        # 我们向数据库发起一个最简单的查询 "SELECT 1"
        # 如果数据库回话了，说明连接成功
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print(f"✅ 数据库连接成功！地址: {settings.POSTGRES_SERVER}")
    except Exception as e:
        # 如果连不上，打印红色错误信息
        print(f"❌ 数据库连接失败: {e}")
        # 生产环境中，这里通常会直接抛出异常停止启动，但在开发时我们可以先打印出来

    yield  # --- ⏸️ 这里 App 开始正常运行接收请求 ---

    # --- 🔴 关闭阶段 (Shutdown) ---
    print(f"🛑 {settings.PROJECT_NAME} 正在关闭...")
    # 释放数据库连接资源，防止内存泄漏
    await engine.dispose()


# =========================================================
# 2. 初始化 App
# =========================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan  # 把上面的生命周期管家注册进去
)


# =========================================================
# 3. 写一个最简单的测试接口
# =========================================================
@app.get("/")
def root():
    return {
        "message": "恭喜你，RAG 后端系统已成功启动！",
        "docs_url": "http://127.0.0.1:8000/docs",
        "author": "cjh"
    }


# =========================================================
# 4. 本地调试入口
# =========================================================
# 只有当你直接运行这个文件时，下面这段才会执行
if __name__ == "__main__":
    import uvicorn

    # host="127.0.0.1": 只允许本机访问
    # port=8000: 端口号
    # reload=True: 热重载模式。你改了代码保存，程序会自动重启，不用手动关了再开
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)