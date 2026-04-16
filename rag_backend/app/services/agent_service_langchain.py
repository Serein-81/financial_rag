# app/services/agent_service_langchain.py

"""
LangChain 版本的 Agent 服务

此文件已废弃，功能已合并到 agent_service.py
保留此文件仅为向后兼容，请使用 agent_service.py

使用方式：
    from app.services.agent_service import EnterpriseAgentService, agent_service
    # 使用自定义框架（默认）: EnterpriseAgentService(use_custom_framework=True)
    # 使用 LangChain 框架: EnterpriseAgentService(use_custom_framework=False)
"""

from langchain_community.chat_models import ChatZhipuAI
from langchain.agents import create_agent
from app.core.config import settings
from langchain_core.messages import HumanMessage, AIMessage
from app.prompts.loader import AgentPromptLoader
from app.tools import get_all_tools, get_tools_info


class EnterpriseAgentService:
    def __init__(self):
        self.llm = ChatZhipuAI(
            api_key=settings.ZHIPU_API_KEY,
            model="glm-4-flash",
            temperature=0.1
        )

        self.tools = get_all_tools()

        print("=" * 60)
        print("🛠️ Agent 工具初始化")
        print("=" * 60)
        for i, tool in enumerate(self.tools, 1):
            print(f"{i}. {tool.name}: {tool.description}")
        print("=" * 60)

        prompt_loader = AgentPromptLoader()
        system_prompt_text = prompt_loader.load_system_prompt("react") or "你是一个智能助手。"

        self.agent = create_agent(
            model=self.llm,
            system_prompt=system_prompt_text,
            tools=self.tools
        )
        
        print("✅ Agent 初始化完成！")
        print("=" * 60)

    async def chat(self, user_input: str, kb_id: str, session_id: str = None, history: list = None):
        messages = []

        if history:
            for msg in history:
                role = "assistant" if msg["role"] == "assistant" else "user"
                messages.append({"role": role, "content": msg["content"]})

        agent_input = (
            f"用户问题：{user_input}\n"
            f"【系统指令】：如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}"
        )
        messages.append({"role": "user", "content": agent_input})

        input_dict = {
            "messages": messages
        }

        response = await self.agent.ainvoke(input_dict)
        return response["messages"][-1].content

    async def chat_stream(self, user_input: str, kb_id: str, session_id: str, history: list):
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
            print("🔄 [执行] 开始执行 Agent...")
            result = await self.agent.ainvoke(inputs)
            
            final_message = result["messages"][-1]
            final_content = final_message.content
            
            print(f"✅ [完成] Agent 执行完成，回答长度: {len(final_content)}")
            
            for char in final_content:
                yield char
                
        except Exception as e:
            print(f"❌ 流式被中断: {e}")
            import traceback
            traceback.print_exc()
            yield f"\n[Agent 报错: {str(e)}]"


agent_service = EnterpriseAgentService()
