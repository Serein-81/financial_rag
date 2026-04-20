# app/agent_framework/llm/deepseek_adapter.py

"""
DeepSeek 专属适配器 (OpenRouter API)

支持通过 OpenRouter API 调用 DeepSeek 模型
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
            logger.warning(f"[DeepSeek] 无法加载 LangSmith 追踪器(数据错误): {e}")
            _langsmith_tracer = None
        except (OSError, IOError) as e:
            logger.warning(f"[DeepSeek] 无法加载 LangSmith 追踪器(IO错误): {e}")
            _langsmith_tracer = None
        except Exception as e:
            logger.warning(f"[DeepSeek] 无法加载 LangSmith 追踪器: {e}")
            _langsmith_tracer = None
    return _langsmith_tracer


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
        logger.info("✅ DeepSeek 适配器初始化完成")
        logger.info(f"   - 模型: {self.model_name}")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - API Key: {self.api_key[:12]}...{self.api_key[-4:]}")

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
        client = self._get_client()

        gen_conf, request_kwargs = apply_model_family_policies(
            self.model_name,
            {"temperature": temperature, "max_tokens": max_tokens},
            kwargs
        )

        model = kwargs.pop("model", None) or self.model_name

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

        try:
            url = f"{self.base_url}/chat/completions"
            logger.info(f"[DeepSeek] 发起请求: {url}")

            response = await client.post(url, json=request_body)
            response.raise_for_status()

            logger.info("[DeepSeek] 收到响应，准备解析...")

            result = response.json()

            logger.info(f"[DeepSeek] 响应解析完成，内容长度: {len(str(result))}")

            tracer = _get_langsmith_tracer()
            if tracer and self.enable_langsmith:
                try:
                    await tracer.log_llm_run(
                        model=self.model_name,
                        messages=messages,
                        response=result
                    )
                except Exception as e:
                    logger.warning(f"[DeepSeek] LangSmith 追踪失败: {e}")

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
                            
                            # 调试：前10个API chunk打印日志
                            if chunk_count <= 10:
                                logger.info(f"[DeepSeek] API返回chunk #{chunk_count}: '{content[:30]}...' (累计: {len(full_content)} 字符)")
                            elif chunk_count == 11:
                                logger.info(f"[DeepSeek] API返回完成，共 {chunk_count} 个chunks (总长度: {len(full_content)})")
                            
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

                logger.info(f"[DeepSeek] 流式响应完成 | API chunks: {chunk_count} | 实际输出: {total_chars_yielded} 字符")

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"[DeepSeek] 流式HTTP错误: {error_msg}")
            yield f"{ERROR_PREFIX}DeepSeek API 错误: {error_msg}"
        except Exception as e:
            logger.error(f"[DeepSeek] 流式请求异常: {str(e)}")
            yield f"{ERROR_PREFIX}DeepSeek 请求失败: {str(e)}"
