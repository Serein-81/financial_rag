"""
专业 Agent 基类 (Base Specialist Agent)
继承现有的 BaseAgent，添加专业审查功能
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional
import uuid
import logging

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel

logger = logging.getLogger(__name__)


class BaseSpecialistAgent(BaseAgent):
    """
    专业 Agent 基类
    
    继承自现有的 BaseAgent，添加：
    1. 专业领域属性
    2. 审查方法
    3. 状态访问方法
    4. 风险评估方法
    """
    
    _initialized_instances: Dict[str, bool] = {}
    
    def __init__(
        self,
        specialty: str,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        system_prompt: str = "",
        max_iterations: int = 10,
        timeout: float = 300.0
    ):
        """
        初始化专业 Agent
        
        Args:
            specialty: 专业领域 (finance/tax/legal)
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            system_prompt: 系统提示词
            max_iterations: 最大迭代次数
            timeout: 超时时间
        """
        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )
        
        self.specialty = specialty
        self.current_state: Optional[AuditState] = None
        
        # 专业知识库
        self.knowledge_base = self._load_knowledge_base()
        
        # 风险评估规则
        self.risk_rules = self._load_risk_rules()
        
        # 只在首次初始化时打印详细信息
        if not BaseSpecialistAgent._initialized_instances.get(specialty, False):
            BaseSpecialistAgent._initialized_instances[specialty] = True
            logger.debug(
                "%s specialist initialized: knowledge_rules=%s, risk_rules=%s",
                specialty,
                len(self.knowledge_base),
                len(self.risk_rules),
            )
    
    @abstractmethod
    async def audit(
        self,
        state: AuditState,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行专业审查（子类必须实现）
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表
        """
        pass
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """
        加载专业知识库
        
        Returns:
            知识库规则列表
        """
        # TODO: 从数据库或文件加载专业知识
        # 现在返回模拟数据
        if self.specialty == "finance":
            return [
                {
                    "rule_id": "FIN_001",
                    "category": "资产负债",
                    "description": "资产负债表必须平衡",
                    "risk_level": "high"
                },
                {
                    "rule_id": "FIN_002", 
                    "category": "现金流",
                    "description": "现金流量表与银行对账单应一致",
                    "risk_level": "medium"
                }
            ]
        elif self.specialty == "tax":
            return [
                {
                    "rule_id": "TAX_001",
                    "category": "增值税",
                    "description": "增值税进项税额不得超过销项税额",
                    "risk_level": "high"
                },
                {
                    "rule_id": "TAX_002",
                    "category": "企业所得税",
                    "description": "企业所得税率应符合税法规定",
                    "risk_level": "medium"
                }
            ]
        elif self.specialty == "legal":
            return [
                {
                    "rule_id": "LEG_001",
                    "category": "合同条款",
                    "description": "合同条款不得违反法律法规",
                    "risk_level": "high"
                },
                {
                    "rule_id": "LEG_002",
                    "category": "知识产权",
                    "description": "使用他人知识产权需获得授权",
                    "risk_level": "medium"
                }
            ]
        else:
            return []
    
    def _load_risk_rules(self) -> List[Dict[str, Any]]:
        """
        加载风险评估规则
        
        Returns:
            风险规则列表
        """
        # TODO: 从配置文件或数据库加载
        return [
            {
                "pattern": "资产负债不平衡",
                "risk_score": 0.9,
                "risk_level": "critical"
            },
            {
                "pattern": "现金流异常",
                "risk_score": 0.7,
                "risk_level": "high"
            },
            {
                "pattern": "税率计算错误",
                "risk_score": 0.8,
                "risk_level": "high"
            },
            {
                "pattern": "合同条款模糊",
                "risk_score": 0.6,
                "risk_level": "medium"
            }
        ]
    
    def read_state(self, key: str = None) -> Any:
        """
        读取全局状态
        
        Args:
            key: 状态键名（None 返回整个状态）
            
        Returns:
            状态值
        """
        if not self.current_state:
            return None
        
        if key is None:
            return self.current_state
        
        return self.current_state.get(key)
    
    def write_state(self, key: str, value: Any):
        """
        写入全局状态
        
        Args:
            key: 状态键名
            value: 状态值
        """
        if self.current_state:
            self.current_state[key] = value
    
    def update_state(self, updates: Dict[str, Any]):
        """
        批量更新状态
        
        Args:
            updates: 更新字典
        """
        if self.current_state:
            self.current_state.update(updates)
    
    def calculate_risk_score(
        self,
        description: str,
        evidence: List[str] = None,
        category: str = None
    ) -> float:
        """
        计算风险分数
        
        Args:
            description: 问题描述
            evidence: 证据列表
            category: 问题类别
            
        Returns:
            风险分数 (0-1)
        """
        base_score = 0.5  # 基础分数
        
        # 基于描述匹配风险规则
        description_lower = description.lower()
        for rule in self.risk_rules:
            if rule["pattern"].lower() in description_lower:
                base_score = max(base_score, rule["risk_score"])
        
        # 基于证据数量调整
        if evidence:
            evidence_bonus = min(len(evidence) * 0.1, 0.3)
            base_score += evidence_bonus
        
        # 基于类别调整
        if category:
            category_weights = {
                "资产负债": 1.2,
                "现金流": 1.1,
                "税务合规": 1.3,
                "合同条款": 1.0,
                "知识产权": 0.9
            }
            weight = category_weights.get(category, 1.0)
            base_score *= weight
        
        return min(1.0, max(0.0, base_score))
    
    def determine_risk_level(self, risk_score: float) -> RiskLevel:
        """
        确定风险等级
        
        Args:
            risk_score: 风险分数
            
        Returns:
            风险等级
        """
        if risk_score >= 0.9:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.7:
            return RiskLevel.HIGH
        elif risk_score >= 0.4:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    async def call_specialist_tool(
        self,
        tool_name: str,
        context: str = "",
        **kwargs
    ) -> str:
        """
        调用专业工具
        
        Args:
            tool_name: 工具名称
            context: 上下文信息
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        # 添加专业上下文
        enhanced_kwargs = kwargs.copy()
        if context:
            enhanced_kwargs["context"] = f"[{self.specialty.upper()}] {context}"
        
        return await self.call_tool(tool_name, **enhanced_kwargs)
    
    def create_finding(
        self,
        category: str,
        description: str,
        evidence: List[str] = None,
        recommendations: List[str] = None,
        legal_basis: List[str] = None,
        confidence: float = 0.8
    ) -> Finding:
        """
        创建审查发现
        
        Args:
            category: 问题类别
            description: 问题描述
            evidence: 证据列表
            recommendations: 建议列表
            legal_basis: 法律依据
            confidence: 置信度
            
        Returns:
            Finding 对象
        """
        # 计算风险分数和等级
        risk_score = self.calculate_risk_score(description, evidence, category)
        risk_level = self.determine_risk_level(risk_score)
        
        return Finding(
            id=str(uuid.uuid4()),
            agent_name=f"{self.specialty}_agent",
            category=category,
            description=description,
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=confidence,
            evidence=evidence or [],
            legal_basis=legal_basis,
            recommendations=recommendations
        )
    
    def get_relevant_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        获取相关知识
        
        Args:
            query: 查询内容
            top_k: 返回数量
            
        Returns:
            相关知识列表
        """
        # 简单的关键词匹配
        query_lower = query.lower()
        relevant_knowledge = []
        
        for knowledge in self.knowledge_base:
            # 计算相关性分数
            score = 0
            if query_lower in knowledge["description"].lower():
                score += 2
            if query_lower in knowledge["category"].lower():
                score += 1
            
            if score > 0:
                relevant_knowledge.append({
                    **knowledge,
                    "relevance_score": score
                })
        
        # 按相关性排序
        relevant_knowledge.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return relevant_knowledge[:top_k]
    
    def format_audit_prompt(
        self,
        documents: List[Dict[str, Any]],
        specific_instructions: str = ""
    ) -> str:
        """
        格式化审查提示词
        
        Args:
            documents: 文档列表
            specific_instructions: 特定指令
            
        Returns:
            格式化的提示词
        """
        # 文档信息
        doc_info = []
        for i, doc in enumerate(documents, 1):
            doc_info.append(
                f"{i}. 文档ID: {doc.get('id', 'unknown')}\n"
                f"   类型: {doc.get('type', 'unknown')}\n"
                f"   内容长度: {len(doc.get('content', ''))} 字符"
            )
        
        # 相关知识
        knowledge_info = []
        for knowledge in self.knowledge_base[:5]:  # 最多显示5条
            knowledge_info.append(
                f"- {knowledge['rule_id']}: {knowledge['description']} "
                f"(风险等级: {knowledge['risk_level']})"
            )
        
        prompt = f"""你是一位专业的{self.specialty}审查专家。请仔细审查以下文档，识别潜在的风险和问题。

【待审查文档】
{chr(10).join(doc_info)}

【专业知识库】
{chr(10).join(knowledge_info)}

【审查要求】
1. 仔细分析每个文档的内容
2. 识别与{self.specialty}相关的风险和问题
3. 提供具体的证据支持
4. 给出改进建议
5. 如适用，引用相关法律法规

{specific_instructions}

请以结构化的方式回答，包括：
- 发现的问题
- 风险等级评估
- 支持证据
- 改进建议
- 法律依据（如适用）
"""
        
        return prompt
    
    def get_agent_statistics(self) -> Dict[str, Any]:
        """
        获取 Agent 统计信息
        
        Returns:
            统计信息
        """
        return {
            "specialty": self.specialty,
            "knowledge_base_size": len(self.knowledge_base),
            "risk_rules_count": len(self.risk_rules),
            "execution_summary": self.get_execution_summary()
        }
