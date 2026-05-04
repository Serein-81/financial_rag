"""
智能体编排器 (Agent Orchestrator)
企业智能体系统的核心协调器，负责编排接待、意图识别，专业Agent协作和报告生成
"""

import asyncio
from functools import partial
from app.utils.json_compat import json
import uuid
import traceback
import logging
import re
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass, field

from .agents.intent_router_agent import (
    IntentRouterAgent, 
    IntentAnalysisResult, 
    IntentCategory, 
    RoutingStrategy
)
from .agents.finance_specialist import FinanceSpecialist
from .agents.tax_specialist import TaxSpecialist
from .agents.legal_specialist import LegalSpecialist
from app.prompts.llm_functions import review_quality
from .agents.report_generator import ReportGenerator
from .message_bus import MessageBus
from .rag_retriever import TenantIsolatedRAGRetriever
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.memory_system.memory_manager import MemoryManager
from app.core.config import settings
from app.services.agent_tracer import agent_tracer
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.agent_framework.components import ResultSynthesizer
from .blackboard_payload import BlackboardPayloadFormatter
from .result_cache import ResultCache, CacheConfig

# LangGraph 状态类型导入
from app.langgraph.state import AgentState, SpecialistType

# 🆕 技能系统
from app.skills.skill_registry import SkillRegistry
from app.skills.skill_loader import SkillLoader
from app.skills.skill_matcher import SkillMatcher


logger = logging.getLogger(__name__)


