# app/agent_framework/llm/gpt_adapter.py

"""
GPT 专属适配器 (OpenRouter API)

支持通过 OpenRouter API 调用 GPT 模型
参考 MiniMax 和智谱适配器的设计实现
"""

from app.utils.json_compat import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from app.core.config import settings
from .base_adapter import BaseLLMAdapter, LLMResponse
from .model_policies import apply_model_family_policies
from .errors import ERROR_PREFIX

logger = logging.getLogger(__name__)

_langsmith_tracer = None


def _get_langsmith_tracer():
    """获取 LangSmith 追踪器（延迟初始化）"""
    global _langsmith_tracer
    if _langsmith_tracer is None:
        try:
            from app.langsmith_integration import get_tracer
            _langsmith_tracer = get_tracer()
        except (ValueError, KeyError) as e:
            logger.warning(f"[GPT] 无法加载 LangSmith 追踪器(数据错误): {e}")
            _langsmith_tracer = None
        except (OSError, IOError) as e:
            logger.warning(f"[GPT] 无法加载 LangSmith 追踪器(IO错误): {e}")
            _langsmith_tracer = None
        except Exception as e:
            logger.warning(f"[GPT] 无法加载 LangSmith 追踪器: {e}")
            _langsmith_tracer = None
    return _langsmith_tracer


class GPTAdapter(BaseLLMAdapter):
    """
    GPT 大模型适配器 (支持 OpenRouter)

    支持：
    - 非流式对话
    - 流式对话
    - 工具调用（Function Calling）
    - 推理模型支持 (reasoning 参数)
    - OpenRouter 兼容
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "openai/gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        **kwargs
    ):
        """
        初始化 GPT 适配器

        Args:
            api_key: API 密钥
            model_name: 模型名称（支持 openai/gpt-4.5 系列）
            base_url: API 基础 URL（支持 OpenAI 兼容端点）
            **kwargs: 其他配置参数
        """
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url, **kwargs)
        self.client = None
        logger.info("✅ GPT 适配器初始化完成")
        logger.info(f"   - 模型: {self.model_name}")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - API Key: {self.api_key[:12]}...{self.api_key[-4:]}")

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self.client is None:
            verify_ssl_config = getattr(settings, 'GPT_VERIFY_SSL', True)
            if isinstance(verify_ssl_config, str):
                verify_ssl = verify_ssl_config.lower() not in ('false', '0', 'no', 'off')
            else:
                verify_ssl = bool(verify_ssl_config)
            
            logger.info(f"[GPT] 创建HTTP客户端, verify_ssl={verify_ssl} (原始值: {verify_ssl_config})")
            
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

    async def chat(
        self,
        messages: list,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        对话接口（兼容多轮对话格式）

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        logger.info(f"💬 [GPT] 对话调用: {self.model_name}")
        logger.info(f"    消息数量: {len(messages)}")
        logger.info(f"    温度: {temperature}")
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
            **kwargs: 其他参数，支持 reasoning={"enabled": True} 用于 OpenRouter

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

        reasoning = kwargs.pop("reasoning", None)
        if reasoning:
            request_body["extra_body"] = {"reasoning": reasoning}

        extra_body = kwargs.pop("extra_body", None)
        if extra_body:
            if "extra_body" not in request_body:
                request_body["extra_body"] = {}
            request_body["extra_body"].update(extra_body)

        request_body.update(request_kwargs)

        try:
            url = f"{self.base_url}/chat/completions"
            logger.info(f"[GPT] 发起请求: {url}")

            response = await client.post(url, json=request_body)
            response.raise_for_status()

            data = response.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            usage = data.get("usage", {})

            llm_response = LLMResponse(
                content=content,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                model=data.get("model", self.model_name),
                finish_reason=data.get("choices", [{}])[0].get("finish_reason")
            )

            logger.info(f"✅ [GPT] 生成完成，长度: {len(content)} 字符")
            if usage:
                logger.info(f"    Token: prompt={usage.get('prompt_tokens')}, completion={usage.get('completion_tokens')}, total={usage.get('total_tokens')}")

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
            logger.error(f"[GPT] HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GPT API 错误: {e.response.status_code}")
        except (ValueError, KeyError) as e:
            logger.error(f"[GPT] 请求数据错误: {str(e)}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"[GPT] 请求IO错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[GPT] 请求异常: {str(e)}")
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

        try:
            url = f"{self.base_url}/chat/completions"
            logger.info(f"[GPT] 发起流式请求: {url}")

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

                logger.info(f"[GPT] 流式响应完成，总长度: {len(full_content)} 字符")
                if len(full_content) < 2000:
                    logger.info(f"[GPT] 完整响应内容:\n{full_content}")
                else:
                    logger.info(f"[GPT] 完整响应内容(前1000字符):\n{full_content[:1000]}")

                yield {
                    "type": "done",
                    "content": full_content
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"[GPT] 流式 HTTP 错误: {e.response.status_code}")
            yield {
                "type": "error",
                "content": f"{ERROR_PREFIX}: GPT API 错误: {e.response.status_code}"
            }
        except (ValueError, KeyError) as e:
            logger.error(f"[GPT] 流式请求数据错误: {str(e)}")
            yield {
                "type": "error",
                "content": f"{ERROR_PREFIX}: {str(e)}"
            }
        except (OSError, IOError) as e:
            logger.error(f"[GPT] 流式请求IO错误: {str(e)}")
            yield {
                "type": "error",
                "content": f"{ERROR_PREFIX}: {str(e)}"
            }
        except Exception as e:
            logger.error(f"[GPT] 流式请求异常: {str(e)}")
            yield {
                "type": "error",
                "content": f"{ERROR_PREFIX}: {str(e)}"
            }
