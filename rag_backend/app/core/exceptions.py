"""
统一异常处理模块

提供所有应用级别的自定义异常类，确保错误处理的统一性和可追踪性。
按功能模块组织异常类，便于快速定位问题。

异常层次结构：
├── BaseAppException (基础异常)
│   ├── ServiceException (服务层异常)
│   │   ├── LLMServiceException (LLM服务异常)
│   │   ├── DatabaseException (数据库异常)
│   │   ├── CacheException (缓存异常)
│   │   └── ExternalAPIException (外部API异常)
│   ├── AuthenticationException (认证异常)
│   │   ├── TokenExpiredException
│   │   ├── TokenInvalidException
│   │   ├── TokenRevokedException
│   │   └── UnauthorizedException
│   ├── ValidationException (验证异常)
│   ├── ResourceException (资源异常)
│   │   ├── ResourceNotFoundException
│   │   └── ResourceConflictException
│   └── BusinessException (业务异常)
"""

import logging
import traceback
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class BaseAppException(Exception):
    """
    应用基础异常类
    
    所有自定义异常的基类，提供统一的消息格式和错误追踪功能。
    
    Attributes:
        message: 错误消息
        code: 错误代码，用于前端识别错误类型
        details: 错误详情，包含原始异常信息
        log_level: 日志级别，默认 ERROR
    """
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        log_level: str = "ERROR"
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.log_level = log_level
        super().__init__(self.message)
        
        self._log_exception()
    
    def _log_exception(self):
        """记录异常日志"""
        log_func = getattr(logger, self.log_level.lower(), logger.error)
        log_func(
            f"[{self.code}] {self.message}",
            extra={
                "error_code": self.code,
                "error_details": self.details,
                "error_type": self.__class__.__name__
            },
            exc_info=True
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


class ServiceException(BaseAppException):
    """服务层基础异常"""
    pass


class LLMServiceException(ServiceException):
    """
    LLM服务异常
    
    当与大语言模型交互失败时抛出。
    
    常见场景：
    - API调用超时
    - API Key无效或过期
    - 模型服务不可用
    - 请求被限流
    - 响应格式错误
    """
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None
    ):
        details = {
            "provider": provider,
            "model": model,
            "status_code": status_code,
            "response_preview": response_text[:200] if response_text else None
        }
        super().__init__(
            message=message,
            code="LLM_SERVICE_ERROR",
            details=details,
            log_level="ERROR"
        )


class DatabaseException(ServiceException):
    """
    数据库操作异常
    
    当数据库操作失败时抛出。
    
    常见场景：
    - 连接失败
    - 查询超时
    - 约束违反
    - 事务失败
    - 连接池耗尽
    """
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        table_name: Optional[str] = None,
        original_error: Optional[str] = None
    ):
        details = {
            "operation": operation,
            "table_name": table_name,
            "original_error": str(original_error) if original_error else None
        }
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
            log_level="ERROR"
        )


class CacheException(ServiceException):
    """
    缓存服务异常
    
    当Redis等缓存服务操作失败时抛出。
    注意：缓存异常通常是可选的，不会阻断主流程。
    """
    
    def __init__(
        self,
        message: str,
        cache_type: str = "redis",
        key: Optional[str] = None,
        is_critical: bool = False
    ):
        details = {
            "cache_type": cache_type,
            "key": key,
            "is_critical": is_critical
        }
        super().__init__(
            message=message,
            code="CACHE_ERROR",
            details=details,
            log_level="WARNING" if not is_critical else "ERROR"
        )


class ExternalAPIException(ServiceException):
    """
    外部API调用异常
    
    当调用第三方API失败时抛出。
    
    常见场景：
    - HTTP请求失败
    - API限流
    - 认证失败
    - 返回错误响应
    """
    
    def __init__(
        self,
        message: str,
        api_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None
    ):
        details = {
            "api_name": api_name,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_body": response_body[:500] if response_body else None
        }
        super().__init__(
            message=message,
            code="EXTERNAL_API_ERROR",
            details=details,
            log_level="ERROR"
        )


class AuthenticationException(BaseAppException):
    """认证相关异常基类"""
    pass


