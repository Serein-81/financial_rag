"""
意图工具筛选服务

使用 LLM 进行意图分析和工具筛选

功能：
1. 意图识别 - 分析用户查询的真实意图
2. 工具筛选 - 根据意图选择最合适的工具
3. 意图验证 - 验证工具选择是否合理
4. 意图历史 - 记录和分析历史意图
"""

import json
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from enum import Enum
import re

logger = logging.getLogger(__name__)


class IntentCategory(Enum):
    """意图分类"""
    INFORMATION_RETRIEVAL = "information_retrieval"
    CALCULATION = "calculation"
    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    GENERATION = "generation"
    VALIDATION = "validation"
    RESEARCH = "research"
    GENERAL = "general"


@dataclass
class Intent:
    """意图定义"""
    category: IntentCategory
    keywords: List[str]
    confidence: float
    reasoning: str
    suggested_tools: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ToolIntentMatch:
    """工具意图匹配"""
    tool_name: str
    match_score: float
    intent_alignment: List[str]
    missing_capabilities: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class IntentAnalysisResult:
    """意图分析结果"""
    primary_intent: Intent
    secondary_intents: List[Intent] = field(default_factory=list)
    selected_tools: List[str] = field(default_factory=list)
    rejected_tools: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""


class IntentPatternMatcher:
    """
    基于规则的意图模式匹配器
    
    用于快速识别常见意图模式
    """
    
    def __init__(self):
        self._patterns: Dict[IntentCategory, List[Tuple[str, float]]] = {
            IntentCategory.INFORMATION_RETRIEVAL: [
                (r"搜索|查找|检索|查询|获取", 0.8),
                (r"是什么|什么是|如何|怎么", 0.6),
                (r"介绍|说明|解释|定义", 0.5),
            ],
            IntentCategory.CALCULATION: [
                (r"计算|算|总价|税额|金额", 0.9),
                (r"多少|等于|总计", 0.7),
                (r"税率|百分比|比例", 0.8),
            ],
            IntentCategory.ANALYSIS: [
                (r"分析|评估|判断|比较", 0.9),
                (r"优缺点|优势|劣势|风险", 0.8),
                (r"趋势|变化|发展", 0.7),
            ],
            IntentCategory.COMPARISON: [
                (r"比较|对比|差异|区别", 0.9),
                (r"哪个|更好|更差", 0.8),
                (r"不同|相同|一致", 0.7),
            ],
            IntentCategory.GENERATION: [
                (r"生成|创建|编写|制作", 0.9),
                (r"建议|方案|计划|策略", 0.8),
            ],
            IntentCategory.VALIDATION: [
                (r"检查|验证|审核|确认", 0.9),
                (r"是否|有没有|是否正确", 0.7),
            ],
            IntentCategory.RESEARCH: [
                (r"研究|调研|调查|考察", 0.9),
                (r"了解|掌握|熟悉", 0.6),
            ],
        }
        
        self._tool_keywords: Dict[str, List[str]] = {
            "search_enterprise_knowledge": ["企业", "公司", "制度", "文档"],
            "calculate_tax_vat": ["增值税", "税额", "含税"],
            "calculate_corporate_tax": ["企业所得税", "企业税"],
            "calculate_personal_tax": ["个人所得税", "个税"],
            "check_contract_essentials": ["合同", "条款", "必备"],
            "match_legal_provisions": ["法律", "条款", "匹配"],
            "calculate_asset_liability_ratio": ["资产负债", "负债率"],
            "calculate_current_ratio": ["流动比率", "短期"],
            "calculate_quick_ratio": ["速动比率", "立即"],
        }
    
    def match_intent(self, query: str) -> List[Tuple[IntentCategory, float]]:
        """
        匹配意图类别
        
        Args:
            query: 用户查询
            
        Returns:
            匹配的意图列表（按置信度排序）
        """
        matches: List[Tuple[IntentCategory, float]] = []
        
        for category, patterns in self._patterns.items():
            score = 0.0
            for pattern, weight in patterns:
                if re.search(pattern, query):
                    score = max(score, weight)
            
            if score > 0:
                matches.append((category, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def suggest_tools(self, intents: List[Tuple[IntentCategory, float]]) -> List[str]:
        """
        根据意图建议工具
        
        Args:
            intents: 意图列表
            
        Returns:
            建议的工具列表
        """
        tool_scores: Dict[str, float] = defaultdict(float)
        
        category_tools = {
            IntentCategory.INFORMATION_RETRIEVAL: [
                "search_enterprise_knowledge",
                "search_keywords_in_knowledge",
                "search_documents_by_topic"
            ],
            IntentCategory.CALCULATION: [
                "calculate_tax_vat",
                "calculate_corporate_tax",
                "calculate_personal_tax"
            ],
            IntentCategory.VALIDATION: [
                "check_contract_essentials",
                "match_legal_provisions"
            ],
            IntentCategory.ANALYSIS: [
                "calculate_asset_liability_ratio",
                "calculate_current_ratio",
                "calculate_quick_ratio"
            ],
        }
        
        for category, confidence in intents:
            tools = category_tools.get(category, [])
            for tool in tools:
                tool_scores[tool] += confidence
        
        sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
        return [tool for tool, _ in sorted_tools[:5]]


class LLMIntentAnalyzer:
    """
    使用 LLM 进行深度意图分析
    """
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
    
    async def analyze_intent(
        self,
        query: str,
        available_tools: List[Dict[str, Any]]
    ) -> IntentAnalysisResult:
        """
        使用 LLM 分析意图
        
        Args:
            query: 用户查询
            available_tools: 可用工具列表
            
        Returns:
            意图分析结果
        """
        if not self.llm_service:
            try:
                from app.services.llm_service import llm_service as _llm
                self.llm_service = _llm
            except ImportError:
                logger.warning("无法导入 LLM 服务")
                return self._fallback_analysis(query, available_tools)
        
        tools_desc = "\n".join([
            f"- {t.get('name', 'unknown')}: {t.get('description', '')}"
            for t in available_tools[:10]
        ])
        
        prompt = f"""分析以下用户查询的意图，并选择最合适的工具。

用户查询：{query}

可用工具：
{tools_desc}

请分析并返回 JSON 格式的结果：
{{
  "primary_intent": {{
    "category": "意图类别（information_retrieval|calculation|analysis|comparison|generation|validation|research|general）",
    "confidence": 0.0-1.0,
    "reasoning": "分析理由",
    "suggested_tools": ["tool1", "tool2"]
  }},
  "secondary_intents": [
    {{
      "category": "次要意图类别",
      "confidence": 0.0-1.0,
      "reasoning": "分析理由",
      "suggested_tools": ["tool3"]
    }}
  ],
  "rejected_tools": ["不选择的工具及原因"],
  "confidence": 总体置信度,
  "reasoning": "整体选择理由"
}}

仅返回 JSON，不要其他内容。"""
        
        try:
            result = await self.llm_service.generate(prompt)
            parsed = json.loads(result)
            
            primary_intent_data = parsed.get("primary_intent", {})
            primary_intent = Intent(
                category=IntentCategory(primary_intent_data.get("category", "general")),
                keywords=[],
                confidence=primary_intent_data.get("confidence", 0.5),
                reasoning=primary_intent_data.get("reasoning", ""),
                suggested_tools=primary_intent_data.get("suggested_tools", [])
            )
            
            secondary_intents = [
                Intent(
                    category=IntentCategory(s.get("category", "general")),
                    keywords=[],
                    confidence=s.get("confidence", 0.3),
                    reasoning=s.get("reasoning", ""),
                    suggested_tools=s.get("suggested_tools", [])
                )
                for s in parsed.get("secondary_intents", [])
            ]
            
            return IntentAnalysisResult(
                primary_intent=primary_intent,
                secondary_intents=secondary_intents,
                selected_tools=primary_intent.suggested_tools,
                rejected_tools=parsed.get("rejected_tools", []),
                confidence=parsed.get("confidence", 0.5),
                reasoning=parsed.get("reasoning", "")
            )
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"LLM 意图分析失败: {e}")
            return self._fallback_analysis(query, available_tools)
    
    def _fallback_analysis(
        self,
        query: str,
        available_tools: List[Dict[str, Any]]
    ) -> IntentAnalysisResult:
        """回退到规则匹配"""
        pattern_matcher = IntentPatternMatcher()
        intent_matches = pattern_matcher.match_intent(query)
        
        if not intent_matches:
            return IntentAnalysisResult(
                primary_intent=Intent(
                    category=IntentCategory.GENERAL,
                    keywords=[],
                    confidence=0.5,
                    reasoning="无法确定意图，使用通用分析"
                ),
                selected_tools=[t.get("name") for t in available_tools[:3]],
                confidence=0.3
            )
        
        top_intent, confidence = intent_matches[0]
        suggested_tools = pattern_matcher.suggest_tools(intent_matches)
        
        return IntentAnalysisResult(
            primary_intent=Intent(
                category=top_intent,
                keywords=[],
                confidence=confidence,
                reasoning="基于规则匹配"
            ),
            selected_tools=suggested_tools,
            confidence=confidence * 0.8
        )


class IntentBasedToolFilter:
    """
    意图驱动的工具过滤器
    
    整合模式匹配和 LLM 分析，提供智能工具筛选
    """
    
    def __init__(self, llm_service=None):
        self.pattern_matcher = IntentPatternMatcher()
        self.llm_analyzer = LLMIntentAnalyzer(llm_service)
        self._intent_history: List[Intent] = []
        self._tool_usage_history: Dict[str, int] = defaultdict(int)
        self._max_history_size = 100
    
    async def filter_tools(
        self,
        query: str,
        available_tools: List[Dict[str, Any]],
        use_llm: bool = True
    ) -> IntentAnalysisResult:
        """
        筛选工具
        
        Args:
            query: 用户查询
            available_tools: 可用工具列表
            use_llm: 是否使用 LLM 分析
            
        Returns:
            意图分析结果
        """
        pattern_matches = self.pattern_matcher.match_intent(query)
        
        if use_llm and len(available_tools) <= 20:
            result = await self.llm_analyzer.analyze_intent(query, available_tools)
        else:
            result = self._pattern_based_filter(query, available_tools, pattern_matches)
        
        for tool_name in result.selected_tools:
            self._tool_usage_history[tool_name] += 1
        
        if result.primary_intent:
            self._intent_history.append(result.primary_intent)
            if len(self._intent_history) > self._max_history_size:
                self._intent_history = self._intent_history[-self._max_history_size:]
        
        logger.info(f"意图分析完成: {result.primary_intent.category.value}, 选择了 {len(result.selected_tools)} 个工具")
        
        return result
    
    def _pattern_based_filter(
        self,
        query: str,
        available_tools: List[Dict[str, Any]],
        pattern_matches: List[Tuple[IntentCategory, float]]
    ) -> IntentAnalysisResult:
        """基于规则的工具筛选"""
        suggested_tools = self.pattern_matcher.suggest_tools(pattern_matches)
        
        available_tool_names = {t.get("name") for t in available_tools}
        selected = [t for t in suggested_tools if t in available_tool_names]
        rejected = [t for t in available_tool_names if t not in selected]
        
        if not selected and available_tools:
            selected = [available_tools[0].get("name", "unknown")]
        
        top_intent = pattern_matches[0][0] if pattern_matches else IntentCategory.GENERAL
        confidence = pattern_matches[0][1] if pattern_matches else 0.5
        
        return IntentAnalysisResult(
            primary_intent=Intent(
                category=top_intent,
                keywords=[],
                confidence=confidence,
                reasoning="基于规则匹配"
            ),
            selected_tools=selected,
            rejected_tools=rejected,
            confidence=confidence * 0.7
        )
    
    def match_tool_to_intent(
        self,
        tool: Dict[str, Any],
        intent: Intent
    ) -> ToolIntentMatch:
        """
        评估工具与意图的匹配度
        
        Args:
            tool: 工具信息
            intent: 意图信息
            
        Returns:
            匹配度评分
        """
        tool_name = tool.get("name", "")
        description = tool.get("description", "").lower()
        capabilities = tool.get("capabilities", [])
        
        intent_keywords = [
            "search", "retrieve", "find" if intent.category == IntentCategory.INFORMATION_RETRIEVAL else "",
            "calculate", "compute" if intent.category == IntentCategory.CALCULATION else "",
            "analyze", "evaluate" if intent.category == IntentCategory.ANALYSIS else "",
            "check", "verify" if intent.category == IntentCategory.VALIDATION else "",
        ]
        
        intent_keywords = [k for k in intent_keywords if k]
        
        matches = sum(1 for kw in intent_keywords if kw in description)
        score = min(1.0, matches / max(1, len(intent_keywords)))
        
        return ToolIntentMatch(
            tool_name=tool_name,
            match_score=score * intent.confidence,
            intent_alignment=intent_keywords,
            reasoning=f"关键词匹配度: {score:.2f}"
        )
    
    def get_intent_statistics(self) -> Dict[str, Any]:
        """
        获取意图统计信息
        
        Returns:
            统计信息
        """
        intent_counter = Counter(i.category for i in self._intent_history)
        
        return {
            "total_intents": len(self._intent_history),
            "intent_distribution": {
                cat.value: count for cat, count in intent_counter.items()
            },
            "most_common_intent": intent_counter.most_common(1)[0] if intent_counter else None,
            "tool_usage": dict(self._tool_usage_history),
            "most_used_tools": sorted(
                self._tool_usage_history.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def clear_history(self):
        """
        清除历史记录
        """
        self._intent_history = []
        self._tool_usage_history = defaultdict(int)
        logger.info("✅ 意图历史已清除")


intent_based_tool_filter = IntentBasedToolFilter()
