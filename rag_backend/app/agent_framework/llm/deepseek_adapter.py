# app/agent_framework/llm/deepseek_adapter.py

"""
DeepSeek 专属适配器 (OpenRouter API)

支持通过 OpenRouter API 调用 DeepSeek 模型
参考 MiniMax 和智谱适配器的设计实现
集成 LangSmith 追踪功能（供应商无关）
"""

import os
import asyncio
from app.utils.json_compat import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from app.core.config import settings
from .base_adapter import BaseLLMAdapter, LLMResponse
from .model_policies import apply_model_family_policies
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)


# 进程级 LangSmith 熔断开关：
# LangSmith 包装客户端在某些网络环境（如 Docker 内无法访问 LangSmith 端点）下会挂起，
# 直到超时才回退到 httpx。由于专家适配器按请求重建，旧逻辑导致**每个请求**都白白支付一次
# 超时代价。一旦任意实例探测到追踪客户端超时/失败，立即进程级禁用，后续实例不再尝试，
# 把代价从"每请求一次"降为"进程内至多一次"。
_LANGSMITH_RUNTIME_DISABLED = False


def _langsmith_runtime_disabled() -> bool:
    return _LANGSMITH_RUNTIME_DISABLED


def _disable_langsmith_runtime(reason: str):
    global _LANGSMITH_RUNTIME_DISABLED
    if not _LANGSMITH_RUNTIME_DISABLED:
        _LANGSMITH_RUNTIME_DISABLED = True
        logger.warning(f"[DeepSeek] LangSmith 追踪已进程级熔断，后续请求将直接使用 httpx: {reason}")


def _get_langsmith_traced_client(api_key: str, base_url: str):
    """
    获取 LangSmith 追踪客户端（使用统一管理器）
    
    使用 LangSmithClientManager 获取追踪客户端，完全解耦供应商逻辑
    """
    try:
        from app.langsmith_integration import get_langsmith_manager
        manager = get_langsmith_manager()
        if manager.enabled:
            return manager.get_traced_client(api_key, base_url)
    except Exception as e:
        logger.warning(f"[DeepSeek] 获取 LangSmith 追踪客户端失败: {e}")
    
    return None


