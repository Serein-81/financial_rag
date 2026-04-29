"""
追问服务 (Clarification Service)

负责检测用户模糊输入并生成智能追问，引导用户完善信息。

功能：
1. 模糊输入检测（输入过短、置信度过低、实体缺失）
2. 追问生成（意图澄清、实体补全、范围定义）
3. 建议选项生成（快速选择式交互）
"""

import logging
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClarificationType(str, Enum):
    """追问类型"""
    INTENT_CLARIFICATION = "intent_clarification"
    ENTITY_COMPLETION = "entity_completion"
    SCOPE_DEFINITION = "scope_definition"
    CONTEXT_PROVISION = "context_provision"
    AMBIGUOUS_KEYWORD = "ambiguous_keyword"


class ClarificationRequest(BaseModel):
    """追问请求"""
    type: ClarificationType = Field(..., description="追问类型")
    question: str = Field(..., description="追问问题")
    suggestions: List[str] = Field(default_factory=list, description="建议选项")
    reason: str = Field(..., description="追问原因")
    required: bool = Field(True, description="是否必须回答")
    placeholder: Optional[str] = Field(None, description="输入框占位提示")

    model_config = {"use_enum_values": True}


class ClarificationService:
    """
    追问服务
    
    检测模糊输入并生成引导性问题。
    """
    
    # 关键实体映射：每个意图需要的关键实体
    CRITICAL_ENTITIES_MAP: Dict[str, List[str]] = {
        "tax_calculation": ["税种", "时间段", "金额或收入"],
        "tax_planning": ["企业类型", "税种", "目标"],
        "tax_compliance": ["企业类型", "税种"],
        "financial_analysis": ["企业名称", "分析期间"],
        "accounting_query": ["会计科目", "时间范围"],
        "contract_review": ["合同类型", "合同金额", "签订方"],
        "legal_consultation": ["法律领域", "具体问题"],
        "risk_analysis": ["分析对象", "风险类型"],
        "investment_advisory": ["投资类型", "资金规模", "期限"],
        "compliance_check": ["检查类型", "适用法规"],
    }
    
    # 意图对应的追问建议（实体不是必须的，只有意图模糊时才追问）
    INTENT_SUGGESTIONS: Dict[str, List[str]] = {
        "tax_calculation": ["企业所得税计算", "增值税申报计算", "个人所得税计算", "税务申报指导"],
        "tax_planning": ["企业税务筹划建议", "税负优化方案", "税收优惠申请"],
        "tax_compliance": ["税务合规性检查", "发票合规审核", "申报合规性"],
        "financial_analysis": ["企业财务状况分析", "盈利能力分析", "偿债能力分析", "运营效率分析"],
        "accounting_query": ["会计分录查询", "账务处理咨询", "凭证查找"],
        "contract_review": ["合同条款审查", "法律风险评估", "合同合规性"],
        "legal_consultation": ["法律问题咨询", "法规解读", "合规建议"],
        "policy_interpretation": ["政策适用对象解读", "政策申报条件说明", "政策优惠影响分析", "政策执行时间确认"],
        "risk_analysis": ["税务风险分析", "财务风险评估", "经营风险识别"],
        "investment_advisory": ["投资可行性分析", "项目回报测算", "风险收益评估"],
        "complex_task": ["多领域综合分析", "跨部门协调方案", "复杂问题诊断"],
    }
    
    # 关键词到意图的模糊映射
    KEYWORD_INTENT_MAP: Dict[str, List[str]] = {
        "税": ["tax_calculation", "tax_planning", "tax_compliance"],
        "税务": ["tax_calculation", "tax_planning", "tax_compliance"],
        "财务": ["financial_analysis", "accounting_query", "risk_analysis"],
        "合同": ["contract_review", "legal_consultation"],
        "法律": ["legal_consultation", "contract_review", "compliance_check"],
        "政策": ["policy_interpretation", "legal_consultation", "compliance_check"],
        "政策解读": ["policy_interpretation", "legal_consultation"],
        "法规": ["policy_interpretation", "legal_consultation", "compliance_check"],
        "通知": ["policy_interpretation", "compliance_check"],
        "风险": ["risk_analysis", "compliance_check"],
        "投资": ["investment_advisory", "financial_analysis"],
        "合规": ["compliance_check", "tax_compliance", "legal_consultation"],
        "报表": ["financial_analysis", "accounting_query"],
        "发票": ["tax_calculation", "tax_compliance"],
    }
    
    def __init__(
        self,
        min_query_length: int = 5,
        confidence_threshold: float = 0.6,
        enable_clarification: bool = True
    ):
        """
        初始化追问服务
        
        Args:
            min_query_length: 最小查询长度阈值
            confidence_threshold: 置信度阈值，低于此值触发追问
            enable_clarification: 是否启用追问功能
        """
        self.min_query_length = min_query_length
        self.confidence_threshold = confidence_threshold
        self.enable_clarification = enable_clarification
    
    async def detect_ambiguous_input(
        self,
        query: str,
        intent: str,
        confidence: float,
        entities: List[Dict[str, Any]],
        routing_strategy: str = None
    ) -> Optional[ClarificationRequest]:
        """
        检测模糊输入并生成追问
        
        Args:
            query: 用户查询
            intent: 识别的意图
            confidence: 置信度
            entities: 提取的实体列表
            routing_strategy: 路由策略
            
        Returns:
            ClarificationRequest 或 None（不需要追问）
        """
        if not self.enable_clarification:
            return None
        
        query = query.strip()
        
        clarification = await self._check_input_clarity(
            query, intent, confidence, entities, routing_strategy
        )
        
        if clarification:
            logger.info(f"[Clarification] 生成追问: {clarification.type}")
        
        return clarification
    
    async def _check_input_clarity(
        self,
        query: str,
        intent: str,
        confidence: float,
        entities: List[Dict[str, Any]],
        routing_strategy: str
    ) -> Optional[ClarificationRequest]:
        """检查输入清晰度并返回追问请求
        
        追问逻辑调整：
        - 只有在输入过短或置信度低于阈值时才追问
        - 实体缺失不触发追问（专家节点可以处理）
        - 意图模糊时追问
        """
        if self._is_actionable_policy_query(query):
            return None
        
        if len(query) < self.min_query_length:
            return self._handle_short_input(query)
        
        if confidence < self.confidence_threshold:
            return self._handle_low_confidence(query, intent, confidence)
        
        if intent == "unknown" or intent == "complex_task":
            return self._handle_ambiguous_intent(query)
        
        return None
    
    def _handle_short_input(self, query: str) -> ClarificationRequest:
        """处理过短的输入"""
        
        matched_keywords = []
        for keyword, intents in self.KEYWORD_INTENT_MAP.items():
            if keyword in query:
                matched_keywords.append(keyword)
        
        if matched_keywords:
            base_keyword = matched_keywords[0]
            suggestions = self._get_suggestions_for_keyword(base_keyword)
            
            if not suggestions:
                suggestions = self._generate_suggestions_by_keyword(base_keyword)
            
            return ClarificationRequest(
                type=ClarificationType.AMBIGUOUS_KEYWORD,
                question=f"您提到了\"{base_keyword}\"，具体想了解什么？",
                suggestions=suggestions[:4],
                reason="您的输入较为简短，为了更准确地帮助您，请选择或补充具体问题",
                required=True,
                placeholder="请详细描述您的问题..."
            )
        
        return ClarificationRequest(
            type=ClarificationType.INTENT_CLARIFICATION,
            question="请详细描述您的问题，以便我们更好地帮助您",
            suggestions=["税务问题咨询", "财务分析需求", "法律合规检查", "合同审查服务"],
            reason="您的输入过于简短，我们需要更多信息来理解您的需求",
            required=True,
            placeholder="例如：帮我分析企业所得税有哪些风险..."
        )
    
    def _handle_low_confidence(
        self,
        query: str,
        intent: str,
        confidence: float
    ) -> ClarificationRequest:
        """处理低置信度情况"""
        
        matched_keywords = []
        for keyword in self.KEYWORD_INTENT_MAP.keys():
            if keyword in query:
                matched_keywords.append(keyword)
        
        suggestions = []
        for keyword in matched_keywords:
            suggestions.extend(self._get_suggestions_for_keyword(keyword))
        
        suggestions = list(dict.fromkeys(suggestions))[:4]
        
        if not suggestions:
            suggestions = self._generate_suggestions_by_keyword(matched_keywords[0] if matched_keywords else "general")
        
        return ClarificationRequest(
            type=ClarificationType.INTENT_CLARIFICATION,
            question="我们不太确定您的具体需求，能详细说明一下吗？",
            suggestions=suggestions,
            reason=f"系统置信度仅为 {confidence:.0%}，需要您进一步明确",
            required=False,
            placeholder="请详细描述您的问题..."
        )
    
    def _handle_ambiguous_intent(self, query: str) -> ClarificationRequest:
        """处理意图不明确的情况"""
        
        matched_keywords = []
        for keyword in self.KEYWORD_INTENT_MAP.keys():
            if keyword in query:
                matched_keywords.append(keyword)
        
        suggestions = []
        for keyword in matched_keywords:
            suggestions.extend(self._get_suggestions_for_keyword(keyword))
        
        suggestions = list(dict.fromkeys(suggestions))[:4]

        policy_keywords = ["政策", "政策解读", "法规", "通知", "办法", "意见", "申报", "补贴", "优惠"]
        if any(keyword in query for keyword in policy_keywords):
            if not suggestions:
                suggestions = self.INTENT_SUGGESTIONS["policy_interpretation"]

            return ClarificationRequest(
                type=ClarificationType.SCOPE_DEFINITION,
                question="您想咨询哪类政策，或希望从哪个角度解读这项政策？",
                suggestions=suggestions[:4],
                reason="您的问题涉及政策解读，但还缺少政策范围或解读角度",
                required=True,
                placeholder="例如：解读某项政策的适用对象、申报条件、优惠影响或执行时间..."
            )
        
        if not suggestions:
            suggestions = [
                "多领域综合分析",
                "跨部门协调问题",
                "复杂业务诊断",
                "综合报告生成"
            ]
        
        return ClarificationRequest(
            type=ClarificationType.SCOPE_DEFINITION,
            question="这是一个复杂的问题，请您具体说明需要哪些方面的帮助？",
            suggestions=suggestions,
            reason="系统无法确定具体意图，需要您明确问题范围",
            required=True,
            placeholder="请详细描述您的具体需求..."
        )
    
    def _handle_missing_entities(
        self,
        intent: str,
        missing_entities: List[str]
    ) -> ClarificationRequest:
        """处理关键实体缺失"""
        
        if intent not in self.CRITICAL_ENTITIES_MAP:
            return None
        
        entity_labels = {
            "税种": ["增值税", "企业所得税", "个人所得税", "消费税"],
            "时间段": ["本季度", "本年度", "近一年", "指定期间"],
            "金额或收入": ["收入规模", "具体金额", "预算范围"],
            "企业类型": ["有限责任公司", "股份有限公司", "中小企业", "上市公司"],
            "企业名称": ["具体企业名称"],
            "分析期间": ["本季度", "本年度", "近一年"],
            "目标": ["税负降低", "风险控制", "合规优化"],
            "合同类型": ["采购合同", "销售合同", "服务合同", "租赁合同"],
            "合同金额": ["合同金额范围"],
            "签订方": ["合同双方"],
            "法律领域": ["合同法", "公司法", "税法", "劳动法"],
            "具体问题": ["问题描述"],
            "分析对象": ["具体对象"],
            "风险类型": ["税务风险", "财务风险", "运营风险"],
            "投资类型": ["股权投资", "债权投资", "项目投资"],
            "资金规模": ["小额", "中等", "大额"],
            "期限": ["短期", "中期", "长期"],
            "检查类型": ["税务检查", "财务审计", "合规审查"],
            "适用法规": ["税法", "会计法", "公司法"],
            "会计科目": ["具体科目"],
            "时间范围": ["起始时间", "结束时间"],
        }
        
        questions = {
            "税种": "请选择或描述您关注的税种",
            "时间段": "请指定分析的时间范围",
            "金额或收入": "请提供金额或收入信息",
            "企业类型": "请描述企业类型",
            "企业名称": "请提供企业名称",
            "分析期间": "请指定分析期间",
            "目标": "请描述您的目标",
            "合同类型": "请描述合同类型",
            "合同金额": "请提供合同金额",
            "签订方": "请描述合同签订方",
            "法律领域": "请选择法律领域",
            "具体问题": "请描述具体问题",
            "分析对象": "请描述分析对象",
            "风险类型": "请选择风险类型",
            "投资类型": "请描述投资类型",
            "资金规模": "请描述资金规模",
            "期限": "请指定投资期限",
            "检查类型": "请选择检查类型",
            "适用法规": "请选择适用法规",
            "会计科目": "请描述会计科目",
            "时间范围": "请指定时间范围",
        }
        
        missing_label = missing_entities[0]
        suggestions = entity_labels.get(missing_label, [])
        
        question = questions.get(missing_label, f"请补充 {missing_label} 信息")
        
        return ClarificationRequest(
            type=ClarificationType.ENTITY_COMPLETION,
            question=question,
            suggestions=suggestions[:4] if suggestions else [],
            reason=f"为了准确分析，需要了解{missing_label}信息",
            required=True,
            placeholder=f"请输入{missing_label}..."
        )
    
    def _check_critical_entities(
        self,
        intent: str,
        entities: List[Dict[str, Any]]
    ) -> List[str]:
        """检查关键实体是否缺失"""
        if intent not in self.CRITICAL_ENTITIES_MAP:
            return []
        
        required = self.CRITICAL_ENTITIES_MAP.get(intent, [])
        found_types = {e.get("entity_type", "") for e in entities}
        
        return [r for r in required if r not in found_types]
    
    def _generate_suggestions_by_keyword(self, keyword: str) -> List[str]:
        """根据关键词生成建议"""
        base_suggestions = {
            "税": ["税务风险分析", "税务筹划建议", "税率计算", "申报指导"],
            "税务": ["企业税务健康检查", "税负分析", "税务合规咨询"],
            "财务": ["财务状况分析", "报表解读", "成本控制建议"],
            "合同": ["合同条款审查", "法律风险评估", "合规性检查"],
            "法律": ["法规咨询", "合规建议", "风险评估"],
            "风险": ["风险识别评估", "风险防控建议", "预警分析"],
            "投资": ["投资可行性分析", "回报测算", "风险评估"],
            "合规": ["合规性审查", "制度优化", "风险控制"],
            "报表": ["报表分析", "财务解读", "趋势分析"],
            "发票": ["发票合规检查", "进项抵扣分析", "发票风险识别"],
        }
        
        return base_suggestions.get(keyword, [
            "一般问题咨询",
            "数据分析需求",
            "报告生成",
            "专业建议"
        ])

    def _get_suggestions_for_keyword(self, keyword: str) -> List[str]:
        """根据关键词映射到的意图收集追问建议。"""
        suggestions = []
        for intent in self.KEYWORD_INTENT_MAP.get(keyword, []):
            suggestions.extend(self.INTENT_SUGGESTIONS.get(intent, []))
        return list(dict.fromkeys(suggestions))

    def _is_actionable_policy_query(self, query: str) -> bool:
        """政策类输入已经给出明确动作时不再追问。"""
        policy_keywords = ["政策", "法规", "通知", "办法", "意见", "补贴", "优惠"]
        action_keywords = ["解读", "咨询", "分析", "影响", "适用", "申报", "条件", "材料", "匹配", "查询"]
        return any(keyword in query for keyword in policy_keywords) and any(
            keyword in query for keyword in action_keywords
        )
    
    def should_clarify(
        self,
        query: str,
        intent: str,
        confidence: float,
        entities: List[Dict[str, Any]]
    ) -> bool:
        """
        快速判断是否需要追问
        
        Args:
            query: 用户查询
            intent: 识别的意图
            confidence: 置信度
            entities: 实体列表
            
        Returns:
            True 如果需要追问
        """
        if len(query.strip()) < self.min_query_length:
            return True
        
        if confidence < self.confidence_threshold:
            return True
        
        if intent in ["unknown", "complex_task"]:
            return True
        
        missing = self._check_critical_entities(intent, entities)
        if len(missing) > 0:
            return True
        
        return False
