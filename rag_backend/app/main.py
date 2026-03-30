from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.utils.logging_config import setup_logging, get_logger, LogFormat

# ➕ 1. 导入 Base (我们的模型基类)
from app.db.base import Base
# ➕ 2. 必须导入 models 里的文件！
# 只有导入了 document，SQLAlchemy 才知道 "哦，原来有一个叫 Document 的子类要建表"
# 如果不导入这行，Base.metadata 里面是空的，就不会建表。
from app.models import document, tax_report, audit_task, review_request
from app.api.v1.endpoints import document as document_router, search, chat, auth, session, knowledge, agent_trace, tool_trace, prompt_optimization, memory, knowledge_graph, audit, invite_code, enterprise, logs, chat_logs, tax_report, human_review, multi_agent

# 🔒 导入租户中间件
from app.middleware.tenant_middleware import TenantContextMiddleware
# 🔒 导入日志中间件
from app.middleware.logging_middleware import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger(__name__)
    
    setup_logging(
        log_level="INFO",
        log_dir="logs",
        log_file="app.log",
        max_bytes=10 * 1024 * 1024,
        backup_count=5,
        enable_console=True,
        enable_file=True,
        format_type=LogFormat.DETAILED
    )
    
    logger.info(f"🚀 {settings.PROJECT_NAME} 正在启动...")

    # # --- 🟢 自动建表逻辑 (Magic Happens Here) ---
    # print("正在检查并自动创建数据库表...")
    # try:
    #     async with engine.begin() as conn:
    #         # run_sync: 因为 create_all 是同步方法，所以在异步里要这样运行
    #         await conn.run_sync(Base.metadata.create_all)
    #     print("✅ 数据库表结构同步完成！")
    # except Exception as e:
    #     print(f"❌ 自动建表失败: {e}")
    # # ----------------------------------------------

    logger.info("正在尝试连接数据库...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"✅ 数据库连接成功！地址: {settings.POSTGRES_SERVER}")
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")

    yield

    logger.info(f"🛑 {settings.PROJECT_NAME} 正在关闭...")
    await engine.dispose()
    
    logger.info("✅ 应用已成功关闭")



# ... 下面的代码保持不变 ...
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)



# 添加租户上下文中间件
# 注意：中间件按注册顺序反向执行，所以 TenantContextMiddleware 在 CORSMiddleware 之前
app.add_middleware(TenantContextMiddleware)

# 👇 添加日志中间件（记录所有API请求）
app.add_middleware(LoggingMiddleware)

# 👇 配置 CORS 中间件（必须在最后添加，使其最先执行）
# 允许所有来源访问 (开发阶段图方便，生产环境可以指定域名)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"]) # 👈 注册

app.include_router(document_router.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])

#挂载聊天接口
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])

# app.router.include_router(auth.router, prefix="/auth", tags=["Auth"]) # 👈 新增这行

app.include_router(session.router, prefix="/api/v1/sessions", tags=["Session"]) # 🆕
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge Base"]) # 🆕
app.include_router(agent_trace.router, prefix="/api/v1/agent_trace", tags=["Agent Trace"]) # 🆕 Agent 追踪
app.include_router(tool_trace.router, prefix="/api/v1/tool_trace", tags=["Tool Trace"]) # 🆕 工具追踪
app.include_router(prompt_optimization.router, prefix="/api/v1/prompt", tags=["Prompt Optimization"]) # 🆕 Prompt 优化
app.include_router(memory.router, prefix="/api/v1/memory", tags=["Memory System"]) # 🆕 记忆系统
app.include_router(knowledge_graph.router, prefix="/api/v1/knowledge_graph", tags=["Knowledge Graph"]) # 🆕 知识图谱
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Multi-Agent Audit"]) # 🆕 多智能体审查
app.include_router(invite_code.router, prefix="/api/v1/invite-codes", tags=["Invite Codes"]) # 🆕 邀请码管理
app.include_router(enterprise.router, prefix="/api/v1/enterprise", tags=["Enterprise Management"]) # 🆕 企业用户管理
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logging System"]) # 🆕 日志系统
app.include_router(chat_logs.router, prefix="/api/v1/chat-logs", tags=["Chat Logs"]) # 🆕 对话日志
app.include_router(tax_report.router, prefix="/api/v1/tax-reports", tags=["Tax Reports"]) # 🆕 税务报告管理
app.include_router(human_review.router, prefix="/api/v1/human-review", tags=["Human Review"]) # 🆕 人工审核
app.include_router(multi_agent.router, prefix="/api/v1/multi-agent", tags=["Multi-Agent System"]) # 🆕 多智能体系统

@app.get("/")
def root():
    return {"message": "RAG Backend is Running", "docs": "/docs"}

@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy", "message": "Service is running"}

@app.get("/api/health")
def api_health_check():
    """API健康检查端点"""
    return {"status": "healthy", "message": "API is running"}

@app.get("/personal-page")
def personal_page():
    """个人页面入口"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    static_path = Path(__file__).parent / "static" / "personal_page.html"
    if static_path.exists():
        return FileResponse(str(static_path))
    else:
        return {"error": "个人页面未找到"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)