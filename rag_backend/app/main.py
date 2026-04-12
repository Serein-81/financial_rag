from fastapi import FastAPI
from starlette.requests import Request
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.utils.logging_config import setup_logging, get_logger, LogFormat

from app.core.resource_manager import make_resource_manager, RedisConnectionPool

from app.db.base import Base
# ➕ 2. 必须导入 models 里的文件！
# 只有导入了 document，SQLAlchemy 才知道 "哦，原来有一个叫 Document 的子类要建表"
# 如果不导入这行，Base.metadata 里面是空的，就不会建表。
from app.models import document, tax_report, audit_task, review_request, user_financial_data, tenant_settings, policy, policy_relation, enterprise_policy_match, financial_health, contract_review, scheduled_task
from app.api.v1.endpoints import document as document_router, search, chat, auth, session, knowledge, agent_trace, tool_trace, prompt_optimization, memory, knowledge_graph, audit, invite_code, enterprise, logs, chat_logs, tax_report, human_review, multi_agent, group_chat, user_financial_data, tenant_settings, policy, rate_limit, streaming, snapshot, suggestion, tax_intelligence, financial_health, policy_tracking, contract_review, task_manager, agent_llm_config, agent_discovery, financial_tools_test, workflow_events

# 🔒 导入租户中间件
from app.middleware.tenant_middleware import TenantContextMiddleware
# 🔒 导入日志中间件
from app.middleware.logging_middleware import LoggingMiddleware
# 🔒 导入限流中间件
from app.middleware.rate_limit_middleware import RateLimitMiddleware

import asyncio
from app.services.group_chat_service import group_chat_ws_manager
from app.services.redis_service import get_redis_service


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

    logger.info("正在尝试连接数据库...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"✅ 数据库连接成功！地址: {settings.POSTGRES_SERVER}")
    except ConnectionError as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        raise
    except OSError as e:
        logger.error(f"❌ 数据库网络错误: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ 数据库连接未知错误: {e}")
        raise

    async with make_resource_manager() as resource_manager:
        app.state.resource_manager = resource_manager
        logger.info("✅ ResourceManager 初始化完成")
        
        asyncio.create_task(cleanup_expired_presence_task())
        logger.info("✅ 在线状态清理任务已启动")

        from app.services.policy_scheduler_service import policy_sync_scheduler
        asyncio.create_task(policy_sync_scheduler.start())
        logger.info("✅ 政策同步调度器已启动（定时从官方渠道同步）")
        
        from app.services.task_scheduler import task_scheduler
        await task_scheduler.start()
        logger.info("✅ 定时任务调度器已启动")
        
        try:
            from app.a2a_protocol.initializer import initialize_a2a_protocol
            initializer, registry = await initialize_a2a_protocol()
            app.state.a2a_initializer = initializer
            app.state.a2a_registry = registry
            app.state.a2a_dispatcher = initializer.get_dispatcher()
            logger.info("✅ A2A 协议初始化完成")
        except ImportError as e:
            logger.warning(f"⚠️ A2A 协议导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ A2A 协议运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ A2A 协议初始化失败: {e}")
        
        try:
            from app.a2a_protocol import get_transport_manager
            transport_manager = await get_transport_manager()
            app.state.transport_manager = transport_manager
            logger.info("✅ A2A Transport Manager 初始化完成")
        except ImportError as e:
            logger.warning(f"⚠️ A2A Transport Manager 导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ A2A Transport Manager 运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ A2A Transport Manager 初始化失败: {e}")
        
        try:
            from app.memory_system.model_context_manager import model_context_manager
            init_success = await model_context_manager.initialize()
            if init_success:
                logger.info(f"✅ ModelContextManager 初始化成功 - 从 API 加载")
            else:
                cached_count = len(model_context_manager.get_all_context_limits())
                logger.info(f"✅ ModelContextManager 初始化完成 - 使用缓存 ({cached_count} 个模型)")
        except ImportError as e:
            logger.warning(f"⚠️ ModelContextManager 导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ ModelContextManager 运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ ModelContextManager 初始化失败: {e}")
        
        yield

    logger.info(f"🛑 {settings.PROJECT_NAME} 正在关闭...")
    await task_scheduler.stop()
    logger.info("✅ 定时任务调度器已停止")
    await RedisConnectionPool.close()
    await engine.dispose()
    
    logger.info("✅ 应用已成功关闭")



# ... 下面的代码保持不变 ...
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# 🔧 测试端点 - 用于诊断请求是否到达
from fastapi import UploadFile, File

@app.post("/debug/test-upload")
async def test_upload_debug(file: UploadFile = File(...)):
    """测试端点 - 验证请求是否到达"""
    import time
    logger.info(f"🔧 [TEST-UPLOAD] 收到请求! 文件: {file.filename}, 大小: {file.size}")
    return {
        "status": "ok",
        "filename": file.filename,
        "size": file.size,
        "timestamp": time.time()
    }

@app.get("/debug/ping")
async def ping():
    """简单的 ping 端点"""
    import time
    return {"pong": True, "timestamp": time.time()}

@app.get("/debug/tax-upload-diagnostic")
async def tax_upload_diagnostic(request: Request):
    """税务上传诊断端点 - 验证请求路径和认证"""
    import time
    from app.core.security import decode_access_token
    
    result = {
        "timestamp": time.time(),
        "path": str(request.url.path),
        "method": request.method,
        "headers": dict(request.headers),
        "query_params": dict(request.query_params),
        "client_ip": request.client.host if request.client else None,
        "auth_header_exists": "authorization" in [h.lower() for h in request.headers.keys()],
        "token_payload": None,
        "token_error": None,
    }
    
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = decode_access_token(token)
            result["token_payload"] = {
                "user_id": payload.get("sub"),
                "tenant_id": payload.get("tenant_id"),
                "exp": payload.get("exp"),
            }
        except Exception as e:
            result["token_error"] = str(e)
    
    return result


# 添加租户上下文中间件
# 注意：中间件按注册顺序反向执行，所以 TenantContextMiddleware 在 CORSMiddleware 之前
app.add_middleware(TenantContextMiddleware)

# 👇 添加日志中间件（记录所有API请求）
app.add_middleware(LoggingMiddleware)

# 👇 添加限流中间件（API限流保护）
app.add_middleware(RateLimitMiddleware)

# 👇 配置 CORS 中间件（必须在最后添加，使其最先执行）
# 允许所有来源访问 (开发阶段图方便，生产环境可以指定域名)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"]) # 👈 注册
app.include_router(rate_limit.router, prefix="/api/v1", tags=["Rate Limit Management"])
app.include_router(streaming.router, prefix="/api/v1", tags=["Streaming Enhancement"])
app.include_router(snapshot.router, prefix="/api/v1", tags=["Session Snapshots"])
app.include_router(suggestion.router, prefix="/api/v1", tags=["Suggestion"])

app.include_router(document_router.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(policy.router, prefix="/api/v1/policy", tags=["Policy Management"]) # 🆕 政策管理

#挂载聊天接口
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])

