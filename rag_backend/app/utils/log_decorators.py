# app/utils/log_decorators.py

"""
日志装饰器

提供自动日志记录功能，支持函数调用、性能监控、错误追踪等
"""

import asyncio
import time
import traceback
import os
import logging
from functools import wraps
from typing import Optional, Dict, Any, Callable

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from app.services.log_service import log_service
from app.models.system_log import LogLevel, LogCategory

logger = logging.getLogger(__name__)


def log_function_call(
    category: LogCategory = LogCategory.SYSTEM_EVENT,
    level: LogLevel = LogLevel.INFO,
    action: Optional[str] = None,
    log_args: bool = False,
    log_result: bool = False,
    log_performance: bool = True,
    sensitive_params: Optional[list] = None
):
    """
    函数调用日志装饰器
    
    Args:
        category: 日志分类
        level: 日志级别
        action: 操作名称（默认使用函数名）
        log_args: 是否记录参数
        log_result: 是否记录返回值
        log_performance: 是否记录性能指标
        sensitive_params: 敏感参数列表（不会被记录）
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = _get_memory_usage()
            
            function_name = action or func.__name__
            module_name = func.__module__
            
            # 准备日志数据
            log_data = {
                "module": module_name,
                "function": func.__name__,
                "action": function_name,
                "category": category,
                "level": level,
            }
            
            # 记录参数（过滤敏感信息）
            if log_args:
                safe_kwargs = _filter_sensitive_data(kwargs, sensitive_params or [])
                log_data["extra_data"] = {
                    "args_count": len(args),
                    "kwargs": safe_kwargs
                }
            
            try:
                # 执行函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 计算性能指标
                execution_time = int((time.time() - start_time) * 1000)  # 毫秒
                memory_usage = _get_memory_usage() - start_memory
                
                # 记录成功日志
                message = f"Function {function_name} executed successfully"
                
                if log_performance:
                    log_data.update({
                        "execution_time": execution_time,
                        "memory_usage": memory_usage,
                    })
                
                if log_result and result is not None:
                    if not log_data.get("extra_data"):
                        log_data["extra_data"] = {}
                    log_data["extra_data"]["result_type"] = type(result).__name__
                    if isinstance(result, (str, int, float, bool)):
                        log_data["extra_data"]["result_value"] = result
                
                # 异步记录日志
                asyncio.create_task(
                    log_service.create_system_log(
                        message=message,
                        **log_data
                    )
                )
                
                return result
                
            except Exception as e:
                # 计算性能指标
                execution_time = int((time.time() - start_time) * 1000)
                memory_usage = _get_memory_usage() - start_memory
                
                # 记录错误日志
                error_message = f"Function {function_name} failed: {str(e)}"
                
                log_data.update({
                    "level": LogLevel.ERROR,
                    "execution_time": execution_time,
                    "memory_usage": memory_usage,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                })
                
                # 异步记录错误日志
                asyncio.create_task(
                    log_service.create_system_log(
                        message=error_message,
                        **log_data
                    )
                )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = _get_memory_usage()
            
            function_name = action or func.__name__
            module_name = func.__module__
            
            # 准备日志数据
            log_data = {
                "module": module_name,
                "function": func.__name__,
                "action": function_name,
                "category": category,
                "level": level,
            }
            
            # 记录参数
            if log_args:
                safe_kwargs = _filter_sensitive_data(kwargs, sensitive_params or [])
                log_data["extra_data"] = {
                    "args_count": len(args),
                    "kwargs": safe_kwargs
                }
            
            try:
                # 执行函数
                result = func(*args, **kwargs)
                
                # 计算性能指标
                execution_time = int((time.time() - start_time) * 1000)
                memory_usage = _get_memory_usage() - start_memory
                
                # 记录成功日志
                message = f"Function {function_name} executed successfully"
                
                if log_performance:
                    log_data.update({
                        "execution_time": execution_time,
                        "memory_usage": memory_usage,
                    })
                
                # 同步记录日志（在后台异步执行）
                asyncio.create_task(
                    log_service.create_system_log(
                        message=message,
                        **log_data
                    )
                )
                
                return result
                
            except Exception as e:
                # 计算性能指标
                execution_time = int((time.time() - start_time) * 1000)
                memory_usage = _get_memory_usage() - start_memory
                
                # 记录错误日志
                error_message = f"Function {function_name} failed: {str(e)}"
                
                log_data.update({
                    "level": LogLevel.ERROR,
                    "execution_time": execution_time,
                    "memory_usage": memory_usage,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                })
                
                # 异步记录错误日志
                asyncio.create_task(
                    log_service.create_system_log(
                        message=error_message,
                        **log_data
                    )
                )
                
                raise
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_user_action(
    action_type: str,
    action_name: Optional[str] = None,
    resource_type: Optional[str] = None,
    description: Optional[str] = None,
    log_data_changes: bool = False,
    level: str = 'INFO'
):
    """
    用户操作日志装饰器

    Args:
        action_type: 操作类型
        action_name: 操作名称
        resource_type: 资源类型
        description: 操作描述
        log_data_changes: 是否记录数据变更
        level: 日志等级 (INFO, WARNING, ERROR, DEBUG)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 尝试从参数中获取用户信息
            user_id = _extract_user_id(args, kwargs)
            
            # 获取请求信息
            request_info = _extract_request_info(args, kwargs)
            
            function_action_name = action_name or func.__name__
            
            try:
                # 记录操作前数据（如果需要）
                before_data = None
                if log_data_changes:
                    before_data = _extract_before_data(args, kwargs)
                
                # 执行函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 如果user_id为空，尝试从返回结果中提取（适用于登录等场景）
                extracted_user_id = None
                if not user_id and result:
                    extracted_user_id = _extract_user_id_from_result(result)
                    if extracted_user_id:
                        user_id = extracted_user_id
                        logger.debug(f"从返回值提取到 user_id: {user_id}")
                
                logger.debug(f"装饰器执行 - action: {action_type}/{function_action_name}, user_id: {user_id}, extracted: {extracted_user_id}")
                
                # 记录操作后数据（如果需要）
                after_data = None
                if log_data_changes:
                    after_data = _extract_after_data(result)
                
                # 提取资源信息
                resource_id, resource_name = _extract_resource_info(args, kwargs, result)
                
                # 记录成功的用户操作
                try:
                    # 直接 await 而非 create_task，确保日志被记录
                    await log_service.create_user_action_log(
                        user_id=user_id,
                        action_type=action_type,
                        action_name=function_action_name,
                        description=description or f"User performed {function_action_name}",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        resource_name=resource_name,
                        success=True,
                        result_message="Operation completed successfully",
                        before_data=before_data,
                        after_data=after_data,
                        level=level,
                        **request_info
                    )
                    logger.debug(f"用户操作日志记录成功 - user_id: {user_id}, action: {action_type}/{function_action_name}")
                except Exception as log_error:
                    logger.error(f"用户操作日志记录失败: {log_error}")

                return result

            except Exception as e:
                # 记录失败的用户操作
                try:
                    await log_service.create_user_action_log(
                        user_id=user_id,
                        action_type=action_type,
                        action_name=function_action_name,
                        description=description or f"User attempted {function_action_name}",
                        resource_type=resource_type,
                        success=False,
                        result_message=f"Operation failed: {str(e)}",
                        level='ERROR',
                        **request_info
                    )
                    logger.debug(f"失败操作日志记录成功 - user_id: {user_id}, action: {action_type}/{function_action_name}")
                except Exception as log_error:
                    logger.error(f"失败操作日志记录失败: {log_error}")

                raise
        
        # 同步版本类似，这里省略...
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return func  # 简化处理，实际应该实现同步版本
    
    return decorator


