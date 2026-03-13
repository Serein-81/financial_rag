from typing import List, Dict, Generator, Any, Optional
from app.agent_framework.llm import BaseLLMAdapter, create_llm_adapter
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM 服务 - 统一的大模型调用接口
    
    通过适配器模式支持多种大模型提供商
    切换提供商只需修改 .env 中的 LLM_PROVIDER
    """
    
    def __init__(self, adapter: Optional[BaseLLMAdapter] = None):
        """
        初始化 LLM 服务
        
        Args:
            adapter: LLM 适配器实例
                    如果为 None，则根据配置自动创建默认适配器
        """
        # 使用传入的适配器或自动创建
        self.adapter = adapter or create_llm_adapter()
        
        logger.info(f"✅ LLM 服务初始化完成")
        logger.info(f"   - 提供商: {settings.LLM_PROVIDER}")
        logger.info(f"   - 适配器: {self.adapter.__class__.__name__}")

        # 定义【结构化系统提示词】
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

        # 数据预处理
        if context_chunks:
            # 有资料：拼接资料
            formatted_context = "\n".join([f"【资料{i + 1}】: {chunk}" for i, chunk in enumerate(context_chunks)])
        else:
            # 没资料：告诉 AI 当前无资料
            formatted_context = "（当前搜索未找到直接相关的参考资料，请尝试基于对话历史或通用知识回答，但需告知用户资料缺失。）"

        # 填充 System Prompt
        system_content = self.system_prompt_template.format(context_str=formatted_context)

        # 构建完整提示词
        prompt_parts = [system_content]
        
        # 添加历史记录（只取最近 10 条）
        valid_history = [
            f"{msg['role']}: {msg['content']}"
            for msg in history
            if msg.get("content")
        ]
        if valid_history:
            prompt_parts.append("\n### 对话历史\n" + "\n".join(valid_history[-10:]))
        
        # 添加当前问题
        prompt_parts.append(f"\n### 当前问题\nuser: {query}")
        
        return "\n".join(prompt_parts)

    async def get_answer(self, query: str, context_chunks: List[str], history: List[Dict] = None) -> str:
        """
        非流式回答
        
        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史
            
        Returns:
            AI 生成的回答
        """
        try:
            # 构建提示词
            prompt = self._build_prompt(query, context_chunks, history)
            
            # 打印调试信息
            logger.info(f"🤖 [LLM] 提供商: {settings.LLM_PROVIDER} | 历史: {len(history or [])}条 | 资料: {len(context_chunks)}段")
            
            # 使用适配器生成回答
            response = await self.adapter.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=None
            )
            
            return response

        except Exception as e:
            logger.error(f"❌ LLM 调用失败: {e}")
            return "抱歉，AI 思考时遇到了技术问题，请稍后重试。"

    def get_answer_stream(self, query: str, context_chunks: List[str], history: List[Dict] = None) -> Generator[str, None, None]:
        """
        流式生成回答 (Generator)
        
        Args:
            query: 用户问题
            context_chunks: 检索到的参考资料
            history: 对话历史
            
        Yields:
            逐步生成的文本片段
        """
        try:
            # 构建提示词
            prompt = self._build_prompt(query, context_chunks, history)
            
            # 打印调试信息
            logger.info(f"🌊 [LLM Stream] 提供商: {settings.LLM_PROVIDER} | 历史: {len(history or [])}条 | 资料: {len(context_chunks)}段")
            
            # 使用适配器流式生成
            # 注意：需要在事件循环中运行异步生成器
            async_gen = self.adapter.stream_generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=None
            )
            
            # 将异步生成器转换为同步生成器
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                while True:
                    try:
                        chunk = loop.run_until_complete(async_gen.__anext__())
                        yield chunk
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"❌ 流式调用失败: {e}")
            yield f"生成出错: {str(e)}"


# 单例模式
llm_service = LLMService()
