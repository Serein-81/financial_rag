# app/middleware/logging_middleware.py

"""
日志中间件

自动记录API请求、响应和错误信息
"""

import time
import uuid
import json
import traceback
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.services.log_service import log_service
from app.models.system_log import LogLevel, LogCategory
import asyncio


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    日志记录中间件
    
    自动记录所有API请求的详细信息，包括：
    - 请求信息（URL、方法、参数、头部）
    - 响应信息（状态码、响应时间）
    - 错误信息（异常类型、堆栈跟踪）
    - 性能指标（执行时间、内存使用）
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.excluded_paths = {
            "/docs", "/redoc", "/openapi.json", 
            "/health", "/metrics", "/favicon.ico"
        }
        self.sensitive_headers = {
            "authorization", "cookie", "x-api-key", 
            "x-auth-token", "x-csrf-token"
        }
        self.sensitive_params = {
            "password", "token", "secret", "key", 
            "auth", "credential", "api_key"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 记录开始时间
        start_time = time.time()
        
        # 获取用户名用于日志
        user_id = getattr(request.state, "user_id", None)
        log_prefix = f"{user_id[:8] if user_id else 'anonymous'}"
        
        # 只在慢请求或错误时打印日志
        skip_full_logging = any(request.url.path.startswith(path) for path in self.excluded_paths)
        
        # 提取请求信息（只有不跳过时才提取）
        if not skip_full_logging:
            request_info = await self._extract_request_info(request)
            asyncio.create_task(
                self._log_request_start(request_id, request_info)
            )
        
        try:
            response = await call_next(request)
            execution_time = int((time.time() - start_time) * 1000)
            
            # 🔧 调试：打印所有税务相关请求
            if '/tax' in request.url.path.lower() or '/upload' in request.url.path.lower():
                print(f"📥 [{log_prefix}] {request.method} {request.url.path} - {response.status_code} ({execution_time}ms)")
            
            # 原有的慢请求或错误日志
            if execution_time > 1000 or response.status_code >= 400:
                print(f"🔍 [{log_prefix}] {request.method} {request.url.path} - {response.status_code} ({execution_time}ms)")
            
            if not skip_full_logging:
                asyncio.create_task(
                    self._log_request_success(
                        request_id, request_info, response, execution_time
                    )
                )
            
            return response
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            print(f"❌ [{log_prefix}] {request.method} {request.url.path} - Error: {str(e)} ({execution_time}ms)")
            
            if not skip_full_logging:
                asyncio.create_task(
                    self._log_request_error(
                        request_id, request_info, e, execution_time
                    )
                )
            
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "内部服务器错误",
                    "request_id": request_id,
                    "error": str(e) if hasattr(e, '__str__') else "未知错误"
                }
            )
    
    async def _extract_request_info(self, request: Request) -> dict:
        """提取请求信息"""
        # 获取用户信息
        user_id = None
        user_email = None
        if hasattr(request.state, 'user'):
            user = request.state.user
            user_id = str(user.id) if user else None
            user_email = user.email if user else None
        
        # 获取客户端IP
        ip_address = self._get_client_ip(request)
        
        # 获取用户代理
        user_agent = request.headers.get("user-agent", "")
        
        # 获取会话ID
        session_id = request.cookies.get("session_id") or request.headers.get("x-session-id")
        
        # 过滤敏感头部信息
        safe_headers = {}
        for key, value in request.headers.items():
            if key.lower() not in self.sensitive_headers:
                safe_headers[key] = value
            else:
                safe_headers[key] = "***FILTERED***"
        
        # 获取查询参数（过滤敏感信息）
        safe_params = {}
        for key, value in request.query_params.items():
            if key.lower() not in self.sensitive_params:
                safe_params[key] = value
            else:
                safe_params[key] = "***FILTERED***"
        
        return {
            "user_id": user_id,
            "user_email": user_email,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "headers": safe_headers,
            "query_params": safe_params,
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP地址"""
        # 尝试从各种头部获取真实IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # 回退到客户端IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _log_request_start(self, request_id: str, request_info: dict):
        """记录请求开始日志"""
        try:
            message = f"API请求开始: {request_info['method']} {request_info['path']}"
            
            await log_service.create_system_log(
                level=LogLevel.INFO,
                category=LogCategory.API_REQUEST,
                action="api_request_start",
                message=message,
                user_id=request_info["user_id"],
                session_id=request_info["session_id"],
                request_id=request_id,
                ip_address=request_info["ip_address"],
                user_agent=request_info["user_agent"],
                endpoint=request_info["path"],
                method=request_info["method"],
                extra_data={
                    "url": request_info["url"],
                    "headers": request_info["headers"],
                    "query_params": request_info["query_params"],
                }
            )
        except Exception as e:
            # 日志记录失败不应该影响正常请求
            print(f"记录请求开始日志失败: {e}")
    
    async def _log_request_success(
        self, 
        request_id: str, 
        request_info: dict, 
        response: Response, 
        execution_time: int
    ):
        """记录成功响应日志"""
        try:
            message = f"API请求成功: {request_info['method']} {request_info['path']} - {response.status_code}"
            
            await log_service.create_system_log(
                level=LogLevel.INFO,
                category=LogCategory.API_REQUEST,
                action="api_request_success",
                message=message,
                user_id=request_info["user_id"],
                session_id=request_info["session_id"],
                request_id=request_id,
                ip_address=request_info["ip_address"],
                user_agent=request_info["user_agent"],
                endpoint=request_info["path"],
                method=request_info["method"],
                status_code=response.status_code,
                execution_time=execution_time,
                extra_data={
                    "response_headers": dict(response.headers),
                }
            )
        except Exception as e:
            print(f"记录成功响应日志失败: {e}")
    
    async def _log_request_error(
        self, 
        request_id: str, 
        request_info: dict, 
        error: Exception, 
        execution_time: int
    ):
        """记录错误响应日志"""
        try:
            message = f"API请求失败: {request_info['method']} {request_info['path']} - {str(error)}"
            
            await log_service.create_system_log(
                level=LogLevel.ERROR,
                category=LogCategory.API_REQUEST,
                action="api_request_error",
                message=message,
                user_id=request_info["user_id"],
                session_id=request_info["session_id"],
                request_id=request_id,
                ip_address=request_info["ip_address"],
                user_agent=request_info["user_agent"],
                endpoint=request_info["path"],
                method=request_info["method"],
                status_code=500,
                execution_time=execution_time,
                error_type=type(error).__name__,
                error_message=str(error),
                stack_trace=traceback.format_exc(),
                extra_data={
                    "error_details": {
                        "type": type(error).__name__,
                        "message": str(error),
                        "args": error.args if hasattr(error, 'args') else None,
                    }
                }
            )
        except Exception as e:
            print(f"记录错误响应日志失败: {e}")