# app.router.include_router(auth.router, prefix="/auth", tags=["Auth"]) # 👈 新增这行

app.include_router(session.router, prefix="/api/v1/sessions", tags=["Session"]) # 🆕
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge Base"]) # 🆕
app.include_router(agent_trace.router, prefix="/api/v1/agent_trace", tags=["Agent Trace"]) # 🆕 Agent 追踪
app.include_router(agent_discovery.router, prefix="/api/v1/agent-discovery", tags=["Agent Discovery"]) # 🆕 Agent 发现与追踪
app.include_router(tool_trace.router, prefix="/api/v1/tool_trace", tags=["Tool Trace"]) # 🆕 工具追踪
app.include_router(prompt_optimization.router, prefix="/api/v1/prompt", tags=["Prompt Optimization"]) # 🆕 Prompt 优化
app.include_router(financial_tools_test.router, prefix="/api/v1/financial-tools-test", tags=["财务工具测试"]) # 🆕 财务工具测试
app.include_router(memory.router, prefix="/api/v1/memory", tags=["Memory System"]) # 🆕 记忆系统
app.include_router(knowledge_graph.router, prefix="/api/v1/knowledge_graph", tags=["Knowledge Graph"]) # 🆕 知识图谱
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Multi-Agent Audit"]) # 🆕 多智能体审查
app.include_router(invite_code.router, prefix="/api/v1/invite-codes", tags=["Invite Codes"]) # 🆕 邀请码管理
app.include_router(enterprise.router, prefix="/api/v1/enterprise", tags=["Enterprise Management"]) # 🆕 企业用户管理
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logging System"]) # 🆕 日志系统
app.include_router(chat_logs.router, prefix="/api/v1/chat-logs", tags=["Chat Logs"]) # 🆕 对话日志
app.include_router(tax_report.router, prefix="/api/v1/tax-reports", tags=["Tax Reports"]) # 🆕 税务报告管理
app.include_router(tax_intelligence.router, prefix="/api/v1", tags=["Tax Intelligence"]) # 🆕 税务智能分析
app.include_router(financial_health.router, prefix="/api/v1", tags=["Financial Health"]) # 🆕 财务健康监控
app.include_router(policy_tracking.router, prefix="/api/v1", tags=["Policy Tracking"]) # 🆕 政策法规追踪
app.include_router(contract_review.router, prefix="/api/v1", tags=["Contract Review"]) # 🆕 合同审核
app.include_router(human_review.router, prefix="/api/v1/human-review", tags=["Human Review"]) # 🆕 人工审核
app.include_router(multi_agent.router, prefix="/api/v1/multi-agent", tags=["Multi-Agent System"]) # 🆕 多智能体系统
app.include_router(user_financial_data.router, prefix="/api/v1", tags=["Financial Data Management"]) # 🆕 财务数据管理

try:
    from app.api.v1.endpoints.a2a_protocol import router as a2a_router
    app.include_router(a2a_router, prefix="/api/v1", tags=["A2A Protocol"])
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"A2A Protocol 路由未注册: {e}")

