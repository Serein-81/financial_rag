"""
API 依赖注入
提供通用的依赖项，如数据库会话、当前用户、租户上下文等
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.middleware.tenant_middleware import (
    get_current_tenant_id, 
    get_current_user_id,
    set_tenant_context_for_db
)
from app.services.tenant_security_service import tenant_security
import logging

logger = logging.getLogger(__name__)


async def get_db() -> AsyncSession:
    """
    获取数据库会话
    
    注意：这个会话已经自动设置了租户上下文
    """
    async with AsyncSessionLocal() as session:
        try:
            # 获取当前租户和用户上下文
            tenant_id = get_current_tenant_id()
            user_id = get_current_user_id()
            
            # 为数据库会话设置租户上下文（如果有租户ID）
            if tenant_id:
                try:
                    await set_tenant_context_for_db(session, tenant_id, user_id)
                except Exception as e:
                    logger.warning(f"设置租户上下文失败: {e}")
                    # 🔥 修复：回滚事务，避免进入失败状态
                    await session.rollback()
                    # 重新开始事务
                    await session.begin()
            
            yield session
        except Exception as e:
            logger.error(f"数据库会话错误: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user_from_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    从 JWT Token 获取当前用户
    
    Args:
        request: FastAPI 请求对象
        db: 数据库会话
    
    Returns:
        User: 当前用户对象
    
    Raises:
        HTTPException: 认证失败
    """
    # 从请求头获取 Token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        # 解码 Token
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 从数据库查询用户（自动应用租户隔离）
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取当前用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_tenant() -> str:
    """
    获取当前租户ID
    
    Returns:
        str: 租户ID
    
    Raises:
        HTTPException: 租户上下文缺失
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing tenant context"
        )
    return tenant_id


def get_current_user_id_from_context() -> Optional[str]:
    """
    从上下文获取当前用户ID
    
    Returns:
        Optional[str]: 用户ID，如果未认证则返回 None
    """
    return get_current_user_id()


async def validate_tenant_access(
    target_tenant_id: str,
    operation: str = "read",
    resource_type: str = "data"
) -> bool:
    """
    验证租户访问权限的依赖项
    
    Args:
        target_tenant_id: 目标租户ID
        operation: 操作类型
        resource_type: 资源类型
    
    Returns:
        bool: 验证通过
    
    Raises:
        HTTPException: 权限验证失败
    """
    try:
        return await tenant_security.validate_tenant_access(
            target_tenant_id=target_tenant_id,
            operation=operation,
            resource_type=resource_type
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


class TenantAccessValidator:
    """租户访问验证器类，用于创建参数化的依赖项"""
    
    def __init__(self, operation: str = "read", resource_type: str = "data"):
        self.operation = operation
        self.resource_type = resource_type
    
    async def __call__(self, tenant_id: str = Depends(get_current_tenant)) -> str:
        """
        验证租户访问权限
        
        Args:
            tenant_id: 当前租户ID
        
        Returns:
            str: 验证通过的租户ID
        """
        await validate_tenant_access(
            target_tenant_id=tenant_id,
            operation=self.operation,
            resource_type=self.resource_type
        )
        return tenant_id


# 预定义的常用验证器
validate_read_access = TenantAccessValidator("read", "data")
validate_write_access = TenantAccessValidator("write", "data")
validate_delete_access = TenantAccessValidator("delete", "data")
validate_file_access = TenantAccessValidator("read", "file")
validate_api_access = TenantAccessValidator("read", "api")


async def get_db_with_tenant_context(
    tenant_id: str = Depends(get_current_tenant)
) -> AsyncSession:
    """
    获取已设置租户上下文的数据库会话
    
    Args:
        tenant_id: 租户ID
    
    Yields:
        AsyncSession: 数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            # 设置租户上下文
            user_id = get_current_user_id()
            await set_tenant_context_for_db(session, tenant_id, user_id)
            
            yield session
        except Exception as e:
            logger.error(f"数据库会话错误: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


def require_admin_user(
    current_user: User = Depends(get_current_user_from_token)
) -> User:
    """
    要求管理员用户权限
    
    Args:
        current_user: 当前用户
    
    Returns:
        User: 管理员用户
    
    Raises:
        HTTPException: 权限不足
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def require_active_user(
    current_user: User = Depends(get_current_user_from_token)
) -> User:
    """
    要求活跃用户
    
    Args:
        current_user: 当前用户
    
    Returns:
        User: 活跃用户
    
    Raises:
        HTTPException: 用户未激活
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    return current_user


# 为了向后兼容，提供别名
get_current_user = get_current_user_from_token


def get_tenant_context() -> dict:
    """
    获取租户上下文信息
    
    Returns:
        dict: 租户上下文字典
    """
    tenant_id = get_current_tenant_id()
    user_id = get_current_user_id()
    
    return {
        "tenant_id": tenant_id,
        "user_id": user_id
    }


def get_tenant_db():
    """
    获取租户数据库会话（别名）
    
    Returns:
        AsyncSession: 数据库会话
    """
    return get_db_with_tenant_context