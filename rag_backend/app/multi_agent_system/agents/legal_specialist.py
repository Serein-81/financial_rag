"""
法务专家智能体 (Legal Specialist Agent)
处理企业法律相关问题，包括合同审查、知识产权、劳动法、公司治理等
"""

import re
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .base_specialist import BaseSpecialistAgent
from .base_agent_prompt import load_agent_prompt
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


class LegalDomain(str, Enum):
    """法律领域"""
    CONTRACT = "contract"  # 合同法务
    INTELLECTUAL_PROPERTY = "ip"  # 知识产权
    LABOR = "labor"  # 劳动法
    CORPORATE = "corporate"  # 公司法务
    COMPLIANCE = "compliance"  # 合规审查
    LITIGATION = "litigation"  # 诉讼支持
    REGULATORY = "regulatory"  # 监管合规
    OTHER = "other"  # 其他法律领域


class ContractType(str, Enum):
    """合同类型"""
    PURCHASE = "purchase"  # 采购合同
    SALES = "sales"  # 销售合同
    LEASE = "lease"  # 租赁合同
    SERVICE = "service"  # 服务合同
    EMPLOYMENT = "employment"  # 劳动合同
    LICENSING = "licensing"  # 许可协议
    JOINT_VENTURE = "joint_venture"  # 合资合同
    CONFIDENTIALITY = "confidentiality"  # 保密协议
    OTHER = "other"


class LegalAnalysisResult(BaseModel):
    """法律分析结果"""
    domain: LegalDomain = Field(description="法律领域")
    contract_type: Optional[ContractType] = Field(default=None, description="合同类型")
    key_clauses: List[str] = Field(default_factory=list, description="关键条款")
    risk_clauses: List[Dict[str, Any]] = Field(default_factory=list, description="风险条款")
    obligations: List[str] = Field(default_factory=list, description="主要义务")
    termination_conditions: List[str] = Field(default_factory=list, description="终止条件")
    compliance_status: str = Field(default="compliant", description="合规状态")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")


