# app/agent_framework/llm/base_adapter.py

"""
LLM 适配器抽象基类

定义统一的大模型调用接口，集成错误处理、重试机制、工具调用支持
"""

import os
import random
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional, List

from .errors import ErrorClassifier, LLMErrorCode, ERROR_PREFIX
from .notifications import append_length_notification

logger = logging.getLogger(__name__)


class LLMResponse:
    """LLM 调用响应"""

    def __init__(
        self,
        content: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        model: Optional[str] = None,
        finish_reason: Optional[str] = None,
        reasoning_content: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model = model
        self.finish_reason = finish_reason
        self.reasoning_content = reasoning_content
        self.raw_response = raw_response

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
            "model": self.model,
            "finish_reason": self.finish_reason,
            "reasoning_content": self.reasoning_content,
            "raw_response": self.raw_response,
        }


class BaseLLMAdapter(ABC):
    """
    LLM 适配器抽象基类

    所有具体的 LLM 适配器都应该继承这个类
    提供：
    - 统一的接口定义
    - 重试机制
    - 错误处理
    - 工具调用支持
    """

    def __init__(
        self,
        model_name: str = "",
        api_key: str = "",
        base_url: str = "",
        **kwargs
    ):
        """
        初始化适配器

        Args:
            model_name: 模型名称
            api_key: API 密钥
            base_url: API 基础 URL
            **kwargs: 其他配置参数
        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs

        self.max_retries = int(os.environ.get("LLM_MAX_RETRIES", kwargs.get("max_retries", 5)))
        self.base_delay = float(os.environ.get("LLM_BASE_DELAY", kwargs.get("retry_interval", 2.0)))
        self.max_rounds = kwargs.get("max_rounds", 5)
        self.timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", kwargs.get("timeout", 600)))

        self.enable_langsmith = os.environ.get("LANGSMITH_TRACING", "false").lower() in ("true", "1", "yes")

        self.is_tools = False
        self.tools: List[Dict[str, Any]] = []
        self.toolcall_session = None

    def _get_delay(self, attempt: int = 0) -> float:
        """
        获取重试延迟时间（指数退避 + 抖动）

        Args:
            attempt: 当前已尝试次数（从 0 开始），用于指数退避

        Returns:
            延迟秒数
        """
        # 指数退避：base_delay * 2^attempt，封顶 max_delay，叠加 ±25% 抖动避免重试风暴
        max_delay = float(os.environ.get("LLM_MAX_RETRY_DELAY", 60.0))
        backoff = min(self.base_delay * (2 ** attempt), max_delay)
        return backoff * random.uniform(0.75, 1.25)

    def _should_retry(self, error_code: LLMErrorCode) -> bool:
        """
        判断错误是否应该重试

        Args:
            error_code: 错误码

        Returns:
            是否应该重试
        """
        retryable_codes = {
            LLMErrorCode.ERROR_RATE_LIMIT,
            LLMErrorCode.ERROR_SERVER,
            LLMErrorCode.ERROR_TIMEOUT,
            LLMErrorCode.ERROR_CONNECTION,
        }
        return error_code in retryable_codes

    async def _handle_error(self, error: Exception, attempt: int) -> Optional[str]:
        """
        处理错误

        Args:
            error: 异常对象
            attempt: 当前尝试次数

        Returns:
            如果应该重试返回 None，否则返回错误消息
        """
        llm_error = ErrorClassifier.create_error(
            error,
            max_retries_exceeded=(attempt >= self.max_retries)
        )

        if attempt >= self.max_retries:
            msg = f"{ERROR_PREFIX}: {llm_error.code.value} - {llm_error.message}"
            logger.error(f"[重试耗尽] {msg}")
            return msg

        if llm_error.retryable:
            delay = self._get_delay(attempt)
            logger.warning(
                f"[重试] 错误: {llm_error.code.value}, "
                f"{delay:.2f} 秒后重试... (尝试 {attempt + 1}/{self.max_retries})"
            )
            await self._async_sleep(delay)
            return None

        msg = f"{ERROR_PREFIX}: {llm_error.code.value} - {llm_error.message}"
        logger.error(f"[不可重试错误] {msg}")
        return msg

    async def _async_sleep(self, seconds: float):
        """异步睡眠"""
        import asyncio
        await asyncio.sleep(seconds)

    def _handle_length_stop(self, content: str, is_chinese: bool = True) -> str:
        """
        处理上下文窗口截断

        Args:
            content: 内容
            is_chinese: 是否为中文

        Returns:
            追加截断通知后的内容
        """
        return append_length_notification(content)

    def bind_tools(self, toolcall_session, tools: List[Dict[str, Any]]):
        """
        绑定工具到适配器

        Args:
            toolcall_session: 工具调用会话
            tools: 工具定义列表
        """
        if not (toolcall_session and tools):
            return

        self.is_tools = True
        self.toolcall_session = toolcall_session
        self.tools = tools
        logger.info(f"[工具绑定] 已绑定 {len(tools)} 个工具")

    def _format_tool_calls(
        self,
        tool_calls: List[Any],
        results: List[Any]
    ) -> str:
        """
        格式化工具调用结果

        Args:
            tool_calls: 工具调用列表
            results: 执行结果列表

        Returns:
            格式化的 XML 字符串
        """
        import json

        output = []
        for tc, result, err in results:
            name = tc.function.name
            args = tc.function.arguments

            if err:
                res_str = str(err)
            elif isinstance(result, dict):
                res_str = json.dumps(result, ensure_ascii=False)
            else:
                res_str = str(result)

            output.append(
                f"<tool_call>{json.dumps({'name': name, 'args': args, 'result': res_str}, ensure_ascii=False, indent=2)}</tool_call>"
            )

        return "\n".join(output)

    def _append_history_batch(
        self,
        history: List[Dict[str, Any]],
        tool_calls: List[Any],
        results: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        批量追加工具调用到历史

        Args:
            history: 历史消息列表
            tool_calls: 工具调用列表
            results: 执行结果列表

        Returns:
            更新后的历史
        """
        history.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "index": tc.index,
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                    "type": "function",
                }
                for tc, _, _, _, _ in results
            ],
        })

        for tc, _, _, result, err in results:
            if err:
                content = str(err)
            elif isinstance(result, dict):
                import json
                content = json.dumps(result, ensure_ascii=False)
            else:
                content = str(result)

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content
            })

        return history

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成回答（非流式）

        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象，包含生成文本和 token 使用量
        """
        pass

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式生成回答

        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Yields:
            Dict，包含以下类型之一：
            - {"type": "delta", "content": "文本片段"}
            - {"type": "reasoning", "content": "推理内容"}
            - {"type": "tool_call", "tool": "工具名", "arguments": "参数"}
            - {"type": "usage", "data": {"total_tokens": N}}
        """
        pass

    async def chat(
        self,
        system: Optional[str],
        history: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        对话（非流式）

        Args:
            system: 系统提示词
            history: 对话历史
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        messages = []
        if system and history and history[0].get("role") != "system":
            messages.append({"role": "system", "content": system})
        messages.extend(history)

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._chat(messages, temperature, max_tokens, **kwargs)
                return response
            except (ValueError, KeyError) as e:
                error_msg = await self._handle_error(e, attempt)
                if error_msg:
                    return LLMResponse(content=error_msg)
                continue
            except (OSError, IOError) as e:
                error_msg = await self._handle_error(e, attempt)
                if error_msg:
                    return LLMResponse(content=error_msg)
                continue
            except Exception as e:
                error_msg = await self._handle_error(e, attempt)
                if error_msg:
                    return LLMResponse(content=error_msg)
                continue

        return LLMResponse(content=f"{ERROR_PREFIX}: 最大重试次数已超限")

    @abstractmethod
    async def _chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> LLMResponse:
        """
        内部对话实现

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            模型信息字典
        """
        return {
            "model_name": self.model_name,
            "adapter_type": self.__class__.__name__,
            "base_url": self.base_url,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "tools_bound": self.is_tools,
            "tools_count": len(self.tools),
        }
