# app/services/agent_service.py

from langchain_community.chat_models import ChatZhipuAI
from langchain.agents import create_agent
from app.core.config import settings
from langchain_core.messages import HumanMessage, AIMessage

# 引入提示词加载器（已从简单版升级到高级版）
from app.services.prompt_service import load_agent_system_prompt

# 引入工具管理模块
from app.tools import get_all_tools, get_tools_info



# ==========================================
# 🧠 2. 智能体大脑
# ==========================================
class EnterpriseAgentService:
    def __init__(self):
        # 1. 初始化大模型
        self.llm = ChatZhipuAI(
            api_key=settings.ZHIPU_API_KEY,
            model="glm-4-flash",
            temperature=0.1
            # streaming=True
        )

        # 从工具管理模块获取所有工具
        self.tools = get_all_tools()

        # 打印工具列表，确认工具已注册
        print("=" * 60)
        print("🛠️ Agent 工具初始化")
        print("=" * 60)
        for i, tool in enumerate(self.tools, 1):
            print(f"{i}. {tool.name}: {tool.description}")
        print("=" * 60)

        # 2. 读取系统提示词
        system_prompt_text = load_agent_system_prompt()

        # 👇 3. 核心修复：直接使用你的 create_agent 方法，精简、优雅、无错！
        self.agent = create_agent(
            model=self.llm,
            system_prompt=system_prompt_text,
            tools=self.tools
        )
        
        print("✅ Agent 初始化完成！")
        print("=" * 60)

    async def chat(self, user_input: str, kb_id: str, session_id: str = None, history: list = None):
        """
        供 API 路由调用的主入口
        """
        # 1. 组装消息列表 (完美契合你新版 Agent 需要的字典格式)
        messages = []

        if history:
            for msg in history:
                # 兼容历史记录格式
                role = "assistant" if msg["role"] == "assistant" else "user"
                messages.append({"role": role, "content": msg["content"]})

        # 2. 添加本次的新问题和隐式系统指令
        agent_input = (
            f"用户问题：{user_input}\n"
            f"【系统指令】：如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}"
        )
        messages.append({"role": "user", "content": agent_input})

        # 3. 组装成新版 Graph Agent 需要的 input_dict
        input_dict = {
            "messages": messages
        }

        # 4. 异步执行 Agent 并获取结果
        # ainvoke 会执行整个思考和工具调用流程，返回最终状态字典
        response = await self.agent.ainvoke(input_dict)

        # 提取最新的一条消息内容作为回答
        return response["messages"][-1].content

    # 新增流式对话方法
    async def chat_stream(self, user_input: str, kb_id: str, session_id: str, history: list):
        """流式对话生成器"""
        print(f"🌊 [Agent 流式生成开始] Session: {session_id}")

        messages = []
        if history:
            messages.extend(history)

        agent_input = (
            f"用户问题：{user_input}\n"
            f"【系统指令】：如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}"
        )
        messages.append(HumanMessage(content=agent_input))

        inputs = {"messages": messages}

        try:
            # 先非流式执行，获取完整结果（包括工具调用）
            print("🔄 [执行] 开始执行 Agent...")
            result = await self.agent.ainvoke(inputs)
            
            # 获取最终的回答
            final_message = result["messages"][-1]
            final_content = final_message.content
            
            print(f"✅ [完成] Agent 执行完成，回答长度: {len(final_content)}")
            
            # 逐字符流式输出最终结果
            for char in final_content:
                yield char
                
        except Exception as e:
            print(f"❌ 流式被中断: {e}")
            import traceback
            traceback.print_exc()
            yield f"\n[Agent 报错: {str(e)}]"

# 导出单例
agent_service = EnterpriseAgentService()