@dataclass
class LegalEntity:
    """法律实体"""
    contract_type: Optional[str] = None
    parties: List[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    jurisdiction: Optional[str] = None
    governing_law: Optional[str] = None
    dispute_resolution: Optional[str] = None


class LegalSpecialist(BaseSpecialistAgent):
    """
    法务专家智能体
    
    职责：
    1. 合同审查与风险评估
    2. 知识产权保护咨询
    3. 劳动法合规指导
    4. 公司治理建议
    5. 合规审查与建议
    6. 法律法规解读
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        specialty: str = "legal",
        skill_registry: Optional['SkillRegistry'] = None,  # 🆕 技能系统
    ):
        """
        初始化法务专家

        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            specialty: 专业领域标识
            skill_registry: 技能注册表 (可选)
        """
        # 必须在 _load_system_prompt() 之前设置 skill_registry
        # 因为 _get_prompt_context() 会访问它
        self.skill_registry = skill_registry
        system_prompt = self._load_system_prompt()

        super().__init__(
            specialty=specialty,
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=10,
            timeout=60.0,
            skill_registry=skill_registry,  # 🆕 技能系统
        )
        
        self.entity_patterns = self._compile_entity_patterns()
        self.contract_templates = self._load_contract_templates()
        
        self._register_mcp_tools()
        self._register_enhanced_legal_tools()
        self._register_mcp_legal_tools()
    
    def _register_mcp_tools(self):
        """
        注册 MCP 工具（时间锚点工具）
        
        所有专家 Agent 都需要时间感知能力来处理相对时间查询
        """
        try:
            from app.mcp.foundation_tools import get_current_time_and_context
            
            try:
                self.tool_manager.register_langchain_tool(get_current_time_and_context)
                logger.info(f"✅ [法务专家] 注册时间锚点工具: get_current_time_and_context")
            except Exception as e:
                logger.warning(f"⚠️ [法务专家] 注册时间锚点工具失败: {e}")
            
            logger.info(f"📊 [法务专家] MCP 工具注册完成")
            
        except ImportError as e:
            logger.warning(f"⚠️ [法务专家] 无法导入 MCP 工具: {e}")
        except Exception as e:
            logger.error(f"❌ [法务专家] 注册 MCP 工具时出错: {e}")
    
    def _register_enhanced_legal_tools(self):
        """
        注册增强的法务合规工具（ToolBase 格式）
        
        这些工具基于项目现有数据模型，与 contract_review、scheduled_task 等模块配合
        """
        try:
            from app.agent_framework.tools.legal_enhanced_tools import (
                ContractComplianceDeadlineTool,
                ContractTemplateMatcher,
                DisputeResolutionAdvisor,
                ContractRiskTrendAnalyzer,
                EnterprisePolicyMatchReader,
                EnterprisePolicyMatcher
            )
            
            tools_to_register = [
                ContractComplianceDeadlineTool(),
                ContractTemplateMatcher(),
                DisputeResolutionAdvisor(),
                ContractRiskTrendAnalyzer(),
                EnterprisePolicyMatchReader(),
                EnterprisePolicyMatcher()
            ]
            
            for tool in tools_to_register:
                try:
                    self.tool_manager.register_tool(tool)
                    logger.info(f"✅ [法务专家] 注册增强工具: {tool.name}")
                except Exception as e:
                    logger.warning(f"⚠️ [法务专家] 注册增强工具 {tool.name} 失败: {e}")
            
            logger.info(f"📊 [法务专家] 增强工具注册完成，共 {len(tools_to_register)} 个")
            
        except ImportError as e:
            logger.warning(f"⚠️ [法务专家] 无法导入增强工具模块: {e}")
        except Exception as e:
            logger.error(f"❌ [法务专家] 注册增强工具时出错: {e}")
    
    def _register_mcp_legal_tools(self):
        """
        注册 MCP 格式的法律合规工具
        
        这些工具使用 @local_tool 装饰器，符合 MCP STDIO 协议
        """
        try:
            from app.mcp import create_legal_compliance_tools_v2
            
            mcp_tools = create_legal_compliance_tools_v2()
            
            for tool_func in mcp_tools:
                try:
                    self.tool_manager.register_langchain_tool(tool_func)
                    logger.info(f"✅ [法务专家] 注册 MCP 工具: {tool_func.name}")
                except Exception as e:
                    logger.warning(f"⚠️ [法务专家] 注册 MCP 工具 {tool_func.name} 失败: {e}")
            
            logger.info(f"📊 [法务专家] MCP 法律工具注册完成，共 {len(mcp_tools)} 个")
            
        except ImportError as e:
            logger.warning(f"⚠️ [法务专家] 无法导入 MCP 法律工具: {e}")
        except Exception as e:
            logger.error(f"❌ [法务专家] 注册 MCP 法律工具时出错: {e}")
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="legal",
                filename="legal_agent.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            logger.debug(f"[法务专家智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        # 获取领域技能描述 (Level 1: 仅名称+说明, 完整内容按需加载)
        skill_descriptions = ""
        try:
            if self.skill_registry and self.skill_registry.is_initialized():
                skill_descriptions = self.skill_registry.format_domain_skill_descriptions("legal")
        except Exception:
            pass

        return {
            "legal_domains": [d.value for d in LegalDomain],
            "contract_types": [c.value for c in ContractType],
            "skill_descriptions": skill_descriptions or "暂无可用技能",
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """你是一位专业的企业法律顾问，具有以下能力：
1. 精通中国法律法规，包括公司法、合同法、劳动法、知识产权法等
2. 熟悉各类合同的审查要点和风险识别
3. 能够提供合规性建议和风险防控措施
4. 了解行业监管要求和最佳实践

## 可用工具
- 时间锚点工具 get_current_time_and_context（【重要】处理时间相关查询时必须使用）

## 时间感知原则
大模型没有生物钟，当处理以下场景时，必须先调用 get_current_time_and_context：
- 用户询问"今年最新法规"、"去年法律变化"等相对时间
- 需要分析"近期政策动向"、"法律时效性"等时间相关分析
- 任何涉及法律法规生效日期的查询
- 合同条款中涉及时间条款的解释

## 法律时间敏感性
- 法律法规有明确的生效日期和失效日期
- 司法解释和指导案例有时效性
- 合同中的期限条款需要准确的时间理解
- 法律程序有严格的时间限制（如诉讼时效、上诉期限）

## 工作流程
1. 当用户查询包含相对时间词时，先调用 get_current_time_and_context 获取准确时间基准
2. 根据时间基准查询对应时期的法律法规
3. 分析法律条款的时效性和适用性
4. 提供基于准确时间的专业法律建议

在回答时，请：
- 引用相关法律法规条款（注明生效日期和修订情况）
- 明确指出法律风险点（考虑时效性）
- 提供具体的修改建议（针对合同条款）
- 建议合理的风险防控措施
- 明确说明法律界限和合规要求（基于当前法律环境）
- 清晰说明时间基准（例如："基于当前 2026 年 4 月的时间，根据 2026 年最新修订的《公司法》..."）
"""
    
    def _compile_entity_patterns(self) -> Dict[str, re.Pattern]:
        """编译法律实体提取正则表达式"""
        return {
            "money": re.compile(
                r'(?:CNY|USD|EUR|GBP|美元|欧元|英镑)?\s*[\d,]+(?:\.\d{2})?',
                re.IGNORECASE
            ),
            "date": re.compile(
                r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?'
            ),
            "percentage": re.compile(
                r'(\d+(?:\.\d+)?)\s*%',
                re.IGNORECASE
            ),
            "email": re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            "phone": re.compile(
                r'\+?[\d\s-]{10,}'
            ),
            "company_name": re.compile(
                r'(?:公司|集团|企业|有限合伙|股份有限公司)\b'
            )
        }
    
    def _load_contract_templates(self) -> Dict[str, Dict[str, Any]]:
        """加载合同模板知识"""
        return {
            "purchase": {
                "key_clauses": ["标的物", "价格与支付", "交付与验收", "质量保证", "违约责任"],
                "risk_points": ["所有权转移风险", "质量标准不明确", "交付延迟责任", "验收标准缺失"]
            },
            "sales": {
                "key_clauses": ["产品规格", "价格条款", "交付方式", "售后服务", "知识产权归属"],
                "risk_points": ["产品责任风险", "定价机制风险", "独家销售限制", "竞业限制条款"]
            },
            "service": {
                "key_clauses": ["服务内容", "服务标准", "费用与支付", "保密义务", "竞业限制"],
                "risk_points": ["服务范围界定不清", "验收标准模糊", "知识产权归属", "人员管理责任"]
            },
            "employment": {
                "key_clauses": ["工作内容", "薪酬福利", "工作地点", "保密与竞业", "解除条件"],
                "risk_points": ["试用期约定", "加班条款", "竞业限制", "离职交接", "保密义务范围"]
            }
        }
    
    def extract_entities(self, text: str) -> LegalEntity:
        """
        提取法律实体
        
        Args:
            text: 输入文本
            
        Returns:
            提取的法律实体
        """
        # 防御性处理：确保 text 是字符串
        if not isinstance(text, str):
            text = str(text) if text else ""
        
        entity = LegalEntity(parties=[])
        
        for pattern_name, pattern in self.entity_patterns.items():
            matches = pattern.findall(text)
            if matches:
                if pattern_name == "money":
                    amount_str = matches[0].replace(',', '')
                    entity.amount = float(re.sub(r'[^\d.]', '', amount_str))
                elif pattern_name == "date":
                    if not entity.effective_date:
                        entity.effective_date = matches[0]
                    elif not entity.expiration_date:
                        entity.expiration_date = matches[0]
                elif pattern_name == "percentage":
                    entity.amount = float(matches[0])
                elif pattern_name == "company_name":
                    entity.parties.append(matches[0])
        
        contract_keywords = {
            "采购合同": ContractType.PURCHASE,
            "销售合同": ContractType.SALES,
            "租赁合同": ContractType.LEASE,
            "服务合同": ContractType.SERVICE,
            "劳动合同": ContractType.EMPLOYMENT,
            "许可协议": ContractType.LICENSING,
            "保密协议": ContractType.CONFIDENTIALITY,
            "NDA": ContractType.CONFIDENTIALITY,
            "竞业禁止": ContractType.EMPLOYMENT,
            "竞业限制": ContractType.EMPLOYMENT
        }
        
        for keyword, contract_type in contract_keywords.items():
            if keyword.lower() in text.lower():
                entity.contract_type = contract_type.value
                break
        
        domain_keywords = {
            "知识产权": LegalDomain.INTELLECTUAL_PROPERTY,
            "专利": LegalDomain.INTELLECTUAL_PROPERTY,
            "商标": LegalDomain.INTELLECTUAL_PROPERTY,
            "著作权": LegalDomain.INTELLECTUAL_PROPERTY,
            "版权": LegalDomain.INTELLECTUAL_PROPERTY,
            "劳动法": LegalDomain.LABOR,
            "劳动合同": LegalDomain.LABOR,
            "开除": LegalDomain.LABOR,
            "裁员": LegalDomain.LABOR,
            "公司治理": LegalDomain.CORPORATE,
            "股权": LegalDomain.CORPORATE,
            "股东": LegalDomain.CORPORATE,
            "董事会": LegalDomain.CORPORATE,
            "合规": LegalDomain.COMPLIANCE,
            "监管": LegalDomain.REGULATORY
        }
        
        return entity
    
    def identify_domain(self, text: str) -> LegalDomain:
        """
        识别法律领域
        
        Args:
            text: 输入文本
            
        Returns:
            法律领域
        """
        # 防御性处理：确保 text 是字符串
        if not isinstance(text, str):
            text = str(text) if text else ""
        
        domain_keywords = {
            "知识产权": LegalDomain.INTELLECTUAL_PROPERTY,
            "专利": LegalDomain.INTELLECTUAL_PROPERTY,
            "商标": LegalDomain.INTELLECTUAL_PROPERTY,
            "著作权": LegalDomain.INTELLECTUAL_PROPERTY,
            "版权": LegalDomain.INTELLECTUAL_PROPERTY,
            "劳动法": LegalDomain.LABOR,
            "劳动合同": LegalDomain.LABOR,
            "开除": LegalDomain.LABOR,
            "裁员": LegalDomain.LABOR,
            "公司治理": LegalDomain.CORPORATE,
            "股权": LegalDomain.CORPORATE,
            "股东": LegalDomain.CORPORATE,
            "董事会": LegalDomain.CORPORATE,
            "合规": LegalDomain.COMPLIANCE,
            "监管": LegalDomain.REGULATORY,
            "诉讼": LegalDomain.LITIGATION,
            "仲裁": LegalDomain.LITIGATION
        }
        
        for keyword, domain in domain_keywords.items():
            if keyword in text:
                return domain
        
        if "合同" in text:
            return LegalDomain.CONTRACT
        
        return LegalDomain.OTHER
    
    def identify_contract_type(self, text: str) -> Optional[ContractType]:
        """
        识别合同类型
        
        Args:
            text: 输入文本
            
        Returns:
            合同类型
        """
        # 防御性处理：确保 text 是字符串
        if not isinstance(text, str):
            text = str(text) if text else ""
        
        contract_keywords = {
            "采购合同": ContractType.PURCHASE,
            "销售合同": ContractType.SALES,
            "租赁合同": ContractType.LEASE,
            "服务合同": ContractType.SERVICE,
            "劳动合同": ContractType.EMPLOYMENT,
            "许可协议": ContractType.LICENSING,
            "保密协议": ContractType.CONFIDENTIALITY,
            "NDA": ContractType.CONFIDENTIALITY,
            "竞业禁止": ContractType.EMPLOYMENT,
            "竞业限制": ContractType.EMPLOYMENT
        }
        
        for keyword, contract_type in contract_keywords.items():
            if keyword.lower() in text.lower():
                return contract_type
        
        return None
    
    async def review_contract(
        self,
        contract_text: str,
        contract_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        审查合同
        
        Args:
            contract_text: 合同文本
            contract_type: 合同类型
            
        Returns:
            合同审查结果
        """
        template = self.contract_templates.get(contract_type, {})
        key_clauses = template.get("key_clauses", [])
        risk_points = template.get("risk_points", [])
        
        prompt = f"""请审查以下合同文本：
        
        合同类型：{contract_type or '未指定'}
        重点检查条款：{', '.join(key_clauses)}
        
        合同文本：
        {contract_text}
        
        请分析：
        1. 合同的有效性和可执行性
        2. 各方权利义务是否对等
        3. 关键条款是否完整
        4. 潜在的法律风险点
        5. 修改建议
        """
        
        full_prompt = f"{self.system_prompt}\n\n{prompt}" if self.system_prompt else prompt
        response = await self.llm_adapter.generate(
            prompt=full_prompt,
            temperature=0.3
        )
        
        return {
            "contract_type": contract_type,
            "key_clauses": key_clauses,
            "risk_points": risk_points,
            "analysis": response,
            "requires_revision": len(risk_points) > 0
        }
    
    async def run(
        self,
        user_input: str,
        history: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
        rag_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理法务咨询请求 — LLM 驱动模式

        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            rag_context: RAG 检索到的知识库上下文（{"documents": [...]}）
            **kwargs: 其他参数

        Returns:
            处理结果
        """
        try:
            entities = self.extract_entities(user_input)
            domain = self.identify_domain(user_input)
            contract_type = self.identify_contract_type(user_input)

            prompt = self._build_legal_prompt(user_input, entities, domain)

            # 构建 chat messages（从 generate 模式迁移到 chat 模式以支持 function calling）
            chat_messages = []
            if self.system_prompt:
                chat_messages.append({"role": "system", "content": self.system_prompt})

            # 注入知识库 grounding
            if rag_context and rag_context.get("documents"):
                doc_texts = []
                for i, doc in enumerate(rag_context["documents"][:3], 1):
                    c = doc.get("content", "")
                    if c:
                        doc_texts.append(f"### 文档{i}\n{c[:1000]}")
                if doc_texts:
                    chat_messages.append({
                        "role": "system",
                        "content": "## 企业知识库相关文档\n" + "\n".join(doc_texts),
                    })

            chat_messages.append({"role": "user", "content": prompt})

            # 上下文参数（供工具自动注入）+ 流式回调（由 orchestrator 挂载）
            tenant_id = context.get("tenant_id", "default") if context else "default"
            user_id = context.get("user_id", "default") if context else "default"
            chunk_cb = None
            try:
                if getattr(self, "_orchestrator_ref", None):
                    chunk_cb = self._orchestrator_ref._chunk_callback
            except Exception:
                pass

            response_text, tool_results = await self._call_with_tool_loop(
                messages=chat_messages,
                temperature=0.3,
                timeout=90.0,
                context_params={"tenant_id": tenant_id, "user_id": user_id},
                chunk_callback=chunk_cb,
            )
            logger.info(
                f"[LegalSpecialist] response: {len(response_text)} chars, "
                f"tool calls: {len(tool_results)}"
            )

            analysis = self._parse_llm_response(response_text, domain, contract_type)
            risk_assessment = self.assess_legal_risk(analysis, entities)

            return {
                "success": True,
                "domain": domain,
                "contract_type": contract_type,
                "text_answer": response_text,
                "analysis": analysis.dict(),
                "risk_assessment": risk_assessment,
                "entities": {
                    "parties": entities.parties,
                    "amount": entities.amount,
                    "effective_date": entities.effective_date,
                    "expiration_date": entities.expiration_date,
                },
                "recommendations": self._generate_recommendations(analysis, domain),
                "confidence": analysis.confidence,
                "tool_calls": tool_results,
            }
            
        except (ValueError, KeyError) as e:
            import traceback
            logger.error(f"法律分析数据失败: {e}")
            return {
                "success": False,
                "error": f"数据错误: {str(e)}",
                "fallback": "建议您咨询专业法律顾问获取准确信息"
            }
        except (OSError, IOError) as e:
            import traceback
            logger.error(f"法律分析IO失败: {e}")
            return {
                "success": False,
                "error": f"IO错误: {str(e)}",
                "fallback": "建议您咨询专业法律顾问获取准确信息"
            }
        except Exception as e:
            import traceback
            logger.error(f"法律分析失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "fallback": "建议您咨询专业法律顾问获取准确信息"
            }
    
    def _build_legal_prompt(
        self,
        user_input: str,
        entities: LegalEntity,
        domain: LegalDomain
    ) -> str:
        """构建法律分析提示词"""
        prompt_parts = [
            f"用户问题：{user_input}\n",
            f"识别法律领域：{domain.value}",
            "\n提取的法律实体："
        ]
        
        if entities.parties:
            prompt_parts.append(f"- 当事人：{', '.join(entities.parties)}")
        if entities.amount:
            prompt_parts.append(f"- 金额：{entities.amount}")
        if entities.effective_date:
            prompt_parts.append(f"- 生效日期：{entities.effective_date}")
        if entities.expiration_date:
            prompt_parts.append(f"- 到期日期：{entities.expiration_date}")
        
        prompt_parts.extend([
            "\n请进行法律分析，包括：",
            "1. 相关法律条款和规定",
            "2. 权利义务分析",
            "3. 法律风险点识别",
            "4. 合规性建议",
            "5. 风险防控措施"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(
        self,
        response: str,
        domain: LegalDomain,
        contract_type: Optional[ContractType]
    ) -> LegalAnalysisResult:
        """解析LLM响应"""
        try:
            key_clauses = []
            risk_clauses = []
            
            if "风险" in response or "风险点" in response:
                risk_clauses.append({
                    "description": "发现潜在法律风险",
                    "severity": "medium"
                })
            
            confidence = 0.8
            if domain != LegalDomain.OTHER and domain != LegalDomain.CONTRACT:
                confidence = 0.9
            
            return LegalAnalysisResult(
                domain=domain,
                contract_type=contract_type,
                key_clauses=key_clauses,
                risk_clauses=risk_clauses,
                compliance_status="review_required" if risk_clauses else "compliant",
                confidence=confidence
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"解析法律响应数据失败: {e}")
            return LegalAnalysisResult(
                domain=LegalDomain.OTHER,
                confidence=0.0,
                compliance_status="error"
            )
        except (OSError, IOError) as e:
            logger.warning(f"解析法律响应IO失败: {e}")
            return LegalAnalysisResult(
                domain=LegalDomain.OTHER,
                confidence=0.0,
                compliance_status="error"
            )
        except Exception as e:
            logger.warning(f"解析法律响应失败: {e}")
            return LegalAnalysisResult(
                domain=LegalDomain.OTHER,
                confidence=0.5
            )
    
    def assess_legal_risk(
        self,
        analysis: LegalAnalysisResult,
        entities: LegalEntity
    ) -> Dict[str, Any]:
        """
        评估法律风险
        
        Args:
            analysis: 法律分析结果
            entities: 法律实体
            
        Returns:
            风险评估结果
        """
        risk_level = "low"
        risk_factors = []
        
        if analysis.confidence < 0.7:
            risk_level = "medium"
            risk_factors.append("置信度较低，建议人工复核")
        
        if analysis.risk_clauses:
            risk_level = "high"
            risk_factors.append("发现多个法律风险条款")
        
        if entities.amount and entities.amount > 5000000:
            risk_level = "high"
            risk_factors.append("涉及金额较大，建议专业法务审核")
        
        if analysis.domain in [LegalDomain.LITIGATION, LegalDomain.REGULATORY]:
            risk_level = "high"
            risk_factors.append("涉及诉讼或监管事项，建议专业处理")
        
        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "requires_legal_review": risk_level in ["high", "medium"]
        }
    
    def _generate_recommendations(
        self,
        analysis: LegalAnalysisResult,
        domain: LegalDomain
    ) -> List[str]:
        """生成法律建议"""
        recommendations = []
        
        if analysis.compliance_status == "review_required":
            recommendations.append("建议进行详细的法律合规性审查")
        
        if analysis.domain == LegalDomain.CONTRACT:
            recommendations.append("确保合同条款清晰、完整、无歧义")
            recommendations.append("明确各方的权利义务和违约责任")
            recommendations.append("建议设置合理的争议解决机制")
        
        if analysis.domain == LegalDomain.INTELLECTUAL_PROPERTY:
            recommendations.append("确保知识产权归属明确")
            recommendations.append("签订保密协议保护商业秘密")
            recommendations.append("及时进行知识产权登记和保护")
        
        if analysis.domain == LegalDomain.LABOR:
            recommendations.append("确保劳动合同符合劳动法规定")
            recommendations.append("明确薪酬、福利和工作条件")
            recommendations.append("遵守社保和公积金缴纳义务")
        
        recommendations.append("如涉及重大法律事项，建议咨询专业律师")
        recommendations.append("保留完整的法律文档和沟通记录")
        
        return recommendations
    
    async def audit(
        self,
        state: AuditState,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行法律审查
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表
        """
        findings = []
        
        for doc in documents:
            content = doc.get("content", "")
            
            domain = self.identify_domain(content)
            contract_type = self.identify_contract_type(content)
            
            if contract_type:
                findings.append(Finding(
                    id=f"LEG_CON_{len(findings) + 1}",
                    agent_name="legal",
                    category="合同管理",
                    description=f"发现{contract_type.value}类型合同",
                    risk_level=RiskLevel.INFO,
                    risk_score=10.0,
                    confidence=0.8,
                    evidence=[],
                    recommendations=["核实合同条款完备性"]
                ))
            
            for pattern_name, pattern in self.entity_patterns.items():
                matches = pattern.findall(content)
                if matches and pattern_name == "date" and len(matches) >= 2:
                    findings.append(Finding(
                        id=f"LEG_DATE_{len(findings) + 1}",
                        agent_name="legal",
                        category="日期审查",
                        description="发现合同日期信息",
                        risk_level=RiskLevel.INFO,
                        risk_score=10.0,
                        confidence=0.8,
                        evidence=[],
                        recommendations=["核实日期的合理性"]
                    ))
            
            for rule in self.knowledge_base:
                if rule.get("rule_id", "").startswith("LEG"):
                    if any(keyword in content for keyword in ["不符", "违规", "缺失", "模糊"]):
                        findings.append(Finding(
                            id=f"LEG_KB_{len(findings) + 1}",
                            agent_name="legal",
                            category=rule.get("category", "法律合规"),
                            description=rule.get("description", ""),
                            risk_level=RiskLevel.HIGH,
                            risk_score=70.0,
                            confidence=0.8,
                            evidence=[],
                            recommendations=["进行法律合规性检查"]
                        ))
        
        return findings
    
    def get_legal_knowledge(self, domain: str) -> List[Dict[str, Any]]:
        """
        获取特定法律领域的知识
        
        Args:
            domain: 法律领域
            
        Returns:
            法律知识列表
        """
        legal_knowledge_map = {
            "contract": [
                {
                    "rule_id": "CON_001",
                    "category": "合同有效性",
                    "description": "合同有效的要件",
                    "requirements": ["当事人具有民事行为能力", "意思表示真实", "不违反法律强制性规定", "不违反公序良俗"]
                },
                {
                    "rule_id": "CON_002",
                    "category": "合同审查要点",
                    "description": "合同审查的基本要素",
                    "checkpoints": ["主体资格", "标的物", "数量质量", "价款支付", "履行期限", "违约责任", "争议解决"]
                }
            ],
            "ip": [
                {
                    "rule_id": "IP_001",
                    "category": "专利保护",
                    "description": "专利申请和保护策略",
                    "requirements": ["新颖性", "创造性", "实用性"]
                },
                {
                    "rule_id": "IP_002",
                    "category": "商标保护",
                    "description": "商标注册和使用规范",
                    "tips": ["尽早注册", "防御性注册", "持续使用"]
                }
            ],
            "labor": [
                {
                    "rule_id": "LAB_001",
                    "category": "劳动合同",
                    "description": "劳动合同的签订要求",
                    "requirements": ["书面形式", "试用期规定", "社会保险", "加班补偿"]
                },
                {
                    "rule_id": "LAB_002",
                    "category": "竞业限制",
                    "description": "竞业限制的法律规定",
                    "limits": ["期限不超过2年", "需支付补偿金", "范围地域合理"]
                }
            ]
        }
        
        return legal_knowledge_map.get(domain, [])
    
    async def stream_run(
        self,
        user_input: str,
        history: List[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        流式执行法务专家智能体
        
        实现基类的抽象方法
        
        Args:
            user_input: 用户输入
            history: 对话历史
            
        Yields:
            处理结果片段
        """
        result = await self.run(user_input, history, **kwargs)
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
        
        for char in result_str:
            yield char
