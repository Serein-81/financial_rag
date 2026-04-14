"""
认证错误类型定义

定义标准化的认证错误类型，用于中间件和 API 的统一错误响应
"""

from enum import Enum


class AuthErrorType(str, Enum):
    """
    认证错误类型枚举
    
    用途：
    1. 统一错误码体系
    2. 前端智能错误处理
    3. 日志分类和分析
    """
    
    NO_TOKEN = "no_token"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    TENANT_MISSING = "tenant_missing"
    TENANT_INACTIVE = "tenant_inactive"
    USER_NOT_FOUND = "user_not_found"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN_ERROR = "unknown_error"


class AuthErrorMessages:
    """
    认证错误消息映射
    
    提供中英文错误消息，便于前端显示和国际化
    """
    
    MESSAGES = {
        AuthErrorType.NO_TOKEN: {
            "detail": "Authentication required",
            "message": "请先登录",
            "status_code": 401
        },
        AuthErrorType.TOKEN_EXPIRED: {
            "detail": "Login expired, please login again",
            "message": "登录已过期，请重新登录",
            "status_code": 401
        },
        AuthErrorType.TOKEN_INVALID: {
            "detail": "Invalid login session",
            "message": "登录会话无效，请重新登录",
            "status_code": 401
        },
        AuthErrorType.TENANT_MISSING: {
            "detail": "Missing tenant context",
            "message": "会话无效，请重新登录",
            "status_code": 401
        },
        AuthErrorType.TENANT_INACTIVE: {
            "detail": "Tenant account is inactive",
            "message": "租户账户已被禁用",
            "status_code": 403
        },
        AuthErrorType.USER_NOT_FOUND: {
            "detail": "User not found",
            "message": "用户不存在",
            "status_code": 404
        },
        AuthErrorType.PERMISSION_DENIED: {
            "detail": "Permission denied",
            "message": "权限不足，无法访问该资源",
            "status_code": 403
        },
        AuthErrorType.UNKNOWN_ERROR: {
            "detail": "Authentication failed",
            "message": "认证失败，请稍后重试",
            "status_code": 401
        }
    }
    
    @classmethod
    def get_response(cls, error_type: AuthErrorType) -> dict:
        """
        获取标准化的错误响应
        
        Args:
            error_type: 错误类型
            
        Returns:
            dict: 包含 error_type, detail, message 的字典
        """
        msg_config = cls.MESSAGES.get(error_type, cls.MESSAGES[AuthErrorType.UNKNOWN_ERROR])
        return {
            "error_type": error_type.value,
            "detail": msg_config["detail"],
            "message": msg_config["message"]
        }
    
    @classmethod
    def get_status_code(cls, error_type: AuthErrorType) -> int:
        """
        获取错误对应的 HTTP 状态码
        
        Args:
            error_type: 错误类型
            
        Returns:
            int: HTTP 状态码
        """
        msg_config = cls.MESSAGES.get(error_type, cls.MESSAGES[AuthErrorType.UNKNOWN_ERROR])
        return msg_config["status_code"]