try:
    from app.api.v1.endpoints.a2a_v1 import router as a2a_v1_router
    app.include_router(a2a_v1_router, prefix="/api/v1", tags=["A2A Protocol v1"])
    logger = get_logger(__name__)
    logger.info("✅ A2A Protocol v1 路由已注册")
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"A2A Protocol v1 路由未注册: {e}")

# 群聊相关路由
app.include_router(group_chat.router, prefix="/api/v1/groups", tags=["Group Chat"]) # 🆕 群聊
app.include_router(group_chat.invitation_router, prefix="/api/v1/invitations", tags=["Group Invitations"]) # 🆕 群聊邀请
app.include_router(group_chat.notification_router, prefix="/api/v1/notifications", tags=["Notifications"]) # 🆕 通知
app.include_router(group_chat.ws_router, prefix="/api/v1/ws/groups", tags=["Group Chat WebSocket"]) # 🆕 群聊 WebSocket

# 租户设置
app.include_router(tenant_settings.router, prefix="/api/v1", tags=["Tenant Settings"]) # 🆕 租户设置

# 智能体LLM配置
app.include_router(agent_llm_config.router, prefix="/api/v1/agents", tags=["Agent LLM Config"]) # 🆕 智能体LLM配置

# 任务管理
app.include_router(task_manager.router, prefix="/api/v1/task-manager", tags=["Task Manager"]) # 🆕 定时任务管理

# 工作流事件 SSE 推送
app.include_router(workflow_events.router, prefix="/api/v1", tags=["Workflow Events"]) # 🆕 工作流事件实时推送

@app.get("/")
def root():
    return {"message": "RAG Backend is Running", "docs": "/docs"}

@app.get("/health")
async def health_check(request: Request):
    """健康检查端点（增强版）"""
    from app.services.health_service import health_service
    
    # 执行健康检查
    report = await health_service.check_all(use_cache=True)
    
    # 返回健康报告
    return report.to_dict()


@app.get("/health/quick")
async def health_check_quick(request: Request):
    """快速健康检查端点（只检查关键组件）"""
    from app.services.health_service import health_service
    
    report = await health_service.check_quick()
    
    return report


@app.get("/health/{component}")
async def health_check_component(
    request: Request,
    component: str
):
    """单个组件健康检查"""
    from app.services.health_service import health_service
    
    # 检查指定的组件
    report = await health_service.check_all(
        use_cache=True,
        components=[component]
    )
    
    if not report.components:
        return {
            "status": "unknown",
            "message": f"Unknown component: {component}",
            "component": component
        }
    
    component_health = report.components[0]
    return component_health.to_dict()

@app.get("/api/health")
def api_health_check():
    """API健康检查端点"""
    return {"status": "healthy", "message": "API is running", "version": settings.VERSION if hasattr(settings, "VERSION") else "1.0.0"}

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


async def cleanup_expired_presence_task():
    """后台任务：定期清理过期的在线状态"""
    logger = get_logger(__name__)
    
    while True:
        try:
            await asyncio.sleep(60)
            
            redis_service = get_redis_service()
            if not redis_service or not redis_service.client:
                continue
            
            try:
                presence_keys = redis_service.client.keys("group:presence:*")
                
                for key in presence_keys:
                    group_id = key.split(":")[-1]
                    
                    members_data = redis_service.client.hgetall(key)
                    now = asyncio.get_event_loop().time()
                    removed_count = 0
                    
                    for user_id, data_str in members_data.items():
                        try:
                            import json
                            from datetime import datetime
                            data = json.loads(data_str)
                            last_heartbeat = data.get("timestamp", 0)
                            
                            if now - last_heartbeat > 90:
                                redis_service.client.hdel(key, user_id)
                                removed_count += 1
                                
                                await group_chat_ws_manager.broadcast_to_group(
                                    group_id,
                                    {
                                        "event": "member_offline",
                                        "data": {
                                            "user_id": user_id,
                                            "reason": "timeout",
                                            "timestamp": datetime.fromtimestamp(last_heartbeat).isoformat()
                                        }
                                    }
                                )
                        except json.JSONDecodeError:
                            logger.warning(f"无法解析用户在线状态数据: {user_id}")
                            continue
                        except (ValueError, KeyError) as e:
                            logger.warning(f"用户在线状态数据格式错误: {user_id}, {e}")
                            continue
                        except (OSError, IOError) as e:
                            logger.warning(f"处理用户在线状态IO错误: {user_id}, {e}")
                            continue
                        except Exception:
                            logger.warning(f"处理用户在线状态时发生未知错误: {user_id}")
                            continue
                    
                    if removed_count > 0:
                        logger.debug(f"清理群组 {group_id} 中 {removed_count} 个过期在线成员")
                        
            except OSError as e:
                logger.error(f"清理在线状态任务 Redis 连接错误: {e}")
                await asyncio.sleep(5)
            except RuntimeError as e:
                logger.error(f"清理在线状态任务运行时错误: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"清理在线状态任务出错: {e}")
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("在线状态清理任务已停止")
            break
        except Exception as e:
            logger.error(f"在线状态清理任务异常: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)