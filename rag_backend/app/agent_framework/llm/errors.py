# app/agent_framework/llm/errors.py

"""
LLM 错误码分类系统

提供精细化的 LLM 调用错误分类和处理
"""

import re
from enum import Enum
from typing import Set, Optional


class LLMErrorCode(Enum):
    """LLM 错误码枚举"""
    ERROR_RATE_LIMIT = "RATE_LIMIT_EXCEEDED"
    ERROR_AUTHENTICATION = "AUTH_ERROR"
    ERROR_INVALID_REQUEST = "INVALID_REQUEST"
    ERROR_SERVER = "SERVER_ERROR"
    ERROR_TIMEOUT = "TIMEOUT"
    ERROR_CONNECTION = "CONNECTION_ERROR"
    ERROR_MODEL = "MODEL_ERROR"
    ERROR_MAX_ROUNDS = "ERROR_MAX_ROUNDS"
    ERROR_CONTENT_FILTER = "CONTENT_FILTERED"
    ERROR_QUOTA = "QUOTA_EXCEEDED"
    ERROR_MAX_RETRIES = "MAX_RETRIES_EXCEEDED"
    ERROR_GENERIC = "GENERIC_ERROR"


class LLMError(Exception):
    """LLM 错误异常"""

    def __init__(
        self,
        code: LLMErrorCode,
        message: str,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        self.code = code
        self.message = message
        self.original_error = original_error
        self.retryable = retryable
        super().__init__(f"{code.value}: {message}")

    def to_dict(self):
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable
        }


class ErrorClassifier:
    """
    错误分类器

    通过关键词匹配对错误进行精细分类
    """

    KEYWORDS_MAPPING = [
        (["quota", "capacity", "credit", "billing", "balance", "欠费"], LLMErrorCode.ERROR_QUOTA),
        (["rate limit", "429", "tpm limit", "too many requests", "requests per minute"], LLMErrorCode.ERROR_RATE_LIMIT),
        (["auth", "key", "apikey", "401", "forbidden", "permission"], LLMErrorCode.ERROR_AUTHENTICATION),
        (["invalid", "bad request", "400", "format", "malformed", "parameter"], LLMErrorCode.ERROR_INVALID_REQUEST),
        (["server", "503", "502", "504", "500", "unavailable"], LLMErrorCode.ERROR_SERVER),
        (["timeout", "timed out"], LLMErrorCode.ERROR_TIMEOUT),
        (["connect", "network", "unreachable", "dns"], LLMErrorCode.ERROR_CONNECTION),
        (["filter", "content", "policy", "blocked", "safety", "inappropriate"], LLMErrorCode.ERROR_CONTENT_FILTER),
        (["model", "not found", "does not exist", "not available"], LLMErrorCode.ERROR_MODEL),
        (["max rounds"], LLMErrorCode.ERROR_MODEL),
    ]

    @classmethod
    def classify(cls, error: Exception) -> LLMErrorCode:
        """
        对错误进行分类

        Args:
            error: 原始异常对象

        Returns:
            LLMErrorCode 枚举值
        """
        error_str = str(error).lower()

        for keywords, code in cls.KEYWORDS_MAPPING:
            pattern = "|".join(re.escape(kw) for kw in keywords)
            if re.search(pattern, error_str):
                return code

        return LLMErrorCode.ERROR_GENERIC

    @classmethod
    def is_retryable(cls, error_code: LLMErrorCode) -> bool:
        """
        判断错误是否可重试

        Args:
            error_code: 错误码

        Returns:
            是否可重试
        """
        retryable_codes: Set[str] = {
            LLMErrorCode.ERROR_RATE_LIMIT.value,
            LLMErrorCode.ERROR_SERVER.value,
            LLMErrorCode.ERROR_TIMEOUT.value,
            LLMErrorCode.ERROR_CONNECTION.value,
        }
        return error_code.value in retryable_codes

    @classmethod
    def create_error(
        cls,
        error: Exception,
        max_retries_exceeded: bool = False
    ) -> LLMError:
        """
        创建 LLM 错误对象

        Args:
            error: 原始异常
            max_retries_exceeded: 是否是最大重试次数超限

        Returns:
            LLMError 对象
        """
        if max_retries_exceeded:
            code = LLMErrorCode.ERROR_MAX_RETRIES
            retryable = False
        else:
            code = cls.classify(error)
            retryable = cls.is_retryable(code)

        return LLMError(
            code=code,
            message=str(error),
            original_error=error,
            retryable=retryable
        )


ERROR_PREFIX = "**ERROR**"
