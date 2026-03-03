# app/services/agent_service.py

from langchain_community.chat_models import ChatZhipuAI
from langchain.agents import create_agent  # 👈 使用你验证过绝对成功的导入方式！
from app.services.search_service import search_service
import httpx
from langchain_core.tools import tool
from app.core.config import settings
from langchain_core.messages import HumanMessage, AIMessage

# 引入提示词加载器
from app.utils.prompt_loader import load_agent_system_prompt


# ==========================================
# 🛠️ 1. 定义工具
# ==========================================
@tool(description="核心企业知识库检索工具。当需要参考公司制度、业务文档等资料时必须调用。必须输入查询关键词 query 和知识库ID kb_id。")
async def search_enterprise_knowledge(query: str, kb_id: str) -> str:
    """根据查询词和知识库ID检索相关文档片段"""
    print(f"🤖 [Agent 主动调用工具] 正在搜索知识库: {kb_id} | 关键词: {query}")

    results = await search_service.search(query=query, kb_id=kb_id, top_k=5)

    if not results:
        return "知识库中未找到相关内容。请告诉用户没有相关参考资料。"

    context = "\n\n".join([f"[片段 {i + 1}] {r.content}" for i, r in enumerate(results)])
    return context



@tool(description="天气查询工具。当用户询问任何城市的天气状况、温度、穿衣建议时，必须调用此工具。必须传入城市名称 city_name（例如'北京市'、'上海'）。")
async def get_weather(city_name: str) -> str:
    """根据城市名称查询实时天气"""
    print(f"🌤️ [Agent 调用工具] 正在查询天气: {city_name}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. 使用专属 Geo Host 查询城市 ID（注意：需要加 /geo 路径）
            geo_url = f"{settings.QWEATHER_GEO_HOST}/geo/v2/city/lookup?location={city_name}&key={settings.QWEATHER_API_KEY}"
            print(f"🔍 [调试] 请求城市信息: {geo_url}")
            
            geo_res = await client.get(geo_url)
            geo_data = geo_res.json()
            print(f"🔍 [调试] 城市信息响应: {geo_data}")

            if geo_data.get("code") != "200":
                error_msg = f"抱歉，未能找到 {city_name} 的城市信息。API 返回码: {geo_data.get('code')}"
                print(f"❌ [错误] {error_msg}")
                return error_msg

            location_id = geo_data["location"][0]["id"]
            print(f"✅ [成功] 获取到城市ID: {location_id}")

            # 2. 使用专属 Weather Host 查询实时天气
            weather_url = f"{settings.QWEATHER_WEATHER_HOST}/v7/weather/now?location={location_id}&key={settings.QWEATHER_API_KEY}"
            print(f"🔍 [调试] 请求天气信息: {weather_url}")
            
            weather_res = await client.get(weather_url)
            weather_data = weather_res.json()
            print(f"🔍 [调试] 天气信息响应: {weather_data}")

            if weather_data.get("code") == "200":
                now = weather_data["now"]
                result = f"{city_name}当前的实时天气：{now['text']}，气温 {now['temp']}°C，体感温度 {now['feelsLike']}°C，风向 {now['windDir']}，相对湿度 {now['humidity']}%。"
                print(f"✅ [成功] 天气查询完成: {result}")
                return result
            else:
                error_msg = f"抱歉，获取天气数据失败。API 返回码: {weather_data.get('code')}"
                print(f"❌ [错误] {error_msg}")
                return error_msg
        except httpx.TimeoutException as e:
            error_msg = f"天气服务请求超时: {str(e)}"
            print(f"❌ [超时] {error_msg}")
            return error_msg
        except httpx.HTTPError as e:
            error_msg = f"天气服务HTTP错误: {str(e)}"
            print(f"❌ [HTTP错误] {error_msg}")
            return error_msg
        except KeyError as e:
            error_msg = f"天气数据解析错误，缺少字段: {str(e)}"
            print(f"❌ [解析错误] {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"天气服务请求异常: {type(e).__name__} - {str(e)}"
            print(f"❌ [未知错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return error_msg


@tool(
    description="地图与位置查询工具。当用户询问某个地址的经纬度、所在省市区、或者精确位置信息时调用此工具。必须传入详细地址 address。")
async def get_location_info(address: str) -> str:
    """根据详细地址查询经纬度和标准行政区划"""
    print(f"🗺️ [Agent 调用工具] 正在查询地图地址: {address}")

    url = f"https://restapi.amap.com/v3/geocode/geo?address={address}&key={settings.GAODE_API_KEY}"

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url)
            data = res.json()

            if data.get("status") == "1" and data.get("geocodes"):
                geo = data["geocodes"][0]
                return f"地址【{address}】的查询结果：\n标准名称：{geo['formatted_address']}\n所在省份：{geo['province']}\n所在城市：{geo['city']}\n所在区县：{geo['district']}\n经纬度：{geo['location']}"
            else:
                return "高德地图未找到该地址的精确信息，请用户提供更详细的地址。"
        except Exception as e:
            return f"地图服务请求异常: {str(e)}"



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

        self.tools = [
            search_enterprise_knowledge,
            get_weather,  # 👈 加入天气工具
            get_location_info  # 👈 加入地图工具
        ]

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