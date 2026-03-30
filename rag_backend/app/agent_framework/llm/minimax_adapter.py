# app/agent_framework/llm/minimax_adapter.py

"""
MiniMax 适配器

支持 MiniMax API 的 LLM 适配器实现
文档: https://www.minimaxi.com/document
"""

import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from .base_adapter import BaseLLMAdapter, LLMResponse
from .model_policies import apply_model_family_policies
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)

# LangSmith 追踪器（延迟导入避免循环依赖）
_langsmith_tracer = None


def _get_langsmith_tracer():
    """获取 LangSmith 追踪器（延迟初始化）"""
    global _langsmith_tracer
    if _langsmith_tracer is None:
        try:
            from app.langsmith_integration import get_tracer
            _langsmith_tracer = get_tracer()
        except Exception as e:
            logger.warning(f"[MiniMax] 无法加载 LangSmith 追踪器: {e}")
            _langsmith_tracer = None
    return _langsmith_tracer


class MiniMaxAdapter(BaseLLMAdapter):
    """
    MiniMax 大模型适配器

    支持：
    - 非流式对话
    - 流式对话
    - 工具调用（Function Calling）
    - 推理模型支持
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "MiniMax-Text-01",
        base_url: str = "https://api.minimax.chat/v1",
        group_id: str = "",
        **kwargs
    ):
        """
        初始化 MiniMax 适配器

        Args:
            api_key: MiniMax API 密钥
            model_name: 模型名称
            base_url: API 基础 URL
            group_id: MiniMax Group ID
            **kwargs: 其他配置参数
        """
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url, **kwargs)
        self.group_id = group_id
        self.client = None

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
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
            - {"type": "usage", "data": {"total_tokens": N}}
        """
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self._stream_chat(messages, temperature, max_tokens, **kwargs):
            yield chunk

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
            "stream": False,
        }

        if max_tokens:
            request_body["max_tokens"] = max_tokens

        if "top_p" in gen_conf:
            request_body["top_p"] = gen_conf["top_p"]
        if "stop" in gen_conf:
            request_body["stop"] = gen_conf["stop"]

        request_body.update(request_kwargs)

        if self.group_id:
            request_body["group_id"] = self.group_id

        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            logger.info(f"[MiniMax] 发起请求: {url}")

            response = await client.post(url, json=request_body)
            response.raise_for_status()

            data = response.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})

            llm_response = LLMResponse(
                content=content,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                model=data.get("model", self.model_name),
                finish_reason=data.get("choices", [{}])[0].get("finish_reason")
            )

            # LangSmith 追踪
            tracer = _get_langsmith_tracer()
            if tracer and tracer.client:
                tracer.trace_llm_call(
                    model_name=self.model_name,
                    prompt=str(messages),
                    response=content,
                    token_usage={
                        "prompt": usage.get("prompt_tokens", 0),
                        "completion": usage.get("completion_tokens", 0),
                        "total": usage.get("total_tokens", 0)
                    },
                    metadata={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "base_url": self.base_url
                    }
                )

            return llm_response

        except httpx.HTTPStatusError as e:
            logger.error(f"[MiniMax] HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"MiniMax API 错误: {e.response.status_code}")
        except Exception as e:
            logger.error(f"[MiniMax] 请求异常: {str(e)}")
            raise

    async def _stream_chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式对话实现

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Yields:
            Dict，包含以下类型之一：
            - {"type": "delta", "content": "文本片段"}
            - {"type": "usage", "data": {"total_tokens": N}}
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

        request_body.update(request_kwargs)

        if self.group_id:
            request_body["group_id"] = self.group_id

        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            logger.info(f"[MiniMax] 发起流式请求: {url}")

            async with client.stream("POST", url, json=request_body) as response:
                response.raise_for_status()

                full_content = ""
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    if line.startswith("data: "):
                        line = line[6:]

                    if line == "[DONE]":
                        break

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")

                        if content:
                            full_content += content
                            yield {
                                "type": "delta",
                                "content": content
                            }

                    if "usage" in data:
                        yield {
                            "type": "usage",
                            "data": data["usage"]
                        }

                yield {
                    "type": "done",
                    "content": full_content
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"[MiniMax] 流式 HTTP 错误: {e.response.status_code}")
            yield {
                "type": "error",
                "content": f"{ERROR_PREFIX}: MiniMax API 错误: {e.response.status_code}"
            }
        except Exception as e:
            logger.error(f"[MiniMax] 流式请求异常: {str(e)}")
            yield {
                "type": "error",
                "content": f"{ERROR_PREFIX}: {str(e)}"
            }
