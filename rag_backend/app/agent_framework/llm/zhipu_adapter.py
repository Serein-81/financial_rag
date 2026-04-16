# app/agent_framework/llm/zhipu_adapter.py

"""
智谱 AI 适配器

封装智谱 AI 的调用逻辑
"""

from typing import AsyncGenerator, Optional, Dict, Any
try:
    from zhipuai import ZhipuAI
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    ZhipuAI = None

from .base_adapter import BaseLLMAdapter, LLMResponse


class ZhipuAdapter(BaseLLMAdapter):
    """
    智谱 AI 适配器

    封装智谱 AI 的 API 调用
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "glm-4-flash",
        **kwargs
    ):
        """
        初始化智谱 AI 适配器

        Args:
            api_key: API 密钥
            model_name: 模型名称
            **kwargs: 其他配置
        """
        super().__init__(model_name, **kwargs)

        if not ZHIPU_AVAILABLE:
            raise ImportError("zhipuai 包未安装，请运行: pip install zhipuai")

        if not api_key:
            raise ValueError("智谱 AI API Key 不能为空")

        self.client = ZhipuAI(api_key=api_key)
        self.api_key = api_key

        # 只在首次初始化时打印详细信息
        if not getattr(ZhipuAdapter, '_initialized', False):
            ZhipuAdapter._initialized = True
            print("✅ 智谱 AI 适配器初始化完成")
            print(f"   - 模型: {self.model_name}")
            print(f"   - API Key: {api_key[:8]}...{api_key[-4:]}")

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
        try:
            messages = [{"role": "user", "content": prompt}]

            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            request_params.update(kwargs)

            print(f"🤖 [智谱AI] 调用模型: {self.model_name}")
            print(f"    提示词长度: {len(prompt)} 字符")
            print(f"    温度: {temperature}")

            response = self.client.chat.completions.create(**request_params)

            content = response.choices[0].message.content
            usage = response.usage

            print(f"✅ [智谱AI] 生成完成，长度: {len(content)} 字符")
            if usage:
                print(f"    Token: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")

            return LLMResponse(
                content=content,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
            )

        except (ValueError, KeyError) as e:
            error_msg = f"智谱 AI 调用数据错误: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            raise Exception(error_msg)
        except (OSError, IOError) as e:
            error_msg = f"智谱 AI 调用IO错误: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"智谱 AI 调用失败: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            raise Exception(error_msg)

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
            Dict，包含 "delta" 文本片段和最后的 "usage" token统计
        """
        try:
            messages = [{"role": "user", "content": prompt}]

            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            request_params.update(kwargs)

            print(f"🌊 [智谱AI] 流式调用: {self.model_name}")
            print(f"    提示词长度: {len(prompt)} 字符")

            response = self.client.chat.completions.create(**request_params)

            total_chars = 0
            full_content = []
            usage = None

            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_chars += len(content)
                    full_content.append(content)
                    yield {"delta": content}

                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = chunk.usage

            print(f"✅ [智谱AI] 流式生成完成，总长度: {total_chars} 字符")

            if usage:
                print(f"    Token: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
                yield {
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                    "model": self.model_name,
                }

        except (ValueError, KeyError) as e:
            error_msg = f"智谱 AI 流式调用数据错误: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            yield {"delta": f"[错误: {error_msg}]"}
        except (OSError, IOError) as e:
            error_msg = f"智谱 AI 流式调用IO错误: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            yield {"delta": f"[错误: {error_msg}]"}
        except Exception as e:
            error_msg = f"智谱 AI 流式调用失败: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            yield {"delta": f"[错误: {error_msg}]"}

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
        try:
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            request_params.update(kwargs)

            print(f"💬 [智谱AI] 对话调用: {self.model_name}")
            print(f"    消息数量: {len(messages)}")
            print(f"    温度: {temperature}")

            response = self.client.chat.completions.create(**request_params)

            content = response.choices[0].message.content
            usage = response.usage

            print(f"✅ [智谱AI] 对话完成，长度: {len(content)} 字符")
            if usage:
                print(f"    Token: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")

            return LLMResponse(
                content=content,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                model=self.model_name,
            )

        except Exception as e:
            error_msg = f"智谱 AI 对话调用失败: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            raise Exception(error_msg)

    async def _chat(
        self,
        messages: list,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> LLMResponse:
        """
        内部对话实现（由基类调用）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        try:
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            request_params.update(kwargs)

            response = self.client.chat.completions.create(**request_params)

            content = response.choices[0].message.content
            usage = response.usage

            return LLMResponse(
                content=content,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                model=self.model_name,
            )

        except Exception as e:
            error_msg = f"智谱 AI _chat 调用失败: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            raise Exception(error_msg)