from typing import List, Dict, Generator, Any, Optional
from app.agent_framework.llm import (
    BaseLLMAdapter, 
    create_llm_adapter, 
    LLMResponse,
    LLMError,
    ErrorClassifier,
    get_length_notification,
    num_tokens_from_string
)
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)


class LLMAnswerResult:
    """LLM 回答结果，包含文本和 token 统计"""

    def __init__(
        self,
        content: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        model: Optional[str] = None,
        is_truncated: bool = False,
        error_info: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model = model
        self.is_truncated = is_truncated
        self.error_info = error_info

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "is_truncated": self.is_truncated,
            "error_info": self.error_info,
        }


class LLMService:
    """
    LLM 服务 - 统一的大模型调用接口
    
    通过适配器模式支持多种大模型提供商
    切换提供商只需修改 .env 中的 LLM_PROVIDER
    
    支持的特性：
    - 多提供商：zhipu, openai, claude, minimax, xinference, huggingface, modelscope, baichuan
    - 错误重试：自动重试可恢复的错误
    - Token 统计：精确统计 token 使用量
    - 截断通知：上下文截断时自动提示
    """

    # 截断关键词（用于检测响应是否被截断）
    TRUNCATION_KEYWORDS = [
        "由于上下文长度限制",
        "由于大模型上下文窗口限制", 
        "由于会话长度限制",
        "context length limit",
        "maximum context length",
        "exceeds the context window",
        "truncated"
    ]

    def __init__(self, adapter: Optional[BaseLLMAdapter] = None):
        """
        初始化 LLM 服务
        
        Args:
            adapter: LLM 适配器实例
                    如果为 None，则根据配置自动创建默认适配器
        """
        self.adapter = adapter or create_llm_adapter()
        
        logger.info(f"LLM 服务初始化完成")
        logger.info(f"   - 提供商: {settings.LLM_PROVIDER}")
        logger.info(f"   - 适配器: {self.adapter.__class__.__name__}")
        logger.info(f"   - 模型: {self.adapter.model_name}")
        logger.info(f"   - 最大重试次数: {self.adapter.max_retries}")
        logger.info(f"   - 超时时间: {self.adapter.timeout}s")

        self.system_prompt_template = """
### 角色定义
你是一名专业的智能助手。你拥有一个外部知识库（参考资料）和一段对话记忆（对话历史）。

### 核心思考逻辑 (Priority)
1.  **优先检索**: 如果用户的问题需要依靠【参考资料】（如具体事实、政策、数据），请优先基于资料回答。
2.  **兼顾历史**: 如果用户的问题是关于上下文的（如"我刚才说了什么"、"继续"、"那个已生效吗"），请必须结合【对话历史】进行回答。
3.  **诚实原则**: 如果问题既不在资料里，也不在历史里（比如问"今天天气"但资料里没有），请告知无法回答。

### 回答规范
- 使用 Markdown 格式。
- 引用来源：如果使用了【参考资料】中的内容，请在句尾标注 `[资料X]`。如果仅基于历史回答，无需标注。
- 语气：专业、客观。

### 输入数据
以下是检索到的参考资料片段：
{context_str}
"""

    def _estimate_prompt_tokens(self, prompt: str) -> int:
        """估算提示词的 token 数量"""
        return num_tokens_from_string(prompt)

    def _is_truncated_response(self, content: str) -> bool:
        """检测响应是否被截断"""
        if not content:
            return False
        content_lower = content.lower()
        for keyword in self.TRUNCATION_KEYWORDS:
            if keyword.lower() in content_lower:
                return True
        return False

    def _append_truncation_notification(self, content: str, is_chinese: bool = True) -> str:
        """追加截断通知"""
        if self._is_truncated_response(content):
            return content
        notification = get_length_notification([content])
        return content + notification

    def _handle_error(self, error: Exception, provider: str) -> str:
        """处理 LLM 调用错误"""
        llm_error = ErrorClassifier.create_llm_error(error)
        error_info = {
            "code": llm_error.code.value,
            "message": str(error),
            "retryable": llm_error.retryable
        }
        
        logger.error(f"[LLM Error] 提供商: {provider} | 错误码: {llm_error.code.value} | 可重试: {llm_error.retryable}")
        logger.error(f"   错误详情: {str(error)[:200]}")
        
        if llm_error.code.value == "ERROR_MAX_RETRIES":
            return "抱歉，AI 服务暂时繁忙，已超过最大重试次数，请稍后重试。"
        elif llm_error.code.value == "ERROR_RATE_LIMIT":
            return "抱歉，AI 服务请求过于频繁，请稍后重试。"
        elif llm_error.code.value == "ERROR_QUOTA":
            return "抱歉，AI 服务配额已用尽，请联系管理员。"
        elif llm_error.code.value == "ERROR_AUTHENTICATION":
            return "抱歉，AI 服务认证失败，请检查配置。"
        elif llm_error.code.value == "ERROR_TIMEOUT":
            return "抱歉，AI 服务响应超时，请稍后重试。"
        else:
            return f"抱歉，AI 思考时遇到了问题（错误码：{llm_error.code.value}），请稍后重试。"

    def _build_prompt(self, query: str, context_chunks: List[str], history: List[Dict]) -> str:
        """
        构建完整的提示词
        
        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史
            
        Returns:
            格式化的提示词
        """
        if history is None:
            history = []

        if context_chunks:
            formatted_context = "\n".join([f"【资料{i + 1}】: {chunk}" for i, chunk in enumerate(context_chunks)])
        else:
            formatted_context = "（当前搜索未找到直接相关的参考资料，请尝试基于对话历史或通用知识回答，但需告知用户资料缺失。）"

        system_content = self.system_prompt_template.format(context_str=formatted_context)

        prompt_parts = [system_content]
        
        valid_history = [
            f"{msg['role']}: {msg['content']}"
            for msg in history
            if msg.get("content")
        ]
        if valid_history:
            prompt_parts.append("\n### 对话历史\n" + "\n".join(valid_history[-10:]))
        
        prompt_parts.append(f"\n### 当前问题\nuser: {query}")
        
        return "\n".join(prompt_parts)

    async def get_answer(
        self, 
        query: str, 
        context_chunks: List[str], 
        history: List[Dict] = None,
        add_truncation_notification: bool = True
    ) -> str:
        """
        非流式回答

        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史
            add_truncation_notification: 是否添加截断通知

        Returns:
            AI 生成的回答
        """
        try:
            prompt = self._build_prompt(query, context_chunks, history)
            estimated_tokens = self._estimate_prompt_tokens(prompt)

            logger.info(f"[LLM] 提供商: {settings.LLM_PROVIDER} | 历史: {len(history or [])}条 | 资料: {len(context_chunks)}段 | 估算Token: {estimated_tokens}")

            llm_response = await self.adapter.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=None
            )

            if isinstance(llm_response, LLMResponse):
                content = llm_response.content
                if add_truncation_notification and self._is_truncated_response(content):
                    content = self._append_truncation_notification(content)
                return content
            return llm_response

        except Exception as e:
            return self._handle_error(e, settings.LLM_PROVIDER)

    async def get_answer_with_usage(
        self,
        query: str,
        context_chunks: List[str],
        history: List[Dict] = None,
        add_truncation_notification: bool = True
    ) -> LLMAnswerResult:
        """
        非流式回答（包含 token 使用量）

        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史
            add_truncation_notification: 是否添加截断通知

        Returns:
            LLMAnswerResult 对象，包含回答文本和 token 统计
        """
        try:
            prompt = self._build_prompt(query, context_chunks, history)
            estimated_tokens = self._estimate_prompt_tokens(prompt)

            logger.info(f"[LLM+Usage] 提供商: {settings.LLM_PROVIDER} | 历史: {len(history or [])}条 | 资料: {len(context_chunks)}段 | 估算Token: {estimated_tokens}")

            llm_response = await self.adapter.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=None
            )

            if isinstance(llm_response, LLMResponse):
                content = llm_response.content
                is_truncated = self._is_truncated_response(content)
                if add_truncation_notification and is_truncated:
                    content = self._append_truncation_notification(content)
                
                return LLMAnswerResult(
                    content=content,
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    total_tokens=llm_response.total_tokens,
                    model=llm_response.model or self.adapter.model_name,
                    is_truncated=is_truncated
                )
            return LLMAnswerResult(content=llm_response)

        except Exception as e:
            error_msg = self._handle_error(e, settings.LLM_PROVIDER)
            llm_error = ErrorClassifier.create_llm_error(e)
            return LLMAnswerResult(
                content=error_msg,
                error_info={
                    "code": llm_error.code.value,
                    "retryable": llm_error.retryable
                }
            )

    async def stream_answer_with_usage(
        self,
        query: str,
        context_chunks: List[str],
        history: List[Dict] = None
    ) -> tuple:
        """
        流式回答（包含 token 使用量）

        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史

        Returns:
            (async_generator, usage_dict) 元组
            generator 产生文本片段，最后一条包含 usage 信息
        """
        try:
            prompt = self._build_prompt(query, context_chunks, history)
            estimated_tokens = self._estimate_prompt_tokens(prompt)

            logger.info(f"[LLM Stream+Usage] 提供商: {settings.LLM_PROVIDER} | 历史: {len(history or [])}条 | 资料: {len(context_chunks)}段 | 估算Token: {estimated_tokens}")

            accumulated_content = []
            usage_info = {}

            async def async_gen():
                nonlocal usage_info
                try:
                    async for chunk in self.adapter.stream_generate(
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=None
                    ):
                        delta = chunk.get("delta", "")
                        if delta:
                            accumulated_content.append(delta)
                            yield chunk
                        
                        if "usage" in chunk:
                            usage_info = chunk["usage"]
                    
                    if accumulated_content:
                        full_content = "".join(accumulated_content)
                        if self._is_truncated_response(full_content):
                            notification = get_length_notification(accumulated_content)
                            yield {"delta": notification, "is_truncated": True}
                    
                    yield {"usage": usage_info}
                        
                except Exception as e:
                    error_msg = self._handle_error(e, settings.LLM_PROVIDER)
                    yield {"delta": error_msg, "error": True}

            return async_gen, None

        except Exception as e:
            logger.error(f"流式调用失败: {e}")

            async def error_gen():
                error_msg = self._handle_error(e, settings.LLM_PROVIDER)
                yield {"delta": error_msg, "error": True}

            return error_gen, None

    def get_answer_stream(
        self, 
        query: str, 
        context_chunks: List[str], 
        history: List[Dict] = None,
        add_truncation_notification: bool = True
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式生成回答 (Generator)

        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史
            add_truncation_notification: 是否添加截断通知

        Yields:
            Dict，包含 "delta" 文本片段，最后一条包含 "usage" token统计
        """
        try:
            prompt = self._build_prompt(query, context_chunks, history)
            estimated_tokens = self._estimate_prompt_tokens(prompt)

            logger.info(f"[LLM Stream] 提供商: {settings.LLM_PROVIDER} | 历史: {len(history or [])}条 | 资料: {len(context_chunks)}段 | 估算Token: {estimated_tokens}")

            async_gen = self.adapter.stream_generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=None
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            accumulated_content = []

            try:
                while True:
                    try:
                        chunk = loop.run_until_complete(async_gen.__anext__())
                        
                        delta = chunk.get("delta", "")
                        if delta:
                            accumulated_content.append(delta)
                        
                        if add_truncation_notification:
                            yield chunk
                        else:
                            if "usage" not in chunk:
                                yield chunk
                            
                    except StopAsyncIteration:
                        if add_truncation_notification and accumulated_content:
                            full_content = "".join(accumulated_content)
                            if self._is_truncated_response(full_content):
                                notification = get_length_notification(accumulated_content)
                                yield {"delta": notification, "is_truncated": True}
                        break
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"流式调用失败: {e}")
            error_msg = self._handle_error(e, settings.LLM_PROVIDER)
            yield {"delta": error_msg, "error": True}


llm_service = LLMService()
