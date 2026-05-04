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

import re
import logging
from contextvars import ContextVar
from langchain_core.tools import tool
from app.services.search_service import search_service

logger = logging.getLogger(__name__)

# 当前租户 ID + 用户 ID 上下文变量 — 在 chat_with_agent_stream 中设置，
# get_enterprise_kb_overview 等工具通过此变量获取当前用户所属租户和用户ID，
# 避免跨租户查询到其他企业的知识库，也避免查到同租户其他用户的私人知识库。
_current_tenant_id: ContextVar[str] = ContextVar("_current_tenant_id", default="")
_current_user_id: ContextVar[str] = ContextVar("_current_user_id", default="")


def set_tool_context(tenant_id: str, user_id: str = "") -> None:
    """设置当前工具调用的租户和用户上下文"""
    _current_tenant_id.set(tenant_id)
    if user_id:
        _current_user_id.set(user_id)


def get_tool_tenant_id() -> str:
    """获取当前工具调用的租户上下文"""
    return _current_tenant_id.get()


def get_tool_user_id() -> str:
    """获取当前工具调用的用户 ID"""
    return _current_user_id.get()

try:
    from app.mcp.financial_tools import create_financial_tools
    FINANCIAL_TOOLS_AVAILABLE = True
except ImportError:
    FINANCIAL_TOOLS_AVAILABLE = False
    logger.warning("财务工具模块导入失败，相关工具将不可用")


GREETING_PATTERNS = [
    r'^[\s]*$',
    r'^你好[吗呀啊哦嗯\?\.！!]*[\s]*$',
    r'^您好[吗呀啊哦嗯\?\.！!]*[\s]*$',
    r'^hi[,\s]*$',
    r'^hello[,\s]*$',
    r'^嗨[吗呀啊哦嗯\?\.！!]*[\s]*$',
    r'^hey[,\s]*$',
    r'^在吗[吗呀啊哦嗯\?\.！!]*[\s]*$',
    r'^在不在[\?\.！!]*$',
    r'^早上好[啊呀吗\?\.！!]*$',
    r'^下午好[啊呀吗\?\.！!]*$',
    r'^晚上好[啊呀吗\?\.！!]*$',
    r'^晚安[啊呀吗\?\.！!]*$',
    r'^谢谢[你呀啊哦嗯\?\.！!]*$',
    r'^thanks[,\s]*$',
    r'^请问你是谁',
    r'^你是谁',
    r'^你是.*吗',
    r'^你能做什么',
    r'^有什么功能',
    r'^介绍一下',
    r'^帮帮我',
    r'^救命',
    r'^打扰.*',
    r'^冒昧.*',
]


def is_greeting_query(query: str) -> bool:
    """
    判断是否为问候型/闲聊型查询
    
    Args:
        query: 用户输入
        
    Returns:
        True 表示是问候语，应该跳过 RAG 检索
    """
    query = query.strip()
    if not query:
        return True
    
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, query, re.IGNORECASE):
            return True
    
    short_words = ["你好", "您好", "嗨", "hi", "hello", "在吗", "在不在", "早", "晚"]
    if len(query) <= 4 and any(w in query.lower() for w in short_words):
        return True
    
    return False


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
    
    if is_greeting_query(query):
        print("💬 检测到问候语/闲聊，直接返回空结果让 Agent 自由回答")
        return "用户问题不需要检索知识库。Agent 应该友好地回应用户，不需要引用任何文档。"

    results = await search_service.search(query=query, kb_id=kb_id, top_k=5, score_threshold=0.5)

    if not results:
        return "[检索结果为空]"
    
    from app.utils.tool_result_formatter import tool_result_formatter
    return tool_result_formatter.format_knowledge_result(results)


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
    
    if is_greeting_query(keywords):
        print("💬 检测到问候语/闲聊，跳过关键词搜索")
        return "用户问题不需要检索知识库。"
    
    keyword_list = [k.strip() for k in keywords.split(",")]
    
    results = await search_service.keyword_search(
        keywords=keyword_list,
        kb_id=kb_id,
        top_k=10,
        exact_match=exact_match
    )
    
    if not results:
        return "[检索结果为空]"
    
    from app.utils.tool_result_formatter import tool_result_formatter
    return tool_result_formatter.format_knowledge_result(results)


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
    
    if is_greeting_query(topic):
        print("💬 检测到问候语/闲聊，跳过文档搜索")
        return "用户问题不需要检索知识库。"
    
    results = await search_service.document_level_search(
        query=topic,
        kb_id=kb_id,
        top_k=10
    )
    
    if not results:
        return "[检索结果为空]"
    
    context = f"找到 {len(results)} 个相关文档：\n\n"
    for i, doc in enumerate(results):
        context += f"[{i + 1}] {doc.get('filename', '未知文件')}\n"
        context += f"文件类型: {doc.get('file_type', '未知类型')}\n"
        preview = doc.get('preview', '')[:150] if doc.get('preview') else ''
        context += f"预览: {preview}...\n\n"
    
    return context