class DeepSeekAdapter(BaseLLMAdapter):
    """
    DeepSeek 大模型适配器 (支持 OpenRouter)

    支持：
    - 非流式对话
    - 流式对话
    - 工具调用（Function Calling）
    - OpenRouter 兼容
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "deepseek/deepseek-chat-v3-0324",
        base_url: str = "https://openrouter.ai/api/v1",
        **kwargs
    ):
        """
        初始化 DeepSeek 适配器

        Args:
            api_key: API 密钥
            model_name: 模型名称（如 deepseek/deepseek-chat-v3-0324）
            base_url: API 基础 URL
            **kwargs: 其他配置参数
        """
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url, **kwargs)
        self.client = None
        self.langsmith_client = None
        
        # 如果启用了 LangSmith，且进程级熔断未触发，获取追踪客户端
        if self.enable_langsmith and not _langsmith_runtime_disabled():
            self.langsmith_client = _get_langsmith_traced_client(api_key, base_url)
            if self.langsmith_client:
                logger.info("✅ LangSmith 追踪已启用（供应商无关模式）")
        elif self.enable_langsmith:
            logger.info("ℹ️ LangSmith 追踪已配置，但因进程级熔断已禁用，使用标准 HTTP 客户端")
        
        logger.info("✅ DeepSeek 适配器初始化完成")
        logger.info(f"   - 模型: {self.model_name}")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - API Key: {self.api_key[:12]}...{self.api_key[-4:]}")
        logger.info(f"   - LangSmith 追踪: {'启用' if self.langsmith_client else '禁用'}")

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self.client is None:
            verify_ssl_config = getattr(settings, 'OPENROUTER_VERIFY_SSL', True)
            if isinstance(verify_ssl_config, str):
                verify_ssl = verify_ssl_config.lower() not in ('false', '0', 'no', 'off')
            else:
                verify_ssl = bool(verify_ssl_config)
            
            logger.info(f"[DeepSeek] 创建HTTP客户端, verify_ssl={verify_ssl}")
            
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                verify=verify_ssl
            )
        return self.client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None

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
            LLMResponse 对象
        """
        messages = [{"role": "user", "content": prompt}]
        return await self._chat(messages, temperature, max_tokens, **kwargs)

    async def agenerate(
        self,
        prompts: List[str],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成回答（接受列表格式，与其他适配器兼容）

        Args:
            prompts: 提示词列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        prompt = prompts[0] if prompts else ""
        return await self.generate(prompt, temperature, max_tokens, **kwargs)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        对话接口（外部调用入口）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        logger.info(f"💬 [DeepSeek] 对话调用: {self.model_name}")
        logger.info(f"     消息数量: {len(messages)}")
        logger.info(f"     温度: {temperature}")

        return await self._chat(messages, temperature, max_tokens, **kwargs)

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
        gen_conf, request_kwargs = apply_model_family_policies(
            self.model_name,
            {"temperature": temperature, "max_tokens": max_tokens},
            kwargs
        )

        model = kwargs.pop("model", None) or self.model_name

        try:
            # 优先使用 LangSmith 包装的客户端（如果启用）
            if self.langsmith_client:
                logger.info("[DeepSeek] 使用 LangSmith 追踪客户端...")
                # 超时阈值需高于模型正常生成耗时（否则健康的慢生成会被误判超时），
                # 默认 30s，可通过 LANGSMITH_TRACE_TIMEOUT 配置。
                ls_timeout = float(getattr(settings, "LANGSMITH_TRACE_TIMEOUT", 30.0) or 30.0)
                try:
                    response = await asyncio.wait_for(
                        self.langsmith_client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=gen_conf.get("temperature", temperature),
                            max_tokens=max_tokens,
                            **request_kwargs
                        ),
                        timeout=ls_timeout,
                    )
                except (asyncio.TimeoutError, Exception) as ls_err:
                    # 超时或任意异常：触发进程级熔断，后续请求不再尝试追踪客户端，回退 httpx
                    if isinstance(ls_err, asyncio.TimeoutError):
                        reason = f"追踪客户端超时({ls_timeout:.0f}s)"
                    else:
                        reason = f"追踪客户端异常: {type(ls_err).__name__}: {ls_err}"
                    logger.warning(f"[DeepSeek] {reason}，回退到标准 HTTP 客户端")
                    _disable_langsmith_runtime(reason)
                    self.langsmith_client = None
                    # 不 return，继续到下面的 httpx 路径
                else:
                    # 转换为标准格式（保留 tool_calls）
                    raw_message = response.choices[0].message
                    message_dict = {
                        "role": raw_message.role,
                        "content": raw_message.content,
                    }
                    tool_calls_data = None
                    if hasattr(raw_message, "tool_calls") and raw_message.tool_calls:
                        tool_calls_data = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                            }
                            for tc in raw_message.tool_calls
                        ]
                        message_dict["tool_calls"] = tool_calls_data

                    result = {
                        "model": response.model,
                        "choices": [{"message": message_dict, "finish_reason": response.choices[0].finish_reason}],
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                            "total_tokens": response.usage.total_tokens if response.usage else 0
                        }
                    }

                    content = raw_message.content or ""
                    finish_reason = response.choices[0].finish_reason

                    has_tool_calls = bool(tool_calls_data)
                    logger.info(
                        f"[DeepSeek] LangSmith 追踪响应，长度: {len(content)} 字符"
                        + (f", 工具调用: {len(tool_calls_data)}" if has_tool_calls else "")
                    )

                    return LLMResponse(
                    content=content,
                    model=model,
                    raw_response=result,
                    finish_reason=finish_reason,
                    prompt_tokens=result["usage"]["prompt_tokens"],
                    completion_tokens=result["usage"]["completion_tokens"],
                    total_tokens=result["usage"]["total_tokens"]
                )
            
            # 回退到 httpx 客户端
            logger.info("[DeepSeek] 使用标准 HTTP 客户端...")
            client = self._get_client()

            request_body = {
                "model": model,
                "messages": messages,
                "temperature": gen_conf.get("temperature", temperature),
                "stream": False,
            }

            if max_tokens:
                request_body["max_tokens"] = max_tokens

            if "top_p" in gen_conf:
                request_body["top_p"] = gen_conf["top_p"]
            if "stop" in gen_conf:
                request_body["stop"] = gen_conf["stop"]

            extra_body = kwargs.pop("extra_body", None)
            if extra_body:
                request_body["extra_body"] = extra_body

            request_body.update(request_kwargs)

            url = f"{self.base_url}/chat/completions"
            logger.info(f"[DeepSeek] 发起请求: {url}")

            response = await client.post(url, json=request_body)
            response.raise_for_status()

            logger.info("[DeepSeek] 收到响应，准备解析...")

            result = response.json()

            logger.info(f"[DeepSeek] 响应解析完成，内容长度: {len(str(result))}")

            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")

                logger.info(f"[DeepSeek] 提取到内容，长度: {len(content)} 字符")

                return LLMResponse(
                    content=content,
                    model=self.model_name,
                    raw_response=result,
                    finish_reason=finish_reason
                )
            else:
                logger.warning(f"[DeepSeek] 响应格式异常: {result}")
                return LLMResponse(
                    content="",
                    model=self.model_name,
                    raw_response=result,
                    finish_reason="error"
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"[DeepSeek] HTTP 错误: {error_msg}")
            return LLMResponse(
                content=f"{ERROR_PREFIX}DeepSeek API 错误: {error_msg}",
                model=self.model_name,
                raw_response=None,
                finish_reason="error"
            )
        except Exception as e:
            logger.error(f"[DeepSeek] 请求异常: {str(e)}")
            return LLMResponse(
                content=f"{ERROR_PREFIX}DeepSeek 请求失败: {str(e)}",
                model=self.model_name,
                raw_response=None,
                finish_reason="error"
            )

    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回答

        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Yields:
            逐步生成的内容
        """
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self._stream_chat(messages, temperature, max_tokens, **kwargs):
            yield chunk

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式对话接口

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Yields:
            逐步生成的内容
        """
        logger.info(f"💬 [DeepSeek] 流式对话调用: {self.model_name}")
        async for chunk in self._stream_chat(messages, temperature, max_tokens, **kwargs):
            yield chunk

    async def _stream_chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        内部流式对话实现

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Yields:
            逐步生成的内容
        """
        client = self._get_client()

        gen_conf, request_kwargs = apply_model_family_policies(
            self.model_name,
            {"temperature": temperature, "max_tokens": max_tokens},
            kwargs
        )

        request_body = {
            "model": self.model_name,
            "messages": messages,
            "temperature": gen_conf.get("temperature", temperature),
            "stream": True,
        }

        if max_tokens:
            request_body["max_tokens"] = max_tokens

        if "top_p" in gen_conf:
            request_body["top_p"] = gen_conf["top_p"]
        if "stop" in gen_conf:
            request_body["stop"] = gen_conf["stop"]

        extra_body = kwargs.pop("extra_body", None)
        if extra_body:
            request_body["extra_body"] = extra_body

        request_body.update(request_kwargs)

        try:
            url = f"{self.base_url}/chat/completions"
            logger.info(f"[DeepSeek] 发起流式请求: {url}")

            async with client.stream("POST", url, json=request_body) as response:
                response.raise_for_status()

                full_content = ""
                chunk_count = 0
                total_chars_yielded = 0
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data = line[6:].strip()
                    if data == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data)
                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        
                        if content:
                            chunk_count += 1
                            full_content += content
                            
                            if chunk_count == 1:
                                logger.debug(f"[DeepSeek] API开始返回，首chunk: '{content[:20]}...'")
                            elif chunk_count == 11:
                                logger.debug(f"[DeepSeek] API返回chunk #{chunk_count}: (前10个chunk总长: {len(full_content)} 字符)")
                            
                            # 💡 关键优化：如果content较长，逐字符yield实现打字机效果
                            if len(content) > 1:
                                # 逐字符yield，实现逐字显示
                                for char in content:
                                    yield char
                                    total_chars_yielded += 1
                            else:
                                # 单字符直接yield
                                yield content
                                total_chars_yielded += 1
                                
                    except json.JSONDecodeError:
                        continue

                logger.debug(f"[DeepSeek] 流式响应完成 | chunks: {chunk_count} | 实际输出: {total_chars_yielded} 字符")

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"[DeepSeek] 流式HTTP错误: {error_msg}")
            yield f"{ERROR_PREFIX}DeepSeek API 错误: {error_msg}"
        except Exception as e:
            logger.error(f"[DeepSeek] 流式请求异常: {str(e)}")
            yield f"{ERROR_PREFIX}DeepSeek 请求失败: {str(e)}"
