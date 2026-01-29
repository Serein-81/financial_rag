from typing import List, Dict, Optional
from zhipuai import ZhipuAI
from app.core.config import settings


class LLMService:
    def __init__(self):
        # 1. 检查 API Key
        if not settings.ZHIPU_API_KEY:
            print("❌ 警告: 未设置 ZHIPU_API_KEY，请检查 .env 文件")
            self.client = None
        else:
            self.client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)

        # 2. 选定模型 (使用你的最强模型 GLM-4-Plus)
        self.model_name = "glm-4-plus"

        # 3. 定义【结构化系统提示词】 (System Prompt)
        # 这种写法被称为 "Structured Prompting"，能大幅提升模型遵循指令的能力
        self.system_prompt_template = """
### 角色定义
你是一名极其专业、严谨的知识库问答专家。你的任务是根据给定的【参考资料】和【对话历史】，精准回答用户的【问题】。

### 核心原则 (必须严格遵守)
1.  **事实导向**：你的所有回答必须 **100% 基于提供的【参考资料】**。严禁使用你训练数据中的外部知识，严禁编造事实。
2.  **诚实拒答**：如果【参考资料】中没有包含回答问题所需的信息，请直接回复：“抱歉，当前的知识库中未找到相关信息。”，不要尝试强行回答。
3.  **引用标注**：在回答的关键观点后，如果可能，请简短标注来源（例如：根据[资料1]...）。
4.  **语言风格**：保持专业、客观、简洁。避免使用口语化或情绪化的表达。

### 回答格式要求
- 使用 **Markdown** 格式。
- 对于复杂的流程或多点信息，**必须使用无序列表或有序列表**。
- 对关键术语或重点结论进行 **加粗** 处理。
- 结构清晰：先给出核心结论，再展开详细说明。

### 输入数据
以下是本次查询检索到的参考资料片段：
{context_str}
"""

    async def get_answer(self, query: str, context_chunks: list[str], history: List[Dict] = None) -> str:
        """
        :param query: 用户当前问题
        :param context_chunks: 搜索到的参考资料
        :param history: 历史对话记录
        :return: AI 回答
        """
        if not self.client:
            return "AI 服务未初始化，请检查 API Key。"

        if history is None:
            history = []

        # --- A. 数据预处理 ---
        # 拼接参考资料，保留序号，方便 AI 引用
        if not context_chunks:
            # 如果完全没有搜到资料，直接返回预设话术，省钱省 Token
            return "抱歉，知识库中没有找到相关内容，请尝试更换关键词。"

        formatted_context = "\n".join([f"【资料{i + 1}】: {chunk}" for i, chunk in enumerate(context_chunks)])

        # --- B. 填充 System Prompt ---
        system_content = self.system_prompt_template.format(context_str=formatted_context)

        # --- C. 构建消息链 ---
        messages = [{"role": "system", "content": system_content}]

        # 插入历史记录 (过滤空消息，防止报错)
        # 我们只取最近的 4 轮对话，防止 Token 溢出
        valid_history = [msg for msg in history if msg.get("content")]
        messages.extend(valid_history[-4:])

        # 插入当前问题
        messages.append({"role": "user", "content": query})

        try:
            # --- D. 调用 API ---
            print(f"🤖 [LLM] 模型: {self.model_name} | 历史: {len(valid_history)}条 | 资料: {len(context_chunks)}段")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.05,  # 极低温度，最大程度减少幻觉
                top_p=0.7,  # 稍微收缩采样范围，保证逻辑性
                stream=False
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return "抱歉，AI 思考时遇到了技术问题，请稍后重试。"


# 单例导出
llm_service = LLMService()