@tool(description="知识库文档列表工具。列出知识库中已上传的所有文档名称和类型，帮助用户了解知识库包含哪些内容。")
async def list_knowledge_documents(kb_id: str) -> str:
    """
    列出知识库中的所有文档
    
    Args:
        kb_id: 知识库ID
    
    Returns:
        文档列表信息
    """
    from app.models.document import Document
    from app.db import AsyncSessionLocal
    from sqlalchemy import select, or_
    
    print(f"📋 [Agent 文档列表] 知识库: {kb_id}")
    
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Document)
                .where(
                    Document.kb_id == kb_id,
                    or_(
                        Document.visibility == "public",
                        Document.visibility is None
                    )
                )
                .order_by(Document.created_at.desc())
                .limit(50)
            )
            documents = result.scalars().all()
    except (ValueError, KeyError) as e:
        print(f"❌ [Agent] 文档列表查询数据错误: {e}")
        return f"查询文档列表数据错误: {str(e)}"
    except (OSError, IOError) as e:
        print(f"❌ [Agent] 文档列表查询IO错误: {e}")
        return f"查询文档列表IO错误: {str(e)}"
    except Exception as e:
        print(f"❌ [Agent] 文档列表查询失败: {e}")
        return f"查询文档列表失败: {str(e)}"
    
    if not documents:
        return "[知识库为空] 当前知识库中没有上传任何文档。"
    
    context = f"📚 知识库文档列表（共 {len(documents)} 个文档）：\n\n"
    for i, doc in enumerate(documents):
        filename = getattr(doc, 'name', getattr(doc, 'filename', '未知文件'))
        file_type = getattr(doc, 'file_type', '未知类型')
        created_at = getattr(doc, 'created_at', None)
        date_str = created_at.strftime('%Y-%m-%d') if created_at else '未知日期'
        context += f"[{i + 1}] {filename}\n"
        context += f"    类型: {file_type} | 上传时间: {date_str}\n\n"
    
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
    
    if is_greeting_query(keyword):
        print("💬 检测到问候语/闲聊，跳过统计查询")
        return "用户问题不需要检索知识库。"
    
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