def _get_memory_usage() -> int:
    """获取当前内存使用量（KB）"""
    if not PSUTIL_AVAILABLE:
        return 0
    try:
        process = psutil.Process(os.getpid())
        return int(process.memory_info().rss / 1024)  # 转换为KB
    except Exception:
        return 0


def _filter_sensitive_data(data: Dict[str, Any], sensitive_keys: list) -> Dict[str, Any]:
    """过滤敏感数据"""
    if not isinstance(data, dict):
        return data
    
    filtered = {}
    for key, value in data.items():
        if key.lower() in [k.lower() for k in sensitive_keys]:
            filtered[key] = "***FILTERED***"
        elif isinstance(value, dict):
            filtered[key] = _filter_sensitive_data(value, sensitive_keys)
        else:
            filtered[key] = value
    
    return filtered


def _extract_user_id(args: tuple, kwargs: dict) -> Optional[str]:
    """从参数中提取用户ID"""
    # 尝试从kwargs中获取
    user_id = kwargs.get('user_id') or kwargs.get('current_user_id')
    if user_id:
        return str(user_id)
    
    # 尝试从kwargs中的current_user对象获取
    current_user = kwargs.get('current_user')
    if current_user and hasattr(current_user, 'id'):
        return str(current_user.id)
    
    # 尝试从args中获取（遍历所有参数）
    if args:
        for arg in args:
            if hasattr(arg, 'id') and hasattr(arg, 'email'):  # User对象特征
                return str(arg.id)
            elif isinstance(arg, str) and len(arg) == 36:  # UUID格式
                return arg
    
    return None


def _extract_user_id_from_result(result: Any) -> Optional[str]:
    """从函数返回值中提取用户ID"""
    if not result:
        return None
    
    # 如果结果是字典
    if isinstance(result, dict):
        # 尝试常见的字段名
        for key in ['user_id', 'id', 'userId', 'uid']:
            if key in result and result[key]:
                return str(result[key])
    
    # 如果结果是对象
    elif hasattr(result, 'id'):
        return str(result.id)
    
    return None


def _extract_request_info(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """从参数中提取请求信息"""
    request_info = {}
    
    # 尝试从kwargs中获取请求相关信息
    for key in ['ip_address', 'user_agent', 'session_id']:
        if key in kwargs:
            request_info[key] = kwargs[key]
    
    return request_info


def _extract_before_data(args: tuple, kwargs: dict) -> Optional[Dict[str, Any]]:
    """提取操作前数据"""
    # 这里可以根据具体业务逻辑实现
    # 例如，如果是更新操作，可以先查询当前数据
    return None


def _extract_after_data(result: Any) -> Optional[Dict[str, Any]]:
    """提取操作后数据"""
    # 这里可以根据具体业务逻辑实现
    if hasattr(result, 'to_dict'):
        return result.to_dict()
    elif isinstance(result, dict):
        return result
    return None


def _extract_resource_info(args: tuple, kwargs: dict, result: Any) -> tuple:
    """提取资源信息"""
    resource_id = kwargs.get('resource_id') or kwargs.get('id')
    resource_name = kwargs.get('resource_name') or kwargs.get('name')
    
    # 尝试从结果中获取
    if result and hasattr(result, 'id'):
        resource_id = str(result.id)
    if result and hasattr(result, 'name'):
        resource_name = result.name
    
    return str(resource_id) if resource_id else None, resource_name