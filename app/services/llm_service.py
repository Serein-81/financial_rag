from typing import List, Dict, Generator, Any
from zhipuai import ZhipuAI
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class LLMService:
    def __init__(self):
        # 1. 检查 API Key (使用 os.getenv 更通用)
        self.api_key = os.getenv("ZHIPU_API_KEY")
        if not self.api_key:
            print("❌ 警告: 未设置 ZHIPU_API_KEY，请检查 .env 文件")
            self.client = None
        else:
            self.client = ZhipuAI(api_key=self.api_key)

        # 2. 选定模型
        self.model_name = "glm-4-plus"

        # 3. 定义【结构化系统提示词】
        self.system_prompt_template = """
### 角色定义
你是一名专业的智能助手。你拥有一个外部知识库（参考资料）和一段对话记忆（对话历史）。

### 核心思考逻辑 (Priority)
1.  **优先检索**: 如果用户的问题需要依靠【参考资料】（如具体事实、政策、数据），请优先基于资料回答。
2.  **兼顾历史**: 如果用户的问题是关于上下文的（如“我刚才说了什么”、“继续”、“那个已生效吗”），请必须结合【对话历史】进行回答。
3.  **诚实原则**: 如果问题既不在资料里，也不在历史里（比如问“今天天气”但资料里没有），请告知无法回答。

### 回答规范
- 使用 Markdown 格式。
- 引用来源：如果使用了【参考资料】中的内容，请在句尾标注 `[资料X]`。如果仅基于历史回答，无需标注。
- 语气：专业、客观。

### 输入数据
以下是检索到的参考资料片段：
{context_str}
"""

    def _build_messages(self, query: str, context_chunks: List[str], history: List[Dict]) -> List[Dict]:
        """
        内部辅助方法：构建发送给 LLM 的完整消息链
        """
        if history is None:
            history = []

        # --- A. 数据预处理 (关键修改：不要直接返回，而是填充占位符) ---
        if context_chunks:
            # 有资料：拼接资料
            formatted_context = "\n".join([f"【资料{i + 1}】: {chunk}" for i, chunk in enumerate(context_chunks)])
        else:
            # 没资料：告诉 AI 当前无资料，迫使它去看历史
            formatted_context = "（当前搜索未找到直接相关的参考资料，请尝试基于对话历史或通用知识回答，但需告知用户资料缺失。）"

        # --- B. 填充 System Prompt ---
        system_content = self.system_prompt_template.format(context_str=formatted_context)

        # --- C. 构建消息链 ---
        messages = [{"role": "system", "content": system_content}]

        # 插入历史记录 (只取最近 10 条，防止 Token 溢出)
        # 过滤掉内容为空的消息
        valid_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg.get("content")
        ]
        messages.extend(valid_history[-10:])  # 增加一点历史长度，方便长对话

        # 插入当前问题
        messages.append({"role": "user", "content": query})

        return messages

    async def get_answer(self, query: str, context_chunks: List[str], history: List[Dict] = None) -> str:
        """非流式回答"""
        if not self.client:
            return "AI 服务未初始化，请检查 API Key。"

        try:
            # 1. 构建消息
            messages = self._build_messages(query, context_chunks, history)

            # 2. 打印调试信息
            print(f"🤖 [LLM] 模型: {self.model_name} | 历史: {len(messages) - 2}条 | 资料: {len(context_chunks)}段")

            # 3. 调用 API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,  # 稍微给一点点创造性，防止太死板
                top_p=0.7,
                stream=False
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return "抱歉，AI 思考时遇到了技术问题，请稍后重试。"

    def get_answer_stream(self, query: str, context_chunks: List[str], history: List[Dict] = None) -> Generator[
        str, None, None]:
        """流式生成回答 (Generator)"""
        if not self.client:
            yield "AI 服务未初始化"
            return

        try:
            # 1. 构建消息 (复用逻辑)
            messages = self._build_messages(query, context_chunks, history)

            # 2. 打印调试信息
            print(f"🤖 [LLM Stream] 历史: {len(messages) - 2}条 | 资料: {len(context_chunks)}段")

            # 3. 流式调用
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                top_p=0.7,
                stream=True
            )

            # 4. 逐个字抛出
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"❌ 流式调用失败: {e}")
            yield f"生成出错: {str(e)}"


# 单例模式
llm_service = LLMService()