@tool(description="企业知识库概览工具。查询企业拥有多少个知识库，以及每个知识库中有多少文档。不传 kb_id 时返回企业所有知识库概览，传入 kb_id 时返回该知识库的详细文档统计。")
async def get_enterprise_kb_overview(kb_id: str = "", tenant_id: str = "") -> str:
    """
    获取企业知识库概览，包括知识库数量和各知识库的文档统计

    Args:
        kb_id: 知识库ID（可选），为空时返回所有知识库概览
        tenant_id: 租户ID（可选），为空时自动从知识库推断当前租户

    Returns:
        知识库概览信息
    """
    from app.db import AsyncSessionLocal
    from sqlalchemy import text

    print(f"🏢 [Agent 企业概览] kb_id={kb_id or '全部'}")

    try:
        async with AsyncSessionLocal() as db:
            if kb_id:
                # 查单个知识库（用 text column 避免 ORM 枚举转换问题）
                kb_row = await db.execute(
                    text("SELECT id, name, description, visibility, created_at, tenant_id FROM knowledge_bases WHERE id = :id"),
                    {"id": kb_id}
                )
                kb = kb_row.mappings().first()
                if not kb:
                    return f"[未找到] 知识库 ID {kb_id} 不存在。"

                _dc = await db.execute(
                    text("SELECT COUNT(*) FROM documents WHERE kb_id = CAST(:kb_id AS UUID)"),
                    {"kb_id": str(kb_id)}
                )
                total_docs = _dc.scalar() or 0
                _cc = await db.execute(
                    text("SELECT COUNT(*) FROM documents WHERE kb_id = CAST(:kb_id AS UUID) AND status IN ('completed', 'ready')"),
                    {"kb_id": str(kb_id)}
                )
                completed_docs = _cc.scalar() or 0
                vis = (kb["visibility"] or "").lower()
                visibility_cn = "企业级" if vis == "enterprise" else "私有"

                return (
                    f"📚 知识库详情：\n"
                    f"  名称：{kb['name']}\n"
                    f"  描述：{kb['description'] or '无'}\n"
                    f"  可见性：{visibility_cn}\n"
                    f"  文档数：{total_docs}（已完成 {completed_docs}）\n"
                    f"  创建时间：{kb['created_at'].strftime('%Y-%m-%d %H:%M') if kb['created_at'] else '未知'}\n"
                )

            # ── 推断当前租户 ──
            # 优先用传入的 tenant_id；否则取 ContextVar 中当前用户的租户
            if not tenant_id:
                tenant_id = get_tool_tenant_id()
            _uid = get_tool_user_id()

            # 查当前租户下当前用户可见的知识库：
            # - 企业级知识库：同租户所有用户可见
            # - 私有知识库：仅创建者本人可见
            if tenant_id and _uid:
                kb_rows = await db.execute(
                    text("""
                        SELECT id, name, description, visibility, created_at
                        FROM knowledge_bases
                        WHERE tenant_id = :tid
                          AND (visibility = 'enterprise' OR (visibility = 'private' AND user_id = CAST(:uid AS UUID)))
                        ORDER BY created_at DESC
                    """),
                    {"tid": tenant_id, "uid": _uid}
                )
            elif tenant_id:
                kb_rows = await db.execute(
                    text("SELECT id, name, description, visibility, created_at FROM knowledge_bases WHERE tenant_id = :tid AND visibility = 'enterprise' ORDER BY created_at DESC"),
                    {"tid": tenant_id}
                )
            else:
                kb_rows = await db.execute(
                    text("SELECT id, name, description, visibility, created_at FROM knowledge_bases ORDER BY created_at DESC")
                )
            all_kbs = kb_rows.mappings().all()

            if not all_kbs:
                return "[企业知识库概览] 当前企业没有创建任何知识库。"

            lines = [f"📚 企业知识库概览（共 {len(all_kbs)} 个知识库）：\n"]
            for i, kb in enumerate(all_kbs, 1):
                # 用 raw SQL 统计文档数，避免 UUID 类型转换问题
                _dc = await db.execute(
                    text("SELECT COUNT(*) FROM documents WHERE kb_id = CAST(:kb_id AS UUID)"),
                    {"kb_id": str(kb["id"])}
                )
                total_docs = _dc.scalar() or 0
                _cc = await db.execute(
                    text("SELECT COUNT(*) FROM documents WHERE kb_id = CAST(:kb_id AS UUID) AND status IN ('completed', 'ready')"),
                    {"kb_id": str(kb["id"])}
                )
                completed_docs = _cc.scalar() or 0
                vis = (kb["visibility"] or "").lower()
                visibility_cn = "企业级" if vis == "enterprise" else "私有"
                lines.append(
                    f"[{i}] {kb['name']}\n"
                    f"    文档数：{total_docs}（已完成 {completed_docs}）| 可见性：{visibility_cn}\n"
                )

            return "\n".join(lines)

    except (ValueError, KeyError) as e:
        print(f"❌ [Agent] 企业概览查询数据错误: {e}")
        return f"查询企业知识库概览数据错误: {str(e)}"
    except (OSError, IOError) as e:
        print(f"❌ [Agent] 企业概览查询IO错误: {e}")
        return f"查询企业知识库概览IO错误: {str(e)}"
    except Exception as e:
        print(f"❌ [Agent] 企业概览查询失败: {e}")
        return f"查询企业知识库概览失败: {str(e)}"


# ==========================================
# MCP 工具说明
# ==========================================
# 以下工具已移至 MCP Server 实现，通过 mcp_tool_proxy.py 调用：
# - get_weather: 天气查询工具
# - get_location_info: 地理位置查询工具
# - search_web: 网络搜索工具
# 
# 这些工具不需要访问本地数据库，直接调用外部 API，
# 因此通过 MCP Server 统一管理，提高复用性。
# 
# 如需修改这些工具的实现，请编辑 mcp_server/app/tools/external_tools.py


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
    tools = [
        search_enterprise_knowledge,
        search_keywords_in_knowledge,
        search_documents_by_topic,
        list_knowledge_documents,
        get_knowledge_statistics,
        get_enterprise_kb_overview,
    ]
    
    if FINANCIAL_TOOLS_AVAILABLE:
        try:
            financial_tools = create_financial_tools()
            tools.extend(financial_tools)
            logger.debug("Loaded %s financial tools", len(financial_tools))
        except Exception as e:
            logger.warning(f"财务工具加载失败: {e}")
    
    try:
        from app.services.custom_tool_service import get_published_custom_tool_callables

        tools.extend(get_published_custom_tool_callables())
    except Exception as e:
        logger.debug("Published custom tools are not ready: %s", e)

    return tools


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
    
    for i, t in enumerate(tools, 1):
        print(f"{i}. {t.name}")
        print(f"   描述: {t.description}")
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
