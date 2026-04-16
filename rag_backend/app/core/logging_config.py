# app/core/logging_config.py

"""
统一日志配置模块

提供结构化日志、敏感信息过滤、统一日志格式等功能
"""

import logging
import sys
import json
import re
import os
from typing import Any, Dict, List
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class SensitiveDataFilter(logging.Filter):
    """
    敏感数据过滤器
    
    自动过滤日志中的敏感信息，如密码、API密钥、Token等
    """
    
    SENSITIVE_PATTERNS = [
        (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[PASSWORD]'),
        (re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[SECRET]'),
        (re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[API_KEY]'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[TOKEN]'),
        (re.compile(r'bearer\s+([a-zA-Z0-9\-_.]+)', re.IGNORECASE), 'Bearer [TOKEN]'),
        (re.compile(r'access[_-]?token["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[ACCESS_TOKEN]'),
        (re.compile(r'refresh[_-]?token["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[REFRESH_TOKEN]'),
        (re.compile(r'authorization["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[AUTH_HEADER]'),
        (re.compile(r'jwt["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[JWT]'),
        (re.compile(r'secret[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[SECRET_KEY]'),
        (re.compile(r'private[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), '[PRIVATE_KEY]'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg:
            record.msg = self._filter_message(str(record.msg))
        if record.args:
            record.args = tuple(
                self._filter_message(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True
    
    def _filter_message(self, message: str) -> str:
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        return message


class StructuredLogFormatter(logging.Formatter):
    """
    结构化日志格式化器
    
    输出 JSON 格式的日志，便于日志收集和分析
    """
    
    def __init__(
        self,
        include_extra: bool = True,
        include_caller_info: bool = True,
        include_trace_id: bool = True
    ):
        super().__init__()
        self.include_extra = include_extra
        self.include_caller_info = include_caller_info
        self.include_trace_id = include_trace_id
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if self.include_caller_info and record.filename:
            log_data["file"] = f"{record.filename}:{record.lineno}"
            log_data["function"] = record.funcName
        
        if self.include_extra:
            extra_fields = {
                k: v for k, v in record.__dict__.items()
                if k not in [
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "asctime"
                ] and not k.startswith("_")
            }
            if extra_fields:
                log_data["extra"] = extra_fields
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """
    带颜色的控制台日志格式化器（标准 ANSI 颜色）
    
    在终端中输出彩色日志，便于开发调试
    """
    
    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[35m",  # 紫红色
        "RESET": "\033[0m",
        "BOLD": "\033[1m",
        "DIM": "\033[2m",
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        dim = self.COLORS["DIM"]
        bold = self.COLORS["BOLD"]
        
        timestamp = f"{dim}{record.asctime}{self.RESET}"
        log_level = f"{color}{bold}{record.levelname}{self.RESET}"
        module = f"{dim}{record.name}{self.RESET}"
        
        return f"{timestamp} | {module} | {log_level} | {record.getMessage()}"


def setup_logging(
    log_level: str = None,
    log_file: str = None,
    log_dir: str = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    structured: bool = True,
    console_output: bool = True
) -> None:
    """
    配置统一日志系统
    
    Args:
        log_level: 日志级别，默认从环境变量 LOG_LEVEL 获取
        log_file: 日志文件名（如果指定）
        log_dir: 日志目录（默认 logs/）
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数量
        structured: 是否使用结构化日志（JSON格式）
        console_output: 是否输出到控制台
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    sensitive_filter = SensitiveDataFilter()
    
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.encoding = 'utf-8'
        console_handler.addFilter(sensitive_filter)
        
        if sys.stdout.isatty():
            console_handler.setFormatter(ColoredConsoleFormatter())
        else:
            if structured:
                console_handler.setFormatter(StructuredLogFormatter())
            else:
                console_handler.setFormatter(
                    logging.Formatter(
                        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S"
                    )
                )
        
        root_logger.addHandler(console_handler)
    
    if log_file or log_dir:
        if log_dir is None:
            log_dir = "logs"
        
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        if log_file is None:
            log_file = f"app_{datetime.now().strftime('%Y%m%d')}.log"
        
        log_path = os.path.join(log_dir, log_file)
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.addFilter(sensitive_filter)
        
        if structured:
            file_handler.setFormatter(StructuredLogFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s | %(name)s | %(levelname)s | %(pathname)s:%(lineno)d | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
            )
        
        root_logger.addHandler(file_handler)
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if log_level == "DEBUG" else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(name)


class LogContext:
    """
    日志上下文管理器
    
    用于在代码块执行期间添加额外的日志上下文信息
    
    Example:
        ```python
        with LogContext(request_id="123", user_id="456"):
            logger.info("处理请求")
            # 所有在这个块中的日志都会包含 request_id 和 user_id
        ```
    """
    
    _context_stack: List[Dict[str, Any]] = []
    
    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self._old_context = None
    
    def __enter__(self) -> "LogContext":
        self._old_context = getattr(
            logging.getLogger(), "_app_context", {}
        ).copy()
        logging.getLogger()._app_context = {
            **self._old_context,
            **self.context
        }
        self._context_stack.append(self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._context_stack.pop()
        if self._context_stack:
            logging.getLogger()._app_context = {
                **self._old_context,
                **self._context_stack[-1]
            }
        else:
            logging.getLogger()._app_context = self._old_context


def log_function_call(func):
    """
    函数调用日志装饰器
    
    自动记录函数的输入参数和返回值
    
    Example:
        ```python
        @log_function_call
        def my_function(a, b):
            return a + b
        ```
    """
    import functools
    import inspect
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        call_args = {
            **{k: v for k, v in zip(param_names, args)},
            **kwargs
        }
        
        logger.debug(f"调用 {func.__name__}: {call_args}")
        
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"{func.__name__} 返回: {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} 异常: {e}")
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        call_args = {
            **{k: v for k, v in zip(param_names, args)},
            **kwargs
        }
        
        logger.debug(f"调用 {func.__name__}: {call_args}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} 返回: {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} 异常: {e}")
            raise
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


setup_logging()