class LatencyTracker:
    """延迟追踪器"""
    
    def __init__(self):
        self.stages = {}
        self.start_time = None
    
    def start(self):
        """开始追踪"""
        self.start_time = datetime.now()
        self.stages = {}
    
    def mark(self, stage: str):
        """标记阶段完成"""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds() * 1000
            self.stages[stage] = {
                "elapsed_ms": elapsed,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_summary(self) -> Dict[str, Any]:
        """获取延迟摘要"""
        if not self.start_time:
            return {}
        
        total_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        return {
            "total_ms": round(total_ms, 2),
            "stages": self.stages,
            "ttft_ms": self.stages.get("first_token", {}).get("elapsed_ms", total_ms)
        }


class Nodes:
    """LangGraph 节点函数集合"""
    
    def __init__(self, orchestrator: 'AgentOrchestrator'):
        self.orchestrator = orchestrator

    def _simple_finance_markdown(self, result: dict) -> str:
        """降级格式化：直接返回原始结果文本"""
        if not isinstance(result, dict):
            return str(result)
        text_answer = result.get("text_answer") or result.get("analysis_report") or result.get("content")
        return str(text_answer) if text_answer else str(result)

    def _simple_specialist_markdown(self, result: dict, title: str) -> str:
        """降级格式化：直接返回原始结果文本"""
        if not isinstance(result, dict):
            return str(result)
        text_answer = result.get("text_answer") or result.get("content")
        return str(text_answer) if text_answer else str(result)

    # =========================================================================
    # 🆕 元问题检测
    # =========================================================================

    @staticmethod
    def _is_meta_question(query: str) -> bool:
        """检测是否是元问题（技能询问、配置查询、自我介绍等），不需要 RAG/图谱检索/反思"""
        q = query.lower()
        meta_patterns = [
            "技能", "能力", "会做什么", "擅长", "功能介绍", "工具",
            "skill", "capability",
            "你是什么", "你是谁", "你能做什么",
        ]
        return any(p in q for p in meta_patterns)

    @staticmethod
    def _sanitize_llm_text(text: str) -> str:
        """清理 LLM 输出的纯文本：去除工具调用残留、JSON 包装、错误信息包装"""
        if not text:
            return ""

        import re as _re

        # 0. 检测工具调用残留（<tool_call>, <invoke>, {"name":...} 等，出现在文本任何位置）
        stripped = text.strip()
        tool_residue_patterns = [
            r"<tool_call>",
            r"<invoke\s+name=",
            r'\{\s*"name"\s*:.*"arguments"',
            r"Action:\s*\w+",
        ]
        is_tool_residue = any(_re.search(p, stripped) for p in tool_residue_patterns)
        if is_tool_residue:
            logger.warning(f"[sanitize] 检测到工具调用残留，替换为友好消息")
            return "抱歉，系统处理时遇到异常，请稍后重试。"

        # 1. 去除 ```json ... ``` 包装
        json_block = _re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, _re.DOTALL)
        if json_block:
            inner = json_block.group(1).strip()
            # 如果内部是 JSON，尝试提取 executive_summary 或 description 字段
            if inner.startswith("{") and inner.endswith("}"):
                try:
                    import json as _json
                    parsed = _json.loads(inner)
                    # 优先提取文本内容
                    summary = (parsed.get("executive_summary") or
                               parsed.get("description") or
                               parsed.get("output_data", {}).get("executive_summary") or
                               parsed.get("blackboard_action", {}).get("output_data", {}).get("executive_summary"))
                    if summary and isinstance(summary, str):
                        return summary.strip()
                    text = inner  # 无法提取有用文本，继续检查
                except _json.JSONDecodeError:
                    text = inner  # 不是合法 JSON，直接用内部文本

        # 2. 去除 ``` ... ``` 代码块（非 JSON），取纯文本
        code_block = _re.search(r"```\s*\n?(.*?)```", text, _re.DOTALL)
        if code_block:
            text = code_block.group(1).strip()

        # 3. 检测纯 JSON 对象（无代码块包裹），提取文本字段
        stripped2 = text.strip()
        if stripped2.startswith("{") and stripped2.endswith("}"):
            try:
                import json as _json
                parsed = _json.loads(stripped2)
                for key in ("executive_summary", "description", "summary", "content", "text_answer", "final_answer"):
                    val = parsed.get(key)
                    if val and isinstance(val, str) and len(val) > 10:
                        return val.strip()
                # 如果能找到 analysis_type + 其他字段，拼接
                analysis_type = parsed.get("analysis_type") or parsed.get("domain")
                summary = parsed.get("executive_summary") or parsed.get("summary") or ""
                if analysis_type and summary:
                    return f"**{analysis_type}**\n\n{summary}"
                return "抱歉，系统未能正确生成回答。请重试。"
            except _json.JSONDecodeError:
                pass  # 不是 JSON，继续

        # 4. 检测纯错误内容：短消息且包含"失败"/"error"等关键词
        result = text.strip()
        if len(result) < 50 and any(kw in result for kw in ["失败", "error", "异常", "出错", "failed", "exception"]):
            logger.warning(f"[sanitize] 检测到错误内容短消息，替换: {result[:50]}")
            return f"抱歉，系统处理时遇到异常：{result[:100]}。请稍后重试。"

        # 5. 检测非常短且无实质内容的回答（< 15 字符）
        if len(result) < 15:
            logger.warning(f"[sanitize] 回答过短 ({len(result)} 字符)，补充友好消息")
            if not result:
                return "抱歉，系统未能生成回答。请稍后重试。"
            return result + "\n\n若以上内容不完整，请重新描述您的问题。"

        return result

    async def receptionist(self, state: AgentState) -> AgentState:
        logger.info("[节点] receptionist 开始")
        
        updated_state = {
            **state,
            "metadata": {
                **state.get("metadata", {}),
                "reception_time": datetime.now().isoformat()
            }
        }
        
        logger.debug(f"receptionist 完成 | user_query: {state.get('user_query', 'N/A')[:50]}...")
        return updated_state
    
    async def intent_router(self, state: AgentState) -> AgentState:
        logger.info(f"[节点] intent_router | query: {state.get('user_query', '')[:50]}...")
        
        user_query = state["user_query"]
        intent_result = await self.orchestrator.intent_router.run(user_input=user_query)
        
        if intent_result.is_simple:
            logger.info(f"[意图路由] 简单问题，直接回答")
            updated_state = {
                **state,
                "intent": "simple",
                "intent_confidence": 1.0,
                "specialists_needed": [],
                "routing_strategy": "direct_answer",
                "metadata": {
                    **state.get("metadata", {}),
                    "simple_response": intent_result.simple_response
                }
            }
            return updated_state
        
        inner_result = intent_result.intent_result
        specialists_needed = inner_result.requires_specialists[:3] if inner_result.requires_specialists else ["finance"]
        logger.info(f"[意图路由] 意图: {inner_result.intent.value} | 需要专家: {specialists_needed}")
        
        updated_state = {
            **state,
            "intent": inner_result.intent.value,
            "intent_confidence": inner_result.confidence,
            "specialists_needed": specialists_needed,
            "routing_strategy": inner_result.routing_strategy.value,
            "metadata": {
                **state.get("metadata", {}),
                "intent_result": {
                    "intent": inner_result.intent.value,
                    "confidence": inner_result.confidence
                }
            }
        }
        
        if intent_result.clarification_request:
            logger.info(f"[意图路由] 需要追问: {intent_result.clarification_request.type}")
            updated_state["clarification_request"] = intent_result.clarification_request.model_dump()
            updated_state["needs_clarification"] = True
        
        return updated_state
    
    async def rag_retrieval(self, state: AgentState) -> AgentState:
        logger.info("[节点] rag_retrieval 开始")

        # 🆕 元问题跳过 RAG 检索
        query = state.get("user_query", "")
        if self._is_meta_question(query):
            logger.info("[RAG] 元问题，跳过 RAG 检索")
            return {**state, "rag_context": []}

        if not self.orchestrator.rag_retriever:
            logger.debug("RAG 检索器未初始化，跳过")
            return {**state, "rag_context": []}
        try:
            rag_context = await self.orchestrator.rag_retriever.retrieve(
                query=state["user_query"],
                tenant_id=self.orchestrator.tenant_id,
                top_k=5
            )
            results = rag_context.results if rag_context else []
            docs = [{"content": r.content, "source": r.source, "score": r.relevance_score} for r in results]
            logger.info(f"[RAG] 检索到 {len(docs)} 条文档")
            
            updated_state = {**state, "rag_context": docs}
            return updated_state
        except Exception as e:
            logger.warning(f"[RAG] 检索失败: {e}")
            return {**state, "rag_context": []}

    async def graph_path_retrieval(self, state: AgentState) -> AgentState:
        """
        图谱路径检索节点

        检测用户查询中是否包含"X和Y之间的关系"类问题，
        如果是，查找两个实体之间的最短路径并注入 context。
        """
        query = state.get("user_query", "")
        logger.info(f"[节点] graph_path_retrieval 开始: {query[:40]}...")

        # ⚡ 轻量规则：检测 "X 和 Y" 样式的实体对
        # 匹配模式：中文名+和+中文名（各 2-6 字）
        entity_pairs = re.findall(r'([\u4e00-\u9fa5]{2,6})和([\u4e00-\u9fa5]{2,6})', query)
        if not entity_pairs:
            logger.debug("[图谱路径] 未检测到实体对，跳过")
            return {**state, "graph_path_context": None}

        try:
            neo4j = Neo4jManager(
                uri=settings.NEO4J_URI,
                user=settings.NEO4J_USER,
                password=settings.NEO4J_PASSWORD
            )
            if not neo4j.driver:
                logger.warning("[图谱路径] Neo4j 不可用")
                return {**state, "graph_path_context": None}

            tenant_id = state.get("tenant_id") or getattr(self.orchestrator, "tenant_id", None)
            all_paths = []

            for src, tgt in entity_pairs:
                logger.info(f"[图谱路径] 查询: {src} ↔ {tgt}")
                paths = neo4j.find_path_between(
                    source_name=src,
                    target_name=tgt,
                    tenant_id=tenant_id,
                    max_depth=4
                )
                if paths:
                    all_paths.append({
                        "source": src,
                        "target": tgt,
                        "paths": paths,
                        "paths_count": len(paths)
                    })
                    logger.info(f"[图谱路径] 找到 {len(paths)} 条路径: {src} ↔ {tgt}")

            if all_paths:
                context = {
                    "has_graph_paths": True,
                    "paths": all_paths,
                    "summary": self._format_graph_paths_for_prompt(all_paths)
                }
                logger.info(f"[图谱路径] 共找到 {sum(p['paths_count'] for p in all_paths)} 条路径")
                return {**state, "graph_path_context": context}
            else:
                logger.debug("[图谱路径] 未找到任何路径")
                return {**state, "graph_path_context": None}

        except Exception as e:
            logger.warning(f"[图谱路径] 检索失败: {e}")
            return {**state, "graph_path_context": None}
        finally:
            try:
                neo4j.close()
            except Exception:
                pass

    def _format_graph_paths_for_prompt(self, all_paths: List[Dict]) -> str:
        """将路径结果格式化为 LLM 提示词片段"""
        parts = ["【知识图谱关系路径】"]
        for pair in all_paths:
            parts.append(f"\n{pair['source']} ↔ {pair['target']} 的关系路径：")
            for i, path in enumerate(pair['paths'], 1):
                chain = " → ".join(
                    f"{e['name']}({e['type']})"
                    for e in path.get('entities', [])
                )
                rels = " → ".join(path.get('relations', []))
                parts.append(f"  路径{i}: {chain}")
                if rels:
                    parts.append(f"         关系: {rels}")
        return "\n".join(parts)

    def _build_specialist_context(self, state: AgentState) -> Dict:
        """构建专家上下文（含 RAG + 图谱路径结果）"""
        actual_tenant_id = self.orchestrator.tenant_id
        actual_user_id = self.orchestrator.user_id

        ctx = {"tenant_id": actual_tenant_id, "user_id": actual_user_id}

        # 注入 RAG 结果
        rag_ctx = state.get("rag_context", [])
        if rag_ctx:
            ctx["rag_context"] = rag_ctx

        # 注入图谱路径结果
        graph_ctx = state.get("graph_path_context")
        if graph_ctx and graph_ctx.get("has_graph_paths"):
            ctx["graph_path_context"] = graph_ctx["summary"]

        return ctx

    def _build_history_dicts(self, state: AgentState) -> Optional[List[Dict]]:
        """构建历史消息字典列表"""
        history_msgs = state.get("messages", [])
        if not history_msgs:
            return None
        history_dicts = []
        for msg in history_msgs[:-1]:  # 排除当前用户消息
            if hasattr(msg, "role") and hasattr(msg, "content"):
                history_dicts.append({"role": msg.role, "content": msg.content})
            elif isinstance(msg, dict):
                history_dicts.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        return history_dicts or None

    async def finance_specialist(self, state: AgentState) -> AgentState:
        logger.info("[节点] finance_specialist 开始")

        specialist_context = self._build_specialist_context(state)
        trace_id = state.get("trace_id") or state.get("metadata", {}).get("trace_id")
        if trace_id:
            self.orchestrator.finance_specialist.current_trace_id = trace_id

        history_dicts = self._build_history_dicts(state)
        rag_ctx = {"documents": state.get("rag_context", [])} if state.get("rag_context") else None
        previous_trace_id = getattr(self.orchestrator.finance_specialist, "current_trace_id", None)

        try:
            result = await self.orchestrator.finance_specialist.run(
                user_input=state["user_query"],
                history=history_dicts or None,
                context=specialist_context,
                rag_context=rag_ctx
            )
            logger.info(f"[财务专家] 分析完成, success={result.get('success')}")

            # 🔧 检查专家是否分析失败，失败时生成清晰的错误报告而非误导性 JSON
            if not result.get('success', True):
                error_type = result.get('error_type', 'unknown')
                error_msg = result.get('error', '未知错误')
                fallback = result.get('fallback', '建议您稍后重试')
                logger.warning(f"[财务专家] 分析失败 (type={error_type}): {error_msg}")

                # 根据错误类型生成用户可读的报告
                if error_type == 'timeout':
                    markdown_report = f"""## 💰 财务专家分析报告

### ⚠️ 分析处理超时

**原因**：财务分析请求处理时间超过系统上限，未能按时完成。

**建议**：
1. 稍后重新提交查询
2. 尝试缩短或简化您的问题描述
3. 如持续出现此问题，请联系系统管理员

---
*⏱️ 超时时间: 60秒*"""
                elif error_type == 'data_error':
                    markdown_report = f"""## 💰 财务专家分析报告

### ⚠️ 数据获取异常

**原因**：{error_msg}

**建议**：
1. 确认企业财务数据已正确导入系统
2. 检查数据格式是否符合要求
3. 如需帮助，请联系系统管理员

---
*📊 数据来源: 企业财务数据库*"""
                else:
                    markdown_report = f"""## 💰 财务专家分析报告

### ⚠️ 分析处理失败

**原因**：{error_msg}

**建议**：{fallback}

---
*🔍 请稍后重试*"""
            else:
                # 🔧 使用 ResultSynthesizer 级别的丰富格式化（与流式路径保持一致）
                try:
                    markdown_report = self.orchestrator._format_finance_result(result)
                    logger.debug(f"[财务专家] 使用 _format_finance_result 生成丰富报告，长度: {len(markdown_report)}")
                except Exception as format_err:
                    logger.warning(f"[财务专家] _format_finance_result 失败，降级到简单格式: {format_err}")
                    markdown_report = self._simple_finance_markdown(result)
            
            specialist_data = {
                "source": "finance",
                "content": markdown_report,
                "data": result,
                "confidence": result.get('confidence', 0.85),
                "success": result.get('success', True)
            }
            
            # 只返回增量字段，不 spread state（避免并行写冲突）
            return {"specialist_results": [specialist_data]}
        except Exception as e:
            logger.error(f"[财务专家] 执行失败: {e}")
            return {"specialist_results": [{"source": "finance", "data": {"error": str(e)}, "confidence": 0.0, "success": False}]}
        finally:
            self.orchestrator.finance_specialist.current_trace_id = previous_trace_id

    async def tax_specialist(self, state: AgentState) -> AgentState:
        logger.info("[节点] tax_specialist 开始")

        specialist_context = self._build_specialist_context(state)
        try:
            result = await self.orchestrator.tax_specialist.run(user_input=state["user_query"], context=specialist_context)
            logger.info("[税务专家] 分析完成")

            if not result.get('success', True):
                error_msg = result.get('error', '未知错误')
                logger.warning(f"[税务专家] 分析失败: {error_msg}")
                markdown_content = f"""## 📋 税务专家分析报告

### ⚠️ 分析处理失败

**原因**：{error_msg}

**建议**：请稍后重试，或联系系统管理员获取帮助。

---
*🔍 税务分析未能完成*"""
            else:
                try:
                    markdown_content = self.orchestrator._format_tax_result(result)
                    logger.debug(f"[税务专家] 使用 _format_tax_result 生成报告，长度: {len(markdown_content)}")
                except Exception as format_err:
                    logger.warning(f"[税务专家] _format_tax_result 失败，降级: {format_err}")
                    markdown_content = self._simple_specialist_markdown(result, "📋 税务专家分析报告")
            
            specialist_data = {
                "source": "tax",
                "content": markdown_content,
                "data": result,
                "confidence": result.get('confidence', 0.85),
                "success": result.get('success', True)
            }
            
            return {"specialist_results": [specialist_data]}
        except Exception as e:
            logger.error(f"[税务专家] 执行失败: {e}")
            return {"specialist_results": [{"source": "tax", "content": f"税务专家分析失败: {str(e)}", "data": {"error": str(e)}, "confidence": 0.0, "success": False}]}

    async def legal_specialist(self, state: AgentState) -> AgentState:
        logger.info("[节点] legal_specialist 开始")

        specialist_context = self._build_specialist_context(state)
        try:
            result = await self.orchestrator.legal_specialist.run(user_input=state["user_query"], context=specialist_context)
            logger.info("[法律专家] 分析完成")

            if not result.get('success', True):
                error_msg = result.get('error', '未知错误')
                logger.warning(f"[法律专家] 分析失败: {error_msg}")
                markdown_content = f"""## ⚖️ 法律专家分析报告

### ⚠️ 分析处理失败

**原因**：{error_msg}

**建议**：请稍后重试，或联系系统管理员获取帮助。

---
*🔍 法律分析未能完成*"""
            else:
                try:
                    markdown_content = self.orchestrator._format_legal_result(result)
                    logger.debug(f"[法律专家] 使用 _format_legal_result 生成报告，长度: {len(markdown_content)}")
                except Exception as format_err:
                    logger.warning(f"[法律专家] _format_legal_result 失败，降级: {format_err}")
                    markdown_content = self._simple_specialist_markdown(result, "⚖️ 法律专家分析报告")

            specialist_data = {
                "source": "legal",
                "content": markdown_content,
                "data": result,
                "confidence": result.get('confidence', 0.85),
                "success": result.get('success', True)
            }
            
            return {"specialist_results": [specialist_data]}
        except Exception as e:
            logger.error(f"[法律专家] 执行失败: {e}")
            return {"specialist_results": [{"source": "legal", "content": f"法律专家分析失败: {str(e)}", "data": {"error": str(e)}, "confidence": 0.0, "success": False}]}
    
    async def reflection(self, state: AgentState) -> AgentState:
        logger.info("[节点] reflection 审核开始")
        
        if not state.get("enable_reflection", self.orchestrator.enable_reflection):
            logger.info("[reflection] disabled, skip quality review")
            return {
                **state,
                "reflection_result": {"score": 1.0, "acceptable": True, "skipped": True},
                "retry_count": state.get("retry_count", 0)
            }

        specialist_results = state.get("specialist_results", [])
        current_retry = state.get("retry_count", 0)
        
        if not specialist_results:
            logger.debug("[反思] 无专家结果，跳过")
            return {
                "reflection_result": {"score": 0.5, "acceptable": True},
                "retry_count": current_retry
            }
        
        if len(specialist_results) == 1:
            result = specialist_results[0]
            result_confidence = result.get('confidence', 0.0)
            has_db_data = result.get('has_financial_db_data', False)
            
            if result_confidence >= 0.85 and has_db_data:
                logger.debug(f"[反思] 快速通过 | confidence={result_confidence:.2f}")
                return {
                    "reflection_result": {"score": result_confidence, "acceptable": True},
                    "retry_count": current_retry
                }
        
        response_text = "\n\n".join([f"### {r.get('source')}\n{r.get('content', '')}" for r in specialist_results])
        logger.info(f"[反思] 合并 {len(specialist_results)} 个专家结果")
        
        data_source_parts = []
        for r in specialist_results:
            source = r.get('source', 'unknown')
            has_db_data = r.get('has_financial_db_data', False) or r.get('data', {}).get('has_financial_db_data', False)
            if has_db_data:
                data = r.get('data', {})
                total_revenue = data.get('data_summary', {}).get('total_revenue') or data.get('total_revenue', 'N/A')
                total_profit = data.get('data_summary', {}).get('total_profit') or data.get('total_profit', 'N/A')
                data_source_parts.append(
                    f"- {source}专家：来自企业数据库（营业收入: {total_revenue}元，利润: {total_profit}元）"
                )
        
        data_source_info = "\n".join(data_source_parts) if data_source_parts else "无数据来源信息"
        
        try:
            from app.prompts.llm_functions import review_quality
            quality_result = await review_quality(
                user_question=state["user_query"], 
                ai_answer=response_text,
                data_source_info=data_source_info
            )
            
            actual_score = quality_result.get('scores', {}).get('overall', quality_result.get('score', 0.0))
            is_acceptable = quality_result.get('is_quality_acceptable', quality_result.get('acceptable', False))
            
            logger.info(f"[反思] 质量分数: {actual_score:.2f}, 可接受: {is_acceptable}")
            
            new_retry_count = current_retry + 1 if not is_acceptable else current_retry
            
            updated_state = {
                **state,
                "reflection_result": {"score": actual_score, "acceptable": is_acceptable},
                "retry_count": new_retry_count
            }
            
            if not is_acceptable:
                logger.warning("[反思] 质量不达标")
            
            return updated_state
        except Exception as e:
            logger.warning(f"[反思] 审核异常，标记跳过: {e}")
            return {
                **state,
                "reflection_result": {
                    "score": 0.5,          # 降一半置信度
                    "acceptable": True,     # 仍然放行（业务连续性）
                    "skipped": True,        # 🆕 明确标记审查未完成
                    "issues": [f"质量审查异常: {str(e)[:100]}"],
                },
                "retry_count": current_retry,
            }
    
    async def final(self, state: AgentState) -> AgentState:
        logger.info("[节点] final 开始")
        
        if state.get("needs_clarification") and state.get("clarification_request"):
            clarification = state.get("clarification_request", {})
            question = clarification.get("question", "") if isinstance(clarification, dict) else str(clarification)
            logger.info("[最终答案] 需要追问: %s", question[:80])
            # 把追问内容作为 final_answer，前端至少能显示，而不是"处理完成"
            fallback = f"❓ {question}" if question else "请更详细地描述您的问题，以便我为您提供准确的帮助。"
            return {
                **state,
                "final_answer": fallback,
                "output": fallback,
                "needs_clarification": False,
                "clarification_request": None
            }
        
        simple_response = state.get("metadata", {}).get("simple_response")
        if simple_response and simple_response == "__CONFIG_QUERY__":
            reflection_status = "已启用" if self.orchestrator.enable_reflection else "已禁用"
            rag_status = "已启用" if self.orchestrator.enable_rag else "已禁用"
            report_status = "已启用" if self.orchestrator.enable_report_generation else "已禁用"
            
            config_response = f"""📋 **当前系统配置状态**

以下是当前会话的系统设置：

| 功能 | 状态 |
|------|------|
| **反思审核** | {reflection_status} |
| **知识检索 (RAG)** | {rag_status} |
| **报告生成** | {report_status} |

**说明**：
- 反思审核：对多智能体回答进行质量评估和审核
- 知识检索：从企业知识库中检索相关信息
- 报告生成：自动生成结构化分析报告

如需更改设置，请在对话页面的设置面板中调整。"""
            
            logger.info("[最终答案] 配置查询模式")
            return {
                **state,
                "final_answer": config_response,
                "output": config_response
            }
        
        specialist_results = state.get("specialist_results", [])
        logger.debug(f"[最终答案] specialist_results: {len(specialist_results)} 个")
        
        if state.get("needs_clarification") and state.get("clarification_request"):
            logger.info("[最终答案] 需要追问")
            return {
                **state,
                "final_answer": "",
                "output": "",
                "needs_clarification": True,
                "clarification_request": state.get("clarification_request")
            }
        
        logger.debug(f"[最终答案] 收到 {len(specialist_results)} 个专家结果")
        
        if not specialist_results:
            # ── 直接回答 / 简单问答分支 ──
            simple_response = state.get("metadata", {}).get("simple_response")
            routing_strategy = state.get("routing_strategy", "")
            intent = state.get("intent", "")
            user_query = state.get("user_query", "")
            rag_context = state.get("rag_context", [])

            # 1) 正则预检测的简单响应（问候、感谢、帮助等）
            if simple_response and simple_response != "__CONFIG_QUERY__":
                logger.info("[最终答案] 使用预生成的简单响应: %s", simple_response[:80])
                return {
                    **state,
                    "final_answer": simple_response,
                    "output": simple_response
                }

            # 2) 前端传入了 direct_answer 路由 + 非正则匹配的通用对话
            if routing_strategy == "direct_answer" or intent in ("direct_answer", "simple"):
                logger.info("[最终答案] 直接回答模式，调用 LLM 生成回复")
                try:
                    direct_answer = await self._generate_direct_answer(user_query)
                    if direct_answer:
                        return {
                            **state,
                            "final_answer": direct_answer,
                            "output": direct_answer
                        }
                except Exception as e:
                    logger.warning("[最终答案] LLM 直接回答失败: %s", e)
                # LLM 失败时回退到 simple_response（如果有的话）
                if simple_response:
                    return {
                        **state,
                        "final_answer": simple_response,
                        "output": simple_response
                    }

            if rag_context:
                logger.info("[最终答案] 使用 RAG 检索结果生成回答，文档数: %s", len(rag_context))
                try:
                    rag_answer = await self._generate_rag_answer(user_query, rag_context)
                    if rag_answer:
                        return {
                            **state,
                            "final_answer": rag_answer,
                            "output": rag_answer
                        }
                except Exception as e:
                    logger.warning("[最终答案] RAG 回答生成失败: %s", e)

            logger.warning("[最终答案] 无专家结果，返回降级响应")
            return {
                **state,
                "final_answer": "抱歉，未能获取到有效的分析结果。",
                "output": "抱歉，未能获取到有效的分析结果。"
            }
        
        try:
            # 🔧 过滤原始结果：只保留成功且有实际分析数据的专家结果
            raw_results = []
            failed_sources = []
            for sr in specialist_results:
                if isinstance(sr, dict) and "data" in sr:
                    data = sr.get("data", {})
                    success = sr.get("success") or data.get("success")
                    if success is False:
                        # 专家分析失败，记录失败信息但不传给合成器
                        failed_sources.append(sr.get("source", "unknown"))
                        logger.warning(f"[最终答案] 专家 {sr.get('source', 'unknown')} 分析失败，已跳过")
                        continue
                    raw_results.append(sr)

            # 检查是否有任何成功的结果
            if not raw_results:
                logger.warning(f"[最终答案] 所有专家分析均失败 (failed: {failed_sources})，返回错误信息")

                # 构建清晰的用户错误消息
                error_detail = "分析处理失败"
                if failed_sources:
                    source_names = {"finance": "财务", "tax": "税务", "legal": "法律"}
                    failed_names = [source_names.get(s, s) for s in failed_sources]
                    error_detail = f"{'、'.join(failed_names)}分析处理失败"

                return {
                    **state,
                    "final_answer": f"⚠️ 抱歉，{error_detail}。建议您简化查询或稍后重试。如需帮助，请联系系统管理员。",
                    "output": f"⚠️ 抱歉，{error_detail}。建议您简化查询或稍后重试。如需帮助，请联系系统管理员。"
                }

            # 如果有部分专家成功、部分失败，记录日志
            if failed_sources:
                logger.info(f"[最终答案] 部分专家失败 (failed: {failed_sources})，仅合成成功结果")

            # 如果只有一个专家且返回了 text_answer，直接返回（跳过合成器）
            if len(raw_results) == 1:
                r = raw_results[0]
                data = r.get("data", {})
                if isinstance(data, dict) and data.get("text_answer"):
                    answer = self._sanitize_llm_text(data["text_answer"])
                    logger.info("[最终答案] 单专家 text_answer，跳过合成器")
                    return {**state, "final_answer": answer, "output": answer}

            # 多专家场景（或单专家无 text_answer）：使用 ResultSynthesizer 合并
            from app.agent_framework.components.result_synthesizer import ResultSynthesizer
            synthesizer = ResultSynthesizer(llm_adapter=self.orchestrator.llm_adapter)

            logger.info("[最终答案] 开始调用 ResultSynthesizer，成功结果数: %s", len(raw_results))
            # 🔧 只传入成功的专家数据，避免错误数据污染合成结果
            synthesis_data = {}
            for r in raw_results:
                data = r.get("data", {})
                # 如果 data 中只有 error/fallback/success 等错误字段，跳过
                error_only_keys = {'success', 'error', 'fallback', 'error_type'}
                if isinstance(data, dict) and error_only_keys.issuperset(data.keys()):
                    logger.warning(f"[最终答案] 跳过无效数据 (keys: {list(data.keys())})")
                    continue
                synthesis_data[r.get("source", "unknown")] = data

            if not synthesis_data:
                return {
                    **state,
                    "final_answer": "⚠️ 抱歉，分析结果无效，无法生成报告。请稍后重试。",
                    "output": "⚠️ 抱歉，分析结果无效，无法生成报告。请稍后重试。"
                }

            final_markdown = await synthesizer.synthesize_and_format(
                specialist_results=synthesis_data,
                user_query=state.get("user_query", "")
            )

            final_markdown = self._clean_markdown_output(final_markdown)
            logger.debug(f"[最终答案] 清洗后长度: {len(final_markdown)}")

            if final_markdown:
                logger.info(f"[最终答案] 合成成功，长度: {len(final_markdown)}")
                updated_state = {
                    **state,
                    "final_answer": final_markdown,
                    "output": final_markdown
                }
            else:
                logger.warning("[最终答案] 合成器返回空，使用降级方案")
                updated_state = {
                    **state,
                    "final_answer": "抱歉，生成报告时遇到问题。",
                    "output": "抱歉，生成报告时遇到问题。"
                }

        except Exception as e:
            logger.error(f"[最终答案] 合成器异常: {e}")
            updated_state = {
                **state,
                "final_answer": "抱歉，生成报告时遇到问题。",
                "output": "抱歉，生成报告时遇到问题。"
            }
        
        return updated_state

    async def _generate_rag_answer(self, user_query: str, rag_context: list) -> str:
        """基于 LangGraph RAG 节点检索结果生成最终回答。"""
        docs = []
        for idx, doc in enumerate(rag_context[:5], 1):
            if not isinstance(doc, dict):
                continue
            content = (doc.get("content") or "").strip()
            if not content:
                continue
            source = doc.get("source") or f"文档{idx}"
            score = doc.get("score")
            score_text = f"，相关度 {score:.2f}" if isinstance(score, (int, float)) else ""
            docs.append(f"[{idx}] 来源：{source}{score_text}\n{content[:1200]}")

        if not docs:
            return "抱歉，我在知识库中没有找到可用于回答该问题的有效内容。"

        context_text = "\n\n".join(docs)
        prompt = f"""你是企业政策、财税和合规知识助手。请只依据给定的知识库内容回答用户问题。

回答要求：
1. 先直接回答用户关心的问题，不要说“无法确定”开场。
2. 如果材料只支持部分结论，要明确说明“根据当前检索到的材料”。
3. 对政策解读类问题，优先覆盖：政策主题、适用对象、关键条件、可能影响、建议动作。
4. 不要编造知识库中没有的政策名称、日期、金额或适用条件。
5. 末尾列出“参考来源”，使用下方来源编号。

用户问题：{user_query}

知识库内容：
{context_text}

请用中文输出结构清晰的 Markdown 回答。"""

        response = await self.orchestrator.llm_adapter.agenerate([prompt], temperature=0.1, max_tokens=1800)
        answer = response.content.strip() if response and response.content else ""
        return self._clean_markdown_output(answer) if answer else "抱歉，未能基于检索内容生成回答。"
    
    def _clean_markdown_output(self, text: str) -> str:
        """
        清洗 LLM 返回的 Markdown 文本
        
        移除多余的反引号包裹（如 ```markdown ... ```）
        
        Args:
            text: 原始 LLM 输出
            
        Returns:
            清洗后的文本
        """
        if not text:
            return text
        
        original = text
        text = text.strip()
        
        if text.startswith("```markdown\n"):
            text = text[12:]
        elif text.startswith("```markdown"):
            text = text[11:]
        elif text.startswith("```\n"):
            text = text[4:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        if original != text:
            print(f"🔧 [清洗] 移除了 markdown 代码块标记")
        
        return text
    
    def _fallback_concat(self, specialist_results: list) -> str:
        """降级方案：灾难发生时的基础拼接"""
        parts = ["## 📊 综合分析报告 (系统降级版)\n\n"]
        source_names = {"finance": "💰 财务专家", "tax": "📋 税务专家", "legal": "⚖️ 法律专家"}
        for result in specialist_results:
            source = result.get("source", "unknown")
            name = source_names.get(source, f"🤖 {source}专家")
            content = result.get("content", "")
            parts.append(f"### {name}\n\n{content}\n\n---\n\n")
        return "".join(parts)

    async def _generate_direct_answer(self, user_query: str) -> str:
        """针对闲聊/问候/常识性问题，使用 LLM 直接生成回复"""
        prompt = f"""你是一个企业级财税法务智能助手。用户正在和你进行对话。

你的职责：
- 友好、自然地回应用户的问候和日常闲聊
- 对专业知识类问题，给出准确、清晰的解答
- 适当介绍你能提供的服务：财务分析、税务咨询、法律顾问、合同审查、政策检索等
- 如果问题超出你的专业范围（财税法务），礼貌说明并引导到相关领域

用户输入：{user_query}

请用中文给出简洁、友好的回复（不超过200字）："""

        try:
            response = await self.orchestrator.llm_adapter.agenerate([prompt])
            if response and response.content:
                return response.content.strip()
        except Exception as e:
            logger.warning("[直接回答] LLM 调用失败: %s", e)

        # 硬编码兜底
        greeting_keywords = ["你好", "您好", "hi", "hello", "嗨", "hey"]
        if any(kw in user_query.lower() for kw in greeting_keywords):
            from datetime import datetime
            hour = datetime.now().hour
            time_greeting = "上午好" if hour < 12 else ("下午好" if hour < 18 else "晚上好")
            return f"{time_greeting}！欢迎使用企业智能助手。我可以帮您处理财务、税务、法律等方面的问题。请问有什么可以帮到您的？"

        return "您好！有什么可以帮助您的吗？"


@dataclass
class OrchestrationContext:
    """编排上下文"""
    session_id: str
    tenant_id: str
    user_id: str
    user_query: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    enable_reflection: bool = True
    enable_rag: bool = True
    enable_report_generation: bool = False
    confidence_threshold: float = 0.7
    max_specialists: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    intent_result: Optional[IntentAnalysisResult] = None
    specialist_results: List[Dict[str, Any]] = field(default_factory=list)
    reflection_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    needs_human_review: bool = False
    needs_clarification: bool = False
    clarification_request: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """
    智能体编排器
    
    核心职责：
    1. 初始化和管理所有智能体
    2. 协调接待Agent和意图识别Agent的工作流程
    3. 将任务路由到合适的专业Agent
    4. 管理多Agent并行/串行协作
    5. 调用反思Agent进行质量审核
    6. 管理对话上下文和状态
    
    工作流程：
    用户输入 → 接待Agent → 意图识别Agent → 
    (RAG/单专家/多专家) → 反思Agent → 返回结果
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        user_id: str = "default",
        enable_reflection: bool = True,
        enable_rag: bool = True,
        max_parallel_agents: int = 3,
        timeout: float = 120.0,
        context: Optional[OrchestrationContext] = None
    ):
        """
        初始化编排器
        
        Args:
            tenant_id: 租户ID（用于数据隔离）
            user_id: 用户ID
            enable_reflection: 是否启用反思审核
            enable_rag: 是否启用RAG检索
            max_parallel_agents: 最大并行Agent数量
            timeout: 超时时间（秒）
            context: 编排上下文（可选）
        """
        if context:
            self.tenant_id = context.tenant_id
            self.user_id = context.user_id
            self.enable_reflection = context.enable_reflection
            self.max_parallel_agents = context.max_specialists
            self.enable_rag = enable_rag
            self.enable_report_generation = context.enable_report_generation
            self.timeout = timeout
            self.context = context
        else:
            self.tenant_id = tenant_id
            self.user_id = user_id
            self.enable_reflection = enable_reflection
            self.enable_rag = enable_rag
            self.enable_report_generation = False
            self.max_parallel_agents = max_parallel_agents
            self.timeout = timeout
            self.context = None
        
        self.llm_adapter = None
        self.tool_manager = None
        self.message_bus = MessageBus()
        self.memory_manager = None
        
        self.intent_router: Optional[IntentRouterAgent] = None
        self.finance_specialist: Optional[FinanceSpecialist] = None
        self.tax_specialist: Optional[TaxSpecialist] = None
        self.legal_specialist: Optional[LegalSpecialist] = None

        self.output_agent: Optional[ResultSynthesizer] = None
        
        self.rag_retriever: Optional[TenantIsolatedRAGRetriever] = None
        
        self._capability_config: Dict[str, Any] = {}
        self._specialist_descriptions: str = ""
        self._intent_mapping: Dict[str, str] = {}

        # 🆕 技能系统
        self.skill_registry = SkillRegistry
        self.skill_matcher = SkillMatcher(registry=SkillRegistry)

        self.initialized = False
        
        self.result_cache: Optional[ResultCache] = None
        self._init_result_cache()
        
        print("🎭 [编排器] 初始化完成")
        print(f"   - 租户ID: {tenant_id}")
        print(f"   - 反思审核: {'启用' if enable_reflection else '禁用'}")
        print(f"   - RAG检索: {'启用' if enable_rag else '禁用'}")
    
    def _init_result_cache(self):
        """初始化结果缓存"""
        try:
            cache_config = CacheConfig(
                max_size=1000,
                default_ttl=3600,
                similarity_threshold=0.85,
                enable_semantic=True
            )
            self.result_cache = ResultCache(config=cache_config)
            print("💾 [编排器] 结果缓存已初始化")
        except Exception as e:
            print(f"⚠️ [编排器] 结果缓存初始化失败: {e}")
            self.result_cache = None
    
    def _generate_cache_key(self, query: str, tenant_id: str) -> str:
        """生成缓存键"""
        import hashlib
        key_data = f"{tenant_id}:{query.strip().lower()}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]
    
    async def _check_cache(self, query: str, embedding: Optional[List[float]] = None) -> Optional[Any]:
        """检查缓存"""
        if not self.result_cache:
            return None
        
        try:
            cache_key = self._generate_cache_key(query, self.tenant_id)
            
            if embedding:
                result = await self.result_cache.get_similar(query, embedding)
                if result:
                    logger.info(f"💾 [缓存] 语义命中: {cache_key[:8]}...")
                    return result[0]
            else:
                result = await self.result_cache.get(query)
                if result:
                    logger.info(f"💾 [缓存] 精确命中: {cache_key[:8]}...")
                    return result
            
            return None
        except Exception as e:
            logger.error(f"❌ [缓存] 检查失败: {e}")
            return None
    
    async def _save_to_cache(self, query: str, result: Any, embedding: Optional[List[float]] = None):
        """保存结果到缓存"""
        if not self.result_cache:
            return
        
        try:
            await self.result_cache.set(
                query=query,
                result=result,
                embedding=embedding,
                ttl=3600
            )
            logger.info(f"💾 [缓存] 已保存结果")
        except Exception as e:
            logger.error(f"❌ [缓存] 保存失败: {e}")
    
    # =========================================================================
    # 🚀 状态机启动器模式 (LangGraph 集成)
    # =========================================================================
    
    async def process_user_request(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    ) -> OrchestrationContext:
        """
        🚀 状态机启动器 - 核心入口（LangGraph 集成版）
        
        这是重构后的核心处理方法，使用 LangGraph 状态机进行多智能体协作。
        废弃了旧的 _handle_single_specialist、_handle_multiple_specialists 等自研方法。
        
        工作流程：
        1. 组装初始黑板状态 (Initial State)
        2. 实例化 LangGraph Workflow
        3. 携带 Checkpointer 记忆执行
        4. 从最终状态中提取报告并返回
        
        Args:
            user_input: 用户输入
            session_id: 会话ID（用于 Checkpointer 记忆持久化）
            history: 历史消息
            metadata: 其他元数据
            
        Returns:
            OrchestrationContext: 包含最终响应的上下文
        """
        logger.info("[Orchestrator] 启动 LangGraph 状态机: session_id=%s, query=%s", session_id, user_input[:80])
        
        session_id = session_id or str(uuid.uuid4())
        start_time = datetime.now()
        trace_id = None
        
        if not self.initialized:
            await self.initialize()
        
        # 🆕 从前端传入的 metadata 中提取 enable_reflection，兼容 orchestrator 默认值
        enable_reflection = self.enable_reflection
        if metadata and "enable_reflection" in metadata:
            enable_reflection = metadata["enable_reflection"]

        context = OrchestrationContext(
            session_id=session_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            user_query=user_input,
            context={"history": history or [], **(metadata or {})},
            enable_reflection=enable_reflection,
            enable_rag=self.enable_rag
        )
        
        try:
            try:
                trace_session_id = str(uuid.UUID(str(session_id)))
            except (ValueError, TypeError):
                trace_session_id = None

            try:
                trace_id = await agent_tracer.start_trace(
                    agent_type="langgraph_orchestrator",
                    user_query=user_input,
                    user_id=self.user_id,
                    tenant_id=self.tenant_id,
                    session_id=trace_session_id
                )
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=1,
                    step_type="thought",
                    content="开始执行 LangGraph 多智能体编排流程",
                    metadata={
                        "enable_reflection": self.enable_reflection,
                        "enable_rag": self.enable_rag
                    }
                )
            except Exception as trace_error:
                trace_id = None
                logger.warning("[AgentTrace] LangGraph 编排追踪启动失败，不阻塞主流程: %s", trace_error)

            # 1️⃣ 组装初始黑板状态
            logger.debug("[状态机] 组装初始黑板状态")
            initial_state = self._create_initial_blackboard_state(
                user_input=user_input,
                session_id=session_id,
                history=history,
                metadata=metadata
            )
            if trace_id:
                initial_state["trace_id"] = trace_id
                initial_state.setdefault("metadata", {})["trace_id"] = trace_id
            
            # 2️⃣ 执行 LangGraph 状态机（带超时保护）
            logger.debug("[状态机] 执行 LangGraph 工作流")
            MAX_WORKFLOW_TIMEOUT = 120  # 最大执行时间 120 秒
            
            try:
                final_state = await asyncio.wait_for(
                    self._execute_langgraph_workflow(initial_state, context, progress_callback),
                    timeout=MAX_WORKFLOW_TIMEOUT
                )
                logger.info("[状态机] LangGraph 执行完成: session_id=%s", session_id)
            except asyncio.TimeoutError:
                logger.error("[状态机] LangGraph 执行超时 (%s秒): session_id=%s", MAX_WORKFLOW_TIMEOUT, session_id)
                final_state = initial_state.copy()
                final_state["final_answer"] = "抱歉，处理时间过长。系统已在规定时间内完成了基础分析。"
                final_state["specialist_results"] = context.specialist_results or []
                context.metadata["timeout"] = True
            except Exception as e:
                logger.error("[状态机] 执行异常: %s", e, exc_info=True)
                error_msg = str(e)
                if "enable_report_generation" in error_msg or "enable_reflection" in error_msg or "enable_rag" in error_msg:
                    final_answer = "⚠️ 系统配置加载失败，请刷新页面后重试"
                elif "AttributeError" in error_msg or "object has no attribute" in error_msg or "'NoneType'" in error_msg:
                    final_answer = "⚠️ 智能体初始化不完整，请稍后重试或刷新页面"
                else:
                    final_answer = "⚠️ 处理过程中遇到问题，请稍后重试"
                final_state = initial_state.copy()
                final_state["final_answer"] = final_answer
                final_state["specialist_results"] = []
                context.metadata["error"] = error_msg
                context.metadata["user_friendly_error"] = final_answer
            
            # 3️⃣ 从最终状态提取结果
            logger.debug("[状态机] 提取最终响应")
            context.final_response = final_state.get("final_answer", "")
            context.specialist_results = final_state.get("specialist_results", [])
            
            logger.debug("[状态机] final_state keys=%s", list(final_state.keys()))
            logger.debug(
                "[状态机] clarification flags: needs=%s, request_exists=%s",
                final_state.get("needs_clarification"),
                bool(final_state.get("clarification_request"))
            )
            
            # 🚨 从 specialist_results 提取生肉数据（因为 LangGraph 可能丢失 raw_results）
            specialist_results = final_state.get("specialist_results", [])
            raw_results = []
            for sr in specialist_results:
                if isinstance(sr, dict) and "data" in sr:
                    raw_results.append(sr)
            
            context.intent_result = final_state.get("intent")
            context.needs_human_review = final_state.get("needs_human_review", False)
            
            context.needs_clarification = final_state.get("needs_clarification", False)
            if final_state.get("clarification_request"):
                clarification = final_state.get("clarification_request")
                if isinstance(clarification, dict):
                    from app.multi_agent_system.clarification_service import ClarificationRequest, ClarificationType
                    context.clarification_request = ClarificationRequest(
                        type=clarification.get("type", ClarificationType.INTENT_CLARIFICATION),
                        question=clarification.get("question", "请详细描述您的问题"),
                        suggestions=clarification.get("suggestions", []),
                        reason=clarification.get("reason", "您的输入需要更多信息来帮助您"),
                        required=clarification.get("required", True),
                        placeholder=clarification.get("placeholder")
                    )
                else:
                    context.clarification_request = clarification
            
            if context.needs_clarification and context.clarification_request:
                logger.info("[状态机] 检测到需要追问，跳过结果合成: session_id=%s", session_id)
                context.final_response = ""
            
            # 🚨 添加详细日志追踪数据
            logger.debug(
                "[状态机] 提取结果: answer_len=%s, specialist_results=%s, raw_results=%s, needs_clarification=%s",
                len(context.final_response or ""),
                len(specialist_results),
                len(raw_results),
                context.needs_clarification
            )
            
            # 4️⃣ 如果有生肉数据，调用 ResultSynthesizer 生成最终答案
            if raw_results and not context.final_response:
                print("🎨 [状态机] 检测到生肉数据，调用 ResultSynthesizer...")
                try:
                    # 获取用户原始查询
                    messages = final_state.get("messages", [])
                    user_query = user_input
                    if messages and isinstance(messages[0], dict):
                        user_query = messages[0].get("content", user_input)
                    
                    # 调用 ResultSynthesizer
                    synthesizer = self.output_agent
                    if synthesizer:
                        print("🎨 [状态机] 开始智能合成...")
                        context.final_response = await synthesizer.synthesize_and_format(
                            specialist_results={r.get("source", "unknown"): r.get("data", {}) for r in raw_results},
                            user_query=user_query
                        )
                        if context.final_response:
                            print(f"🎨 [状态机] 合成完成，长度: {len(context.final_response)} 字符")
                        else:
                            print(f"🎨 [状态机] 合成完成，但结果为空")
                    else:
                        # 降级：使用 fallback 方法
                        print("⚠️ [状态机] ResultSynthesizer 未初始化，使用降级方案...")
                        context.final_response = self._fallback_concat(raw_results)
                except Exception as e:
                    print(f"❌ [状态机] ResultSynthesizer 执行失败: {e}")
                    # 降级方案
                    context.final_response = self._fallback_concat(raw_results)
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            execution_path = context.metadata.get("execution_path", [])
            if trace_id:
                try:
                    await agent_tracer.add_step(
                        trace_id=trace_id,
                        step_number=2,
                        step_type="observation",
                        content=f"LangGraph 执行路径: {' → '.join(execution_path) if execution_path else 'unknown'}",
                        metadata={
                            "execution_path": execution_path,
                            "intent": final_state.get("intent"),
                            "routing_strategy": final_state.get("routing_strategy"),
                            "specialists_needed": final_state.get("specialists_needed", []),
                            "needs_clarification": context.needs_clarification
                        }
                    )
                    await agent_tracer.add_step(
                        trace_id=trace_id,
                        step_number=3,
                        step_type="final_answer",
                        content=(context.final_response or "需要用户补充信息")[:1000],
                        confidence=final_state.get("intent_confidence")
                    )
                    await agent_tracer.end_trace(
                        trace_id=trace_id,
                        final_answer=context.final_response or "",
                        success=not bool(context.metadata.get("error"))
                    )
                except Exception as trace_error:
                    logger.warning("[AgentTrace] LangGraph 编排追踪写入失败，不阻塞主流程: %s", trace_error)
            logger.info(
                "[状态机] 处理完成: session_id=%s, path=%s, 耗时=%.0fms",
                session_id,
                " → ".join(execution_path) if execution_path else "unknown",
                elapsed_ms
            )
            
            return context
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error("[状态机] 执行失败: %s: %s", type(e).__name__, e, exc_info=True)
            
            error_msg = str(e)
            if "enable_report_generation" in error_msg or "enable_reflection" in error_msg or "enable_rag" in error_msg:
                context.final_response = "⚠️ 系统配置加载失败，请刷新页面后重试"
                context.metadata["error"] = "配置加载失败"
            elif "AttributeError" in error_msg or "'NoneType'" in error_msg:
                context.final_response = "⚠️ 智能体初始化不完整，请稍后重试或刷新页面"
                context.metadata["error"] = "智能体初始化失败"
            else:
                context.final_response = f"⚠️ 处理过程中遇到问题，请稍后重试"
                context.metadata["error"] = error_msg
            
            context.metadata["error_type"] = type(e).__name__
            context.metadata["error_trace"] = error_trace
            if trace_id:
                try:
                    await agent_tracer.end_trace(
                        trace_id=trace_id,
                        final_answer=context.final_response or "",
                        success=False,
                        error_message=str(e)
                    )
                except Exception as trace_error:
                    logger.warning("[AgentTrace] LangGraph 失败追踪写入失败: %s", trace_error)
            return context
    
    def _create_initial_blackboard_state(
        self,
        user_input: str,
        session_id: str,
        history: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建 LangGraph 初始黑板状态
        
        这个状态会被传入 LangGraph 的 StateGraph，作为工作流的起点。
        所有后续的处理都会基于这个状态进行增量修改。
        
        Args:
            user_input: 用户输入
            session_id: 会话ID
            history: 历史消息
            metadata: 其他元数据
            
        Returns:
            Dict: 初始黑板状态
        """
        from app.langgraph.state import (
            AgentState, 
            create_initial_state as create_langgraph_state,
            AgentMessage,
            SpecialistType
        )
        
        # 构建消息历史
        messages = []
        if history:
            for msg in history[-10:]:  # 最多保留最近10条
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append(AgentMessage(
                    role=role,
                    content=content
                ))
        
        # 添加当前用户消息
        messages.append(AgentMessage(
            role="user",
            content=user_input
        ))
        
        # 从用户输入中提取关键实体
        entities = self._extract_entities(user_input)
        
        initial_state = create_langgraph_state(
            session_id=session_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            user_query=user_input,
            max_iterations=10,
            max_retries=3,
            entities=entities,
            messages=messages,
            specialists_needed=[],
            specialist_results=[],
            rag_context=[],
            metadata=metadata or {}
        )
        initial_state["enable_reflection"] = self.enable_reflection
        
        logger.debug("[黑板] 初始状态已创建: messages=%s, entities=%s", len(messages), entities)
        
        return initial_state
    
    # =========================================================================
    # 🚦 LangGraph 条件边路由函数（系统交警）
    # =========================================================================
    
    @staticmethod
    def route_after_intent(state: Dict[str, Any]) -> str | List[str]:
        """
        🚦 冷酷的交警逻辑：根据 IntentRouter 写在黑板上的意图，决定流量去向。
        
        这是一个纯代码函数，不调用大模型，只根据状态数据瞬间决定下一秒的流转方向。
        
        Args:
            state: AgentState 黑板状态
            
        Returns:
            str | List[str]: 路由目标（单路由返回字符串，并行路由返回列表）
        """
        logger.debug(
            "[Router Edge] intent=%s, routing=%s, specialists=%s, needs_clarification=%s",
            state.get("intent"),
            state.get("routing_strategy"),
            state.get("specialists_needed", []),
            state.get("needs_clarification")
        )
        
        if state.get("needs_clarification") and state.get("clarification_request"):
            logger.debug("[Router Edge] 需要追问，路由到 final")
            return "final"
        
        intent = state.get("intent", "direct_answer")
        specialists = state.get("specialists_needed", [])
        
        routing_strategy = state.get("routing_strategy", "")
        
        if intent == "direct_answer" or routing_strategy == "direct_answer":
            logger.debug("[Router Edge] 直接回答，路由到 final")
            return "final"
            
        elif intent == "rag_only" or routing_strategy == "rag_retrieval":
            logger.debug("[Router Edge] 路由到 rag_retrieval")
            return "rag_retrieval"
            
        # 多专家判断优先：compliance_check、multi_specialist 意图或 specialists > 1
        elif intent in ["compliance_check", "multi_specialist"] or len(specialists) > 1:
            logger.debug("[Router Edge] 多专家并行: %s", specialists)
            routes = []
            for s in specialists:
                if s == "finance":
                    routes.append("finance_specialist")
                elif s == "tax":
                    routes.append("tax_specialist")
                elif s == "legal":
                    routes.append("legal_specialist")

            if routes:
                return routes
            return ["finance_specialist"]

        # 单专家：single_specialist 策略或单意图
        elif routing_strategy in ("single_specialist", "report_queue") or intent in ["risk_analysis", "financial_analysis", "accounting_query", "tax_calculation", "tax_compliance", "contract_review", "legal_consultation"]:
            if not specialists:
                logger.debug("[Router Edge] 单专家无指定，默认 finance_specialist")
                return "finance_specialist"

            target = specialists[0]
            logger.debug("[Router Edge] 单专家: %s", target)

            if target == "finance":
                return "finance_specialist"
            elif target == "tax":
                return "tax_specialist"
            elif target == "legal":
                return "legal_specialist"
            else:
                return "finance_specialist"

        logger.debug("[Router Edge] 默认路由到 final")
        return "final"
    
    async def _execute_langgraph_workflow(
        self,
        initial_state: Dict[str, Any],
        context: OrchestrationContext,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        执行 LangGraph 工作流
        
        使用 LangGraph 的 StateGraph 和条件边来实现意图驱动的动态路由。
        
        Args:
            initial_state: 初始黑板状态
            context: 编排上下文
            
        Returns:
            Dict: 最终状态
        """
        from langgraph.graph import StateGraph, END, START
        
        logger.debug("[LangGraph] 构建工作流图")
        
        # 初始化节点函数集合
        nodes = Nodes(self)
        
        workflow = StateGraph(AgentState)
        
        # 📍 定义工作流节点（带日志追踪）
        logger.debug("[工作流构建] START → receptionist → intent_router → specialist/rag/final → reflection → final")
        
        workflow.add_node("receptionist", nodes.receptionist)
        workflow.add_node("intent_router", nodes.intent_router)
        workflow.add_node("rag_retrieval", nodes.rag_retrieval)
        workflow.add_node("graph_path_retrieval", nodes.graph_path_retrieval)
        workflow.add_node("finance_specialist", nodes.finance_specialist)
        workflow.add_node("tax_specialist", nodes.tax_specialist)
        workflow.add_node("legal_specialist", nodes.legal_specialist)
        workflow.add_node("reflection", nodes.reflection)
        workflow.add_node("final", nodes.final)
        
        workflow.add_edge(START, "receptionist")
        logger.debug("[边定义] START → receptionist")
        workflow.add_edge("receptionist", "intent_router")
        logger.debug("[边定义] receptionist → intent_router")
        
        # 意图路由后先去查图谱路径，再走 specialists
        workflow.add_edge("intent_router", "graph_path_retrieval")
        logger.debug("[边定义] intent_router → graph_path_retrieval")

        workflow.add_conditional_edges(
            "graph_path_retrieval",
            self.route_after_intent,
            {
                "finance_specialist": "finance_specialist",
                "tax_specialist": "tax_specialist",
                "legal_specialist": "legal_specialist",
                "rag_retrieval": "rag_retrieval",
                "final": "final"
            }
        )
        logger.debug("[边定义] graph_path_retrieval → (条件边) → specialist/final")
        
        def route_after_analysis(state: AgentState) -> str:
            enable_reflection = state.get("enable_reflection", self.enable_reflection)
            # 🆕 元问题不管前端是否开启反思，都跳过
            query = state.get("user_query", "")
            if hasattr(Nodes, '_is_meta_question') and Nodes._is_meta_question(query):
                logger.debug("[analysis route] 元问题，跳过反思")
                return "final"
            logger.debug("[analysis route] enable_reflection=%s", enable_reflection)
            return "reflection" if enable_reflection else "final"

        analysis_routes = {
            "reflection": "reflection",
            "final": "final"
        }
        workflow.add_conditional_edges("finance_specialist", route_after_analysis, analysis_routes)
        workflow.add_conditional_edges("tax_specialist", route_after_analysis, analysis_routes)
        workflow.add_conditional_edges("legal_specialist", route_after_analysis, analysis_routes)
        workflow.add_conditional_edges("rag_retrieval", route_after_analysis, analysis_routes)
        
        def check_reflection(state: AgentState) -> str:
            """反思审核后的条件路由：根据质量评估结果决定下一步"""
            res = state.get("reflection_result", {})
            acceptable = res.get("acceptable", True)
            retries = state.get("retry_count", 0)
            max_retries = state.get("max_retries", 3)
            logger.debug("[反思路由] acceptable=%s, retry_count=%s/%s", acceptable, retries, max_retries)
            
            if acceptable:
                logger.debug("[反思路由] 质量达标，路由到 final")
                return "final"
            else:
                logger.debug("[反思路由] 质量不达标")
                if retries >= max_retries:
                    logger.warning("[架构级熔断] 已达最大重试次数 (%s>=%s)，强制放行", retries, max_retries)
                    return "final"
                logger.debug("[反思路由] 打回重做 (第 %s 次)", retries + 1)
                return "finance_specialist"
        
        workflow.add_conditional_edges(
            "reflection",
            check_reflection,
            {
                "final": "final",
                "finance_specialist": "finance_specialist"
            }
        )
        workflow.add_edge("final", END)
        logger.debug("[边定义] specialists → reflection → (条件边) → final/finance_specialist → END")
        
        # 启用 MemorySaver 实现跨请求记忆持久化
        from langgraph.checkpoint.memory import MemorySaver
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)
        
        logger.debug("[LangGraph] 工作流图编译完成，已启用 MemorySaver")
        
        config = {
            "configurable": {
                "thread_id": context.session_id
            }
        }
        
        logger.debug("[LangGraph] 开始执行，thread_id=%s", context.session_id)
        
        # 🔧 创建节点执行追踪器
        class NodeTransitionTracker:
            def __init__(self):
                self.execution_path = []
            
            def on_node_start(self, node_name: str):
                logger.debug("[节点执行] 进入节点: %s", node_name)
            
            def on_node_end(self, node_name: str, state: dict):
                logger.debug("[节点执行] 节点完成: %s", node_name)
                self.execution_path.append(node_name)
                
                # 打印写入黑板的数据
                if isinstance(state, dict):
                    logger.debug("[黑板写入] %s keys=%s", node_name, list(state.keys()))
                    for key, value in state.items():
                        if value is not None and value != [] and value != {}:
                            if isinstance(value, (str, int, float, bool)):
                                logger.debug("   %s=%s", key, value)
                            elif isinstance(value, list):
                                logger.debug("   %s=list[%s]", key, len(value))
                                if value and len(value) <= 3:
                                    for i, item in enumerate(value):
                                        if isinstance(item, dict):
                                            logger.debug("     [%s]: %s", i, list(item.keys()))
                                        else:
                                            logger.debug("     [%s]: %s", i, str(item)[:100])
                            elif isinstance(value, dict):
                                logger.debug("   %s=dict keys=%s", key, list(value.keys())[:5])
                            else:
                                logger.debug("   %s=%s", key, type(value).__name__)
        
        tracker = NodeTransitionTracker()
        
        try:
            logger.debug("[LangGraph] initial_state type=%s keys=%s", type(initial_state), list(initial_state.keys()) if isinstance(initial_state, dict) else "not a dict")
            
            # 🚀 使用 stream 模式以获取节点执行信息
            logger.debug("[LangGraph] 准备执行工作流")
            final_state = initial_state
            async for event in app.astream(initial_state, config):
                for node_name, node_state in event.items():
                    if node_name != "__end__":
                        tracker.on_node_start(node_name)
                        tracker.on_node_end(node_name, node_state)
                        if progress_callback:
                            try:
                                await progress_callback(node_name, node_state if isinstance(node_state, dict) else {})
                            except Exception as callback_error:
                                logger.warning("[LangGraph] progress callback failed: %s", callback_error)
                        final_state = node_state
            
            logger.debug(
                "[LangGraph] 最终状态已更新: answer_len=%s, keys=%s",
                len(final_state.get("final_answer") or ""),
                list(final_state.keys())[:10]
            )
        except Exception as invoke_error:
            import traceback
            error_detail = traceback.format_exc()
            logger.error("[LangGraph] invoke 失败: %s", invoke_error)
            logger.debug("[LangGraph] 详细错误: %s", error_detail)
            raise invoke_error
        
        context.metadata["execution_path"] = tracker.execution_path
        logger.info("[LangGraph] 执行完成: path=%s", " → ".join(tracker.execution_path))
        
        return final_state
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """从文本中提取实体"""
        entities = {}
        
        # 提取公司名
        company_patterns = [
            r'公司', r'企业', r'集团', r'股份有限公司', r'有限公司'
        ]
        for pattern in company_patterns:
            if pattern in text:
                entities["has_company"] = True
                break
        
        # 提取金额
        import re
        amount_pattern = r'(\d+(?:\.\d+)?)\s*(?:万|亿|元)'
        amounts = re.findall(amount_pattern, text)
        if amounts:
            entities["amounts"] = amounts
        
        return entities
    
    # =========================================================================
    # 📴 废弃的方法（保留用于兼容性，逐步移除）
    # =========================================================================
    
    async def process_context(
        self,
        context: OrchestrationContext
    ) -> OrchestrationContext:
        """
        使用编排上下文处理请求（API路由专用方法）
        
        Args:
            context: 编排上下文
            
        Returns:
            更新后的编排上下文
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = datetime.now()
        trace_id = None
        step_number = 0
        
        try:
            user_input = context.user_query
            
            if not user_input:
                context.final_response = "用户查询不能为空"
                return context
            
            trace_id = await agent_tracer.start_trace(
                agent_type="multi_agent_orchestrator",
                user_query=user_input,
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                message_id=context.session_id
            )
            step_number += 1
            await agent_tracer.add_step(
                trace_id=trace_id,
                step_number=step_number,
                step_type="thought",
                content="开始多智能体协作流程"
            )
            
            routing_result = await self.intent_router.run(
                user_input=user_input,
                history=[],
                context={"session_id": context.session_id, "tenant_id": context.tenant_id}
            )
            step_number += 1
            await agent_tracer.add_step(
                trace_id=trace_id,
                step_number=step_number,
                step_type="action",
                content=f"意图路由Agent处理完成: {routing_result.model_dump_json()[:200]}...",
                tool_name="IntentRouterAgent",
                tool_input={"user_input": user_input},
                tool_output=routing_result.model_dump_json()[:500]
            )
            
            if routing_result.is_simple:
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content="直接返回简单响应"
                )
                
                if routing_result.simple_response == "__CONFIG_QUERY__":
                    config_response = self._build_config_query_response()
                    await agent_tracer.end_trace(
                        trace_id=trace_id,
                        final_answer=config_response,
                        success=True
                    )
                    context.final_response = config_response
                    return context
                
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=routing_result.simple_response,
                    success=True
                )
                context.final_response = routing_result.simple_response
                return context
            
            if routing_result.clarification_request:
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="thought",
                    content=f"检测到模糊输入，需要追问: {routing_result.clarification_request.type}"
                )
                print(f"💬 [编排器] 检测到需要追问: {routing_result.clarification_request.type}")
                context.clarification_request = routing_result.clarification_request
                context.final_response = None
                context.needs_clarification = True
                return context
            
            intent_result = routing_result.intent_result
            context.intent_result = intent_result
            step_number += 1
            await agent_tracer.add_step(
                trace_id=trace_id,
                step_number=step_number,
                step_type="thought",
                content=f"意图识别完成: {intent_result.intent.value}, 置信度: {intent_result.confidence:.2f}, 路由策略: {intent_result.routing_strategy.value}",
                tool_name="IntentRouterAgent",
                tool_input={"user_input": user_input},
                tool_output={
                    "intent": intent_result.intent.value,
                    "confidence": intent_result.confidence,
                    "routing_strategy": intent_result.routing_strategy.value,
                    "requires_specialists": intent_result.requires_specialists
                }
            )
            
            if hasattr(intent_result, 'needs_report_generation') and intent_result.needs_report_generation:
                context.enable_report_generation = True
                print("📄 [编排器] 检测到用户要求生成报告")
            
            from app.services.admin_notification_service import (
                admin_notification_service
            )
            
            risk_check_result = await admin_notification_service.handle_high_risk_operation(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                user_query=user_input,
                context={
                    "confidence": intent_result.confidence,
                    "entities": getattr(intent_result, 'entities', []),
                    "intent": intent_result.intent.value
                }
            )
            
            if risk_check_result["status"] == "pending_approval":
                context.metadata['hitl_pending'] = True
                context.metadata['hitl_approval_id'] = risk_check_result['approval_id']
                context.metadata['hitl_risk_level'] = risk_check_result['risk_level']
                context.final_response = f"⚠️ 检测到高风险操作，当前请求需要管理员审批。审批ID: {risk_check_result['approval_id']}，请等待审批完成。"
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="observation",
                    content="高风险操作，需要人工审批"
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.DIRECT_ANSWER:
                response = await self._handle_direct_answer(user_input, intent_result)
                context.final_response = response
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"直接回答: {response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.RAG_RETRIEVAL:
                response = await self._handle_rag_retrieval(user_input, intent_result)
                context.final_response = response
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"RAG检索回答: {response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.SINGLE_SPECIALIST:
                specialist_result = await self._handle_single_specialist(
                    user_input, intent_result
                )
                step_number += 1
                specialist_name = specialist_result.get('specialist', 'unknown')
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="action",
                    content=f"单专家{specialist_name}处理完成",
                    tool_name=f"{specialist_name.title()}Specialist"
                )
                
                context.specialist_results.append({
                    'specialist_type': specialist_result.get('specialist', 'unknown'),
                    'specialist_name': specialist_result.get('specialist', 'unknown'),
                    'success': specialist_result.get('status') == 'success',
                    'confidence': intent_result.confidence,
                    'analysis': specialist_result.get('result', {}),
                    'entities': intent_result.entities if hasattr(intent_result, 'entities') else [],
                    'recommendations': [],
                    'risks': [],
                    'metadata': {},
                    'processing_time': 0.0,
                    'error_message': specialist_result.get('error')
                })
                
                if context.enable_report_generation and self.report_generator:
                    context.final_response = await self._generate_report(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                    step_number += 1
                    await agent_tracer.add_step(
                        trace_id=trace_id,
                        step_number=step_number,
                        step_type="action",
                        content="生成报告完成",
                        tool_name="ReportGenerator"
                    )
                else:
                    if context.enable_reflection:
                        context = await self._run_reflection(context, user_input)
                        step_number += 1
                        await agent_tracer.add_step(
                            trace_id=trace_id,
                            step_number=step_number,
                            step_type="observation",
                            content="反思审核完成"
                        )
                    
                    context.final_response = await self._synthesize_output(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"单专家协作完成: {context.final_response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy in [
                RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
                RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
            ]:
                specialist_results = await self._handle_multi_specialist(
                    user_input, intent_result
                )
                
                specialists_list = list(specialist_results.get('results', {}).keys())
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="action",
                    content=f"多专家协作完成 [{intent_result.routing_strategy.value}]: {', '.join(specialists_list)}",
                    tool_name="MultiSpecialistCollaboration",
                    tool_input={"specialists": specialists_list, "strategy": intent_result.routing_strategy.value}
                )
                
                for specialist_name, result in specialist_results.get('results', {}).items():
                    context.specialist_results.append({
                        'specialist_type': specialist_name,
                        'specialist_name': specialist_name,
                        'success': result.get('status') == 'success',
                        'confidence': intent_result.confidence,
                        'analysis': result.get('result', {}),
                        'entities': [],
                        'recommendations': [],
                        'risks': [],
                        'metadata': {},
                        'processing_time': 0.0,
                        'error_message': result.get('error')
                    })
                
                if context.enable_report_generation and self.report_generator:
                    context.final_response = await self._generate_report(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                    step_number += 1
                    await agent_tracer.add_step(
                        trace_id=trace_id,
                        step_number=step_number,
                        step_type="action",
                        content="生成报告完成",
                        tool_name="ReportGenerator"
                    )
                else:
                    if context.enable_reflection:
                        context = await self._run_reflection(context, user_input)
                        step_number += 1
                        await agent_tracer.add_step(
                            trace_id=trace_id,
                            step_number=step_number,
                            step_type="observation",
                            content="反思审核完成"
                        )
                    
                    context.final_response = await self._synthesize_output(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"多专家协作完成: {context.final_response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.REPORT_QUEUE:
                context.metadata['status'] = 'queued'
                context.metadata['message'] = '报告生成请求已加入队列'
                context.final_response = "报告生成请求已加入队列"
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            context.final_response = "抱歉，暂时无法处理您的请求，请稍后重试。"
            await agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=context.final_response,
                success=True
            )
            return context
            
        except (ValueError, KeyError) as e:
            print(f"❌ [编排器] 处理数据错误: {e}")
            traceback.print_exc()
            context.final_response = f"处理数据错误: {str(e)}"
            if trace_id:
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=False,
                    error_message=str(e)
                )
        except (OSError, IOError) as e:
            print(f"❌ [编排器] 处理IO错误: {e}")
            traceback.print_exc()
            context.final_response = f"处理IO错误: {str(e)}"
            if trace_id:
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=False,
                    error_message=str(e)
                )
        except Exception as e:
            print(f"❌ [编排器] 处理异常: {e}")
            traceback.print_exc()
            context.final_response = f"处理失败: {str(e)}"
            context.metadata['error'] = str(e)
            if trace_id:
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=False,
                    error_message=str(e)
                )
            return context
    
    async def process(self, context: OrchestrationContext) -> OrchestrationContext:
        """处理请求（内部路由到 LangGraph 工作流）

        Args:
            context: 编排上下文

        Returns:
            更新后的编排上下文
        """
        # 🆕 使用 LangGraph 工作流，包含守卫逻辑
        return await self.process_user_request(
            user_input=context.user_query,
            session_id=context.session_id,
            metadata={'enable_reflection': context.enable_reflection, **(context.context or {})},
        )
    
    async def initialize(self):
        """
        异步初始化所有智能体和组件
        
        使用方式:
            orchestrator = AgentOrchestrator(tenant_id="xxx")
            await orchestrator.initialize()
        """
        if self.initialized:
            print("⚠️ [编排器] 已经初始化，跳过")
            return
        
        print("🎭 [编排器] 开始初始化所有组件...")
        
        try:
            from app.agent_framework.tools.agent_tool_registry import (
                initialize_tool_manager
            )
            
            default_provider = settings.get_llm_provider_for_agent("receptionist")
            print(f"🎭 [编排器] 默认智能体使用 LLM: {default_provider}")
            self.llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            self.tool_manager = ToolManager()
            
            # 注册 MCP 工具和本地工具
            print("🔧 [编排器] 注册工具...")
            tool_result = await initialize_tool_manager(
                self.tool_manager,
                include_mcp=True,
                include_local=True,
                tenant_id=self.tenant_id
            )
            logger.info(f"已注册 {tool_result['total_count']} 个工具")
            
            print("🤖 [编排器] 创建意图路由智能体（融合接待+意图识别）...")
            self.intent_router = IntentRouterAgent(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                confidence_threshold=0.7,
                timeout=30.0,
                specialist_descriptions=self._specialist_descriptions,
                intent_mapping=self._intent_mapping
            )
            
            print("📊 [编排器] 初始化能力配置...")
            
            print("💼 [编排器] 创建专业智能体...")
            self.finance_specialist = FinanceSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                skill_registry=self.skill_registry,
            )

            self.tax_specialist = TaxSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                skill_registry=self.skill_registry,
            )

            self.legal_specialist = LegalSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                skill_registry=self.skill_registry,
            )
            
            if self.enable_reflection:
                print("🔍 [编排器] 启用质量审查函数...")
            
            print("📝 [编排器] 创建报告生成器...")
            self.report_generator = ReportGenerator(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            
            print("🎨 [编排器] 创建结果合成器...")
            self.output_agent = ResultSynthesizer(llm_adapter=self.llm_adapter)
            
            if self.enable_rag:
                print("📚 [编排器] 初始化RAG检索器...")
                await self._initialize_rag()
            
            print("🧠 [编排器] 初始化记忆管理器...")
            session_id = f"orchestrator_{self.tenant_id}_{uuid.uuid4().hex[:8]}"
            self.memory_manager = MemoryManager(
                session_id=session_id,
                user_id=self.user_id
            )
            
            self.initialized = True
            print("✅ [编排器] 所有组件初始化完成")
            
        except (ValueError, KeyError) as e:
            print(f"❌ [编排器] 初始化数据错误: {e}")
            raise
        except (OSError, IOError) as e:
            print(f"❌ [编排器] 初始化IO错误: {e}")
            raise
        except Exception as e:
            print(f"❌ [编排器] 初始化失败: {e}")
            raise
    
    async def _initialize_rag(self):
        """初始化RAG检索器"""
        try:
            from app.services.embedding_service import EmbeddingService
            from app.services.search_service import SearchService
            
            embedding_service = EmbeddingService()
            search_service = SearchService()
            
            self.rag_retriever = TenantIsolatedRAGRetriever(
                embedding_service=embedding_service,
                enable_audit=True,
                search_service=search_service
            )
            
            print("📚 [编排器] RAG检索器初始化成功 (使用 pgvector)")
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [编排器] RAG检索器初始化数据错误: {e}")
            self.rag_retriever = None
        except (OSError, IOError) as e:
            print(f"⚠️ [编排器] RAG检索器初始化IO错误: {e}")
            self.rag_retriever = None
        except Exception as e:
            print(f"⚠️ [编排器] RAG检索器初始化失败: {e}")
            self.rag_retriever = None
    
    def _initialize_capabilities(self):
        """
        初始化能力配置（启动时一次性加载）
        
        从配置文件加载专家能力，生成描述文本，用于嵌入意图智能体提示词
        """
        try:
            from .capability_loader import get_capability_loader
            
            loader = get_capability_loader()
            loader.load_from_file()
            self._capability_config = loader._config
            
            self._specialist_descriptions = self._generate_specialist_descriptions()
            self._intent_mapping = loader.get_intent_mapping()
            
            intent_count = len(self._intent_mapping)
            specialist_count = len(set(self._intent_mapping.values()))
            print(f"✅ [编排器] 能力配置加载成功，共 {specialist_count} 个专家，{intent_count} 种意图类型")
            
        except Exception as e:
            print(f"⚠️ [编排器] 能力配置加载失败: {e}")
            self._specialist_descriptions = self._get_default_descriptions()
            self._intent_mapping = {}
    
    def _generate_specialist_descriptions(self) -> str:
        """
        从配置文件生成专家能力描述文本
        
        这些描述会被嵌入到意图智能体的提示词中
        """
        agents_config = self._capability_config.get('agents', {})
        
        descriptions = []
        for agent_type, config in agents_config.items():
            if not config.get('enabled', True):
                continue
            
            name = config.get('agent_name', agent_type)
            domains = [d['display_name'] for d in config.get('domains', [])]
            
            high_keywords = config.get('keywords', {}).get('high_weight', [])
            medium_keywords = config.get('keywords', {}).get('medium_weight', [])
            all_keywords = high_keywords + medium_keywords[:5]
            
            intent_mappings = []
            for intent, specialist in self._intent_mapping.items():
                if specialist == agent_type:
                    intent_mappings.append(intent)
            
            desc = f"""
### {name} ({agent_type})
- **核心领域**: {', '.join(domains[:5])}
- **关键词**: {', '.join(all_keywords[:10])}
- **识别的意图**: {', '.join(intent_mappings[:5]) if intent_mappings else '通用查询'}
"""
            descriptions.append(desc)
        
        return '\n'.join(descriptions)
    
    def _get_default_descriptions(self) -> str:
        """获取默认专家描述（当配置加载失败时使用）"""
        return """
### 财务专家 (finance)
- **核心领域**: 投资分析、贷款融资、预算管理、财务报表分析、成本控制
- **关键词**: 财务、投资、融资、贷款、报表、利润、成本、预算
- **识别的意图**: financial_analysis, accounting_query, investment_advisory

### 税务专家 (tax)
- **核心领域**: 税务计算、税务政策咨询、税务合规、发票管理
- **关键词**: 税务、税收、纳税、申报、抵扣、发票、税率
- **识别的意图**: tax_calculation, tax_planning, tax_compliance

### 法务专家 (legal)
- **核心领域**: 合同审查、法律咨询、合规检查、知识产权保护
- **关键词**: 法律、合同、协议、条款、违约、赔偿、合规
- **识别的意图**: contract_review, legal_consultation, compliance_check

### 通用助手 (general)
- **核心领域**: 通用查询、问候、闲聊
- **关键词**: 你好、请问、帮助
- **识别的意图**: greeting, chit_chat
"""
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取意图智能体提示词的渲染上下文"""
        return {
            "specialist_descriptions": self._specialist_descriptions,
            "intent_mapping": self._intent_mapping,
        }
    
    def _resolve_specialist(
        self,
        query: str,
        intent_result: Optional[IntentAnalysisResult] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        使用意图映射解析专家列表
        
        解析策略：
        1. 如果有意图分析结果，使用意图映射表
        2. 否则返回默认专家
        
        注意：这里只做简单的映射查询，不做运行时匹配计算
        """
        if not self._intent_mapping:
            logger.warning("⚠️ [编排器] 意图映射未初始化，使用默认路由")
            if intent_result and intent_result.requires_specialists:
                return intent_result.requires_specialists[:self.max_parallel_agents]
            return ["general"]
        
        if intent_result and intent_result.intent.value in self._intent_mapping:
            specialist = self._intent_mapping[intent_result.intent.value]
            logger.info(f"📊 [编排器] 意图映射路由: {intent_result.intent.value} -> {specialist}")
            return [specialist]
        
        if intent_result and intent_result.requires_specialists:
            return intent_result.requires_specialists[:self.max_parallel_agents]
        
        return ["general"]
    
    async def _emit_thinking_events(
        self,
        messages: List[Dict[str, Any]],
        interval: float = 2.0
    ) -> AsyncGenerator[str, None]:
        """
        定期发送思考事件
        
        Args:
            messages: 消息列表
            interval: 发送间隔（秒）
        """
        for i, msg in enumerate(messages):
            await asyncio.sleep(interval)
            yield json.dumps({
                "type": "thinking",
                "stage": msg.get("stage", "processing"),
                "message": msg.get("message", "正在思考..."),
                "progress": msg.get("progress", 50)
            }, ensure_ascii=False)
    
    async def _run_thinking_loop(
        self,
        messages: List[Dict[str, Any]],
        interval: float = 2.0,
        queue: Optional[asyncio.Queue] = None,
        stop_event: asyncio.Event|None = None
    ):
        """
        运行思考循环，通过队列发送进度消息直到任务完成
        
        Args:
            messages: 消息列表（会循环发送）
            interval: 发送间隔（秒）
            queue: 用于传递消息的队列
            stop_event: 停止事件（可选）
        """
        import itertools
        
        for msg in itertools.cycle(messages):
            if stop_event and stop_event.is_set():
                break
            
            await asyncio.sleep(interval)
            msg_data = {
                "type": "thinking",
                "stage": msg.get("stage", "processing"),
                "message": msg.get("message", "正在思考..."),
                "progress": msg.get("progress", 50)
            }
            json_msg = json.dumps(msg_data, ensure_ascii=False)
            
            if queue is not None:
                await queue.put(json_msg)
    
    async def stream_process_context(
        self,
        context: OrchestrationContext
    ) -> AsyncGenerator[str, None]:
        """
        流式处理编排上下文
        
        Args:
            context: 编排上下文
            
        Yields:
            逐步生成的内容（统一为JSON格式的stage事件或文本块）
        """
        from datetime import datetime
        
        if not self.initialized:
            await self.initialize()
        
        start_time = datetime.now()
        latency_tracker = LatencyTracker()
        latency_tracker.start()
        
        try:
            user_input = context.user_query
            
            yield json.dumps({
                "type": "ttft",
                "stage": "received",
                "timestamp": start_time.isoformat()
            }, ensure_ascii=False)
            
            cached_result = await self._check_cache(user_input)
            if cached_result:
                latency_tracker.mark("cache_hit")
                yield json.dumps({
                    "type": "cache_hit",
                    "result": cached_result,
                    "latency_ms": latency_tracker.get_summary()["total_ms"]
                }, ensure_ascii=False)
                yield json.dumps({
                    "type": "done",
                    "processing_time": latency_tracker.get_summary()["total_ms"],
                    "from_cache": True
                }, ensure_ascii=False)
                return
            
            yield json.dumps({
                "type": "stage",
                "stage": "receptionist",
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False)
            
            if not user_input:
                error_event = json.dumps({
                    "type": "error",
                    "error": "用户查询不能为空"
                }, ensure_ascii=False)
                print(f"📤 [流式] 发送错误事件: {error_event}")
                yield error_event
                done_event = json.dumps({
                    "type": "done",
                    "processing_time": 0
                }, ensure_ascii=False)
                print(f"📤 [流式] 发送完成事件: {done_event}")
                yield done_event
                return
            
            latency_tracker.mark("intent_routing")
            
            print("🎯 [流式] 开始意图路由分析...")
            routing_result = await self.intent_router.run(
                user_input=user_input,
                history=[],
                context={"session_id": context.session_id, "tenant_id": context.tenant_id}
            )
            print(f"✅ [流式] 意图路由完成，is_simple={routing_result.is_simple}")
            
            if routing_result.is_simple:
                print("📝 [流式] 发送简单响应阶段...")
                stage_event = json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                yield stage_event
                
                if routing_result.simple_response == "__CONFIG_QUERY__":
                    config_response = self._build_config_query_response()
                    text_event = json.dumps({
                        "type": "text",
                        "content": config_response
                    }, ensure_ascii=False)
                else:
                    text_event = json.dumps({
                        "type": "text",
                        "content": routing_result.simple_response
                    }, ensure_ascii=False)
                    await self._save_to_cache(user_input, routing_result.simple_response)
                
                print(f"📤 [流式] 发送文本事件: {text_event[:100]}...")
                yield text_event
                
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                latency_tracker.mark("response_ready")
                
                done_event = json.dumps({
                    "type": "done",
                    "processing_time": processing_time,
                    "latency_summary": latency_tracker.get_summary()
                }, ensure_ascii=False)
                print(f"📤 [流式] 发送完成事件: 处理时间={processing_time}ms")
                yield done_event
                return
            
            intent_stage_event = json.dumps({"type": "stage", "stage": "intent"}, ensure_ascii=False)
            print("📤 [流式] 发送意图分析阶段事件")
            yield intent_stage_event
            
            intent_result = routing_result.intent_result
            context.intent_result = intent_result
            
            if hasattr(intent_result, 'needs_report_generation') and intent_result.needs_report_generation:
                context.enable_report_generation = True
                print("📄 [编排器] 检测到用户要求生成报告")
            
            intent_detail_event = json.dumps({
                "type": "stage",
                "stage": "intent",
                "intent": {
                    "category": intent_result.intent.value,
                    "confidence": intent_result.confidence,
                    "routing_strategy": intent_result.routing_strategy.value
                }
            }, ensure_ascii=False)
            print(f"📤 [流式] 发送意图详情事件: category={intent_result.intent.value}, confidence={intent_result.confidence}")
            yield intent_detail_event
            
            from app.services.admin_notification_service import (
                admin_notification_service
            )
            
            risk_check_result = await admin_notification_service.handle_high_risk_operation(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                user_query=user_input,
                context={
                    "confidence": intent_result.confidence,
                    "entities": getattr(intent_result, 'entities', []),
                    "intent": intent_result.intent.value
                }
            )
            
            if risk_check_result["status"] == "pending_approval":
                yield json.dumps({
                    "type": "error",
                    "error": f"⚠️ 检测到高风险操作，当前请求需要管理员审批。审批ID: {risk_check_result['approval_id']}"
                }, ensure_ascii=False)
                yield json.dumps({
                    "type": "done",
                    "processing_time": int((datetime.now() - start_time).total_seconds() * 1000)
                }, ensure_ascii=False)
                return
            
            specialists_stage_event = json.dumps({"type": "stage", "stage": "specialists"}, ensure_ascii=False)
            print("📤 [流式] 发送专家处理阶段事件")
            yield specialists_stage_event
            
            if intent_result.routing_strategy == RoutingStrategy.SINGLE_SPECIALIST:
                specialist_type = intent_result.requires_specialists[0] if intent_result.requires_specialists else "finance"
                specialist_name_map = {"finance": "💰 财务专家", "tax": "📋 税务专家", "legal": "⚖️ 法务专家"}
                specialist_display = specialist_name_map.get(specialist_type, specialist_type)
                
                latency_tracker.mark("specialist_start")
                
                specialist_result = await self._handle_single_specialist_stream(
                    user_input, intent_result
                )
                
                latency_tracker.mark("specialist_complete")
                
                specialists_needed = intent_result.requires_specialists[:1] if intent_result.requires_specialists else []
                suggested = intent_result.requires_specialists[0] if intent_result.requires_specialists else None
                
                context.specialist_results.append({
                    'specialist_type': suggested,
                    'specialist_name': suggested,
                    'response': specialist_result,
                    'success': specialist_result.get('success', True)
                })
                
                if context.enable_reflection:
                    yield json.dumps({"type": "stage", "stage": "reflection"}, ensure_ascii=False)
                    specialist_result_str = json.dumps(specialist_result, ensure_ascii=False)
                    reflection_result = await review_quality(
                        user_question=user_input,
                        ai_answer=specialist_result_str
                    )
                    context.reflection_result = reflection_result
                    yield json.dumps({
                        "type": "stage",
                        "stage": "reflection",
                        "result": reflection_result.get("issues", [])
                    }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "generating",
                    "message": "正在生成最终回复...",
                    "progress": 85
                }, ensure_ascii=False)
                
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                
                final_response = await self._format_specialist_response(
                    specialist_result,
                    intent_result,
                    user_input
                )
                
                # 按行发送，保持Markdown格式
                print(f"📤 [流式] 准备发送响应，长度: {len(final_response)} 字符")
                
                if not final_response or len(final_response.strip()) == 0:
                    final_response = "抱歉，暂时无法生成回复，请稍后重试。"
                
                # 逐行发送，确保完整性
                for line in final_response.split('\n'):
                    if line.strip():  # 跳过空行
                        text_event = json.dumps({
                            "type": "text",
                            "content": line + "\n"
                        }, ensure_ascii=False)
                        yield text_event
                        print(f"📤 [流式] 发送行: {line[:30]}...")
                
                print(f"📤 [流式] 响应发送完成")
                
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                done_event = json.dumps({
                    "type": "done",
                    "processing_time": processing_time,
                    "latency_summary": latency_tracker.get_summary()
                }, ensure_ascii=False)
                print(f"📤 [流式] 发送完成事件: 处理时间={processing_time}ms")
                yield done_event
                return
            
            elif intent_result.routing_strategy in [
                RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
                RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
            ]:
                yield json.dumps({
                    "type": "thinking",
                    "stage": "preparing",
                    "message": "正在准备多专家协作分析...",
                    "progress": 15
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "coordinating",
                    "message": f"正在协调 {len(intent_result.requires_specialists)} 个专业顾问...",
                    "progress": 30
                }, ensure_ascii=False)
                
                specialist_results = await self._handle_multi_specialist(
                    user_input, intent_result
                )
                
                specialists_needed = list(specialist_results.get('results', {}).keys())
                yield json.dumps({
                    "type": "stage",
                    "stage": "specialists",
                    "specialists": specialists_needed
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "analyzing",
                    "message": "正在综合分析各专家意见...",
                    "progress": 70
                }, ensure_ascii=False)
                
                for specialist_name, result in specialist_results.get('results', {}).items():
                    context.specialist_results.append({
                        'specialist_type': specialist_name,
                        'specialist_name': specialist_name,
                        'response': result,
                        'success': result.get('status') == 'success'
                    })
                
                if context.enable_reflection:
                    yield json.dumps({"type": "stage", "stage": "reflection"}, ensure_ascii=False)
                    specialist_results_str = json.dumps(specialist_results, ensure_ascii=False)
                    reflection_result = await review_quality(
                        user_question=user_input,
                        ai_answer=specialist_results_str
                    )
                    context.reflection_result = reflection_result
                    yield json.dumps({
                        "type": "stage",
                        "stage": "reflection",
                        "result": reflection_result.get("issues", [])
                    }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "generating",
                    "message": "正在生成综合分析报告...",
                    "progress": 85
                }, ensure_ascii=False)
                
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                
                final_response = await self._format_multi_specialist_response(
                    specialist_results,
                    intent_result,
                    user_input
                )
                
                # 逐行发送，保持Markdown格式
                print(f"📤 [流式-多专家] 准备发送响应，长度: {len(final_response)} 字符")
                
                if not final_response or len(final_response.strip()) == 0:
                    final_response = "抱歉，暂时无法生成回复，请稍后重试。"
                
                # 逐行发送
                for line in final_response.split('\n'):
                    if line.strip():
                        text_event = json.dumps({
                            "type": "text",
                            "content": line + "\n"
                        }, ensure_ascii=False)
                        yield text_event
                        print(f"📤 [流式-多专家] 发送行: {line[:30]}...")
                
                print(f"📤 [流式-多专家] 响应发送完成")
                
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                yield json.dumps({
                    "type": "done",
                    "processing_time": processing_time,
                    "latency_summary": latency_tracker.get_summary()
                }, ensure_ascii=False)
                return
            
            elif intent_result.routing_strategy == RoutingStrategy.REPORT_QUEUE:
                yield json.dumps({
                    "type": "error",
                    "error": "报告生成请求已加入队列"
                }, ensure_ascii=False)
                yield json.dumps({
                    "type": "done",
                    "processing_time": int((datetime.now() - start_time).total_seconds() * 1000)
                }, ensure_ascii=False)
                return

            elif intent_result.routing_strategy == RoutingStrategy.DIRECT_ANSWER:
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                direct_response = await self._handle_direct_answer(user_input, intent_result)
                # 逐行发送直接回答
                for line in direct_response.split('\n'):
                    if line.strip():
                        text_event = json.dumps({
                            "type": "text",
                            "content": line + "\n"
                        }, ensure_ascii=False)
                        yield text_event
                await self._save_to_cache(user_input, direct_response)
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                yield json.dumps({
                    "type": "done",
                    "processing_time": processing_time,
                    "latency_summary": latency_tracker.get_summary()
                }, ensure_ascii=False)
                return

            elif intent_result.routing_strategy == RoutingStrategy.RAG_RETRIEVAL:
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                rag_response = await self._handle_rag_retrieval(user_input, intent_result)
                for line in rag_response.split('\n'):
                    if line.strip():
                        text_event = json.dumps({
                            "type": "text",
                            "content": line + "\n"
                        }, ensure_ascii=False)
                        yield text_event
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                yield json.dumps({
                    "type": "done",
                    "processing_time": processing_time,
                    "latency_summary": latency_tracker.get_summary()
                }, ensure_ascii=False)
                return
            
            latency_tracker.mark("first_token")
            
            yield json.dumps({
                "type": "error",
                "error": "抱歉，暂时无法处理您的请求，请稍后重试。"
            }, ensure_ascii=False)
            
            await self._save_to_cache(user_input, context.final_response)
            yield json.dumps({
                "type": "done",
                "processing_time": int((datetime.now() - start_time).total_seconds() * 1000),
                "latency_summary": latency_tracker.get_summary()
            }, ensure_ascii=False)
            
        except Exception as e:
            print(f"❌ [编排器] 流式处理错误: {e}")
            traceback.print_exc()
            yield json.dumps({
                "type": "error",
                "error": str(e)
            }, ensure_ascii=False)
            yield json.dumps({
                "type": "done",
                "processing_time": int((datetime.now() - start_time).total_seconds() * 1000),
                "latency_summary": latency_tracker.get_summary()
            }, ensure_ascii=False)
    
    async def stream_process(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式处理请求（API路由专用方法）
        
        Args:
            user_input: 用户输入
            session_id: 会话ID
            history: 历史消息
            
        Yields:
            逐步生成的内容
        """
        context = OrchestrationContext(
            session_id=session_id or str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            user_query=user_input,
            context={"history": history or []},
            enable_reflection=self.enable_reflection,
            enable_rag=self.enable_rag
        )
        
        async for chunk in self.stream_process_context(context):
            yield chunk
    
    def _is_simple_response(self, response: str) -> bool:
        """判断是否为简单回答（不需要进一步处理）"""
        simple_indicators = [
            "你好", "您好", "hi", "hello",
            "现在", "今天",
            "谢谢", "thanks",
            "不客气", "很高兴"
        ]
        
        return any(indicator in response[:20] for indicator in simple_indicators)
    
    def _build_config_query_response(self) -> str:
        """构建系统配置查询响应"""
        reflection_status = "已启用" if self.enable_reflection else "已禁用"
        rag_status = "已启用" if self.enable_rag else "已禁用"
        report_status = "已启用" if self.enable_report_generation else "已禁用"
        
        response = f"""📋 **当前系统配置状态**

以下是当前会话的系统设置：

| 功能 | 状态 |
|------|------|
| **反思审核** | {reflection_status} |
| **知识检索 (RAG)** | {rag_status} |
| **报告生成** | {report_status} |

**说明**：
- 反思审核：对多智能体回答进行质量评估和审核
- 知识检索：从企业知识库中检索相关信息
- 报告生成：自动生成结构化分析报告

如需更改设置，请在对话页面的设置面板中调整。"""

        return response
    
    async def _handle_direct_answer(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> str:
        """处理直接回答类型的请求（闲聊/问候/简单问答）"""
        prompt = f"""你是一个企业级财税法务智能助手。用户正在和你进行对话。

你的职责：
- 友好、自然地回应用户的问候和日常闲聊
- 对专业知识类问题，给出准确、清晰的解答
- 适当介绍你能提供的服务：财务分析、税务咨询、法律顾问、合同审查、政策检索等
- 如果问题超出你的专业范围（财税法务），礼貌说明并引导到相关领域

用户输入：{user_input}

请用中文给出简洁、友好的回复（不超过200字）："""

        try:
            response = await self.llm_adapter.agenerate([prompt])
            if response and response.content:
                return response.content.strip()
        except Exception as e:
            logger.warning("[直接回答] LLM 调用失败，使用兜底回复: %s", e)

        # 硬编码兜底
        greeting_responses = {
            IntentCategory.GREETING: "您好！有什么可以帮助您的吗？",
            IntentCategory.CHIT_CHAT: "我们来聊聊吧，有什么感兴趣的话题吗？"
        }
        return greeting_responses.get(
            intent_result.intent,
            "好的，我明白了。"
        )
    
    async def _handle_rag_retrieval(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> str:
        """处理RAG检索类型的请求"""
        if not self.rag_retriever:
            return "抱歉，知识库检索功能暂时不可用。"
        
        try:
            rag_context = await self.rag_retriever.retrieve(
                query=user_input,
                tenant_id=self.tenant_id,
                top_k=5
            )
            
            results = rag_context.results if rag_context else []
            
            if not results:
                return "抱歉，我在知识库中没有找到相关信息。"
            
            context = "\n".join([
                f"- {r.content[:200]}"
                for r in results[:3]
            ])
            
            prompt = f"""根据以下知识库内容回答用户问题：

知识库内容：
{context}

用户问题：{user_input}

请给出准确、简洁的回答。"""
            
            response = await self.llm_adapter.agenerate([prompt])
            return response.content if response and response.content else "抱歉，未能生成回答。"
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [编排器] RAG检索数据错误: {e}")
            return "抱歉，知识库检索数据错误。"
        except (OSError, IOError) as e:
            print(f"⚠️ [编排器] RAG检索IO错误: {e}")
            return "抱歉，知识库检索IO错误。"
        except Exception as e:
            print(f"⚠️ [编排器] RAG检索失败: {e}")
            return "抱歉，知识库检索失败。"
    
    async def _handle_single_specialist_stream(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """流式处理单专家类型的请求（供 stream_process_context 使用）
        
        这个方法调用 _handle_single_specialist 并返回结果。
        """
        return await self._handle_single_specialist(user_input, intent_result)
    
    async def _handle_single_specialist(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """处理单专家类型的请求"""
        specialist_map = {
            "finance": self.finance_specialist,
            "tax": self.tax_specialist,
            "legal": self.legal_specialist
        }
        
        specialists_needed = intent_result.requires_specialists
        
        if not specialists_needed or specialists_needed == ["general"]:
            return {
                "status": "no_specialist",
                "message": "未找到合适的专家"
            }
        
        specialist_name = specialists_needed[0]
        specialist = specialist_map.get(specialist_name)
        
        if not specialist:
            return {
                "status": "error",
                "message": f"专家 {specialist_name} 不可用"
            }
        
        rag_context = None
        if self.enable_rag and self.rag_retriever:
            try:
                print("📚 [编排器] 正在检索企业相关数据...")
                rag_retrieval_context = await self.rag_retriever.retrieve(
                    query=user_input,
                    tenant_id=self.tenant_id,
                    top_k=5
                )
                
                rag_results = rag_retrieval_context.results if rag_retrieval_context else []
                
                if rag_results:
                    print(f"📚 [编排器] 检索到 {len(rag_results)} 条相关数据")
                    rag_context = {
                        "documents": [
                            {
                                "content": r.content,
                                "source": r.source,
                                "doc_type": r.doc_type.value if hasattr(r.doc_type, 'value') else str(r.doc_type),
                                "metadata": r.metadata
                            }
                            for r in rag_results
                        ],
                        "summary": self._generate_rag_summary([
                            {"content": r.content, "source": r.source}
                            for r in rag_results
                        ]),
                        "specialist_type": specialist_name
                    }
                else:
                    print("📚 [编排器] 未检索到相关数据")
                    rag_context = {
                        "documents": [],
                        "summary": "RAG检索未完成",
                        "specialist_type": specialist_name,
                        "has_data": False,
                        "data_status": "rag_failed"
                    }
            except Exception as e:
                print(f"⚠️ [编排器] RAG检索失败: {e}")
                rag_context = {
                    "documents": [],
                    "summary": "RAG检索失败",
                    "specialist_type": specialist_name,
                    "has_data": False,
                    "data_status": "rag_error"
                }
        
        specialist_context = intent_result.suggested_params or {}
        specialist_context["tenant_id"] = self.tenant_id
        specialist_context["user_id"] = self.user_id
        
        print("🔍 [编排器] 数据可用性检查:")
        print(f"   - specialist_type: {specialist_name}")
        docs_count = len(rag_context.get('documents', []))
        print(f"   - RAG文档数: {docs_count}")
        rag_summary = rag_context.get('summary', '')
        print(f"   - RAG摘要: {rag_summary[:50] if rag_summary else '无'}...")
        
        print("📤 [编排器] 调用专家处理（无论RAG结果如何，专家都会查询企业数据库）")
        
        try:
            if hasattr(specialist, 'consult'):
                result = await specialist.consult(
                    query=user_input,
                    entities=intent_result.entities,
                    context=specialist_context,
                    rag_context=rag_context
                )
            else:
                result = await specialist.run(
                    user_input=user_input,
                    context=specialist_context,
                    rag_context=rag_context
                )
            
            return {
                "status": "success",
                "specialist": specialist_name,
                "result": result
            }
            
        except (ValueError, KeyError) as e:
            print(f"❌ [编排器] 专家调用数据错误: {e}")
            return {
                "status": "error",
                "error": f"专家调用数据错误: {str(e)}"
            }
        except (OSError, IOError) as e:
            print(f"❌ [编排器] 专家调用IO错误: {e}")
            return {
                "status": "error",
                "error": f"专家调用IO错误: {str(e)}"
            }
        except Exception as e:
            print(f"❌ [编排器] 专家调用失败: {e}")
            return {
                "status": "error",
                "specialist": specialist_name,
                "error": str(e)
            }
    
    async def _handle_multi_specialist(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """处理多专家类型的请求"""
        specialists_needed = intent_result.requires_specialists
        
        specialist_map = {
            "finance": self.finance_specialist,
            "tax": self.tax_specialist,
            "legal": self.legal_specialist
        }
        
        specialist_context = intent_result.suggested_params or {}
        specialist_context["tenant_id"] = self.tenant_id
        specialist_context["user_id"] = self.user_id
        
        if intent_result.routing_strategy == RoutingStrategy.MULTI_SPECIALIST_PARALLEL:
            tasks = {}
            semaphore = asyncio.Semaphore(max(1, self.max_parallel_agents))

            async def run_specialist(name: str, specialist: Any):
                async with semaphore:
                    context_copy = specialist_context.copy()
                    if hasattr(specialist, 'consult'):
                        return await specialist.consult(
                            query=user_input,
                            entities=intent_result.entities,
                            context=context_copy
                        )
                    return await specialist.run(
                        user_input=user_input,
                        context=context_copy
                    )

            for specialist_name in specialists_needed[:self.max_parallel_agents]:
                specialist = specialist_map.get(specialist_name)
                if specialist:
                    tasks[specialist_name] = run_specialist(specialist_name, specialist)
            
            results = {}
            if tasks:
                # 并发执行所有任务
                task_coroutines = list(tasks.values())
                gathered_results = await asyncio.gather(*task_coroutines, return_exceptions=True)
                
                for idx, (specialist_name, task_result) in enumerate(zip(tasks.keys(), gathered_results)):
                    if isinstance(task_result, Exception):
                        # 处理异常
                        if isinstance(task_result, (ValueError, KeyError)):
                            results[specialist_name] = {
                                "status": "error",
                                "error": f"数据错误: {str(task_result)}"
                            }
                        elif isinstance(task_result, (OSError, IOError)):
                            results[specialist_name] = {
                                "status": "error",
                                "error": f"IO错误: {str(task_result)}"
                            }
                        else:
                            results[specialist_name] = {
                                "status": "error",
                                "error": str(task_result)
                            }
                    else:
                        # 正常结果
                        results[specialist_name] = {
                            "status": "success",
                            "result": task_result
                        }
            
            return {
                "status": "success",
                "mode": "parallel",
                "results": results
            }
        
        else:
            results = {}
            accumulated_context = specialist_context.copy()
            
            for specialist_name in specialists_needed:
                specialist = specialist_map.get(specialist_name)
                if not specialist:
                    continue
                
                try:
                    if hasattr(specialist, 'consult'):
                        result = await specialist.consult(
                            query=user_input,
                            entities=accumulated_context.get("entities", intent_result.entities),
                            context=accumulated_context
                        )
                    else:
                        result = await specialist.run(
                            user_input=user_input,
                            context=accumulated_context
                        )
                    
                    results[specialist_name] = {
                        "status": "success",
                        "result": result
                    }
                    
                    accumulated_context[specialist_name] = result
                    
                except (ValueError, KeyError) as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": f"数据错误: {str(e)}"
                    }
                except (OSError, IOError) as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": f"IO错误: {str(e)}"
                    }
                except Exception as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            return {
                "status": "success",
                "mode": "sequential",
                "results": results
            }
    
    def _generate_rag_summary(self, rag_results: List[Dict[str, Any]]) -> str:
        """
        生成RAG检索结果的摘要
        
        Args:
            rag_results: RAG检索结果
            
        Returns:
            摘要文本
        """
        if not rag_results:
            return ""
        
        try:
            summary_parts = []
            
            financial_keywords = ['财务', '投资', '融资', '贷款', '报表', '利润', '成本', '预算', '现金流', '盈利', '亏损', '资产', '负债', '权益']
            tax_keywords = ['税务', '税收', '纳税', '申报', '抵扣', '发票', '税率', '税额', '免税', '退税']
            legal_keywords = ['法律', '合同', '协议', '条款', '违约', '赔偿', '合规', '知识产权', '专利', '商标']
            
            relevant_docs = []
            for doc in rag_results:
                content = doc.get('content', '').lower()
                score = doc.get('score', 0)
                
                if any(kw in content for kw in financial_keywords):
                    relevant_docs.append((doc, score, 'finance'))
                elif any(kw in content for kw in tax_keywords):
                    relevant_docs.append((doc, score, 'tax'))
                elif any(kw in content for kw in legal_keywords):
                    relevant_docs.append((doc, score, 'legal'))
                else:
                    relevant_docs.append((doc, score, 'general'))
            
            relevant_docs.sort(key=lambda x: x[1], reverse=True)
            
            summary_parts.append(f"共检索到 {len(rag_results)} 条相关数据，以下是关键信息摘要：\n")
            
            for i, (doc, score, category) in enumerate(relevant_docs[:3], 1):
                content = doc.get('content', '')[:300]
                metadata = doc.get('metadata', {})
                title = metadata.get('title', f'文档{i}')
                
                summary_parts.append(f"\n**{i}. {title}** (相关性: {score:.2f}, 类型: {category})")
                summary_parts.append(f"   {content}...")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            print(f"⚠️ [编排器] 生成RAG摘要失败: {e}")
            return f"检索到 {len(rag_results)} 条相关数据"
    
    def _requires_enterprise_data(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> bool:
        """
        判断用户查询是否需要企业特定数据
        
        Args:
            user_input: 用户输入
            intent_result: 意图识别结果
            
        Returns:
            是否需要企业数据
        """
        user_input_lower = user_input.lower()
        
        enterprise_patterns = [
            r'我们', r'我司', r'贵公司', r'本公司', r'本企业',
            r'公司', r'企业', r'财务状况', r'经营情况',
            r'税务情况', r'风险分析', r'财务风险', r'税务风险'
        ]
        
        for pattern in enterprise_patterns:
            if re.search(pattern, user_input_lower):
                return True
        
        specialist_keywords = ['finance', 'tax', 'legal', '财务', '税务', '法务', '风险']
        if any(keyword in user_input_lower for keyword in specialist_keywords):
            return True
        
        return False
    
    def _generate_no_data_response(
        self,
        user_input: str,
        specialist_type: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """
        生成数据缺失时的响应
        
        Args:
            user_input: 用户输入
            specialist_type: 专家类型
            intent_result: 意图识别结果
            
        Returns:
            结构化的无数据响应
        """
        specialist_names = {
            "finance": "财务专家",
            "tax": "税务专家",
            "legal": "法务专家"
        }
        
        specialist_name = specialist_names.get(specialist_type, "专家")
        intent_display = intent_result.intent.value.replace("_", " ").title() if intent_result.intent else "分析"
        
        return {
            "specialist_type": specialist_type,
            "status": "no_data",
            "response": f"感谢您的{specialist_name}咨询！根据您的问题「{user_input}」，这是一个需要企业特定{specialist_name}数据才能完成的专业{intent_display}。",
            "summary": f"当前系统中未检索到您的企业相关{specialist_name}数据，无法直接生成{specialist_name}报告。",
            "current_status": "暂无数据",
            "confidence_score": 0.0,
            "limitations": [
                "企业财务/税务数据尚未导入系统",
                "无法进行定量分析",
                "无法生成具体风险评估"
            ],
            "available_actions": [
                "导入企业财务数据",
                "上传税务申报材料",
                "完善企业基础信息"
            ],
            "general_guidance": self._get_general_guidance(specialist_type, user_input)
        }
    
    def _generate_data_import_suggestions(
        self,
        user_input: str,
        specialist_type: str
    ) -> List[Dict[str, Any]]:
        """
        生成数据导入建议
        
        Args:
            user_input: 用户输入
            specialist_type: 专家类型
            
        Returns:
            数据导入建议列表
        """
        suggestions = []
        
        if specialist_type == "finance":
            suggestions.extend([
                {
                    "type": "data_import",
                    "title": "导入财务数据",
                    "description": "通过财务数据上传功能导入您的企业财务报表",
                    "action": "/api/v1/financial/upload",
                    "required_fields": ["资产负债表", "利润表", "现金流量表"],
                    "format": "支持 Excel/CSV 格式"
                },
                {
                    "type": "manual_entry",
                    "title": "手动录入",
                    "description": "如果数据量较小，可以选择手动录入关键财务指标",
                    "action": "/api/v1/financial/manual-entry",
                    "required_fields": ["年度收入", "年度支出", "净利润"]
                }
            ])
        elif specialist_type == "tax":
            suggestions.extend([
                {
                    "type": "document_upload",
                    "title": "上传税务申报材料",
                    "description": "上传增值税申报表、企业所得税申报表等税务材料",
                    "action": "/api/v1/tax/upload",
                    "required_fields": ["增值税申报表", "企业所得税申报表"],
                    "format": "支持 PDF/Excel 格式"
                },
                {
                    "type": "api_integration",
                    "title": "对接电子税务局",
                    "description": "如果您的企业已开通电子税务局接口，可以实现数据自动同步",
                    "action": "/settings/api-integration",
                    "benefits": ["数据自动同步", "实时风险监控", "智能预警"]
                }
            ])
        else:
            suggestions.append({
                "type": "general",
                "title": "完善企业信息",
                "description": "请先完善企业的基本信息和相关业务数据",
                "action": "/settings/enterprise-profile"
            })
        
        return suggestions
    
    def _get_general_guidance(
        self,
        specialist_type: str,
        user_input: str
    ) -> Dict[str, Any]:
        """
        获取通用指导信息（数据缺失时提供）
        
        Args:
            specialist_type: 专家类型
            user_input: 用户输入
            
        Returns:
            通用指导信息
        """
        if specialist_type == "finance":
            return {
                "topic": "企业财务风险分析",
                "general_knowledge": [
                    "财务风险主要包括：流动性风险、信用风险、市场风险、操作风险",
                    "常用的财务风险指标包括：流动比率、速动比率、资产负债率、利息保障倍数等",
                    "建议企业定期进行财务健康度评估，及时发现潜在风险"
                ],
                "best_practices": [
                    "建立完善的财务管理制度",
                    "加强现金流管理，确保流动性充足",
                    "控制负债规模，优化资本结构",
                    "定期进行财务分析和风险评估"
                ],
                "next_steps": "导入财务数据后，系统将为您提供详细的风险评估和改进建议"
            }
        elif specialist_type == "tax":
            return {
                "topic": "企业税务风险分析",
                "general_knowledge": [
                    "企业税务风险主要包括：申报不合规风险、发票管理风险、税收优惠政策适用风险",
                    "常见的税务风险点：进项税额抵扣不规范、税率适用错误、申报时间延误",
                    "建议企业建立税务风险管理体系，定期进行税务健康检查"
                ],
                "best_practices": [
                    "确保发票管理规范，保留完整的抵扣凭证",
                    "关注税收政策变化，及时调整税务筹划",
                    "按时进行税务申报，避免逾期罚款",
                    "建立税务档案，便于后续查阅和审计"
                ],
                "next_steps": "导入税务数据后，系统将为您识别具体的税务风险点并提供改进建议"
            }
        else:
            return {
                "topic": "企业风险分析",
                "general_knowledge": [
                    "企业风险分析需要基于完整的数据才能得出准确结论",
                    "建议完善企业数据后再进行深入分析"
                ],
                "best_practices": [],
                "next_steps": "请先导入相关业务数据"
            }
    
    async def _run_reflection(
        self,
        context: OrchestrationContext,
        user_input: str
    ) -> OrchestrationContext:
        """运行反思审核"""
        if not context.enable_reflection:
            return context

        pass

        try:
            specialist_results_str = json.dumps(context.specialist_results, ensure_ascii=False)
            reflection_result = await review_quality(
                user_question=user_input,
                ai_answer=specialist_results_str
            )

            context.reflection_result = reflection_result

            if not reflection_result.get("is_quality_acceptable", True):
                pass
                context.metadata["revision_suggestions"] = reflection_result.get(
                    "issues", []
                )

            overall_score = reflection_result.get("scores", {}).get("overall", 1.0)
            if overall_score < 0.7:
                context.needs_human_review = True
                pass
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [编排器] 反思审核数据错误: {e}")
        except (OSError, IOError) as e:
            print(f"⚠️ [编排器] 反思审核IO错误: {e}")
        except Exception as e:
            print(f"⚠️ [编排器] 反思审核失败: {e}")
        
        return context
    
    async def _synthesize_output(
        self,
        user_query: str,
        specialist_results: List[Dict[str, Any]],
        intent_result: IntentAnalysisResult
    ) -> str:
        """使用 ResultSynthesizer 合成多专家结果
        
        Args:
            user_query: 用户原始问题
            specialist_results: 各专家的分析结果
            intent_result: 意图识别结果
            
        Returns:
            合成后的自然语言响应
        """
        try:
            task_id = f"task_{datetime.now().timestamp()}"
            
            # 创建 ResultSynthesizer 实例
            synthesizer = ResultSynthesizer(llm_adapter=self.llm_adapter)
            
            for result in specialist_results:
                source_agent = result.get('specialist_type', 'unknown')
                source_type = result.get('specialist_name', 'specialist')
                content = result.get('analysis', {}) or result.get('response', {}).get('result', {})
                confidence = result.get('confidence', 0.8)
                
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                
                synthesizer.add_input(
                    task_id=task_id,
                    source_agent=source_agent,
                    source_type=source_type,
                    content=content,
                    confidence=confidence,
                    metadata={
                        "intent": intent_result.intent.value,
                        "user_query": user_query
                    }
                )
            
            from app.agent_framework.components import SynthesisStrategy
            
            synthesis_result = await synthesizer.synthesize(
                user_query=user_query,
                strategy=SynthesisStrategy.MERGE
            )
            
            if synthesis_result and synthesis_result.final_response:
                return synthesis_result.final_response
            
            return self._format_fallback_response(specialist_results, intent_result)
            
        except Exception as e:
            print(f"⚠️ [编排器] ResultSynthesizer 合成失败: {e}")
            return self._format_fallback_response(specialist_results, intent_result)
    
    def _format_fallback_response(
        self,
        specialist_results: List[Dict[str, Any]],
        intent_result: IntentAnalysisResult
    ) -> str:
        """格式化备用响应（当 ResultSynthesizer 失败时使用）
        
        Args:
            specialist_results: 各专家的分析结果
            intent_result: 意图识别结果
            
        Returns:
            格式化的响应文本
        """
        response_parts = []
        
        specialist_name_map = {
            "finance": "💰 财务专家",
            "tax": "📋 税务专家",
            "legal": "⚖️ 法务专家"
        }
        
        for result in specialist_results:
            specialist_type = result.get('specialist_type', 'unknown')
            specialist_display = specialist_name_map.get(specialist_type, "🤖 专家")
            
            analysis = result.get('analysis', {}) or result.get('response', {}).get('result', {})
            
            if not isinstance(analysis, dict):
                continue
            
            response_parts.append(f"## {specialist_display}\n")
            
            if specialist_type == "finance":
                if analysis.get('financial_indicators'):
                    response_parts.append("### 📊 财务指标\n")
                    for key, value in analysis.get('financial_indicators', {}).items():
                        response_parts.append(f"- **{key}**: {value}")
                    response_parts.append("")
                
                if analysis.get('risk_factors'):
                    response_parts.append("### ⚠️ 风险因素\n")
                    for risk in analysis.get('risk_factors', [])[:5]:
                        response_parts.append(f"- {risk}")
                    response_parts.append("")
                
                if analysis.get('recommendations'):
                    response_parts.append("### 💡 建议\n")
                    for rec in analysis.get('recommendations', [])[:5]:
                        response_parts.append(f"- {rec}")
                    response_parts.append("")
            
            elif specialist_type == "tax":
                if analysis.get('tax_type'):
                    response_parts.append(f"**税种**: {analysis.get('tax_type')}\n")
                if analysis.get('risk_points'):
                    response_parts.append("### ⚠️ 风险点\n")
                    for point in analysis.get('risk_points', [])[:5]:
                        response_parts.append(f"- {point}")
                    response_parts.append("")
                if analysis.get('recommendations'):
                    response_parts.append("### 💡 建议\n")
                    for rec in analysis.get('recommendations', [])[:5]:
                        response_parts.append(f"- {rec}")
                    response_parts.append("")
            
            elif specialist_type == "legal":
                if analysis.get('risk_points'):
                    response_parts.append("### ⚠️ 法律风险\n")
                    for risk in analysis.get('risk_points', [])[:5]:
                        response_parts.append(f"- {risk}")
                    response_parts.append("")
                if analysis.get('suggestions'):
                    response_parts.append("### 💡 建议\n")
                    for sug in analysis.get('suggestions', [])[:5]:
                        response_parts.append(f"- {sug}")
                    response_parts.append("")
            
            confidence = analysis.get('confidence', result.get('confidence', 0.8))
            response_parts.append(f"**置信度**: {confidence * 100:.0f}%\n")
            response_parts.append("\n---\n")
        
        return "\n".join(response_parts) if response_parts else "感谢您的提问，请稍后查看分析结果。"
    
    async def _generate_report(
        self,
        user_query: str,
        specialist_results: List[Dict[str, Any]],
        intent_result: IntentAnalysisResult
    ) -> str:
        """生成综合报告
        
        Args:
            user_query: 用户原始问题
            specialist_results: 各专家的分析结果
            intent_result: 意图识别结果
            
        Returns:
            生成的报告文本
        """
        if not self.report_generator:
            print("⚠️ [编排器] ReportGenerator 未初始化，使用 ResultSynthesizer 合成")
            return await self._synthesize_output(user_query, specialist_results, intent_result)
        
        try:
            from app.multi_agent_system.agents.report_generator import ReportType, ReportFormat
            
            report_type = ReportType.COMPREHENSIVE
            report_format = ReportFormat.MARKDOWN
            
            if intent_result.intent == IntentCategory.FINANCIAL_ANALYSIS:
                report_type = ReportType.SPECIALIST
            elif intent_result.intent == IntentCategory.TAX_CALCULATION:
                report_type = ReportType.SPECIALIST
            elif intent_result.intent == IntentCategory.LEGAL_CONSULTATION:
                report_type = ReportType.SPECIALIST
            
            report_result = await self.report_generator.generate(
                user_query=user_query,
                specialist_results=specialist_results,
                intent_result=intent_result,
                report_type=report_type,
                report_format=report_format
            )
            
            if report_result and report_result.get('content'):
                return report_result['content']
            
            return await self._synthesize_output(user_query, specialist_results, intent_result)
            
        except Exception as e:
            print(f"⚠️ [编排器] ReportGenerator 生成失败: {e}")
            return await self._synthesize_output(user_query, specialist_results, intent_result)
    
    def _format_no_data_response(
        self,
        specialist_result: Dict[str, Any],
        intent_result: IntentAnalysisResult,
        user_query: str = ""
    ) -> str:
        """
        格式化数据缺失时的响应
        
        Args:
            specialist_result: 专家结果
            intent_result: 意图识别结果
            user_query: 用户查询
            
        Returns:
            格式化的无数据响应
        """
        result = specialist_result.get("result", {})
        specialist_type = specialist_result.get("specialist", "general")
        suggestions = specialist_result.get("suggestions", [])
        
        specialist_name_map = {
            "finance": "💰 财务专家",
            "tax": "📋 税务专家",
            "legal": "⚖️ 法务专家"
        }
        
        specialist_display = specialist_name_map.get(specialist_type, "📊 专家")
        response_text = result.get("response", "")
        summary = result.get("summary", "")
        general_guidance = result.get("general_guidance", {})
        limitations = result.get("limitations", [])
        available_actions = result.get("available_actions", [])
        
        suggestions_html = ""
        if suggestions:
            suggestions_html = "\n### 📥 数据导入建议\n\n"
            for i, suggestion in enumerate(suggestions, 1):
                suggestions_html += f"{i}. **{suggestion.get('title', '导入数据')}**\n"
                suggestions_html += f"   - {suggestion.get('description', '')}\n"
                if suggestion.get('required_fields'):
                    suggestions_html += f"   - 必填字段: {', '.join(suggestion.get('required_fields', []))}\n"
                if suggestion.get('format'):
                    suggestions_html += f"   - 支持格式: {suggestion.get('format', '')}\n"
        
        limitations_html = ""
        if limitations:
            limitations_html = "\n### ⚠️ 当前限制\n\n"
            for limitation in limitations:
                limitations_html += f"- {limitation}\n"
        
        guidance_html = ""
        if general_guidance:
            guidance_html = f"""
### 📚 {general_guidance.get('topic', '通用指导')}

#### 基础知识
"""
            for knowledge in general_guidance.get('general_knowledge', []):
                guidance_html += f"- {knowledge}\n"
            
            if general_guidance.get('best_practices'):
                guidance_html += "\n#### 最佳实践\n"
                for practice in general_guidance.get('best_practices', []):
                    guidance_html += f"- {practice}\n"
            
            if general_guidance.get('next_steps'):
                guidance_html += f"\n> 💡 **下一步**: {general_guidance.get('next_steps', '')}\n"
        
        response = f"""## {specialist_display}

### 📋 分析说明

{response_text}

{summary}

{limitations_html}
{guidance_html}
{suggestions_html}

---

**💡 温馨提示**: 为了给您提供更准确的分析报告，建议您先导入企业的相关财务/税务数据。您也可以通过左侧导航栏的「数据管理」功能查看数据导入指南。
"""
        
        return response
    
    async def _format_specialist_response(
        self,
        specialist_result: Dict[str, Any],
        intent_result: IntentAnalysisResult,
        user_query: str = ""
    ) -> str:
        """格式化单专家响应（委托给 ResultSynthesizer）"""
        if specialist_result.get("status") == "no_data":
            formatted_no_data = self._format_no_data_response(specialist_result, intent_result, user_query)
            
            if self.output_agent:
                try:
                    specialist_type = specialist_result.get("specialist", "general")
                    specialist_name_map = {
                        "finance": "财务专家",
                        "tax": "税务专家",
                        "legal": "法务专家"
                    }
                    specialist_display = specialist_name_map.get(specialist_type, "专家")
                    
                    logger.info("📤 [结果合成器] 正在美化无数据响应...")
                    formatted = await self.output_agent.synthesize_and_format(
                        {specialist_display: formatted_no_data},
                        user_query
                    )
                    logger.info("📤 [结果合成器] 无数据响应美化完成")
                    return formatted
                except Exception as e:
                    logger.warning(f"⚠️ [结果合成器] 美化无数据响应失败: {e}")
            
            return formatted_no_data
        
        if specialist_result.get("status") == "success":
            specialist_key = specialist_result.get("specialist", "specialist")
            result = specialist_result.get("result", "")

            specialist_name_map = {
                "finance": "财务专家",
                "tax": "税务专家",
                "legal": "法务专家"
            }

            specialist_display = specialist_name_map.get(specialist_key, "专家")

            # 格式化专家结果，确保有统一的输出格式
            formatted_result = self._format_specialist_result(result, specialist_key)
            
            # 为结果合成器准备原始专家结果和格式化结果
            specialist_results = {
                specialist_display: {
                    "raw_result": result,  # 原始专家结果
                    "formatted_result": formatted_result,  # 格式化后的结果
                    "specialist_type": specialist_key
                }
            }

            if self.output_agent:
                try:
                    logger.info("📤 [结果合成器] 开始整合专家结果...")
                    # 传递包含原始结果和格式化结果的结构
                    formatted = await self.output_agent.synthesize_and_format(
                        specialist_results,
                        user_query
                    )
                    logger.info("📤 [结果合成器] 整合完成")
                    return formatted
                except Exception as e:
                    logger.warning(f"⚠️ [结果合成器] 整合失败: {e}")
                    # 如果结果合成器失败，返回格式化结果
                    return formatted_result

            return formatted_result

        error_msg = specialist_result.get("error", "处理失败")
        specialist_display = specialist_result.get("specialist", "专家")
        specialist_name_map = {"finance": "💰 财务专家", "tax": "📋 税务专家", "legal": "⚖️ 法务专家"}
        
        return f"""## {specialist_name_map.get(specialist_display, specialist_display)}

### ❌ 处理失败

{error_msg}

---

请稍后重试，或联系管理员协助处理。"""
    
    def _format_specialist_result(self, result: Any, specialist_type: str) -> str:
        """
        格式化专家结果，确保统一的输出格式
        
        Args:
            result: 专家返回的结果
            specialist_type: 专家类型
            
        Returns:
            格式化后的结果字符串
        """
        if isinstance(result, dict):
            # 税务专家特殊处理
            if specialist_type == "tax":
                return self._format_tax_result(result)
            # 财务专家特殊处理
            elif specialist_type == "finance":
                return self._format_finance_result(result)
            # 法务专家特殊处理
            elif specialist_type == "legal":
                return self._format_legal_result(result)
            # 通用处理
            else:
                return self._format_general_result(result)
        elif isinstance(result, str):
            return result
        else:
            return str(result)
    
    def _format_tax_result(self, result: Dict[str, Any]) -> str:
        """格式化税务专家结果"""
        try:
            # 优先使用分析报告字段
            analysis_report = result.get("analysis_report")
            if analysis_report:
                return analysis_report
            
            # 如果没有分析报告，则构建一个
            analysis = result.get("analysis", {})
            if isinstance(analysis, dict):
                tax_type = analysis.get("tax_type", "未知税种")
                tax_rate = analysis.get("tax_rate")
                tax_amount = analysis.get("tax_amount")
                risk_points = analysis.get("risk_points", [])
                compliance_status = analysis.get("compliance_status", "未知")
                confidence = analysis.get("confidence", 0.0)
                
                # 构建格式化输出
                formatted = f"""# 📋 税务分析报告

## 1. 税种识别
- **税种类型**: {tax_type}
- **适用税率**: {tax_rate if tax_rate is not None else "未提供"}
- **税额估算**: {tax_amount if tax_amount is not None else "未提供"}

## 2. 合规性评估
- **合规状态**: {compliance_status}
- **置信度**: {confidence:.2%}

## 3. 风险点分析"""
                
                if risk_points:
                    for i, risk in enumerate(risk_points, 1):
                        formatted += f"\n{i}. {risk}"
                else:
                    formatted += "\n- 未发现明显风险点"
                
                # 添加建议
                recommendations = result.get("recommendations", [])
                if recommendations:
                    formatted += "\n\n## 4. 专业建议"
                    for i, rec in enumerate(recommendations, 1):
                        formatted += f"\n{i}. {rec}"
                
                # 添加实体信息
                entities = result.get("entities", {})
                if entities:
                    formatted += "\n\n## 5. 提取信息"
                    for key, value in entities.items():
                        if value is not None:
                            formatted += f"\n- **{key}**: {value}"
                
                # 添加总结
                formatted += f"\n\n## 6. 总结\n"
                if compliance_status == "compliant":
                    formatted += "✅ 税务合规性良好，建议继续保持并关注政策变化。"
                elif compliance_status == "review_required":
                    formatted += "⚠️ 需要进一步审查，建议咨询专业税务顾问。"
                else:
                    formatted += "❌ 存在合规风险，建议立即采取纠正措施。"
                
                return formatted
            else:
                return f"# 📋 税务分析\n\n{str(analysis)}"
        except Exception as e:
            logger.error(f"格式化税务结果失败: {e}")
            return f"# 📋 税务分析\n\n{str(result)}"
    
    def _format_finance_result(self, result: Dict[str, Any]) -> str:
        """格式化财务专家结果"""
        # 🆕 纯文本回答直接返回（经后处理清洗）
        text_answer = result.get("text_answer")
        if text_answer:
            return Nodes._sanitize_llm_text(str(text_answer))

        try:
            # 提取分析结果
            analysis = result.get("analysis", {})
            if isinstance(analysis, dict):
                domain = analysis.get("domain", "未知领域")
                confidence = analysis.get("confidence", 0.0)
                financial_indicators = analysis.get("financial_indicators", {})
                key_metrics = analysis.get("key_metrics", [])
                risk_factors = analysis.get("risk_factors", [])
                recommendations = result.get("recommendations", [])
                
                # 构建美观的Markdown报告
                formatted = f"""# 💰 财务分析报告

## 📊 分析概览
- **分析领域**: {domain}
- **置信度**: {confidence:.2%}
- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📈 财务指标分析"""
                
                if financial_indicators:
                    formatted += "\n\n| 指标名称 | 数值 | 说明 |"
                    formatted += "\n|----------|------|------|"
                    for key, value in financial_indicators.items():
                        # 格式化数值
                        if isinstance(value, (int, float)):
                            if abs(value) >= 1000000:
                                display_value = f"{value/1000000:.2f}百万"
                            elif abs(value) >= 10000:
                                display_value = f"{value/10000:.2f}万"
                            elif abs(value) >= 1000:
                                display_value = f"{value/1000:.1f}千"
                            elif 0 < abs(value) < 1:
                                display_value = f"{value:.2%}"
                            else:
                                display_value = f"{value:.2f}"
                        else:
                            display_value = str(value)
                        
                        # 添加说明
                        description = self._get_financial_indicator_description(key)
                        formatted += f"\n| **{key}** | {display_value} | {description} |"
                else:
                    formatted += "\n\n> ℹ️ 未提取到具体的财务指标数据"
                
                # 关键指标
                if key_metrics:
                    formatted += "\n\n## 🔑 关键指标"
                    for i, metric in enumerate(key_metrics, 1):
                        formatted += f"\n{i}. {metric}"
                
                # 风险因素
                if risk_factors:
                    formatted += "\n\n## ⚠️ 风险因素"
                    for i, risk in enumerate(risk_factors, 1):
                        formatted += f"\n{i}. {risk}"
                else:
                    formatted += "\n\n## ✅ 风险评估\n- 未发现明显风险因素"
                
                # 专业建议
                if recommendations:
                    formatted += "\n\n## 💡 专业建议"
                    for i, rec in enumerate(recommendations, 1):
                        formatted += f"\n{i}. {rec}"
                
                # 详细分析内容
                content = analysis.get("content")
                if content and content != "暂无详细分析":
                    formatted += f"\n\n## 📝 详细分析\n{content}"
                
                # 添加总结
                risk_assessment = result.get("risk_assessment", {})
                risk_level = risk_assessment.get("risk_level", "未知")
                
                formatted += f"\n\n## 🎯 总结"
                if risk_level == "low":
                    formatted += "\n✅ **财务健康状况良好**，建议继续保持当前经营策略。"
                elif risk_level == "medium":
                    formatted += "\n⚠️ **存在中等财务风险**，建议关注关键指标变化，适时调整策略。"
                elif risk_level == "high":
                    formatted += "\n❌ **财务风险较高**，建议立即采取措施改善财务状况。"
                else:
                    formatted += "\n📊 **财务分析完成**，建议根据具体业务情况制定相应策略。"
                
                # 添加数据来源说明 - 基于真实数据状态
                has_rag_data = result.get("rag_enabled", False)
                has_db_data = result.get("has_financial_db_data", False)
                data_error = result.get("financial_data_error")

                if has_db_data:
                    formatted += "\n\n---\n*💾 分析基于企业财务数据库真实数据*"
                elif has_rag_data:
                    formatted += "\n\n---\n*📚 分析基于企业知识库文档数据*"
                elif data_error:
                    formatted += f"\n\n---\n*⚠️ 无法获取企业财务数据: {data_error}*"
                else:
                    formatted += "\n\n---\n*🔍 分析基于通用财务知识框架*"
                
                return formatted
            else:
                # 如果analysis不是字典，尝试直接使用内容
                content = str(analysis) if analysis else str(result)
                return f"""# 💰 财务分析报告

## 📊 分析结果

{content}

---
*🔍 基于通用财务知识分析*"""
        except Exception as e:
            logger.error(f"格式化财务结果失败: {e}")
            return f"""# 💰 财务分析报告

## ❌ 格式化错误

抱歉，格式化财务分析结果时出现错误。

**错误信息**: {str(e)}

**原始数据**: {str(result)[:200]}...

---
*⚠️ 系统内部错误，请联系技术支持*"""
    
    def _get_financial_indicator_description(self, indicator: str) -> str:
        """获取财务指标描述"""
        descriptions = {
            "revenue": "营业收入，反映企业经营规模",
            "profit": "净利润，反映企业盈利能力",
            "profit_margin": "利润率，反映盈利效率",
            "assets": "总资产，反映企业规模",
            "liabilities": "总负债，反映债务水平",
            "equity": "所有者权益，反映股东投资",
            "current_ratio": "流动比率，反映短期偿债能力",
            "debt_ratio": "资产负债率，反映财务杠杆",
            "roa": "资产收益率，反映资产使用效率",
            "roe": "净资产收益率，反映股东回报",
            "gross_margin": "毛利率，反映产品盈利能力",
            "operating_margin": "营业利润率，反映经营效率",
            "cash_flow": "现金流量，反映现金状况",
            "inventory_turnover": "存货周转率，反映存货管理效率",
            "receivables_turnover": "应收账款周转率，反映收款效率",
        }
        return descriptions.get(indicator, "财务指标")
    
    def _format_legal_result(self, result: Dict[str, Any]) -> str:
        """格式化法务专家结果"""
        try:
            # 提取分析结果
            analysis = result.get("analysis", {})
            if isinstance(analysis, dict):
                return f"""## ⚖️ 法务分析报告

### 合规评估
- **合规状态**: {analysis.get('compliance_status', '未知')}
- **置信度**: {analysis.get('confidence', 0.0):.2%}
- **风险等级**: {analysis.get('risk_level', '未知')}

### 详细分析
{analysis.get('content', '暂无详细分析')}"""
            else:
                return f"## ⚖️ 法务分析\n\n{str(analysis)}"
        except Exception as e:
            logger.error(f"格式化法务结果失败: {e}")
            return f"## ⚖️ 法务分析\n\n{str(result)}"
    
    def _format_general_result(self, result: Dict[str, Any]) -> str:
        """格式化通用专家结果"""
        try:
            # 尝试提取各种可能的字段
            content = result.get("content") or result.get("analysis") or result.get("result") or str(result)
            
            if isinstance(content, dict):
                # 如果是字典，转换为格式化的字符串
                formatted = "## 专家分析报告\n\n"
                for key, value in content.items():
                    formatted += f"### {key}\n{value}\n\n"
                return formatted.strip()
            else:
                return f"## 专家分析\n\n{content}"
        except Exception as e:
            logger.error(f"格式化通用结果失败: {e}")
            return f"## 专家分析\n\n{str(result)}"
    
    async def _format_multi_specialist_response(
        self,
        specialist_results: Dict[str, Any],
        intent_result: IntentAnalysisResult,
        user_query: str = ""
    ) -> str:
        """格式化多专家响应"""
        specialist_name_map = {
            "finance": "财务专家",
            "tax": "税务专家",
            "legal": "法务专家"
        }

        results = specialist_results.get("results", specialist_results)
        specialist_results_for_synthesis = {}

        for specialist_name, result in results.items():
            is_success = result.get("status") == "success" or result.get("success") is True
            if is_success:
                specialist_display = specialist_name_map.get(specialist_name, specialist_name)
                specialist_response = result.get("result", "")
                # 使用统一的格式化方法
                formatted_response = self._format_specialist_result(specialist_response, specialist_name)
                # 为结果合成器准备结构化的数据
                specialist_results_for_synthesis[specialist_display] = {
                    "raw_result": specialist_response,
                    "formatted_result": formatted_response,
                    "specialist_type": specialist_name
                }

        if not specialist_results_for_synthesis:
            return "⚠️ 抱歉，所有专家处理均失败。"

        if self.output_agent:
            try:
                logger.info(f"📤 [结果合成器-多专家] 开始整合 {len(specialist_results_for_synthesis)} 位专家结果...")
                formatted_output = await self.output_agent.synthesize_and_format(
                    specialist_results_for_synthesis,
                    user_query
                )
                logger.info("📤 [结果合成器-多专家] 整合完成")
                return formatted_output
            except Exception as e:
                logger.warning(f"⚠️ [结果合成器-多专家] 整合失败: {e}")

        combined_response = "\n\n---\n\n".join(
            f"### {name}\n\n{content}"
            for name, content in specialist_results_for_synthesis.items()
        )
        return combined_response
    
    def _build_response(
        self,
        context: OrchestrationContext,
        start_time: datetime
    ) -> Dict[str, Any]:
        """构建最终响应"""
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = {
            "status": "success",
            "session_id": context.session_id,
            "response": context.final_response,
            "intent": context.intent_result.intent.value if context.intent_result else None,
            "confidence": context.intent_result.confidence if context.intent_result else 0.0,
            "requires_specialists": context.intent_result.requires_specialists if context.intent_result else [],
            "processing_time": round(processing_time, 2),
            "needs_human_review": context.needs_human_review
        }
        
        if context.reflection_result:
            response["reflection"] = {
                "confidence": context.reflection_result.get("confidence", 0.0),
                "needs_revision": context.reflection_result.get("needs_revision", False)
            }
        
        return response
    
    async def generate_report(
        self,
        session_id: str,
        report_type: str = "comprehensive",
        format: str = "markdown",
        include_sections: Optional[List[str]] = None
    ) -> str:
        """
        生成报告（API路由专用方法）
        
        Args:
            session_id: 会话ID
            report_type: 报告类型
            format: 输出格式
            include_sections: 包含的章节
            
        Returns:
            报告内容
        """
        
        report_sections = []
        
        report_sections.append("# 多智能体分析报告\n")
        report_sections.append(f"**会话ID**: {session_id}\n")
        report_sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_sections.append(f"**报告类型**: {report_type}\n")
        report_sections.append("\n---\n")
        
        if self.context and self.context.intent_result:
            report_sections.append("## 意图分析\n")
            intent = self.context.intent_result
            report_sections.append(f"- **主要意图**: {intent.intent}\n")
            report_sections.append(f"- **复杂度**: {intent.complexity}\n")
            report_sections.append(f"- **路由策略**: {intent.routing_strategy}\n")
            report_sections.append(f"- **置信度**: {intent.confidence:.2%}\n")
            report_sections.append("\n---\n")
        
        if self.context and self.context.specialist_results:
            report_sections.append("## 专家分析结果\n")
            for i, result in enumerate(self.context.specialist_results, 1):
                specialist_name = result.get('specialist_name', '未知专家')
                success = result.get('success', False)
                confidence = result.get('confidence', 0.0)
                
                report_sections.append(f"### {i}. {specialist_name}\n")
                report_sections.append(f"- **状态**: {'成功' if success else '失败'}\n")
                report_sections.append(f"- **置信度**: {confidence:.2%}\n")
                
                if result.get('analysis'):
                    analysis = result['analysis']
                    if isinstance(analysis, dict):
                        for key, value in analysis.items():
                            if isinstance(value, (str, int, float)):
                                report_sections.append(f"- **{key}**: {value}\n")
                            elif isinstance(value, list):
                                report_sections.append(f"- **{key}**:\n")
                                for item in value[:5]:
                                    report_sections.append(f"  - {item}\n")
                
                report_sections.append("\n")
            report_sections.append("\n---\n")
        
        if self.context and self.context.reflection_result:
            report_sections.append("## 质量审核\n")
            reflection = self.context.reflection_result
            quality_score = reflection.get('quality_score', 0.0)
            quality_level = reflection.get('quality_level', '未知')
            needs_revision = reflection.get('needs_revision', False)
            
            report_sections.append(f"- **质量评分**: {quality_score:.2%}\n")
            report_sections.append(f"- **质量级别**: {quality_level}\n")
            report_sections.append(f"- **需要修订**: {'是' if needs_revision else '否'}\n")
            
            if reflection.get('suggestions'):
                report_sections.append("\n### 改进建议\n")
                for suggestion in reflection['suggestions']:
                    report_sections.append(f"- {suggestion}\n")
            
            report_sections.append("\n---\n")
        
        report_sections.append("\n## 最终回复\n")
        if self.context and self.context.final_response:
            report_sections.append(f"{self.context.final_response}\n")
        else:
            report_sections.append("暂无回复内容\n")
        
        report_sections.append("\n---\n")
        report_sections.append("*本报告由多智能体系统自动生成*\n")
        
        report_content = "".join(report_sections)
        
        if format == "json":
            import json
            return json.dumps({
                "session_id": session_id,
                "report_type": report_type,
                "content": report_content,
                "generated_at": datetime.now().isoformat()
            }, ensure_ascii=False, indent=2)
        
        return report_content

    async def breakdown_task_to_blackboard(
        self,
        user_goal: str,
        required_expertise: Optional[List[str]] = None,
        priority_tasks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrator Agent 专用工具：将用户宏大目标拆解为 DAG 子任务，写入黑板

        这是 Orchestrator Agent（协调者/主路由智能体）的核心工具之一。
        它的职责是：
        1. 分析用户目标，识别关键子任务
        2. 确定任务间的依赖关系，构建 DAG
        3. 设置任务优先级和执行顺序
        4. 将所有任务写入 TaskBlackboard

        Args:
            user_goal: 用户的宏大目标描述
            required_expertise: 需要哪些专业领域的专家（如 ["finance", "tax", "legal"]）
            priority_tasks: 高优先级任务标识列表

        Returns:
            包含 DAG 结构、创建的任务、执行顺序的字典
        """
        try:
            from app.mcp.orchestrator_tools import breakdown_task_to_blackboard as _breakdown

            result = await _breakdown(
                user_goal=user_goal,
                session_id=self.context.session_id if self.context else str(uuid.uuid4()),
                tenant_id=self.tenant_id,
                required_expertise=required_expertise,
                priority_tasks=priority_tasks
            )

            logger.info(f"[Orchestrator] 任务拆解完成，创建 {result.get('summary', {}).get('total_tasks', 0)} 个子任务")
            return result

        except Exception as e:
            logger.error(f"[Orchestrator] 任务拆解失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"任务拆解失败: {str(e)}"
            }

    async def summarize_final_report(
        self,
        user_query: str,
        report_title: Optional[str] = None,
        include_executive_summary: bool = True,
        include_recommendations: bool = True,
        format: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Orchestrator Agent 专用工具：收集黑板结论，生成最终交付报告

        这是 Orchestrator Agent（协调者/主路由智能体）的核心工具之一。
        它的职责是：
        1. 从 TaskBlackboard 读取所有已完成任务的结论
        2. 整合各专家的分析结果
        3. 生成结构化的最终交付报告
        4. 包含执行摘要、详细分析、建议和后续步骤

        Args:
            user_query: 用户原始查询（用于报告上下文）
            report_title: 报告标题（可选）
            include_executive_summary: 是否包含执行摘要
            include_recommendations: 是否包含建议
            format: 报告格式（markdown/html/json）

        Returns:
            包含报告内容的字典
        """
        try:
            from app.mcp.orchestrator_tools import summarize_final_report as _summarize

            result = await _summarize(
                session_id=self.context.session_id if self.context else str(uuid.uuid4()),
                tenant_id=self.tenant_id,
                user_query=user_query,
                report_title=report_title,
                include_executive_summary=include_executive_summary,
                include_recommendations=include_recommendations,
                format=format
            )

            logger.info(f"[Orchestrator] 最终报告生成完成")
            return result

        except Exception as e:
            logger.error(f"[Orchestrator] 报告生成失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"报告生成失败: {str(e)}"
            }

    def get_available_tools(self) -> List[str]:
        """
        获取 Orchestrator Agent 可用的工具列表

        返回:
            工具名称列表
        """
        return [
            "breakdown_task_to_blackboard",
            "summarize_final_report",
            "check_enterprise_data",
            "retrieve_context"
        ]

    async def execute_orchestrator_workflow(
        self,
        user_goal: str,
        generate_report: bool = True
    ) -> Dict[str, Any]:
        """
        执行完整的 Orchestrator 工作流

        工作流：
        1. 使用 breakdown_task_to_blackboard 拆解任务
        2. 并行/串行执行各子任务（由专家 Agent 处理）
        3. 使用 summarize_final_report 生成最终报告

        Args:
            user_goal: 用户的宏大目标
            generate_report: 是否生成最终报告

        Returns:
            工作流执行结果
        """
        try:
            breakdown_result = await self.breakdown_task_to_blackboard(
                user_goal=user_goal,
                required_expertise=["finance", "tax", "legal"]
            )

            if breakdown_result.get("status") == "error":
                return breakdown_result

            created_tasks = breakdown_result.get("created_tasks", [])
            task_ids = [t["task_id"] for t in created_tasks]

            if generate_report:
                report_result = await self.summarize_final_report(
                    user_query=user_goal,
                    report_title=f"关于「{user_goal[:30]}...」的综合分析报告"
                )
            else:
                report_result = None

            return {
                "status": "success",
                "workflow": "orchestrator",
                "breakdown_result": breakdown_result,
                "task_ids": task_ids,
                "report_result": report_result,
                "message": f"工作流完成：拆解为 {len(created_tasks)} 个任务" + ("，已生成报告" if generate_report else "")
            }

        except Exception as e:
            logger.error(f"[Orchestrator] 工作流执行失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"工作流执行失败: {str(e)}"
            }
