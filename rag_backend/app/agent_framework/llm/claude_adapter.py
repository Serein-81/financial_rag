# app/agent_framework/llm/claude_adapter.py

"""
Claude 适配器

支持 Anthropic Claude API 的 LLM 适配器实现
"""

from app.utils.json_compat import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from .base_adapter import BaseLLMAdapter, LLMResponse
from .model_policies import apply_model_family_policies
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)


class ClaudeAdapter(BaseLLMAdapter):
    """
    Claude 大模型适配器

    支持：
    - 非流式对话
    - 流式对话
    - Claude 3.5 Sonnet, Claude 3 Opus 等模型
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "claude-3-sonnet-20240229",
        base_url: str = "https://api.anthropic.com/v1",
        **kwargs
    ):
        """
        初始化 Claude 适配器

        Args:
            api_key: Anthropic API 密钥
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
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
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
        system = kwargs.pop("system", None)
        messages = [{"role": "user", "content": prompt}]
        return await self._chat(messages, temperature, max_tokens, system=system, **kwargs)

    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成回答"""
        system = kwargs.pop("system", None)
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self._stream_chat(messages, temperature, max_tokens, system=system, **kwargs):
            yield chunk

    async def _chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        system: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """内部对话实现"""
        client = self._get_client()

        gen_conf, request_kwargs = apply_model_family_policies(
            self.model_name,
            {"temperature": temperature, "max_tokens": max_tokens or 4096},
            kwargs
        )

        request_body = {
            "model": self.model_name,
            "messages": messages,
            "temperature": gen_conf.get("temperature", temperature),
            "max_tokens": gen_conf.get("max_tokens", max_tokens or 4096),
        }

        if system:
            request_body["system"] = system

        for key in ["top_p", "stop_sequences", "top_k"]:
            if key in gen_conf:
                request_body[key] = gen_conf[key]

        request_body.update(request_kwargs)

        try:
            url = f"{self.base_url}/messages"
            response = await client.post(url, json=request_body)
            response.raise_for_status()

            data = response.json()

            content = data.get("content", [{}])[0].get("text", "")
            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                prompt_tokens=usage.get("input_tokens"),
                completion_tokens=usage.get("output_tokens"),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                model=data.get("model", self.model_name),
                finish_reason=data.get("stop_reason")
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"[Claude] HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Claude API 错误: {e.response.status_code}")
        except (ValueError, KeyError) as e:
            logger.error(f"[Claude] 请求数据错误: {str(e)}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"[Claude] 请求IO错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Claude] 请求异常: {str(e)}")
            raise

    async def _stream_chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        system: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式对话实现"""
        client = self._get_client()

        gen_conf, request_kwargs = apply_model_family_policies(
            self.model_name,
            {"temperature": temperature, "max_tokens": max_tokens or 4096},
            kwargs
        )

        request_body = {
            "model": self.model_name,
            "messages": messages,
            "temperature": gen_conf.get("temperature", temperature),
            "max_tokens": gen_conf.get("max_tokens", max_tokens or 4096),
            "stream": True,
        }

        if system:
            request_body["system"] = system

        for key in ["top_p", "stop_sequences", "top_k"]:
            if key in gen_conf:
                request_body[key] = gen_conf[key]

        request_body.update(request_kwargs)

        try:
            url = f"{self.base_url}/messages"
            async with client.stream("POST", url, json=request_body) as response:
                response.raise_for_status()

                full_content = ""
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    if line.startswith("data: "):
                        line = line[6:]

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        content = delta.get("text", "")

                        if content:
                            full_content += content
                            yield {"type": "delta", "content": content}

                    elif data.get("type") == "message_delta":
                        usage = data.get("usage", {})
                        yield {"type": "usage", "data": usage}

                    elif data.get("type") == "message_stop":
                        break

                yield {"type": "done", "content": full_content}

        except httpx.HTTPStatusError as e:
            logger.error(f"[Claude] 流式 HTTP 错误: {e.response.status_code}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: Claude API 错误: {e.response.status_code}"}
        except (ValueError, KeyError) as e:
            logger.error(f"[Claude] 流式请求数据错误: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
        except (OSError, IOError) as e:
            logger.error(f"[Claude] 流式请求IO错误: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
        except Exception as e:
            logger.error(f"[Claude] 流式请求异常: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
