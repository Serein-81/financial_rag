"""
租户上下文中间件
负责从请求中提取 tenant_id 并设置到数据库会话上下文中
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.security import decode_access_token
from app.core.exceptions import TokenExpiredException, TokenInvalidException
from app.middleware.auth_types import AuthErrorType, AuthErrorMessages
from contextvars import ContextVar
import logging
import uuid
import time

logger = logging.getLogger(__name__)


def safe_error_str(e: Exception) -> str:
    """Safely convert exception to string, handling all encoding scenarios"""
    try:
        error_str = str(e)
        try:
            return error_str.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return error_str.encode('ascii', errors='replace').decode('ascii', errors='replace')
    except Exception:
        try:
            return repr(e)
        except Exception:
            return "Error converting exception to string"


# 使用 ContextVar 来存储租户上下文，解决异步并发问题
tenant_context: ContextVar[str] = ContextVar('tenant_context', default=None)
user_context: ContextVar[str] = ContextVar('user_context', default=None)


class TenantCache:
    """
    租户信息缓存
    
    用于减少数据库查询，提升性能
    """
    
    def __init__(self, ttl: int = 300):
        self._cache = {}
        self._ttl = ttl
    
    def get(self, key: str) -> str:
        """获取缓存的租户 ID"""
        if key in self._cache:
            cached = self._cache[key]
            if time.time() - cached["timestamp"] < self._ttl:
                return cached["tenant_id"]
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, tenant_id: str):
        """设置租户 ID 缓存"""
        self._cache[key] = {
            "tenant_id": tenant_id,
            "timestamp": time.time()
        }
    
    def clear(self):
        """清空缓存"""
        self._cache = {}


tenant_cache = TenantCache(ttl=300)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    租户上下文中间件
    
    功能：
    1. 从 JWT Token 或 Header 中提取 tenant_id
    2. 设置 PostgreSQL session variable: app.current_tenant_id
    3. 记录租户访问日志
    4. 使用 ContextVar 解决异步并发问题
    """
    
    # 不需要租户隔离的路径（公共接口）
    EXCLUDED_PATHS = [
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/register/admin",
        "/api/v1/auth/me",
        "/api/v1/auth/sms/send",
        "/api/v1/auth/sms/verify",
        "/api/v1/auth/avatar",
        "/api/v1/auth/validate-invite-code",
        "/api/v1/auth/apply-invite-code",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/health",
        "/api/v1/health",
        "/api/v1/health/detailed",
        "/api/v1/chat-logs/test",
        "/api/v1/search/hybrid",
        "/api/v1/search/hybrid/stream",
        "/api/v1/search/hybrid/synonym",
        "/api/v1/search/query",
        "/api/v1/sessions",
        "/api/v1/sessions/",
        "/api/v1/sessions/{session_id}",
        "/api/v1/sessions/{session_id}/messages",
        "/api/v1/chat/completions",
        "/api/v1/chat/agent_chat",
        "/api/v1/chat/agent_chat_stream",
        "/api/v1/a2a",
        "/api/v1/a2a/",
        "/api/v1/tenant-settings",
        "/api/v1/multi-agent/health",
        "/api/v1/multi-agent/monitor/health",
        "/api/v1/multi-agent/metrics",
        "/api/v1/multi-agent/pipelines/active",
        "/api/v1/financial-data/download-template",
        "/api/v1/financial-data/download-test-templates",
        "/api/v1/financial-data",
        "/api/v1/financial-data/",
        "/debug/ping",
        "/debug/test-upload",
        "/api/debug/ping",
        "/api/debug/test-upload",
        "/api/debug/tax-upload-diagnostic",
    ]

    async def dispatch(self, request: Request, call_next):
        """处理请求"""

        # 跳过 OPTIONS 请求
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in ["/", "/docs", "/redoc", "/openapi.json", "/health"]:
            return await call_next(request)

        # 检查是否是排除路径
        request_path = str(request.url.path)
        excluded = any(request_path.startswith(path) for path in self.EXCLUDED_PATHS)
        if excluded:
            return await call_next(request)
        
        # 1. 提取 Token（用于区分是否有 Token）
        token = self._extract_token(request)
        
        # 2. 如果没有 Token，返回 401（兼容前端）
        if not token:
            logger.warning(
                f"[AUTH] [{AuthErrorType.NO_TOKEN.value}] Path={request.url.path} "
                f"Method={request.method} Client={request.client.host if request.client else 'unknown'}"
            )
            error_response = AuthErrorMessages.get_response(AuthErrorType.NO_TOKEN)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_response
            )
        
        # 3. 解析 JWT Token
        payload = await self._extract_jwt_payload(request)
        
        # 4. 检查 Token 是否过期
        if payload and payload.get("__token_expired__"):
            user_id_short = payload.get("sub", "unknown")[:8] if payload else "unknown"
            logger.warning(
                f"[AUTH] [{AuthErrorType.TOKEN_EXPIRED.value}] User={user_id_short} "
                f"Path={request.url.path} Method={request.method}"
            )
            error_response = AuthErrorMessages.get_response(AuthErrorType.TOKEN_EXPIRED)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_response
            )
        
        # 5. 检查 Token 是否无效
        if payload and payload.get("__token_invalid__"):
            logger.warning(
                f"[AUTH] [{AuthErrorType.TOKEN_INVALID.value}] Path={request.url.path} "
                f"Method={request.method} Client={request.client.host if request.client else 'unknown'}"
            )
            error_response = AuthErrorMessages.get_response(AuthErrorType.TOKEN_INVALID)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_response
            )
        
        user_id = payload.get("sub") if payload else None
        
        # 6. 从 JWT 或缓存中获取 tenant_id
        tenant_id = None
        if payload:
            # 优先级1：JWT Token 中直接获取
            tenant_id = payload.get("tenant_id")
            if not tenant_id and user_id:
                # 优先级2：从缓存获取
                tenant_id = tenant_cache.get(user_id)
                if not tenant_id:
                    # 优先级3：从数据库查询
                    tenant_id = await self.get_user_tenant_id(user_id)
                    if tenant_id:
                        # 缓存结果
                        tenant_cache.set(user_id, tenant_id)
        
        # 7. 如果 tenant_id 仍然不存在，返回 401（而非 403）
        # 这样前端会知道需要重新登录
        if not tenant_id:
            user_id_short = user_id[:8] if user_id else "unknown"
            logger.warning(
                f"[AUTH] [{AuthErrorType.TENANT_MISSING.value}] User={user_id_short} "
                f"Path={request.url.path} Method={request.method}"
            )
            error_response = AuthErrorMessages.get_response(AuthErrorType.TENANT_MISSING)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,  # ⬅️ 改为 401，前端会重新登录
                content=error_response
            )
        
        # 设置上下文变量
        tenant_token = tenant_context.set(tenant_id)
        user_token = user_context.set(user_id) if user_id else None
        
        try:
            request.state.tenant_id = tenant_id
            request.state.user_id = user_id
            request.state.request_id = str(uuid.uuid4())
            
            # 只在慢路径打印
            if "/tax-reports" in request.url.path:
                print(f"🏠 [{user_id[:8]}] {request.method} {request.url.path}")
            
            response = await call_next(request)
            
            return response
            
        except (ValueError, KeyError) as e:
            try:
                logger.error(f"Request data error: {safe_error_str(e)}, tenant: {tenant_id}")
            except Exception:
                logger.error(f"Request data error: <failed to format error message>, tenant: {tenant_id}")
            try:
                safe_detail = safe_error_str(e)
            except Exception:
                safe_detail = "数据解析错误"
            raise HTTPException(status_code=400, detail=safe_detail)
        except (OSError, IOError) as e:
            try:
                logger.error(f"Request IO error: {safe_error_str(e)}, tenant: {tenant_id}")
            except Exception:
                logger.error(f"Request IO error: <failed to format error message>, tenant: {tenant_id}")
            try:
                safe_detail = safe_error_str(e)
            except Exception:
                safe_detail = "IO错误"
            raise HTTPException(status_code=500, detail=safe_detail)
        except Exception as e:
            try:
                logger.error(f"Request failed: {safe_error_str(e)}, tenant: {tenant_id}")
            except Exception:
                logger.error(f"Request failed: <failed to format error message>, tenant: {tenant_id}")
            raise
        finally:
            tenant_context.reset(tenant_token)
            if user_token:
                user_context.reset(user_token)
    
    async def extract_tenant_id(self, request: Request) -> str:
        """
        从请求中提取 tenant_id
        
        优先级：
        1. Header: X-Tenant-ID（用于测试和管理员操作）
        2. JWT Token 中的 tenant_id
        3. 用户的默认 tenant_id（从数据库查询）
        """
        
        # 1. 尝试从 Header 提取
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            logger.debug(f"Extract tenant_id from Header: {tenant_id}")
            return tenant_id
        
        # 2. 尝试从 JWT Token 提取（只解析一次）
        payload = await self._extract_jwt_payload(request)
        if payload:
            user_id = payload.get("sub")
            
            # 从 JWT 中直接获取 tenant_id（如果有）
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                logger.debug(f"Extract tenant_id from JWT: {tenant_id}")
                return tenant_id
            
            # 3. 从数据库查询用户的 tenant_id
            if user_id:
                tenant_id = await self.get_user_tenant_id(user_id)
                if tenant_id:
                    logger.debug(f"Query tenant_id from database: {tenant_id}")
                    return tenant_id
                else:
                    logger.warning(f"Database returned empty tenant_id for user_id: {user_id}")
        
        logger.warning(f"No Authorization header found or invalid format")
        return None
    
    def _extract_token(self, request: Request) -> str:
        """
        提取 Token（不解析）
        
        用于判断请求是否包含 Token
        
        支持：
        1. Authorization Header（Bearer Token）
        2. URL Query 参数（token，用于 SSE 连接）
        """
        # 优先从 Authorization Header 获取 Token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ")[1]
        
        # 备用方案：从 URL query 参数获取 token（SSE 连接场景）
        return request.query_params.get("token")
    
    async def _extract_jwt_payload(self, request: Request) -> dict:
        """提取 JWT Payload（只解析一次）
        
        支持从 Authorization Header 或 URL Query 参数获取 token
        （URL Query 参数主要用于 SSE 连接，因为 EventSource 无法设置自定义 headers）
        """
        token = None
        
        # 优先从 Authorization Header 获取 Token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # 备用方案：从 URL query 参数获取 token（SSE 连接场景）
            token = request.query_params.get("token")
        
        if not token:
            return None
        
        try:
            payload = decode_access_token(token)
            return payload
        except TokenExpiredException:
            return {"__token_expired__": True}
        except TokenInvalidException as e:
            logger.warning(f"JWT Token invalid: {e.message}")
            return {"__token_invalid__": True}
        except (ValueError, KeyError) as e:
            try:
                logger.error(f"JWT Token data error: {safe_error_str(e)}")
            except Exception:
                logger.error("JWT Token data error: <failed to format error message>")
        except (OSError, IOError) as e:
            try:
                logger.error(f"JWT Token IO error: {safe_error_str(e)}")
            except Exception:
                logger.error("JWT Token IO error: <failed to format error message>")
        except Exception as e:
            try:
                logger.error(f"JWT Token parsing failed: {safe_error_str(e)}")
            except Exception:
                logger.error("JWT Token parsing failed: <failed to format error message>")
        return None
    
    async def extract_user_id(self, request: Request) -> str:
        """从请求中提取 user_id（复用 JWT 解析结果）"""
        payload = await self._extract_jwt_payload(request)
        if payload:
            return payload.get("sub")
        return None


    async def get_user_tenant_id(self, user_id: str) -> str:
        """从数据库查询用户的 tenant_id"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    text("SELECT tenant_id FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                )
                row = result.fetchone()
                return row[0] if row else None
            except (ValueError, KeyError) as e:
                try:
                    logger.error(f"Query user tenant_id data error: {safe_error_str(e)}")
                except Exception:
                    logger.error("Query user tenant_id data error: <failed to format error message>")
                return None
            except (OSError, IOError) as e:
                try:
                    logger.error(f"Query user tenant_id IO error: {safe_error_str(e)}")
                except Exception:
                    logger.error("Query user tenant_id IO error: <failed to format error message>")
                return None
            except Exception as e:
                try:
                    logger.error(f"Query user tenant_id failed: {safe_error_str(e)}")
                except Exception:
                    logger.error("Query user tenant_id failed: <failed to format error message>")
                return None


def get_current_tenant_id(request: Request = None) -> str:
    """
    获取当前租户 ID
    
    优先级：
    1. 从 ContextVar 获取（推荐）
    2. 从 Request 状态获取（兼容）
    """
    # 优先从 ContextVar 获取
    tenant_id = tenant_context.get(None)
    if tenant_id:
        return tenant_id
    
    # 兼容模式：从 Request 状态获取
    if request:
        return getattr(request.state, "tenant_id", None)
    
    return None


def get_current_user_id(request: Request = None) -> str:
    """
    获取当前用户 ID
    
    优先级：
    1. 从 ContextVar 获取（推荐）
    2. 从 Request 状态获取（兼容）
    """
    # 优先从 ContextVar 获取
    user_id = user_context.get(None)
    if user_id:
        return user_id
    
    # 兼容模式：从 Request 状态获取
    if request:
        return getattr(request.state, "user_id", None)
    
    return None


async def set_tenant_context_for_db(session, tenant_id: str, user_id: str = None):
    """
    为数据库会话设置租户上下文
    
    用法：
        async with AsyncSessionLocal() as session:
            await set_tenant_context_for_db(session, tenant_id, user_id)
            # 执行数据库操作
    """
    try:
        # 🔥 修复：SET LOCAL 不支持参数化查询，必须使用字符串格式化
        # 注意：这里需要对 tenant_id 进行转义以防止 SQL 注入
        safe_tenant_id = tenant_id.replace("'", "''")  # 转义单引号
        await session.execute(
            text(f"SET LOCAL app.current_tenant_id = '{safe_tenant_id}'")
        )
        
        # 设置用户上下文（可选）
        if user_id:
            safe_user_id = user_id.replace("'", "''")  # 转义单引号
            await session.execute(
                text(f"SET LOCAL app.current_user_id = '{safe_user_id}'")
            )
        
        logger.debug(f"Database tenant context set: tenant={tenant_id}, user={user_id}")
        
    except (ValueError, KeyError) as e:
        try:
            logger.warning(f"Set database tenant context data error: {safe_error_str(e)}")
        except Exception:
            logger.warning("Set database tenant context data error: <failed to format error message>")
    except (OSError, IOError) as e:
        try:
            logger.warning(f"Set database tenant context IO error: {safe_error_str(e)}")
        except Exception:
            logger.warning("Set database tenant context IO error: <failed to format error message>")
    except Exception as e:
        try:
            logger.warning(f"Set database tenant context failed: {safe_error_str(e)}")
        except Exception:
            logger.warning("Set database tenant context failed: <failed to format error message>")
        # 不抛出异常，让请求继续处理

# 为了向后兼容，添加别名
TenantMiddleware = TenantContextMiddleware