class TokenExpiredException(AuthenticationException):
    """Token已过期"""
    
    def __init__(self, message: str = "Token已过期，请重新登录", code: str = "TOKEN_EXPIRED"):
        super().__init__(
            message=message,
            code=code,
            details={},
            log_level="INFO"
        )


class TokenInvalidException(AuthenticationException):
    """Token无效"""
    
    def __init__(
        self,
        message: str = "Token无效",
        code: str = "TOKEN_INVALID",
        details: Optional[Dict] = None,
        log_level: str = "WARNING"
    ):
        super().__init__(
            message=message,
            code=code,
            details=details or {},
            log_level=log_level
        )


class TokenRevokedException(AuthenticationException):
    """Token已被撤销"""
    
    def __init__(
        self,
        message: str = "Token已被撤销，请重新登录",
        reason: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="TOKEN_REVOKED",
            details={"reason": reason} if reason else {},
            log_level="INFO"
        )


class UnauthorizedException(AuthenticationException):
    """未授权访问"""
    
    def __init__(self, message: str = "未授权访问"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            details={},
            log_level="WARNING"
        )


class ValidationException(BaseAppException):
    """
    数据验证异常
    
    当输入数据不符合预期格式或约束时抛出。
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        field_value: Any = None,
        constraint: Optional[str] = None
    ):
        details = {
            "field": field,
            "field_value": str(field_value)[:100] if field_value else None,
            "constraint": constraint
        }
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            log_level="WARNING"
        )


class ResourceException(BaseAppException):
    """资源相关异常基类"""
    pass


class ResourceNotFoundException(ResourceException):
    """资源不存在"""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id
        }
        super().__init__(
            message=message or f"{resource_type}不存在",
            code="RESOURCE_NOT_FOUND",
            details=details,
            log_level="INFO"
        )


class ResourceConflictException(ResourceException):
    """资源冲突"""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        existing_resource_id: Optional[str] = None
    ):
        details = {
            "resource_type": resource_type,
            "existing_resource_id": existing_resource_id
        }
        super().__init__(
            message=message,
            code="RESOURCE_CONFLICT",
            details=details,
            log_level="WARNING"
        )


class BusinessException(BaseAppException):
    """
    业务逻辑异常
    
    当业务规则被违反时抛出。
    """
    
    def __init__(
        self,
        message: str,
        business_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        details = {
            "business_code": business_code,
            "context": context or {}
        }
        super().__init__(
            message=message,
            code="BUSINESS_ERROR",
            details=details,
            log_level="WARNING"
        )


def exception_to_http_exception(exc: BaseAppException) -> HTTPException:
    """
    将应用异常转换为FastAPI HTTPException
    
    Args:
        exc: 应用异常实例
        
    Returns:
        FastAPI HTTPException
    """
    status_code_map = {
        "TOKEN_EXPIRED": status.HTTP_401_UNAUTHORIZED,
        "TOKEN_INVALID": status.HTTP_401_UNAUTHORIZED,
        "TOKEN_REVOKED": status.HTTP_401_UNAUTHORIZED,
        "UNAUTHORIZED": status.HTTP_401_UNAUTHORIZED,
        "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "RESOURCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "RESOURCE_CONFLICT": status.HTTP_409_CONFLICT,
        "LLM_SERVICE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "DATABASE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "CACHE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "EXTERNAL_API_ERROR": status.HTTP_502_BAD_GATEWAY,
    }
    
    status_code = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return HTTPException(
        status_code=status_code,
        detail=exc.to_dict()
    )


def handle_uncaught_exception(exc: Exception) -> BaseAppException:
    """
    处理未捕获的异常，将其转换为应用异常
    
    Args:
        exc: 原始异常
        
    Returns:
        应用异常实例
    """
    if isinstance(exc, BaseAppException):
        return exc
    
    logger.exception(f"未捕获的异常: {exc}")
    
    return BaseAppException(
        message="系统内部错误，请稍后重试",
        code="INTERNAL_SERVER_ERROR",
        details={
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc()
        },
        log_level="CRITICAL"
    )
