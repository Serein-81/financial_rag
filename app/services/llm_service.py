from zhipuai import ZhipuAI
from app.core import settings


class LLMService:
    def __init__(self):
        # 1. 检查 API Key
        if not settings.ZHIPU_API_KEY:
            print("❌ 警告: 未设置 ZHIPU_API_KEY，请检查 .env 文件")
            self.client = None
        else:
            self.client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)

        # 2. 选定模型
        # 根据你的资源包截图，你有 GLM-4.7 的资源
        # 在 API 中，GLM-4.7 能力对应的是 "glm-4-plus"
        self.model_name = "glm-4-plus"
        # 备选: "glm-4-flash" (速度极快，免费/便宜)
        # 备选: "glm-4-air" (性价比高)

        # 3. 定义系统提示词 (Prompt Template)
        self.system_prompt_template = """
你是一个专业的知识库助手。请严格根据以下提供的【参考资料】来回答用户的【问题】。

⚠️ 严格遵守以下规则：
1. 你的回答必须完全基于提供的【参考资料】，不要使用你自己的外部知识库。
2. 如果参考资料中没有包含回答问题所需的信息，请直接回答“根据现有资料无法回答该问题”，不要编造。
3. 引用资料时，请尽量自然，回答要条理清晰，格式美观（使用 Markdown）。

【参考资料】：
{context}
"""

    async def get_answer(self, query: str, context_chunks: list[str]) -> str:
        """
        :param query: 用户问题
        :param context_chunks: 搜索到的几段文本列表
        :return: AI 的回答
        """
        if not self.client:
            return "AI 服务未初始化，请检查 API Key。"

        # A. 拼接上下文
        # 给每一段资料加个序号，方便 AI 区分
        context_str = "\n\n".join([f"【资料{i + 1}】: {chunk}" for i, chunk in enumerate(context_chunks)])

        # B. 填充 Prompt
        system_content = self.system_prompt_template.format(context=context_str)

        try:
            # C. 调用智谱 API
            response = self.client.chat.completions.create(
                model=self.model_name,  # 👈 这里使用的是 glm-4-plus (GLM-4.7)
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": query}
                ],
                temperature=0.1,  # RAG 场景温度设低一点，防止胡说八道
                stream=False  # 暂时不用流式输出，先做简单的
            )

            # D. 提取回答
            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return f"抱歉，AI 思考时出现了问题: {str(e)}"


# 单例导出
llm_service = LLMService()