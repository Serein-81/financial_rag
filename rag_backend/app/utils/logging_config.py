"""
统一日志配置模块

特性：
1. 支持控制台和文件输出
2. 支持日志轮转（避免文件过大）
3. 支持结构化日志（JSON格式）
4. STDIO 安全模式（用于 MCP/STDIO 流）
5. 支持不同模块使用不同的日志级别
6. 统一的日志格式

使用方式：
    from app.utils.logging_config import get_logger
    
    logger = get_logger(__name__)
    
    logger.info("这是一个信息日志")
    logger.error("这是一个错误日志")
"""

import logging
import logging.handlers
import sys
from app.utils.json_compat import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """日志格式枚举"""
    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"


class STDIOAwareLogger:
    """
    STDIO 感知日志器
    
    用于 MCP/STDIO 流场景，避免日志输出干扰 JSON-RPC 流
    """
    
    def __init__(self, name: str, stdio_safe: bool = False):
        self.name = name
        self.stdio_safe = stdio_safe
        self._logger = logging.getLogger(name)
    
    def _log_to_stderr(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None):
        """
        将日志输出到 stderr（不干扰 stdout 的 JSON-RPC 流）
        
        仅在 stdio_safe 模式下启用
        """
        if self.stdio_safe:
            import sys
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] [{level}] [{self.name}] {message}"
            if extra:
                log_line += f" | {json.dumps(extra, ensure_ascii=False)}"
            print(log_line, file=sys.stderr, flush=True)
    
    def debug(self, message: str, **kwargs):
        self._logger.debug(message, **kwargs)
        if self.stdio_safe and not self._logger.isEnabledFor(logging.DEBUG):
            self._log_to_stderr("DEBUG", message)
    
    def info(self, message: str, **kwargs):
        self._logger.info(message, **kwargs)
        if self.stdio_safe and not self._logger.isEnabledFor(logging.INFO):
            self._log_to_stderr("INFO", message)
    
    def warning(self, message: str, **kwargs):
        self._logger.warning(message, **kwargs)
        if self.stdio_safe and not self._logger.isEnabledFor(logging.WARNING):
            self._log_to_stderr("WARNING", message)
    
    def error(self, message: str, **kwargs):
        self._logger.error(message, **kwargs)
        if self.stdio_safe and not self._logger.isEnabledFor(logging.ERROR):
            self._log_to_stderr("ERROR", message)
    
    def critical(self, message: str, **kwargs):
        self._logger.critical(message, **kwargs)
        if self.stdio_safe and not self._logger.isEnabledFor(logging.CRITICAL):
            self._log_to_stderr("CRITICAL", message)
    
    def exception(self, message: str, **kwargs):
        self._logger.exception(message, **kwargs)
        if self.stdio_safe and not self._logger.isEnabledFor(logging.ERROR):
            self._log_to_stderr("ERROR", message)


class StructuredLogFormatter(logging.Formatter):
    """
    结构化日志格式化器（JSON 格式）
    """
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if self.include_extra and hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        if record.args:
            log_data["args"] = record.args
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """
    带颜色的控制台格式化器（标准 ANSI 颜色）
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
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        dim = self.COLORS["DIM"]
        
        timestamp = f"{dim}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{reset}"
        log_level = f"{color}{self.COLORS['BOLD']}{record.levelname:8}{reset}"
        module = f"{dim}{record.name}{reset}"
        
        return f"[{timestamp}] [{log_level}] [{module}] {record.getMessage()}"


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_file: str = "app.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    stdio_safe: bool = False,
    enable_console: bool = True,
    enable_file: bool = True,
    format_type: LogFormat = LogFormat.DETAILED
) -> None:
    """
    设置统一日志配置
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录
        log_file: 日志文件名
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        stdio_safe: 是否启用 STDIO 安全模式（用于 MCP）
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        format_type: 日志格式类型
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    if enable_console and not stdio_safe:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.encoding = 'utf-8'
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        if format_type == LogFormat.JSON:
            console_handler.setFormatter(StructuredLogFormatter())
        elif format_type == LogFormat.DETAILED:
            console_handler.setFormatter(ColoredConsoleFormatter())
        else:
            console_handler.setFormatter(
                logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
            )
        
        root_logger.addHandler(console_handler)
    
    if enable_file:
        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(log_path / log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setLevel(getattr(logging, log_level.upper()))
            
            if format_type == LogFormat.JSON:
                file_handler.setFormatter(StructuredLogFormatter())
            else:
                file_handler.setFormatter(
                    logging.Formatter(
                        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s"
                    )
                )
            
            root_logger.addHandler(file_handler)
        except (PermissionError, OSError, IOError) as e:
            root_logger.warning(
                f"无法创建日志文件 {log_dir}/{log_file}: {e}。"
                f"日志将仅输出到控制台。"
            )
    
    if stdio_safe:
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.encoding = 'utf-8'
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )
        root_logger.addHandler(error_handler)


