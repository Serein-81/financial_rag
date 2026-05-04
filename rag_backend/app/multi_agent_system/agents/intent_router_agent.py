"""
意图路由智能体 (Intent Router Agent)
融合了接待智能体和意图识别智能体的功能，统一处理用户输入

职责：
1. 快速简单检测（正则匹配，不调用LLM）
2. 意图分类 + 实体提取 + 复杂度评估（调用LLM）
3. 路由决策
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.services.prompt_service import PromptEngine
from app.multi_agent_system.agents.base_agent_prompt import load_agent_prompt
from app.multi_agent_system.clarification_service import (
    ClarificationService,
    ClarificationRequest,
    ClarificationType
)

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


class IntentCategory(str, Enum):
    """意图分类枚举"""
    GREETING = "greeting"
    CHIT_CHAT = "chit_chat"
    KNOWLEDGE_QUERY = "knowledge_query"
    DOCUMENT_SEARCH = "document_search"
    FINANCIAL_ANALYSIS = "financial_analysis"
    ACCOUNTING_QUERY = "accounting_query"
    INVESTMENT_ADVISORY = "investment_advisory"
    COST_CONTROL = "cost_control"
    TAX_CALCULATION = "tax_calculation"
    TAX_PLANNING = "tax_planning"
    TAX_COMPLIANCE = "tax_compliance"
    TAX_DECLARATION = "tax_declaration"
    CONTRACT_REVIEW = "contract_review"
    LEGAL_CONSULTATION = "legal_consultation"
    COMPLIANCE_CHECK = "compliance_check"
    IP_PROTECTION = "ip_protection"
    REPORT_GENERATION = "report_generation"
    DATA_EXTRACTION = "data_extraction"
    RISK_ANALYSIS = "risk_analysis"
    COMPLEX_TASK = "complex_task"
    MULTI_SPECIALIST = "multi_specialist"
    UNKNOWN = "unknown"


class ComplexityLevel(str, Enum):
    """复杂度等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class RoutingStrategy(str, Enum):
    """路由策略"""
    DIRECT_ANSWER = "direct_answer"
    RAG_RETRIEVAL = "rag_retrieval"
    SINGLE_SPECIALIST = "single_specialist"
    MULTI_SPECIALIST_PARALLEL = "multi_specialist_parallel"
    MULTI_SPECIALIST_SEQUENTIAL = "multi_specialist_sequential"
    REPORT_QUEUE = "report_queue"


class ExtractedEntity(BaseModel):
    """提取的实体"""
    entity_type: str = Field(..., description="实体类型")
    entity_value: str = Field(..., description="实体值")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    source_text: str = Field(..., description="来源文本")


class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    intent: IntentCategory = Field(..., description="主要意图")
    sub_intent: Optional[IntentCategory] = Field(None, description="子意图")
    entities: List[ExtractedEntity] = Field(default_factory=list, description="提取的实体")
    complexity: ComplexityLevel = Field(..., description="复杂度")
    requires_specialists: List[str] = Field(default_factory=list, description="需要的专家列表")
    routing_strategy: RoutingStrategy = Field(..., description="路由策略")
    suggested_params: Dict[str, Any] = Field(default_factory=dict, description="建议参数")
    confidence: float = Field(..., ge=0.0, le=1.0, description="整体置信度")
    needs_human_review: bool = Field(False, description="是否需要人工审核")
    reasoning: str = Field("", description="推理过程")
    needs_report_generation: bool = Field(False, description="是否需要生成报告")


class IntentRoutingResult(BaseModel):
    """意图路由结果（统一返回类型）"""
    is_simple: bool = Field(False, description="是否为简单问题")
    simple_response: Optional[str] = Field(None, description="简单问题的回答")
    intent_result: Optional[IntentAnalysisResult] = Field(None, description="意图分析结果")
    clarification_request: Optional[ClarificationRequest] = Field(None, description="追问请求（当输入模糊时）")
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )


