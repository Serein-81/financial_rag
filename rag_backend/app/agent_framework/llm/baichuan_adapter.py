# app/agent_framework/llm\baichuan_adapter.py

"""
BaiChuan 百川适配器

支持百川大模型 API 的 LLM 适配器实现
"""

import json
import time
import hashlib
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from .base_adapter import BaseLLMAdapter, LLMResponse
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)


class BaiChuanAdapter(BaseLLMAdapter):
    """
    BaiChuan 百川大模型适配器

    支持：
    - 非流式对话
    - 流式对话
    - 百川 2.0 系列模型
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str = "",
        model_name: str = "baichuan4",
        base_url: str = "https://api.baichuan-ai.com/v1",
        **kwargs
    ):
        """
        初始化 BaiChuan 适配器

        Args:
            api_key: 百川 API Key
            secret_key: 百川 Secret Key（用于签名）
            model_name: 模型名称
            base_url: API 基础 URL
            **kwargs: 其他配置参数
        """
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url, **kwargs)
        self.secret_key = secret_key
        self.client = None

    def _generate_signature(self, timestamp: int) -> str:
        """
        生成签名

        Args:
            timestamp: 时间戳

        Returns:
            签名字符串
        """
        sign_str = f"{self.api_key}{timestamp}{self.secret_key}"
        return hashlib.md5(sign_str.encode()).hexdigest()

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                headers={"Content-Type": "application/json"}
            )
        return self.client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None

    def _get_auth_headers(self) -> Dict[str, str]:
        """获取认证头"""
        timestamp = int(time.time())
        signature = self._generate_signature(timestamp)

        return {
            "Authorization": f" Bearer {self.api_key}",
            "X-BC-Request-Id": str(timestamp),
            "X-BC-Signature": signature,
            "X-BC-Timestamp": str(timestamp),
        }

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

        request_body = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            request_body["max_tokens"] = max_tokens

        for key in ["top_p", "with_search_optimization"]:
            if key in kwargs:
                request_body[key] = kwargs[key]

        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            headers = self._get_auth_headers()
            headers["Content-Type"] = "application/json"

            response = await client.post(url, json=request_body, headers=headers)
            response.raise_for_status()

            data = response.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
            logger.error(f"[BaiChuan] HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"BaiChuan API 错误: {e.response.status_code}")
        except Exception as e:
            logger.error(f"[BaiChuan] 请求异常: {str(e)}")
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

        request_body = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            request_body["max_tokens"] = max_tokens

        for key in ["top_p", "with_search_optimization"]:
            if key in kwargs:
                request_body[key] = kwargs[key]

        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            headers = self._get_auth_headers()
            headers["Content-Type"] = "application/json"

            async with client.stream("POST", url, json=request_body, headers=headers) as response:
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
            logger.error(f"[BaiChuan] 流式 HTTP 错误: {e.response.status_code}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: BaiChuan API 错误: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"[BaiChuan] 流式请求异常: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
