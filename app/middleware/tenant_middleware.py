"""
租户上下文中间件
负责从请求中提取 tenant_id 并设置到数据库会话上下文中
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.security import decode_access_token
from contextvars import ContextVar
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)

# 使用 ContextVar 来存储租户上下文，解决异步并发问题
tenant_context: ContextVar[str] = ContextVar('tenant_context', default=None)
user_context: ContextVar[str] = ContextVar('user_context', default=None)


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
        "/api/v1/auth/send-code",
        "/api/v1/auth/verify-code",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/health",
    ]
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""

        if request.url.path in ["/", "/docs", "/redoc", "/openapi.json", "/health"]:
            return await call_next(request)

        # 检查是否是排除路径
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        # 提取 tenant_id 和 user_id
        tenant_id = await self.extract_tenant_id(request)
        user_id = await self.extract_user_id(request)
        
        if not tenant_id:
            # 如果无法提取 tenant_id，拒绝访问
            logger.warning(f"无法提取 tenant_id: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing tenant context"
            )
        
        # 设置上下文变量
        tenant_token = tenant_context.set(tenant_id)
        user_token = user_context.set(user_id) if user_id else None
        
        try:
            # 将上下文信息附加到请求状态
            request.state.tenant_id = tenant_id
            request.state.user_id = user_id
            request.state.request_id = str(uuid.uuid4())  # 添加请求ID用于追踪
            
            logger.debug(f"设置租户上下文: {tenant_id}, 用户: {user_id}, 请求: {request.state.request_id}")
            
            # 继续处理请求
            response = await call_next(request)
            
            return response
            
        except Exception as e:
            logger.error(f"处理请求失败: {e}, 租户: {tenant_id}")
            raise
        finally:
            # 清理上下文变量
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
            logger.debug(f"从 Header 提取 tenant_id: {tenant_id}")
            return tenant_id
        
        # 2. 尝试从 JWT Token 提取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = decode_access_token(token)
                if payload:  # 检查 payload 是否为 None
                    user_id = payload.get("sub")
                    
                    # 从 JWT 中直接获取 tenant_id（如果有）
                    tenant_id = payload.get("tenant_id")
                    if tenant_id:
                        logger.debug(f"从 JWT 提取 tenant_id: {tenant_id}")
                        return tenant_id
                    
                    # 3. 从数据库查询用户的 tenant_id
                    if user_id:
                        tenant_id = await self.get_user_tenant_id(user_id)
                        if tenant_id:
                            logger.debug(f"从数据库查询 tenant_id: {tenant_id}")
                            return tenant_id
                
            except Exception as e:
                logger.error(f"解析 JWT Token 失败: {e}")
        
        return None
    
    async def extract_user_id(self, request: Request) -> str:
        """从请求中提取 user_id"""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = decode_access_token(token)
                if payload:
                    return payload.get("sub")
            except Exception as e:
                logger.error(f"提取用户 ID 失败: {e}")
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
            except Exception as e:
                logger.error(f"查询用户 tenant_id 失败: {e}")
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
        # 设置租户上下文
        await session.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        )
        
        # 设置用户上下文（可选）
        if user_id:
            await session.execute(
                text("SET LOCAL app.current_user_id = :user_id"),
                {"user_id": user_id}
            )
        
        logger.debug(f"已设置数据库租户上下文: {tenant_id}, 用户: {user_id}")
        
    except Exception as e:
        logger.error(f"设置数据库租户上下文失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set tenant context"
        )

# 为了向后兼容，添加别名
TenantMiddleware = TenantContextMiddleware