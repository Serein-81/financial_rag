"""
意图识别智能体 (Intent Agent)
企业智能体系统的"大脑"，负责意图分类、实体提取、复杂度评估和路由决策
"""

import re
import json
from typing import Dict, List, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.services.prompt_service import PromptEngine


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


class IntentAgent(BaseAgent):
    """
    意图识别智能体
    
    核心职责：
    1. 意图分类 - 识别用户问题的真实意图
    2. 实体提取 - 提取关键信息（金额、税种、合同类型等）
    3. 复杂度评估 - 评估问题复杂度，决定处理策略
    4. 路由决策 - 选择合适的专业Agent或组合
    
    设计原则：
    - 使用LLM进行意图分类
    - 规则+LLM混合进行实体提取
    - 基于规则的复杂度评估
    - 基于规则的路由决策
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        confidence_threshold: float = 0.7,
        max_iterations: int = 3,
        timeout: float = 30.0
    ):
        """
        初始化意图识别智能体
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            confidence_threshold: 置信度阈值
            max_iterations: 最大迭代次数
            timeout: 超时时间
        """
        self.confidence_threshold = confidence_threshold
        self.prompt_engine = PromptEngine()
        
        system_prompt = self._load_system_prompt()
        
        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )
        
        self._initialize_entity_patterns()
        self._initialize_complexity_rules()
        
        print("🧠 [意图识别智能体] 初始化完成")
        print(f"   - 置信度阈值: {self.confidence_threshold}")
        print(f"   - 实体模式: {len(self.entity_patterns)} 个")
        print(f"   - 复杂度规则: {len(self.complexity_rules)} 个")
    
    def _load_system_prompt(self) -> str:
        """从文件加载系统提示词"""
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system" / "intent_agent.md"
        
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"⚠️ [意图识别智能体] 加载提示词失败: {e}")
        
        return self._build_default_prompt()
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """# 意图识别智能体

## 角色定位
你是一个专业的意图识别专家，负责理解用户问题并决定最佳处理策略。

## 核心能力

### 1. 意图分类
识别以下意图类别：
- **日常类**: greeting(问候), chit_chat(闲聊)
- **知识类**: knowledge_query(知识查询), document_search(文档搜索)
- **财务类**: financial_analysis(财务分析), accounting_query(会计核算), investment_advisory(投资咨询), cost_control(成本控制)
- **税务类**: tax_calculation(税务计算), tax_planning(税务筹划), tax_compliance(税务合规), tax_declaration(税务申报)
- **法务类**: contract_review(合同审查), legal_consultation(法律咨询), compliance_check(合规检查), ip_protection(知识产权)
- **报告类**: report_generation(报告生成), data_extraction(数据提取)
- **复杂类**: complex_task(复杂任务), multi_specialist(多专家协作)

### 2. 实体提取
识别的实体类型：
- 金额: 数字+货币单位
- 日期: 具体日期或日期范围
- 税种: 增值税、所得税等
- 合同类型: 采购合同、服务合同等
- 公司/人员: 企业名称、人名
- 指标名称: 财务指标名称

### 3. 复杂度评估
- **low**: 简单计算、单一事实查询、定义类问题
- **medium**: 单一领域分析、需要工具计算、多条件查询
- **high**: 多领域交叉、需要多步推理、涉及多个计算
- **very_high**: 综合审查、多专家协作、报告生成

### 4. 路由策略
- **direct_answer**: 直接回答（问候、闲聊）
- **rag_retrieval**: RAG检索（知识查询）
- **single_specialist**: 单专家处理
- **multi_specialist_parallel**: 多专家并行处理
- **multi_specialist_sequential**: 多专家串行处理
- **report_queue**: 报告队列

