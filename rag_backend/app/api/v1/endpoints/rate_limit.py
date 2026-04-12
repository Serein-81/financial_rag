"""
限流管理 API

提供限流状态查询、手动重置等管理功能
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.api import deps

router = APIRouter(prefix="/rate-limit", tags=["Rate Limit"])


@router.get("/stats")
async def get_rate_limit_stats(
    current_user = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    获取限流统计信息
    
    返回：
    - total_requests: 总请求数
    - limited_requests: 被限流的请求数
    - excluded_requests: 排除限流的请求数
    - limit_rate: 限流率
    - strategy: 当前使用的限流策略
    - enabled: 限流是否启用
    """
    from app.main import app
    
    rate_limit_middleware = None
    for middleware in app.user_middleware:
        if hasattr(middleware, "cls") and middleware.cls == RateLimitMiddleware:
            for handler in app.middleware_stack._middleware:
                if isinstance(handler, RateLimitMiddleware):
                    rate_limit_middleware = handler
                    break
            break
    
    if rate_limit_middleware:
        return rate_limit_middleware.get_stats()
    
    return {
        "error": "Rate limit middleware not found",
        "enabled": False,
    }


@router.post("/reset/{key}")
async def reset_rate_limit_key(
    key: str,
    current_user = Depends(deps.get_current_user)
) -> Dict[str, str]:
    """
    重置指定键的限流状态
    
    Args:
        key: 限流键 (格式: type:value, 例如: user:xxx, tenant:xxx, ip:xxx)
    
    Returns:
        操作结果
    """
    from app.main import app
    
    rate_limit_middleware = None
    for middleware in app.user_middleware:
        if hasattr(middleware, "cls") and middleware.cls == RateLimitMiddleware:
            for handler in app.middleware_stack._middleware:
                if isinstance(handler, RateLimitMiddleware):
                    rate_limit_middleware = handler
                    break
            break
    
    if rate_limit_middleware:
        await rate_limit_middleware.reset_key(key)
        return {
            "status": "success",
            "message": f"限流键 {key} 已重置",
            "key": key,
        }
    
    return {
        "status": "error",
        "message": "Rate limit middleware not found",
    }


@router.post("/cleanup")
async def cleanup_expired_limits(
    current_user = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    清理过期的限流状态
    
    Returns:
        清理结果统计
    """
    from app.main import app
    
    rate_limit_middleware = None
    for middleware in app.user_middleware:
        if hasattr(middleware, "cls") and middleware.cls == RateLimitMiddleware:
            for handler in app.middleware_stack._middleware:
                if isinstance(handler, RateLimitMiddleware):
                    rate_limit_middleware = handler
                    break
            break
    
    if rate_limit_middleware:
        await rate_limit_middleware.cleanup_expired()
        return {
            "status": "success",
            "message": "过期限流状态已清理",
        }
    
    return {
        "status": "error",
        "message": "Rate limit middleware not found",
    }
