"""
结构化日志系统

提供与 OpenTelemetry 集成的结构化日志

功能：
1. 自动注入 trace_id 和 span_id
2. 结构化日志格式
3. 多级别日志
4. 日志聚合
"""

import logging
import json
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from app.observability.tracing import get_tracer

logger = logging.getLogger(__name__)

# 内存日志存储（供 API 查询）
_log_store: List[Dict[str, Any]] = []
_MAX_LOG_STORE = 10000


def _add_to_log_store(record_dict: Dict[str, Any]):
    """将日志记录添加到内存存储"""
    _log_store.append(record_dict)
    if len(_log_store) > _MAX_LOG_STORE:
        del _log_store[:1000]


def get_log_store() -> List[Dict[str, Any]]:
    """获取所有存储的日志记录"""
    return list(_log_store)


class LogStoreHandler(logging.Handler):
    """
    日志存储处理器

    拦截所有标准 Python 日志并存入内存缓冲区供 API 查询
    """

    def __init__(self, level: int = logging.INFO):
        super().__init__(level)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord):
        """处理日志记录"""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "service": "rag-backend",
                "trace_id": None,
                "span_id": None,
                "attributes": {},
            }

            # 提取异常信息
            if record.exc_info and record.exc_info[1]:
                log_entry["error"] = {
                    "type": type(record.exc_info[1]).__name__,
                    "message": str(record.exc_info[1]),
                }

            # 提取 extra 属性
            if hasattr(record, "trace_id"):
                log_entry["trace_id"] = getattr(record, "trace_id")
            if hasattr(record, "span_id"):
                log_entry["span_id"] = getattr(record, "span_id")

            _add_to_log_store(log_entry)
        except Exception:
            self.handleError(record)


# 自动注册到根日志器，捕获所有应用的日志
_log_store_handler = LogStoreHandler()
logging.getLogger().addHandler(_log_store_handler)


@dataclass
class LogConfig:
    """日志配置"""
    service_name: str = "rag-backend"
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    format_json: bool = True
    include_trace_context: bool = True
    include_timestamp: bool = True
    max_log_size: int = 10000  # 单条日志最大长度


@dataclass
class LogRecord:
    """日志记录"""
    timestamp: datetime
    level: str
    message: str
    logger_name: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    service_name: str = "rag-backend"
    attributes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "logger": self.logger_name,
            "service": self.service_name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "attributes": self.attributes,
            "error": self.error
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class StructuredLogger:
    """
    结构化日志器
    
    提供与追踪系统集成的结构化日志
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[LogConfig] = None
    ):
        """
        初始化结构化日志器
        
        Args:
            name: 日志器名称
            config: 日志配置
        """
        self.name = name
        self.config = config or LogConfig()
        self._enabled = True
        
        # 创建标准日志器
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # 添加处理器（如果还没有）
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
    
    def _get_trace_context(self) -> tuple:
        """获取追踪上下文"""
        if not self.config.include_trace_context:
            return None, None
        
        tracer = get_tracer()
        span = tracer.get_current_span()
        
        if span:
            return span.trace_id, span.span_id
        
        return None, None
    
    def _format_message(self, level: str, message: str, **kwargs):
        """格式化消息并存储到内存"""
        trace_id, span_id = self._get_trace_context()

        record = LogRecord(
            timestamp=datetime.now(),
            level=level,
            message=message,
            logger_name=self.name,
            trace_id=trace_id,
            span_id=span_id,
            service_name=self.config.service_name,
            attributes=kwargs
        )

        # 存储到内存供 API 查询
        _add_to_log_store(record.to_dict())

        if self.config.format_json:
            return record.to_json()
        else:
            # 文本格式
            parts = [
                f"[{record.timestamp.isoformat()}]",
                f"[{level}]",
                f"[{self.name}]",
                message
            ]

            if trace_id:
                parts.append(f"trace_id={trace_id}")

            if kwargs:
                parts.append(f"attributes={kwargs}")

            return " ".join(parts)
    
    def debug(self, message: str, **kwargs):
        """调试日志"""
        if self._enabled and self._logger.level <= logging.DEBUG:
            self._logger.debug(self._format_message("DEBUG", message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """信息日志"""
        if self._enabled and self._logger.level <= logging.INFO:
            self._logger.info(self._format_message("INFO", message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """警告日志"""
        if self._enabled and self._logger.level <= logging.WARNING:
            self._logger.warning(self._format_message("WARNING", message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """错误日志"""
        if self._enabled and self._logger.level <= logging.ERROR:
            error_info = kwargs.pop("error", None)

            if error_info and isinstance(error_info, Exception):
                error = {
                    "type": type(error_info).__name__,
                    "message": str(error_info)
                }
            else:
                error = error_info

            record = LogRecord(
                timestamp=datetime.now(),
                level="ERROR",
                message=message,
                logger_name=self.name,
                trace_id=self._get_trace_context()[0],
                span_id=self._get_trace_context()[1],
                service_name=self.config.service_name,
                attributes=kwargs,
                error=error
            )

            _add_to_log_store(record.to_dict())
            self._logger.error(record.to_json())
    
    def exception(self, message: str, **kwargs):
        """异常日志（包含堆栈跟踪）"""
        if self._enabled and self._logger.level <= logging.ERROR:
            exc_info = kwargs.pop("exc_info", None)

            error = {
                "type": "Exception",
                "message": message
            }

            if exc_info:
                import traceback
                error["stack_trace"] = traceback.format_exc()

            record = LogRecord(
                timestamp=datetime.now(),
                level="ERROR",
                message=message,
                logger_name=self.name,
                trace_id=self._get_trace_context()[0],
                span_id=self._get_trace_context()[1],
                service_name=self.config.service_name,
                attributes=kwargs,
                error=error
            )

            _add_to_log_store(record.to_dict())
            self._logger.error(record.to_json())


class ObservabilityLogger:
    """
    可观测性日志管理器
    
    管理多个结构化日志器
    """
    
    def __init__(self, config: Optional[LogConfig] = None):
        """
        初始化日志管理器
        
        Args:
            config: 日志配置
        """
        self.config = config or LogConfig()
        self._loggers: Dict[str, StructuredLogger] = {}
    
    def get_logger(self, name: str) -> StructuredLogger:
        """
        获取日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            StructuredLogger 实例
        """
        if name not in self._loggers:
            self._loggers[name] = StructuredLogger(name, self.config)
        
        return self._loggers[name]
    
    def set_level(self, level: str):
        """
        设置日志级别
        
        Args:
            level: 级别（DEBUG, INFO, WARNING, ERROR）
        """
        self.config.level = level
        level_value = getattr(logging, level.upper())
        
        for logger in self._loggers.values():
            logger._logger.setLevel(level_value)
    
    def disable(self):
        """禁用所有日志"""
        for logger in self._loggers.values():
            logger._enabled = False
    
    def enable(self):
        """启用所有日志"""
        for logger in self._loggers.values():
            logger._enabled = True


# 便捷函数
def get_logger(name: str) -> StructuredLogger:
    """
    获取日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        StructuredLogger 实例
    """
    manager = ObservabilityLogger()
    return manager.get_logger(name)


# 默认日志器
default_logger = get_logger(__name__)