class IntentRouterAgent(BaseAgent):
    """
    意图路由智能体
    
    融合了ReceptionistAgent和IntentAgent的功能：
    1. 快速简单检测（正则，不调用LLM）
    2. 意图分类+实体提取+复杂度评估（调用LLM）
    3. 路由决策
    
    优势：
    - 减少LLM调用次数（从2次减少到1-2次）
    - 消除职责重复
    - 简化编排器逻辑
    """
    
    SIMPLE_PATTERNS = {
        "greeting": r"^(你好|您好|hi|hello|嗨|hey)[\s,，.]*",
        "weather": r".*?(天气|weather).*",
        "time": r".*?(时间|time|现在几点).*",
        "help": r".*?(help|帮助|怎么用|如何使用).*",
        "thanks": r"^.*?(谢谢|thanks|感谢)[\s,，.]*",
        "config_query": r".*?(有没有打开|是否启用|开启了吗|关闭了吗|当前状态|当前配置|我的设置|会话状态)",
        # 仅匹配不包含具体领域的通用技能询问（^ 锚定开头防止 re.search 从中间位置绕过负向先行断言）
        # 带"财务/税务/法律/金融"等领域的应路由到对应 specialist 展示实际注册的技能
        "skill_query": r"^(?=.*(?:技能|skill|能力))(?=.*(?:有哪|是什么|有哪些|有什么|列出|介绍|展示))(?!.*(?:财务|金融|税务|税收|法律|法务|合规|合同|投资|审计)).*",
    }
    SKILL_QUERY_FALLBACK = (
        "我具备以下领域的专业技能：\n\n"
        "**财务领域**：投资分析、财务数据分析、成本控制、预算管理、财务报表分析等\n"
        "**税务领域**：增值税计算、企业所得税、税务筹划、发票管理等\n"
        "**法律领域**：合同审查、知识产权、劳动法、合规检查等\n\n"
        "请告诉我您具体想了解哪个领域，我可以为您详细说明该领域可用的功能和技能。"
    )
    
    ENTITY_PATTERNS = {
        "money": {
            "patterns": [
                r"([¥$€£]?\d+(?:,\d{3})*(?:\.\d{2})?)",
                r"(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:万|亿|千|百)?\s*(?:元|美元|欧元|英镑))",
            ],
            "entity_type": "金额"
        },
        "percentage": {
            "patterns": [
                r"(\d+(?:\.\d+)?%)",
                r"百分之(\d+(?:\.\d+)?)",
            ],
            "entity_type": "百分比"
        },
        "date": {
            "patterns": [
                r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"(\d{4}年\d{1,2}月)",
            ],
            "entity_type": "日期"
        },
        "tax_type": {
            "patterns": [
                r"(增值税|企业所得税|个人所得税|消费税|关税|城建税|教育费附加|地方教育附加)",
            ],
            "entity_type": "税种"
        },
        "contract_type": {
            "patterns": [
                r"(采购合同|销售合同|服务合同|租赁合同|劳动合同|咨询合同)",
            ],
            "entity_type": "合同类型"
        },
    }
    
    COMPLEXITY_RULES = {
        ComplexityLevel.LOW: [
            r"(你好|您好|hi|hello)",
            r"(现在几点|今天几号|当前时间)",
            r"(什么是|什么叫|定义)",
        ],
        ComplexityLevel.MEDIUM: [
            r"(计算|分析|查询)",
            r"(如何|怎么|怎样)",
        ],
        ComplexityLevel.HIGH: [
            r"(比较|对比|差异)",
            r"(优化|改进|提升)",
        ],
        ComplexityLevel.VERY_HIGH: [
            r"(报告|报表|生成.*报告)",
            r"(审查|审计|检查)",
        ]
    }
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        confidence_threshold: float = 0.7,
        max_iterations: int = 3,
        timeout: float = 30.0,
        specialist_descriptions: str = "",
        intent_mapping: Dict[str, str] = None,
        skill_registry: Optional['SkillRegistry'] = None,  # 🆕 技能系统
    ):
        """
        初始化意图路由智能体

        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            confidence_threshold: 置信度阈值
            max_iterations: 最大迭代次数
            timeout: 超时时间
            specialist_descriptions: 专家能力描述
            intent_mapping: 意图到专家的映射
            skill_registry: 技能注册表（可选）
        """
        self.confidence_threshold = confidence_threshold
        self.prompt_engine = PromptEngine()
        self._specialist_descriptions = specialist_descriptions
        self._intent_mapping = intent_mapping or {}
        self._classification_prompt_cache: Optional[str] = None

        self.clarification_service = ClarificationService(
            min_query_length=5,
            confidence_threshold=0.6,
            enable_clarification=True
        )

        system_prompt = self._load_system_prompt()

        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout,
            skill_registry=skill_registry,  # 🆕 技能系统
        )
        
        print("🎯 [意图路由智能体] 初始化完成")
        print("   - 快速简单检测: 启用")
        print("   - LLM意图分类: 启用")
        print("   - 置信度阈值: " + str(self.confidence_threshold))
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="intent_router",
                filename="system.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            logger.debug(f"[意图路由智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        mapping_text = self._format_intent_mapping()
        return {
            "intent_categories": [c.value for c in IntentCategory],
            "complexity_levels": [c.value for c in ComplexityLevel],
            "routing_strategies": [c.value for c in RoutingStrategy],
            "specialist_descriptions": self._specialist_descriptions or "暂无专家配置",
            "intents_specialist_mapping": mapping_text,
        }
    
    def _format_intent_mapping(self) -> str:
        """将意图映射格式化为可读文本"""
        if not self._intent_mapping:
            return "暂无映射配置"
        lines = []
        for intent, specialist in sorted(self._intent_mapping.items()):
            lines.append(f"- **{intent}** → {specialist}")
        return "\n".join(lines)
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """# 意图路由智能体

## 角色定位
你是专业的意图路由智能体，负责理解用户问题、分析意图、评估复杂度，并决定最佳处理策略。

## 核心能力

### 1. 快速简单检测（优先执行，不调用LLM）
以下情况直接返回回答：
- 问候语："你好"、"您好"、"hi"等 → 返回友好问候
- 感谢："谢谢"、"感谢"等 → 返回礼貌回复
- 帮助请求：包含"帮助"、"怎么用"等 → 返回使用指南
- 时间查询：包含"现在几点"、"今天几号"等 → 返回当前时间

### 2. 意图分类
识别以下意图类别：
- **日常类**: greeting(问候), chit_chat(闲聊)
- **知识类**: knowledge_query(知识查询), document_search(文档搜索)
- **财务类**: financial_analysis, accounting_query, investment_advisory, cost_control, risk_analysis
- **税务类**: tax_calculation, tax_planning, tax_compliance, tax_declaration
- **法务类**: contract_review, legal_consultation, compliance_check, ip_protection
- **报告类**: report_generation, data_extraction
- **复杂类**: complex_task, multi_specialist

### 3. 实体提取
识别的实体类型：
- 金额: 数字+货币单位
- 日期: 具体日期或日期范围
- 税种: 增值税、所得税等
- 合同类型: 采购合同、服务合同等

### 4. 复杂度评估
- **low**: 简单计算、单一事实查询、定义类问题
- **medium**: 单一领域分析、需要工具计算
- **high**: 多领域交叉、需要多步推理
- **very_high**: 综合审查、多专家协作、报告生成

### 5. 路由策略
- **direct_answer**: 直接回答（问候、闲聊）
- **rag_retrieval**: RAG检索（知识查询）
- **single_specialist**: 单专家处理
- **multi_specialist_parallel/sequential**: 多专家并行/串行处理
- **report_queue**: 报告队列

## 输出格式
```json
{
  "intent": "意图类别",
  "sub_intent": "子意图（可选）",
  "entities": [...],
  "complexity": "low/medium/high/very_high",
  "requires_specialists": ["specialist1"],
  "routing_strategy": "routing_strategy",
  "confidence": 0.0-1.0,
  "needs_human_review": true/false,
  "reasoning": "推理过程"
}
```"""
    
    def _is_simple_greeting(self, text: str) -> Optional[str]:
        """检测简单问候语（正则匹配，不调用LLM）"""
        text_lower = text.lower().strip()
        
        if re.search(self.SIMPLE_PATTERNS["greeting"], text_lower):
            return self._build_greeting_response()
        
        if re.search(self.SIMPLE_PATTERNS["thanks"], text_lower):
            return "不客气！很高兴能帮助您。请问还有什么其他问题吗？"
        
        if re.search(self.SIMPLE_PATTERNS["help"], text_lower):
            return self._build_help_response()
        
        if re.search(self.SIMPLE_PATTERNS["config_query"], text_lower):
            return "__CONFIG_QUERY__"

        if re.search(self.SIMPLE_PATTERNS["skill_query"], text_lower):
            return self.SKILL_QUERY_FALLBACK

        return None
    
    def _build_greeting_response(self) -> str:
        """构建问候响应"""
        from datetime import datetime
        hour = datetime.now().hour
        
        if hour < 12:
            time_greeting = "上午好"
        elif hour < 18:
            time_greeting = "下午好"
        else:
            time_greeting = "晚上好"
        
        return f"{time_greeting}！欢迎使用企业智能助手。我是您的AI助手，可以帮助您解答财务、税务、法律等方面的问题。请问有什么可以帮到您的？"
    
    def _build_help_response(self) -> str:
        """构建帮助响应"""
        return """📖 **智能助手使用指南**

我可以帮助您处理以下类型的问题：

**💰 财务分析**
- 财务报表分析
- 成本控制建议
- 投资风险评估

**📋 税务咨询**
- 税务政策查询
- 发票管理指导
- 税务筹划建议

**⚖️ 法律顾问**
- 合同审查
- 合规检查
- 法律咨询

**📄 报告生成**
- 财务分析报告
- 风险评估报告
- 综合审查报告

**💬 其他**
- 企业知识查询
- 常见问题解答

请直接输入您的问题，我会尽力为您解答！"""

    def _extract_entities(self, text: str) -> List[ExtractedEntity]:
        """提取实体（正则匹配）"""
        entities = []
        
        for entity_name, config in self.ENTITY_PATTERNS.items():
            for pattern in config["patterns"]:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entities.append(ExtractedEntity(
                        entity_type=config["entity_type"],
                        entity_value=match.group(1) if match.groups() else match.group(),
                        confidence=0.9,
                        source_text=text[max(0, match.start()-10):min(len(text), match.end()+10)]
                    ))
        
        return entities
    
    def _assess_complexity(
        self,
        text: str,
        intent: IntentCategory,
        entities: List[ExtractedEntity]
    ) -> ComplexityLevel:
        """评估问题复杂度"""
        if intent in [IntentCategory.GREETING, IntentCategory.CHIT_CHAT]:
            return ComplexityLevel.LOW
        
        if intent == IntentCategory.REPORT_GENERATION:
            return ComplexityLevel.VERY_HIGH
        
        complexity_score = 0
        
        for level, patterns in self.COMPLEXITY_RULES.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    complexity_score += {
                        ComplexityLevel.LOW: 1,
                        ComplexityLevel.MEDIUM: 2,
                        ComplexityLevel.HIGH: 3,
                        ComplexityLevel.VERY_HIGH: 4
                    }[level]
        
        complexity_score += len(entities) * 0.5
        
        if "和" in text or "或" in text or "还是" in text:
            complexity_score += 2
        
        if complexity_score <= 2:
            return ComplexityLevel.LOW
        elif complexity_score <= 4:
            return ComplexityLevel.MEDIUM
        elif complexity_score <= 6:
            return ComplexityLevel.HIGH
        else:
            return ComplexityLevel.VERY_HIGH
    
    def _determine_routing_strategy(
        self,
        intent: IntentCategory,
        complexity: ComplexityLevel
    ) -> RoutingStrategy:
        """决定路由策略"""
        if intent in [IntentCategory.GREETING, IntentCategory.CHIT_CHAT]:
            return RoutingStrategy.DIRECT_ANSWER
        
        if intent in [IntentCategory.KNOWLEDGE_QUERY, IntentCategory.DOCUMENT_SEARCH]:
            return RoutingStrategy.RAG_RETRIEVAL
        
        if intent == IntentCategory.REPORT_GENERATION:
            return RoutingStrategy.REPORT_QUEUE
        
        if intent in [IntentCategory.COMPLEX_TASK, IntentCategory.MULTI_SPECIALIST]:
            return RoutingStrategy.MULTI_SPECIALIST_PARALLEL
        
        if complexity in [ComplexityLevel.LOW, ComplexityLevel.MEDIUM]:
            return RoutingStrategy.SINGLE_SPECIALIST
        
        if complexity in [ComplexityLevel.HIGH, ComplexityLevel.VERY_HIGH]:
            return RoutingStrategy.MULTI_SPECIALIST_PARALLEL
        
        return RoutingStrategy.SINGLE_SPECIALIST
    
    def _determine_required_specialists(
        self,
        intent: IntentCategory,
        routing_strategy: RoutingStrategy
    ) -> List[str]:
        """确定需要的专家"""
        intent_specialist_map = {
            IntentCategory.FINANCIAL_ANALYSIS: ["finance"],
            IntentCategory.ACCOUNTING_QUERY: ["finance"],
            IntentCategory.INVESTMENT_ADVISORY: ["finance"],
            IntentCategory.COST_CONTROL: ["finance"],
            IntentCategory.RISK_ANALYSIS: ["finance"],
            IntentCategory.TAX_CALCULATION: ["tax"],
            IntentCategory.TAX_PLANNING: ["tax"],
            IntentCategory.TAX_COMPLIANCE: ["tax"],
            IntentCategory.TAX_DECLARATION: ["tax"],
            IntentCategory.CONTRACT_REVIEW: ["legal"],
            IntentCategory.LEGAL_CONSULTATION: ["legal"],
            IntentCategory.COMPLIANCE_CHECK: ["finance", "tax", "legal"],
            IntentCategory.IP_PROTECTION: ["legal"],
        }
        
        specialists = intent_specialist_map.get(intent, [])
        
        if intent in [IntentCategory.COMPLEX_TASK, IntentCategory.MULTI_SPECIALIST]:
            specialists = ["finance", "tax", "legal"]
        
        if routing_strategy in [
            RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
            RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
        ]:
            if not specialists:
                specialists = ["finance", "tax", "legal"]
        
        return specialists if specialists else ["general"]
    
    def _should_require_human_review(
        self,
        confidence: float,
        complexity: ComplexityLevel,
        intent: IntentCategory
    ) -> bool:
        """判断是否需要人工审核"""
        if confidence < self.confidence_threshold:
            return True
        
        if complexity == ComplexityLevel.VERY_HIGH:
            return True
        
        if intent == IntentCategory.UNKNOWN:
            return True
        
        return False
    
    def _classify_intent_rule_based(
        self,
        text: str
    ) -> Dict[str, Any]:
        """基于规则的意图分类"""
        text_lower = text.lower()
        
        report_keywords = [
            "生成报告", "生成一份报告", "输出一份报告",
            "给我一份报告", "给我报告", "需要报告",
            "生成分析报告", "生成财务报告", "生成税务报告",
        ]
        needs_report = any(kw in text_lower for kw in report_keywords)
        
        multi_patterns = [
            (["政策", "影响"], IntentCategory.KNOWLEDGE_QUERY, "政策影响分析"),
            (["政策", "优惠"], IntentCategory.KNOWLEDGE_QUERY, "政策优惠分析"),
            (["政策", "解读"], IntentCategory.KNOWLEDGE_QUERY, "政策解读"),
            (["政策", "咨询"], IntentCategory.KNOWLEDGE_QUERY, "政策咨询"),
            (["企业", "税务", "风险"], IntentCategory.TAX_COMPLIANCE, "企业税务风险"),
            (["税务", "筹划"], IntentCategory.TAX_PLANNING, "税务筹划"),
            (["税务", "合规"], IntentCategory.TAX_COMPLIANCE, "税务合规"),
            (["发票", "管理"], IntentCategory.TAX_DECLARATION, "发票管理"),
            (["发票", "风险"], IntentCategory.TAX_COMPLIANCE, "发票风险"),
            (["企业", "财务", "风险"], IntentCategory.RISK_ANALYSIS, "企业财务风险"),
            (["财务系统", "风险"], IntentCategory.RISK_ANALYSIS, "财务系统风险"),
            # 🆕 技能询问: 当"技能/能力"与领域关键词同时出现时路由到对应专家
            (["财务", "技能"], IntentCategory.FINANCIAL_ANALYSIS, "财务技能询问"),
            (["财务", "能力"], IntentCategory.FINANCIAL_ANALYSIS, "财务能力询问"),
            (["税务", "技能"], IntentCategory.TAX_CALCULATION, "税务技能询问"),
            (["税务", "能力"], IntentCategory.TAX_CALCULATION, "税务能力询问"),
            (["法律", "技能"], IntentCategory.LEGAL_CONSULTATION, "法律技能询问"),
            (["法律", "能力"], IntentCategory.LEGAL_CONSULTATION, "法律能力询问"),
            (["法务", "技能"], IntentCategory.LEGAL_CONSULTATION, "法务技能询问"),
            (["法务", "能力"], IntentCategory.LEGAL_CONSULTATION, "法务能力询问"),
        ]
        
        for keywords, intent, _ in multi_patterns:
            if all(kw in text_lower for kw in keywords):
                return {
                    "intent": intent,
                    "confidence": 0.9,
                    "reasoning": f"检测到关键词: {', '.join(keywords)}",
                    "needs_report_generation": needs_report
                }
        
        keyword_map = {
            "税务": IntentCategory.TAX_CALCULATION,
            "发票": IntentCategory.TAX_DECLARATION,
            "税": IntentCategory.TAX_CALCULATION,
            "财务": IntentCategory.FINANCIAL_ANALYSIS,
            "报表": IntentCategory.FINANCIAL_ANALYSIS,
            "利润": IntentCategory.FINANCIAL_ANALYSIS,
            "盈利": IntentCategory.FINANCIAL_ANALYSIS,
            "合同": IntentCategory.CONTRACT_REVIEW,
            "法律": IntentCategory.LEGAL_CONSULTATION,
            "法务": IntentCategory.LEGAL_CONSULTATION,
            "政策": IntentCategory.KNOWLEDGE_QUERY,
            "法规": IntentCategory.KNOWLEDGE_QUERY,
            "通知": IntentCategory.KNOWLEDGE_QUERY,
            "补贴": IntentCategory.KNOWLEDGE_QUERY,
            "优惠": IntentCategory.KNOWLEDGE_QUERY,
            "合规": IntentCategory.COMPLIANCE_CHECK,
            "报告": IntentCategory.REPORT_GENERATION,
            "查询": IntentCategory.KNOWLEDGE_QUERY,
            "知识库": IntentCategory.KNOWLEDGE_QUERY,
            # 🆕 技能关键词与领域关键词的多词组合已在 multi_patterns 中处理
        }
        
        for keyword, intent in keyword_map.items():
            if keyword in text_lower:
                return {
                    "intent": intent,
                    "confidence": 0.8,
                    "reasoning": f"检测到关键词: {keyword}",
                    "needs_report_generation": needs_report
                }
        
        return {
            "intent": IntentCategory.KNOWLEDGE_QUERY,
            "confidence": 0.5,
            "reasoning": "未能明确分类，归类为知识查询",
            "needs_report_generation": needs_report
        }
    
    async def _classify_intent_llm(
        self,
        text: str,
        entities: List[ExtractedEntity],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用LLM进行意图分类"""
        entity_str = ", ".join([
            f"{e.entity_type}: {e.entity_value}"
            for e in entities[:5]
        ])
        
        classification_prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system" / "intent_classification_prompt.md"
        
        if classification_prompt_path.exists():
            try:
                with open(classification_prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
            except Exception:
                prompt_template = None
        else:
            prompt_template = None
        
        if not prompt_template:
            prompt_template = """分析以下用户输入的意图：

用户输入：{user_input}

已识别的实体：{entities}

请返回JSON格式的意图分析：
{{
  "intent": "意图类别",
  "sub_intent": "子意图（可选）",
  "params": {{"建议参数"}},
  "confidence": 0.0-1.0,
  "reasoning": "推理过程"
}}

注意：
1. 如果是问候语，返回 intent: "greeting"
2. 如果是闲聊，返回 intent: "chit_chat"
3. 如果需要多个专家，返回 intent: "multi_specialist"
4. 置信度要基于实体匹配和上下文判断
5. 如果用户要求生成报告，设置 needs_report_generation: true"""
        
        text_lower = text.lower()
        report_keywords = [
            "生成报告", "生成一份报告", "输出一份报告",
            "给我一份报告", "给我报告", "需要报告",
            "生成分析报告", "生成财务报告", "生成税务报告",
            "生成分析文档", "生成分析材料", "请生成报告"
        ]
        needs_report = any(kw in text_lower for kw in report_keywords)
        
        prompt = prompt_template.format(
            user_input=text,
            entities=entity_str or "无"
        )
        
        try:
            response = await self.llm_adapter.agenerate(
                prompts=[prompt],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.content.strip()
            
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(result_text)
            
            if "intent" in result and isinstance(result["intent"], str):
                try:
                    result["intent"] = IntentCategory(result["intent"])
                except ValueError:
                    result["intent"] = IntentCategory.UNKNOWN
                
                if result.get("sub_intent"):
                    try:
                        result["sub_intent"] = IntentCategory(result["sub_intent"])
                    except ValueError:
                        result["sub_intent"] = None
            
            confidence = result.get("confidence", 0.0)
            detected_intent = result.get("intent", IntentCategory.UNKNOWN)
            
            generic_intents = {
                IntentCategory.UNKNOWN,
                IntentCategory.MULTI_SPECIALIST,
                IntentCategory.COMPLEX_TASK,
                IntentCategory.KNOWLEDGE_QUERY
            }
            
            rule_result = self._classify_intent_rule_based(text)
            rule_confidence = rule_result.get("confidence", 0.0)
            
            should_use_rule = False
            if detected_intent in generic_intents and rule_confidence >= 0.8:
                should_use_rule = True
                print("⚠️ [意图路由智能体] LLM返回通用意图，使用规则匹配补充")
            elif confidence <= self.confidence_threshold and rule_confidence > confidence:
                should_use_rule = True
                print(f"⚠️ [意图路由智能体] 置信度({confidence})<=阈值({self.confidence_threshold})，使用规则匹配补充")
            
            if should_use_rule:
                result = rule_result
            
            result["needs_report_generation"] = needs_report
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"⚠️ [意图路由智能体] LLM返回格式错误，使用规则匹配: {e}")
            return self._classify_intent_rule_based(text)
        except Exception as e:
            print(f"⚠️ [意图路由智能体] LLM分类失败，使用规则匹配: {e}")
            return self._classify_intent_rule_based(text)
    
    async def run(
        self,
        user_input: str,
        history: List[Dict] = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> IntentRoutingResult:
        """
        执行意图路由主流程
        
        步骤：
        1. 快速检测简单问题（正则，不调用LLM）
        2. 如果不是简单问题，调用LLM进行意图分类
        3. 实体提取 + 复杂度评估 + 路由决策
        
        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            **kwargs: 其他参数
            
        Returns:
            IntentRoutingResult: 统一的路由结果
        """
        print(f"🎯 [意图路由智能体] 处理输入: {user_input[:50]}...")
        
        simple_response = self._is_simple_greeting(user_input)
        if simple_response:
            print("✅ [意图路由智能体] 简单问题，直接返回")
            return IntentRoutingResult(
                is_simple=True,
                simple_response=simple_response,
                intent_result=None
            )
        
        entities = self._extract_entities(user_input)
        
        rule_based_result = self._classify_intent_rule_based(user_input)
        if rule_based_result["confidence"] >= 0.9:
            print(f"✅ [意图路由智能体] 规则匹配命中，跳过LLM: {rule_based_result['intent'].value}")
            intent_result_dict = rule_based_result
        else:
            intent_result_dict = await self._classify_intent_llm(user_input, entities, context or {})
        
        complexity = self._assess_complexity(
            user_input,
            intent_result_dict["intent"],
            entities
        )
        
        routing_strategy = self._determine_routing_strategy(
            intent_result_dict["intent"],
            complexity
        )
        
        specialists = self._determine_required_specialists(
            intent_result_dict["intent"],
            routing_strategy
        )
        
        needs_review = self._should_require_human_review(
            intent_result_dict["confidence"],
            complexity,
            intent_result_dict["intent"]
        )
        
        intent_result = IntentAnalysisResult(
            intent=intent_result_dict["intent"],
            sub_intent=intent_result_dict.get("sub_intent"),
            entities=entities,
            complexity=complexity,
            requires_specialists=specialists,
            routing_strategy=routing_strategy,
            suggested_params=intent_result_dict.get("params", {}),
            confidence=intent_result_dict["confidence"],
            needs_human_review=needs_review,
            reasoning=intent_result_dict.get("reasoning", ""),
            needs_report_generation=intent_result_dict.get("needs_report_generation", False)
        )
        
        print("✅ [意图路由智能体] 分析完成")
        print(f"   意图: {intent_result.intent.value}")
        print(f"   复杂度: {intent_result.complexity.value}")
        print(f"   路由: {intent_result.routing_strategy.value}")
        print(f"   置信度: {intent_result.confidence:.2f}")
        
        intent_str = (
            intent_result.intent.value 
            if hasattr(intent_result.intent, 'value') 
            else str(intent_result.intent)
        )
        routing_str = (
            intent_result.routing_strategy.value
            if hasattr(intent_result.routing_strategy, 'value')
            else str(intent_result.routing_strategy)
        )
        
        clarification = await self.clarification_service.detect_ambiguous_input(
            query=user_input,
            intent=intent_str,
            confidence=intent_result.confidence,
            entities=[e.model_dump() for e in intent_result.entities],
            routing_strategy=routing_str
        )
        
        return IntentRoutingResult(
            is_simple=False,
            simple_response=None,
            intent_result=intent_result,
            clarification_request=clarification
        )
    
    async def stream_run(self, user_input: str, history: List[Dict] = None, **kwargs):
        """流式执行（暂不支持，返回完整结果）"""
        result = await self.run(user_input, history, **kwargs)
        yield result