def get_logger(
    name: str,
    stdio_safe: bool = False,
    log_level: Optional[str] = None
) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称（通常使用 __name__）
        stdio_safe: 是否使用 STDIO 安全模式
        log_level: 单独的日志级别
    
    Returns:
        日志记录器实例
    """
    if stdio_safe:
        return STDIOAwareLogger(name, stdio_safe=True)
    
    logger = logging.getLogger(name)
    
    if log_level:
        logger.setLevel(getattr(logging, log_level.upper()))
    
    return logger


def add_log_extra(record: logging.LogRecord, **kwargs) -> None:
    """
    为日志记录添加额外数据
    
    Args:
        record: 日志记录
        **kwargs: 额外的键值对
    """
    record.extra_data = kwargs


def log_with_extra(logger: logging.Logger, level: str, message: str, **kwargs) -> None:
    """
    带额外数据的日志记录
    
    Args:
        logger: 日志记录器
        level: 日志级别 (debug, info, warning, error, critical)
        message: 日志消息
        **kwargs: 额外的键值对
    """
    extra_kwargs = kwargs.copy()
    log_func = getattr(logger, level.lower())
    
    if kwargs:
        extra_kwargs = kwargs
        log_func(message, extra={"extra_data": extra_kwargs})
    else:
        log_func(message)


class AppLogger:
    """
    应用日志记录器封装
    
    提供更方便的日志记录接口
    """
    
    def __init__(self, name: str, stdio_safe: bool = False):
        self.logger = get_logger(name, stdio_safe=stdio_safe)
        self.name = name
    
    def debug(self, message: str, **kwargs):
        """调试日志"""
        if kwargs:
            extra = {"extra_data": kwargs}
            self.logger.debug(message, extra=extra)
        else:
            self.logger.debug(message)
    
    def info(self, message: str, **kwargs):
        """信息日志"""
        if kwargs:
            extra = {"extra_data": kwargs}
            self.logger.info(message, extra=extra)
        else:
            self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """警告日志"""
        if kwargs:
            extra = {"extra_data": kwargs}
            self.logger.warning(message, extra=extra)
        else:
            self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        """错误日志"""
        if kwargs:
            extra = {"extra_data": kwargs}
            self.logger.error(message, extra=extra)
        else:
            self.logger.error(message)
    
    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        if kwargs:
            extra = {"extra_data": kwargs}
            self.logger.critical(message, extra=extra)
        else:
            self.logger.critical(message)
    
    def exception(self, message: str, **kwargs):
        """异常日志（包含堆栈跟踪）"""
        if kwargs:
            extra = {"extra_data": kwargs}
            self.logger.exception(message, extra=extra)
        else:
            self.logger.exception(message)
    
    def log_user_action(self, user_id: str, action: str, result: str, **kwargs):
        """
        记录用户操作日志
        
        Args:
            user_id: 用户ID
            action: 操作类型
            result: 操作结果
            **kwargs: 其他信息
        """
        message = f"[用户操作] user_id={user_id}, action={action}, result={result}"
        if kwargs:
            message += f", {kwargs}"
        self.info(message)
    
    def log_api_request(self, method: str, path: str, user_id: Optional[str] = None, **kwargs):
        """
        记录 API 请求日志
        
        Args:
            method: HTTP 方法
            path: 请求路径
            user_id: 用户ID（可选）
            **kwargs: 其他信息
        """
        message = f"[API请求] {method} {path}"
        if user_id:
            message += f", user_id={user_id}"
        self.info(message, **kwargs)
    
    def log_database_query(self, query_type: str, table: str, duration: float, **kwargs):
        """
        记录数据库查询日志
        
        Args:
            query_type: 查询类型 (SELECT, INSERT, UPDATE, DELETE)
            table: 表名
            duration: 执行时长（毫秒）
            **kwargs: 其他信息
        """
        message = f"[数据库] {query_type} {table}, duration={duration}ms"
        self.debug(message, **kwargs)


def get_app_logger(name: str, stdio_safe: bool = False) -> AppLogger:
    """
    获取应用日志记录器
    
    Args:
        name: 模块名称
        stdio_safe: 是否使用 STDIO 安全模式
    
    Returns:
        AppLogger 实例
    """
    return AppLogger(name, stdio_safe=stdio_safe)
