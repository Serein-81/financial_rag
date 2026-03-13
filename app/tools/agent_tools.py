# app/tools/agent_tools.py

"""
Agent 工具集中管理

所有工具定义都在这个文件中，方便添加和管理。
每个工具都应该有对应的 skill 文件在 app/prompts/skills/ 目录下。

添加新工具的步骤：
1. 在这个文件中定义工具函数（使用 @tool 装饰器）
2. 在 app/prompts/skills/ 目录下创建对应的 skill 文件
3. 将工具添加到 get_all_tools() 函数的返回列表中
"""

import httpx
from langchain_core.tools import tool
from app.services.search_service import search_service
from app.core.config import settings


# ==========================================
# 工具定义区域
# ==========================================

@tool(description="核心企业知识库检索工具。当需要参考公司制度、业务文档等资料时必须调用。必须输入查询关键词 query 和知识库ID kb_id。")
async def search_enterprise_knowledge(query: str, kb_id: str) -> str:
    """
    根据查询词和知识库ID检索相关文档片段
    
    Args:
        query: 搜索关键词
        kb_id: 知识库ID
    
    Returns:
        检索到的文档内容
    """
    print(f"🤖 [Agent 主动调用工具] 正在搜索知识库: {kb_id} | 关键词: {query}")

    results = await search_service.search(query=query, kb_id=kb_id, top_k=5)

    if not results:
        return "知识库中未找到相关内容。请告诉用户没有相关参考资料。"

    context = "\n\n".join([f"[片段 {i + 1}] {r.content}" for i, r in enumerate(results)])
    return context


@tool(description="关键词精确搜索工具。当需要查找包含特定关键词的文档时使用。支持多个关键词和精确匹配。")
async def search_keywords_in_knowledge(keywords: str, kb_id: str, exact_match: bool = False) -> str:
    """
    在知识库中进行关键词精确搜索
    
    Args:
        keywords: 关键词，多个关键词用逗号分隔
        kb_id: 知识库ID
        exact_match: 是否精确匹配
    
    Returns:
        搜索结果
    """
    print(f"🔍 [Agent 关键词搜索] 知识库: {kb_id} | 关键词: {keywords} | 精确匹配: {exact_match}")
    
    keyword_list = [k.strip() for k in keywords.split(",")]
    
    results = await search_service.keyword_search(
        keywords=keyword_list,
        kb_id=kb_id,
        top_k=10,
        exact_match=exact_match
    )
    
    if not results:
        return f"在知识库中未找到包含关键词 '{keywords}' 的内容。"
    
    context = f"找到 {len(results)} 个匹配结果：\n\n"
    for i, result in enumerate(results):
        context += f"[结果 {i + 1}] (匹配度: {result.score})\n"
        context += f"文件: {result.source_file}\n"
        context += f"内容: {result.content[:200]}...\n\n"
    
    return context


@tool(description="文档级搜索工具。查找包含特定内容的文档列表，而不是文档片段。适合了解哪些文档涉及某个主题。")
async def search_documents_by_topic(topic: str, kb_id: str) -> str:
    """
    按主题搜索文档
    
    Args:
        topic: 主题或关键词
        kb_id: 知识库ID
    
    Returns:
        相关文档列表
    """
    print(f"📄 [Agent 文档搜索] 知识库: {kb_id} | 主题: {topic}")
    
    results = await search_service.document_level_search(
        query=topic,
        kb_id=kb_id,
        top_k=10
    )
    
    if not results:
        return f"未找到与主题 '{topic}' 相关的文档。"
    
    context = f"找到 {len(results)} 个相关文档：\n\n"
    for i, doc in enumerate(results):
        context += f"[文档 {i + 1}] {doc['filename']}\n"
        context += f"文件类型: {doc['file_type']}\n"
        context += f"匹配片段数: {doc['match_count']}\n"
        context += f"预览: {doc['preview'][:150]}...\n\n"
    
    return context


@tool(description="知识库统计工具。获取关键词在知识库中的统计信息，如出现次数、分布等。")
async def get_knowledge_statistics(keyword: str, kb_id: str) -> str:
    """
    获取知识库中关键词的统计信息
    
    Args:
        keyword: 要统计的关键词
        kb_id: 知识库ID
    
    Returns:
        统计信息
    """
    print(f"📊 [Agent 统计查询] 知识库: {kb_id} | 关键词: {keyword}")
    
    stats = await search_service.search_statistics(
        keyword=keyword,
        kb_id=kb_id
    )
    
    if "error" in stats:
        return f"统计查询失败: {stats['error']}"
    
    context = f"关键词 '{keyword}' 的统计信息：\n\n"
    context += f"📚 涉及文档数: {stats['document_count']}\n"
    context += f"📝 匹配片段数: {stats['chunk_count']}\n"
    context += f"🔢 总出现次数: {stats['total_occurrences']}\n"
    context += f"📊 出现密度: {stats['occurrence_density']:.2f} 次/片段\n"
    context += f"📁 文件类型: {stats['file_types']}\n"
    context += f"⏱️ 查询耗时: {stats['search_time']:.3f}秒\n"
    
    return context


@tool(description="天气查询工具。当用户询问任何城市的天气状况、温度、穿衣建议时，必须调用此工具。必须传入城市名称 city_name（例如'北京市'、'上海'）。")
async def get_weather(city_name: str) -> str:
    """
    根据城市名称查询实时天气
    
    Args:
        city_name: 城市名称（如"北京"、"上海"、"深圳"）
    
    Returns:
        实时天气信息
    """
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


