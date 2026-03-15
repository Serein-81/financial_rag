"""
智能路由服务 (Smart Router Service)

使用 LLM 判断查询应该使用 Memory、RAG 还是混合模式
"""

from typing import Literal, Dict, Any
from enum import Enum
from app.services.llm_service import llm_service


class RouteMode(str, Enum):
    """路由模式枚举"""
    RAG_ONLY = "RAG_ONLY"          # 仅使用 RAG（客观知识查询）
    MEMORY_ONLY = "MEMORY_ONLY"    # 仅使用 Memory（个人历史回顾）
    HYBRID = "HYBRID"              # 混合模式（需要结合两者）


class SmartRouter:
    """
    智能路由器
    
    使用 LLM 判断查询类型，自动选择最合适的检索方式
    """
    
    def __init__(self):
        """初始化智能路由器"""
        self.router_prompt_template = """你是一个智能路由助手，负责判断用户问题应该使用哪种检索方式。

【检索方式说明】
1. RAG_ONLY（知识库检索）：
   - 适用场景：查询客观知识、通用事实、教程文档
   - 示例："什么是变压器原理？"、"Python generator 的定义是什么？"

2. MEMORY_ONLY（记忆检索）：
   - 适用场景：回顾个人历史、查询过往对话、个人偏好
   - 示例："我昨天问了什么？"、"根据我之前的习惯"、"提醒我上次说的事"

3. HYBRID（混合检索）：
   - 适用场景：需要结合知识库和个人记忆
   - 示例："根据我的偏好推荐 Python 教程"、"结合我的情况分析这个问题"

【判断规则】
- 包含"我"、"昨天"、"之前"、"上次"、"记得"、"提醒"等词 → 优先考虑 MEMORY_ONLY 或 HYBRID
- 纯粹的知识查询，无个人化需求 → RAG_ONLY
- 既需要知识又需要个人化 → HYBRID

【用户问题】
{query}

【输出格式】
只输出以下三个选项之一，不要有任何其他内容：
RAG_ONLY
MEMORY_ONLY
HYBRID"""
    
    async def route(self, query: str, enable_cache: bool = True) -> RouteMode:
        """
        路由查询到合适的检索方式
        
        Args:
            query: 用户查询
            enable_cache: 是否启用缓存（未来可实现）
            
        Returns:
            路由模式
        """
        print(f"\n🧭 [智能路由] 正在分析查询: {query[:50]}...")
        
        # 构造 prompt
        prompt = self.router_prompt_template.format(query=query)
        
        try:
            # 调用 LLM 判断
            decision = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[]
            )
            
            # 清理输出
            decision = decision.strip().upper()
            
            # 解析决策
            if "RAG_ONLY" in decision:
                mode = RouteMode.RAG_ONLY
            elif "MEMORY_ONLY" in decision:
                mode = RouteMode.MEMORY_ONLY
            elif "HYBRID" in decision:
                mode = RouteMode.HYBRID
            else:
                # 默认使用 HYBRID（最保险）
                print(f"⚠️ [智能路由] 无法解析决策: {decision}，默认使用 HYBRID")
                mode = RouteMode.HYBRID
            
            print(f"✅ [智能路由] 决策结果: {mode.value}")
            return mode
            
        except Exception as e:
            print(f"❌ [智能路由] 路由失败: {e}，默认使用 HYBRID")
            return RouteMode.HYBRID
    
    async def route_with_explanation(self, query: str) -> Dict[str, Any]:
        """
        路由查询并返回详细解释
        
        Args:
            query: 用户查询
            
        Returns:
            包含路由模式和解释的字典
        """
        mode = await self.route(query)
        
        explanations = {
            RouteMode.RAG_ONLY: "这是一个客观知识查询，将从知识库中检索相关文档",
            RouteMode.MEMORY_ONLY: "这是一个个人历史回顾，将从对话记忆中检索",
            RouteMode.HYBRID: "这个问题需要结合知识库和个人记忆来回答"
        }
        
        return {
            "mode": mode.value,
            "explanation": explanations[mode],
            "query": query
        }


# 全局单例
smart_router = SmartRouter()
