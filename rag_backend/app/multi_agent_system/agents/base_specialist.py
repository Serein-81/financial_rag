"""
专业 Agent 基类 (Base Specialist Agent)
继承现有的 BaseAgent，添加专业审查功能和技能感知能力
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import uuid
import logging

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel
from ..config.knowledge_loader import load_knowledge_base, load_risk_rules

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

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
        timeout: float = 300.0,
        skill_registry: Optional['SkillRegistry'] = None,  # 🆕 技能系统
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
            skill_registry: 技能注册表 (可选, 注入后 Agent 自动感知领域技能)
        """
        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout,
            skill_registry=skill_registry,
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
        加载专业知识库。

        优先从 config/knowledge_base.json 读取，运营人员可直接编辑 JSON 更新规则；
        若文件不存在则回退到内置兜底规则。
        """
        return load_knowledge_base(self.specialty)

    def _load_risk_rules(self) -> List[Dict[str, Any]]:
        """
        加载风险评估规则。

        优先从 config/risk_rules.json 读取，运营人员可直接编辑 JSON 更新规则；
        若文件不存在则回退到内置兜底规则。
        """
        return load_risk_rules(self.specialty)
    
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
    
    # =========================================================================
    # 🆕 技能感知方法
    # =========================================================================

    def get_domain_skills(self) -> List[Dict[str, Any]]:
        """
        获取当前 specialist 领域相关的技能列表 (Level 1: 仅元数据)

        Returns:
            领域技能元数据列表
        """
        if not self.skill_registry:
            return []

        domain_map = {
            "finance": "finance",
            "tax": "tax",
            "legal": "legal",
            "financial": "finance",
            "taxation": "tax",
            "legislation": "legal",
        }
        mapped_domain = domain_map.get(self.specialty.lower())
        if not mapped_domain:
            return []

        try:
            entries = self.skill_registry.list_skills_by_domain(mapped_domain)
            return [
                {
                    "name": e.metadata.name,
                    "description": e.metadata.description,
                    "domain": e.metadata.domain,
                }
                for e in entries
            ]
        except Exception:
            return []

    def activate_skill(self, skill_name: str) -> bool:
        """
        激活指定技能 (Level 2: 加载正文到上下文)

        Args:
            skill_name: 技能名称

        Returns:
            是否成功激活
        """
        if not self.skill_registry:
            return False

        entry = self.skill_registry.get_skill(skill_name)
        if not entry:
            return False

        from app.skills.skill_loader import SkillLoader
        body = SkillLoader.load_full_body(entry)
        if body:
            self.inject_skill_context(body)
            return True
        return False

    def get_agent_statistics(self) -> Dict[str, Any]:
        """
        获取 Agent 统计信息

        Returns:
            统计信息
        """
        domain_skills = self.get_domain_skills()
        return {
            "specialty": self.specialty,
            "knowledge_base_size": len(self.knowledge_base),
            "risk_rules_count": len(self.risk_rules),
            "domain_skills": len(domain_skills),
            "active_skill": bool(self._activated_skill_context),
            "execution_summary": self.get_execution_summary()
        }
