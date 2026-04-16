"""
LLM 工具路由器

使用 LLM 进行意图分析和工具选择
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from app.services.tool_dependency_graph import tool_dependency_graph

logger = logging.getLogger(__name__)


class SelectionConfidence(Enum):
    """选择置信度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class ToolSelection:
    """工具选择结果"""
    selected_tools: List[str]
    confidence: SelectionConfidence
    reasoning: str
    alternative_tools: List[str] = None
    suggested_order: List[str] = None
    
    def __post_init__(self):
        if self.alternative_tools is None:
            self.alternative_tools = []
        if self.suggested_order is None:
            self.suggested_order = self.selected_tools


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    description: str
    parameters: Dict[str, Any]
    capabilities: List[str]
    category: str = "general"


class LLMToolRouter:
    """
    LLM 驱动的工具路由器
    
    功能：
    1. 意图识别 - 分析用户查询的真实意图
    2. 工具选择 - 选择最适合的工具组合
    3. 参数推断 - 推断工具调用的参数
    4. 备选方案 - 提供备选工具建议
    """
    
    def __init__(
        self,
        llm_adapter=None,
        intent_classifier=None,
        enable_fallback: bool = True
    ):
        self.llm = llm_adapter
        self.intent_classifier = intent_classifier
        self.enable_fallback = enable_fallback
        
        self._intent_patterns: Dict[str, List[str]] = {}
        self._tool_capabilities: Dict[str, List[str]] = {}
        
    def register_tool(
        self,
        name: str,
        description: str,
        capabilities: List[str],
        category: str = "general"
    ):
        """
        注册工具信息
        
        Args:
            name: 工具名称
            description: 工具描述
            capabilities: 工具能力列表
            category: 工具分类
        """
        self._tool_capabilities[name] = capabilities
        
        logger.debug(f"[LLMToolRouter] 注册工具: {name}, 能力: {capabilities}")
    
    def register_intent_pattern(self, intent: str, patterns: List[str]):
        """
        注册意图模式
        
        Args:
            intent: 意图名称
            patterns: 匹配模式列表
        """
        self._intent_patterns[intent] = patterns
    
    async def select_tools(
        self,
        user_input: str,
        available_tools: Dict[str, Dict],
        context: Optional[Dict[str, Any]] = None
    ) -> ToolSelection:
        """
        选择合适的工具
        
        Args:
            user_input: 用户输入
            available_tools: 可用工具字典
            context: 额外的上下文信息
            
        Returns:
            工具选择结果
        """
        if not self.llm:
            return self._fallback_selection(user_input, available_tools)
        
        try:
            return await self._llm_selection(user_input, available_tools, context)
        except (ValueError, KeyError) as e:
            logger.warning(f"[LLMToolRouter] LLM选择数据错误: {e}")
            if self.enable_fallback:
                return self._fallback_selection(user_input, available_tools)
            raise
        except (OSError, IOError) as e:
            logger.warning(f"[LLMToolRouter] LLM选择IO错误: {e}")
            if self.enable_fallback:
                return self._fallback_selection(user_input, available_tools)
            raise
        except Exception as e:
            logger.warning(f"[LLMToolRouter] LLM选择失败: {e}")
            if self.enable_fallback:
                return self._fallback_selection(user_input, available_tools)
            raise
    
    async def _llm_selection(
        self,
        user_input: str,
        available_tools: Dict[str, Dict],
        context: Optional[Dict[str, Any]]
    ) -> ToolSelection:
        """使用 LLM 进行工具选择"""
        
        tools_description = self._build_tools_description(available_tools)
        
        prompt = self._build_selection_prompt(user_input, tools_description, context)
        
        response = await self._call_llm(prompt)
        
        return self._parse_selection_response(response, available_tools)
    
    def _build_tools_description(self, tools: Dict[str, Dict]) -> str:
        """构建工具描述"""
        descriptions = []
        
        for name, info in tools.items():
            capabilities = self._tool_capabilities.get(name, [])
            cap_str = ", ".join(capabilities) if capabilities else "通用功能"
            
            desc = f"""- {name}:
  描述: {info.get('description', '无描述')}
  能力: {cap_str}
  参数: {list(info.get('parameters', {}).keys())}"""
            
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def _build_selection_prompt(
        self,
        user_input: str,
        tools_description: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建选择提示词"""
        
        context_str = ""
        if context:
            context_items = [f"- {k}: {v}" for k, v in context.items()]
            context_str = "\n上下文信息:\n" + "\n".join(context_items)
        
        prompt = f"""你是一个工具选择助手。根据用户输入，从可用工具中选择最合适的工具。

用户输入: {user_input}
{context_str}

可用工具:
{tools_description}

请分析用户意图并选择工具。返回 JSON 格式:
{{
  "selected_tools": ["tool_name1", "tool_name2"],
  "confidence": "high|medium|low",
  "reasoning": "选择理由",
  "alternative_tools": ["备选工具"],
  "suggested_order": ["执行顺序"]
}}

注意:
- 如果需要多个工具协同工作，使用多个工具名
- 如果没有合适的工具，返回空数组
- confidence 表示对选择的自信程度"""
        
        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        try:
            response = await self.llm.acreate_completion(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3
            )
            return response
        except (ValueError, KeyError) as e:
            logger.error(f"[LLMToolRouter] LLM 调用数据错误: {e}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"[LLMToolRouter] LLM 调用IO错误: {e}")
            raise
        except Exception as e:
            logger.error(f"[LLMToolRouter] LLM 调用失败: {e}")
            raise
    
    def _parse_selection_response(
        self,
        response: str,
        available_tools: Dict[str, Dict]
    ) -> ToolSelection:
        """解析选择响应"""
        try:
            data = json.loads(response)
            
            selected = data.get("selected_tools", [])
            alternatives = data.get("alternative_tools", [])
            
            valid_selected = [t for t in selected if t in available_tools]
            valid_alternatives = [t for t in alternatives if t in available_tools]
            
            confidence_map = {
                "high": SelectionConfidence.HIGH,
                "medium": SelectionConfidence.MEDIUM,
                "low": SelectionConfidence.LOW
            }
            confidence = confidence_map.get(
                data.get("confidence", "medium"),
                SelectionConfidence.MEDIUM
            )
            
            return ToolSelection(
                selected_tools=valid_selected,
                confidence=confidence,
                reasoning=data.get("reasoning", "基于LLM分析"),
                alternative_tools=valid_alternatives,
                suggested_order=data.get("suggested_order", valid_selected)
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"[LLMToolRouter] JSON 解析失败: {e}")
            return ToolSelection(
                selected_tools=[],
                confidence=SelectionConfidence.NONE,
                reasoning=f"解析失败: {response[:100]}"
            )
    
    def _fallback_selection(
        self,
        user_input: str,
        available_tools: Dict[str, Dict]
    ) -> ToolSelection:
        """回退选择策略（基于关键词匹配）"""
        
        user_input_lower = user_input.lower()
        
        tool_scores: Dict[str, float] = {}
        
        for name, info in available_tools.items():
            score = 0.0
            description = info.get("description", "").lower()
            capabilities = self._tool_capabilities.get(name, [])
            
            keywords_map = {
                "search": ["搜索", "查找", "search", "find", "query"],
                "database": ["查询", "数据库", "database", "db", "数据"],
                "calculation": ["计算", "calculate", "算", "统计"],
                "report": ["报表", "报告", "report", "生成"],
                "file": ["文件", "上传", "下载", "file", "read", "write"],
                "web": ["网页", "web", "http", "url", "网站"]
            }
            
            for category, keywords in keywords_map.items():
                if any(kw in user_input_lower or kw in description for kw in keywords):
                    if category in capabilities or any(kw in description for kw in keywords):
                        score += 1.0
            
            if score > 0:
                tool_scores[name] = score
        
        if not tool_scores:
            return ToolSelection(
                selected_tools=[],
                confidence=SelectionConfidence.LOW,
                reasoning="未找到匹配的工具"
            )
        
        sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
        max_score = sorted_tools[0][1]
        
        selected = [name for name, score in sorted_tools if score >= max_score * 0.5]
        
        confidence = SelectionConfidence.HIGH if max_score >= 2 else (
            SelectionConfidence.MEDIUM if max_score >= 1 else SelectionConfidence.LOW
        )
        
        return ToolSelection(
            selected_tools=selected[:3],
            confidence=confidence,
            reasoning=f"基于关键词匹配: {selected}",
            alternative_tools=[name for name, _ in sorted_tools[3:6]]
        )
    
    async def infer_parameters(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        推断工具参数
        
        Args:
            tool_name: 工具名称
            tool_params: 工具参数模式
            user_input: 用户输入
            context: 上下文
            
        Returns:
            推断的参数
        """
        if not self.llm:
            return {}
        
        try:
            prompt = f"""从用户输入中提取 {tool_name} 的参数。

用户输入: {user_input}
工具参数模式: {json.dumps(tool_params, ensure_ascii=False, indent=2)}
{('额外上下文: ' + str(context)) if context else ''}

请提取参数值，返回 JSON:
{{"param_name": "value", ...}}

只返回确实可以从输入中提取的参数，不要虚构值。"""
            
            response = await self._call_llm(prompt)
            inferred = json.loads(response)
            
            return {k: v for k, v in inferred.items() if k in tool_params}
            
        except (ValueError, KeyError) as e:
            logger.warning(f"[LLMToolRouter] 参数推断数据错误: {e}")
            return {}
        except (OSError, IOError) as e:
            logger.warning(f"[LLMToolRouter] 参数推断IO错误: {e}")
            return {}
        except Exception as e:
            logger.warning(f"[LLMToolRouter] 参数推断失败: {e}")
            return {}
    
    def batch_register_tools(self, tools: List[Dict[str, Any]]):
        """
        批量注册工具
        
        Args:
            tools: 工具信息列表
        """
        for tool in tools:
            self.register_tool(
                name=tool["name"],
                description=tool.get("description", ""),
                capabilities=tool.get("capabilities", []),
                category=tool.get("category", "general")
            )
    
    def get_tool_relationships(self) -> Dict[str, List[str]]:
        """
        获取工具关系图
        
        Returns:
            工具依赖关系
        """
        relationships = tool_dependency_graph.get_all_dependencies()
        
        if not relationships:
            logger.debug("[LLMToolRouter] 依赖图谱为空，使用默认依赖")
            relationships = {
                "database_query": ["data_retrieval"],
                "data_retrieval": ["format_converter"],
                "search": ["content_analysis"],
                "analysis": ["report_generation"]
            }
        
        return relationships
    
    def suggest_execution_order(self, tools: List[str]) -> List[str]:
        """
        建议工具执行顺序
        
        Args:
            tools: 工具列表
            
        Returns:
            排序后的执行顺序
        """
        relationships = self.get_tool_relationships()
        
        in_degree = {t: 0 for t in tools}
        for tool in tools:
            for dep in relationships.get(tool, []):
                if dep in tools:
                    in_degree[tool] += 1
        
        ordered = []
        remaining = set(tools)
        
        while remaining:
            ready = [t for t in remaining if in_degree[t] == 0]
            
            if not ready:
                ready = list(remaining)
            
            ordered.extend(ready)
            remaining -= set(ready)
            
            for t in ready:
                for tool in remaining:
                    if t in relationships.get(tool, []):
                        in_degree[tool] -= 1
        
        return ordered


llm_tool_router = LLMToolRouter()
