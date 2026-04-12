# app/agent_framework/llm/huggingface_adapter.py

"""
HuggingFace 适配器

支持 HuggingFace Inference API 的 LLM 适配器实现
"""

import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from .base_adapter import BaseLLMAdapter, LLMResponse
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)


class HuggingFaceAdapter(BaseLLMAdapter):
    """
    HuggingFace 大模型适配器

    支持：
    - 非流式对话
    - 流式对话
    - 各类 HuggingFace 模型
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "meta-llama/Llama-3.1-8B-Instruct",
        base_url: str = "https://api-inference.huggingface.co/models",
        **kwargs
    ):
        """
        初始化 HuggingFace 适配器

        Args:
            api_key: HuggingFace API 密钥
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
        request_body = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": max_tokens or 512,
                "return_full_text": False,
            }
        }

        request_body["parameters"].update(kwargs)

        try:
            client = self._get_client()
            url = f"{self.base_url}/{self.model_name}"

            response = await client.post(url, json=request_body)
            response.raise_for_status()

            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                content = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                content = data.get("generated_text", "")
            else:
                content = str(data)

            return LLMResponse(
                content=content,
                model=self.model_name
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"[HuggingFace] HTTP 错误: {e.response.status_code}")
            raise Exception(f"HuggingFace API 错误: {e.response.status_code}")
        except (ValueError, KeyError) as e:
            logger.error(f"[HuggingFace] 请求数据错误: {str(e)}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"[HuggingFace] 请求IO错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[HuggingFace] 请求异常: {str(e)}")
            raise

    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成回答"""
        request_body = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": max_tokens or 512,
                "return_full_text": False,
                "stream": True,
            }
        }

        request_body["parameters"].update(kwargs)

        try:
            client = self._get_client()
            url = f"{self.base_url}/{self.model_name}"

            async with client.stream("POST", url, json=request_body) as response:
                response.raise_for_status()

                full_content = ""
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if isinstance(data, list) and len(data) > 0:
                        token = data[0].get("token", {})
                        content = token.get("text", "")

                        if content:
                            full_content += content
                            yield {"type": "delta", "content": content}

                yield {"type": "done", "content": full_content}

        except httpx.HTTPStatusError as e:
            logger.error(f"[HuggingFace] 流式 HTTP 错误: {e.response.status_code}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: HuggingFace API 错误: {e.response.status_code}"}
        except (ValueError, KeyError) as e:
            logger.error(f"[HuggingFace] 流式请求数据错误: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
        except (OSError, IOError) as e:
            logger.error(f"[HuggingFace] 流式请求IO错误: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}
        except Exception as e:
            logger.error(f"[HuggingFace] 流式请求异常: {str(e)}")
            yield {"type": "error", "content": f"{ERROR_PREFIX}: {str(e)}"}

    async def _chat(self, messages, temperature, max_tokens, **kwargs):
        """HuggingFace 不直接支持对话格式，使用 generate 方法"""
        content = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        return await self.generate(content, temperature, max_tokens, **kwargs)

    async def _stream_chat(self, messages, temperature, max_tokens, **kwargs):
        """HuggingFace 不直接支持对话格式，使用 stream_generate 方法"""
        content = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        async for chunk in self.stream_generate(content, temperature, max_tokens, **kwargs):
            yield chunk