## 输出格式
请以JSON格式输出：
```json
{
  "intent": "意图类别",
  "sub_intent": "子意图（可选）",
  "entities": [
    {
      "entity_type": "实体类型",
      "entity_value": "实体值",
      "confidence": 0.0-1.0,
      "source_text": "来源文本"
    }
  ],
  "complexity": "low/medium/high/very_high",
  "requires_specialists": ["specialist1", "specialist2"],
  "routing_strategy": "routing_strategy",
  "confidence": 0.0-1.0,
  "needs_human_review": true/false,
  "reasoning": "推理过程"
}
```"""
    
    def _initialize_entity_patterns(self):
        """初始化实体提取模式"""
        self.entity_patterns = {
            "money": {
                "patterns": [
                    r"([¥$€£]?\d+(?:,\d{3})*(?:\.\d{2})?)",
                    r"(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:万|亿|千|百)?\s*(?:元|美元|欧元|英镑))",
                    r"(\d+(?:\.\d+)?\s*(?:万元|亿元|千元))",
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
                    r"(20\d{2}[-/]\d{1,2})",
                ],
                "entity_type": "日期"
            },
            "tax_type": {
                "patterns": [
                    r"(增值税|企业所得税|个人所得税|消费税|关税|城建税|教育费附加|地方教育附加)",
                    r"(增值税|VAT)",
                ],
                "entity_type": "税种"
            },
            "contract_type": {
                "patterns": [
                    r"(采购合同|销售合同|服务合同|租赁合同|劳动合同|咨询合同)",
                    r"(合同|协议|契约)",
                ],
                "entity_type": "合同类型"
            },
            "company": {
                "patterns": [
                    r"([\u4e00-\u9fa5]{2,}(?:公司|集团|企业|有限|股份))",
                    r"([A-Z][a-zA-Z\s]+(?:Inc|Ltd|Corp|Co)\.?)",
                ],
                "entity_type": "公司"
            }
        }
    
    def _initialize_complexity_rules(self):
        """初始化复杂度评估规则"""
        self.complexity_rules = {
            ComplexityLevel.LOW: [
                r"(你好|您好|hi|hello)",
                r"(现在几点|今天几号|当前时间)",
                r"(什么是|什么叫|定义)",
                r"^简单.*",
            ],
            ComplexityLevel.MEDIUM: [
                r"(计算|分析|查询)",
                r"(如何|怎么|怎样)",
                r"(需要|应该|建议)",
            ],
            ComplexityLevel.HIGH: [
                r"(比较|对比|差异)",
                r"(优化|改进|提升)",
                r"(综合|全面|整体)",
                r"(方案|策划|规划)",
            ],
            ComplexityLevel.VERY_HIGH: [
                r"(报告|报表|生成.*报告)",
                r"(审查|审计|检查)",
                r"(方案|策划|规划).*(报告|分析)",
                r"(多个?|(?:和|或)\d+).*(?:领域|方面)",
            ]
        }
    
    async def run(
        self,
        user_input: str,
        history: List[Dict] = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> IntentAnalysisResult:
        """
        执行意图识别主流程
        
        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            **kwargs: 其他参数
            
        Returns:
            IntentAnalysisResult: 意图分析结果
        """
        print(f"🧠 [意图识别智能体] 分析输入: {user_input[:50]}...")
        
        self.start_time = 0.0
        self.current_iteration = 0
        
        context = context or {}
        
        try:
            entities = await self._extract_entities(user_input)
            
            intent_result = await self._classify_intent_llm(user_input, entities, context)
            
            complexity = await self._assess_complexity(
                user_input,
                intent_result["intent"],
                entities,
                context
            )
            
            routing_strategy = self._determine_routing_strategy(
                intent_result["intent"],
                complexity,
                entities
            )
            
            specialists = self._determine_required_specialists(
                intent_result["intent"],
                routing_strategy
            )
            
            needs_review = self._should_require_human_review(
                intent_result["confidence"],
                complexity,
                intent_result["intent"]
            )
            
            result = IntentAnalysisResult(
                intent=intent_result["intent"],
                sub_intent=intent_result.get("sub_intent"),
                entities=entities,
                complexity=complexity,
                requires_specialists=specialists,
                routing_strategy=routing_strategy,
                suggested_params=intent_result.get("params", {}),
                confidence=intent_result["confidence"],
                needs_human_review=needs_review,
                reasoning=intent_result.get("reasoning", "")
            )
            
            print(f"✅ [意图识别智能体] 完成分析")
            print(f"   意图: {result.intent.value}")
            print(f"   复杂度: {result.complexity.value}")
            print(f"   路由: {result.routing_strategy.value}")
            print(f"   置信度: {result.confidence:.2f}")
            
            return result
            
        except Exception as e:
            print(f"❌ [意图识别智能体] 分析失败: {e}")
            return IntentAnalysisResult(
                intent=IntentCategory.UNKNOWN,
                complexity=ComplexityLevel.MEDIUM,
                requires_specialists=["general"],
                routing_strategy=RoutingStrategy.DIRECT_ANSWER,
                confidence=0.0,
                needs_human_review=True,
                reasoning=f"分析异常: {str(e)}"
            )
    
    async def stream_run(self, user_input: str, history: List[Dict] = None, **kwargs):
        """流式执行（暂不支持，返回完整结果）"""
        result = await self.run(user_input, history, **kwargs)
        yield result
    
    async def _extract_entities(self, text: str) -> List[ExtractedEntity]:
        """
        提取实体
        
        Args:
            text: 输入文本
            
        Returns:
            实体列表
        """
        entities = []
        
        for entity_name, config in self.entity_patterns.items():
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
    
    async def _classify_intent_llm(
        self,
        text: str,
        entities: List[ExtractedEntity],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用LLM进行意图分类
        
        Args:
            text: 输入文本
            entities: 已提取的实体
            context: 上下文
            
        Returns:
            分类结果字典
        """
        entity_str = ", ".join([
            f"{e.entity_type}: {e.entity_value}"
            for e in entities[:5]
        ])
        
        prompt = f"""分析以下用户输入的意图：

用户输入：{text}

已识别的实体：{entity_str or "无"}

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
4. 置信度要基于实体匹配和上下文判断"""
        
        try:
            response = await self.llm.agenerate([prompt])
            
            if isinstance(response, str):
                result = json.loads(response)
            elif isinstance(response, dict):
                result = response
            else:
                result = {"intent": IntentCategory.UNKNOWN.value, "confidence": 0.0}
            
            intent_str = result.get("intent", "unknown")
            try:
                result["intent"] = IntentCategory(intent_str)
            except ValueError:
                result["intent"] = IntentCategory.UNKNOWN
            
            if result.get("sub_intent"):
                try:
                    result["sub_intent"] = IntentCategory(result["sub_intent"])
                except ValueError:
                    result["sub_intent"] = None
            
            return result
            
        except Exception as e:
            print(f"⚠️ [意图识别智能体] LLM分类失败，使用规则匹配: {e}")
            return self._classify_intent_rule_based(text, entities)
    
    def _classify_intent_rule_based(
        self,
        text: str,
        entities: List[ExtractedEntity]
    ) -> Dict[str, Any]:
        """
        基于规则的意图分类（降级方案）
        
        Args:
            text: 输入文本
            entities: 实体列表
            
        Returns:
            分类结果
        """
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["你好", "您好", "hi", "hello", "嗨"]):
            return {
                "intent": IntentCategory.GREETING,
                "confidence": 0.95,
                "reasoning": "检测到问候语"
            }
        
        keyword_intent_map = {
            "税务": IntentCategory.TAX_CALCULATION,
            "发票": IntentCategory.TAX_DECLARATION,
            "税": IntentCategory.TAX_CALCULATION,
            "财务": IntentCategory.FINANCIAL_ANALYSIS,
            "报表": IntentCategory.FINANCIAL_ANALYSIS,
            "合同": IntentCategory.CONTRACT_REVIEW,
            "法律": IntentCategory.LEGAL_CONSULTATION,
            "合规": IntentCategory.COMPLIANCE_CHECK,
            "报告": IntentCategory.REPORT_GENERATION,
            "查询": IntentCategory.KNOWLEDGE_QUERY,
            "知识库": IntentCategory.KNOWLEDGE_QUERY,
        }
        
        for keyword, intent in keyword_intent_map.items():
            if keyword in text_lower:
                return {
                    "intent": intent,
                    "confidence": 0.8,
                    "reasoning": f"检测到关键词: {keyword}"
                }
        
        return {
            "intent": IntentCategory.KNOWLEDGE_QUERY,
            "confidence": 0.5,
            "reasoning": "未能明确分类，归类为知识查询"
        }
    
    async def _assess_complexity(
        self,
        text: str,
        intent: IntentCategory,
        entities: List[ExtractedEntity],
        context: Dict[str, Any]
    ) -> ComplexityLevel:
        """
        评估问题复杂度
        
        Args:
            text: 输入文本
            intent: 意图
            entities: 实体列表
            context: 上下文
            
        Returns:
            复杂度等级
        """
        if intent in [IntentCategory.GREETING, IntentCategory.CHIT_CHAT]:
            return ComplexityLevel.LOW
        
        if intent == IntentCategory.REPORT_GENERATION:
            return ComplexityLevel.VERY_HIGH
        
        complexity_score = 0
        
        for level, patterns in self.complexity_rules.items():
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
        complexity: ComplexityLevel,
        entities: List[ExtractedEntity]
    ) -> RoutingStrategy:
        """
        决定路由策略
        
        Args:
            intent: 意图
            complexity: 复杂度
            entities: 实体列表
            
        Returns:
            路由策略
        """
        if intent in [IntentCategory.GREETING, IntentCategory.CHIT_CHAT]:
            return RoutingStrategy.DIRECT_ANSWER
        
        if intent in [IntentCategory.KNOWLEDGE_QUERY, IntentCategory.DOCUMENT_SEARCH]:
            return RoutingStrategy.RAG_RETRIEVAL
        
        if intent == IntentCategory.REPORT_GENERATION:
            return RoutingStrategy.REPORT_QUEUE
        
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
        """
        确定需要的专家智能体
        
        Args:
            intent: 意图
            routing_strategy: 路由策略
            
        Returns:
            专家列表
        """
        intent_specialist_map = {
            IntentCategory.FINANCIAL_ANALYSIS: ["finance"],
            IntentCategory.ACCOUNTING_QUERY: ["finance"],
            IntentCategory.INVESTMENT_ADVISORY: ["finance"],
            IntentCategory.COST_CONTROL: ["finance"],
            IntentCategory.TAX_CALCULATION: ["tax"],
            IntentCategory.TAX_PLANNING: ["tax"],
            IntentCategory.TAX_COMPLIANCE: ["tax"],
            IntentCategory.TAX_DECLARATION: ["tax"],
            IntentCategory.CONTRACT_REVIEW: ["legal"],
            IntentCategory.LEGAL_CONSULTATION: ["legal"],
            IntentCategory.COMPLIANCE_CHECK: ["legal"],
            IntentCategory.IP_PROTECTION: ["legal"],
        }
        
        specialists = intent_specialist_map.get(intent, [])
        
        if intent == IntentCategory.COMPLEX_TASK:
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
        """
        判断是否需要人工审核
        
        Args:
            confidence: 置信度
            complexity: 复杂度
            intent: 意图
            
        Returns:
            是否需要审核
        """
        if confidence < self.confidence_threshold:
            return True
        
        if complexity == ComplexityLevel.VERY_HIGH:
            return True
        
        if intent == IntentCategory.UNKNOWN:
            return True
        
        return False