@tool(description="地图与位置查询工具。当用户询问某个地址的经纬度、所在省市区、或者精确位置信息时调用此工具。必须传入详细地址 address。")
async def get_location_info(address: str) -> str:
    """
    根据详细地址查询经纬度和标准行政区划
    
    Args:
        address: 详细地址字符串
    
    Returns:
        地理位置信息
    """
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


@tool(description="网络搜索工具。当用户询问实时信息、新闻、最新资讯、或需要搜索互联网内容时调用此工具。必须传入搜索关键词 query。")
async def search_web(query: str) -> str:
    """
    使用 Tavily API 搜索互联网内容
    
    Args:
        query: 搜索关键词
    
    Returns:
        搜索结果摘要
    """
    print(f"🔍 [Agent 调用工具] 正在搜索网络: {query}")

    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 5
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            print(f"🔍 [调试] 请求 Tavily API: {query}")
            
            res = await client.post(url, json=payload, headers=headers)
            data = res.json()
            
            print(f"🔍 [调试] Tavily 响应状态: {res.status_code}")

            if res.status_code == 200:
                # 提取答案和搜索结果
                answer = data.get("answer", "")
                results = data.get("results", [])
                
                # 构建返回内容
                response_parts = []
                
                if answer:
                    response_parts.append(f"📝 答案摘要：\n{answer}\n")
                
                if results:
                    response_parts.append("🔗 相关链接：")
                    for i, result in enumerate(results[:3], 1):
                        title = result.get("title", "无标题")
                        url = result.get("url", "")
                        snippet = result.get("content", "")[:150]
                        response_parts.append(f"\n{i}. {title}\n   {snippet}...\n   链接: {url}")
                
                result_text = "\n".join(response_parts) if response_parts else "未找到相关信息"
                print(f"✅ [成功] 搜索完成，找到 {len(results)} 条结果")
                return result_text
            else:
                error_msg = f"搜索服务返回错误，状态码: {res.status_code}"
                print(f"❌ [错误] {error_msg}")
                return error_msg
                
        except httpx.TimeoutException as e:
            error_msg = f"搜索服务请求超时: {str(e)}"
            print(f"❌ [超时] {error_msg}")
            return error_msg
        except httpx.HTTPError as e:
            error_msg = f"搜索服务HTTP错误: {str(e)}"
            print(f"❌ [HTTP错误] {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"搜索服务请求异常: {type(e).__name__} - {str(e)}"
            print(f"❌ [未知错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return error_msg


# ==========================================
# 新工具示例（注释掉，需要时取消注释）
# ==========================================

# @tool(description="邮件发送工具。当用户需要发送邮件时调用此工具。")
# async def send_email(to: str, subject: str, body: str) -> str:
#     """
#     发送邮件
#     
#     Args:
#         to: 收件人邮箱
#         subject: 邮件主题
#         body: 邮件正文
#     
#     Returns:
#         发送结果
#     """
#     print(f"📧 [Agent 调用工具] 正在发送邮件: {to}")
#     
#     # TODO: 实现邮件发送逻辑
#     
#     return f"邮件已发送到 {to}"


# @tool(description="数据库查询工具。当用户需要查询数据库时调用此工具。")
# async def query_database(sql: str) -> str:
#     """
#     执行数据库查询
#     
#     Args:
#         sql: SQL 查询语句
#     
#     Returns:
#         查询结果
#     """
#     print(f"🗄️ [Agent 调用工具] 正在查询数据库: {sql}")
#     
#     # TODO: 实现数据库查询逻辑
#     
#     return "查询结果..."


# ==========================================
# 工具注册函数
# ==========================================

def get_all_tools():
    """
    获取所有可用的工具
    
    Returns:
        工具列表
    
    添加新工具时，只需在这里添加到列表中即可
    """
    return [
        search_enterprise_knowledge,
        search_keywords_in_knowledge,
        search_documents_by_topic,
        get_knowledge_statistics,
        get_weather,
        get_location_info,
        search_web,  # 新增网络搜索工具
        # send_email,  # 取消注释以启用
        # query_database,  # 取消注释以启用
    ]


def get_tool_names():
    """
    获取所有工具的名称列表
    
    Returns:
        工具名称列表
    """
    tools = get_all_tools()
    return [tool.name for tool in tools]


def get_tools_info():
    """
    获取所有工具的信息（用于提示词渲染）
    
    Returns:
        工具信息列表，每个工具包含 name 和 description
    """
    tools = get_all_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description
        }
        for tool in tools
    ]


# ==========================================
# 工具管理辅助函数
# ==========================================

def print_tools_summary():
    """打印工具摘要信息"""
    tools = get_all_tools()
    
    print("=" * 60)
    print("🛠️ Agent 工具列表")
    print("=" * 60)
    
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool.name}")
        print(f"   描述: {tool.description}")
        print()
    
    print(f"总计: {len(tools)} 个工具")
    print("=" * 60)


if __name__ == "__main__":
    # 测试：打印所有工具信息
    print_tools_summary()
    
    # 测试：获取工具信息
    tools_info = get_tools_info()
    print("\n工具信息（用于提示词）:")
    for info in tools_info:
        print(f"  - {info['name']}: {info['description'][:50]}...")
