# app/agent_framework/llm/openai_adapter.py

"""
OpenAI 适配器

支持 OpenAI API 的 LLM 适配器实现
"""

from app.utils.json_compat import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from .base_adapter import BaseLLMAdapter, LLMResponse
from .model_policies import apply_model_family_policies
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI 大模型适配器

    支持：
    - 非流式对话
    - 流式对话
    - 工具调用（Function Calling）
    - GPT-4o, GPT-4-turbo 等模型
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4",
        base_url: str = "https://api.openai.com/v1",
        **kwargs
    ):
        """
        初始化 OpenAI 适配器

        Args:
            api_key: OpenAI API 密钥
            model_name: 模型名称
            base_url: API 基础 URL
            **kwargs: 其他配置参数
        """
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url, **kwargs)
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
        """生成回答（非流式）"""
        messages = [{"role": "user", "content": prompt}]
        return await self._chat(messages, temperature, max_tokens, **kwargs)

    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成回答"""
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
        """内部对话实现"""
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

        for key in ["top_p", "stop", "presence_penalty", "frequency_penalty", "n"]:
            if key in gen_conf:
                request_body[key] = gen_conf[key]

        request_body.update(request_kwargs)

        try:
            url = f"{self.base_url}/chat/completions"
            response = await client.post(url, json=request_body)
            response.raise_for_status()

            data = response.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                model=data.get("model", self.model_name),
                finish_reason=data.get("choices", [{}])[0].get("finish_reason")
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"[OpenAI] HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"OpenAI API 错误: {e.response.status_code}")
        except (ValueError, KeyError) as e:
            logger.error(f"[OpenAI] 请求数据错误: {str(e)}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"[OpenAI] 请求IO错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[OpenAI] 请求异常: {str(e)}")
            raise

    async def _stream_chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式对话实现"""
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

        for key in ["top_p", "stop", "presence_penalty", "frequency_penalty", "n"]:
            if key in gen_conf:
                request_body[key] = gen_conf[key]

        request_body.update(request_kwargs)

        try:
            url = f"{self.base_url}/chat/completions"
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
                            yield {"type": "delta", "content": content}

                    if "usage" in data:
                        yield {"type": "usage", "data": data["usage"]}

                yield {"type": "done", "content": full_content}

        except httpx.HTTPStatusError as e:
            logger.error(f"[OpenAI] 流式 HTTP 错误: {e.response.status_code}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: OpenAI API 错误: {e.response.status_code}"}
        except (ValueError, KeyError) as e:
            logger.error(f"[OpenAI] 流式请求数据错误: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
        except (OSError, IOError) as e:
            logger.error(f"[OpenAI] 流式请求IO错误: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
        except Exception as e:
            logger.error(f"[OpenAI] 流式请求异常: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
