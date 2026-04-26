"""
合同审核智能助手服务
提供合同深度分析和风险评估功能
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import HTTPException
from app.schemas.contract_review import (
    ContractType,
    RiskLevel,
    ClauseType,
    ReviewStatus,
    ContractClause,
    RiskAssessment,
    ClauseComparison,
    ContractAnalysisRequest,
    ContractAnalysisResponse,
    DeepClauseAnalysisRequest,
    DeepClauseAnalysisResponse,
    ContractComparisonRequest,
    ContractComparisonResponse,
)
from app.services.agent_tracer import AgentTracer
from app.services.policy_retrieval_service import PolicyRetrievalService

logger = logging.getLogger(__name__)


class ContractClauseExtractor:
    """
    合同条款提取器
    
    从合同文本中识别和提取各类条款
    """

    def __init__(self):
        self.clause_patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> Dict[ClauseType, List[str]]:
        """初始化条款识别模式"""
        return {
            ClauseType.PAYMENT: [
                "付款", "支付", "结算", "账期", "发票", "税费"
            ],
            ClauseType.DELIVERY: [
                "交付", "交货", "发货", "验收", "运输", "时间"
            ],
            ClauseType.WARRANTY: [
                "保修", "质保", "维修", "质量保证"
            ],
            ClauseType.LIABILITY: [
                "责任", "义务", "违约", "赔偿", "损失"
            ],
            ClauseType.TERMINATION: [
                "终止", "解除", "到期", "续约", "结束"
            ],
            ClauseType.CONFIDENTIALITY: [
                "保密", "机密", "信息披露", "商业秘密"
            ],
            ClauseType.INTELLECTUAL_PROPERTY: [
                "知识产权", "专利", "商标", "版权", "IP"
            ],
            ClauseType.DISPUTE_RESOLUTION: [
                "争议", "仲裁", "诉讼", "纠纷", "调解"
            ],
            ClauseType.FORCE_MAJEURE: [
                "不可抗力", "自然灾害", "突发事件"
            ],
            ClauseType.INDEMNIFICATION: [
                "赔偿", "补偿", " indemnify", "保障"
            ],
            ClauseType.ASSIGNMENT: [
                "转让", "转移", "分包", "转包"
            ],
            ClauseType.GOVERNING_LAW: [
                "适用法律", "管辖", "法律适用", "司法管辖"
            ],
        }

    def extract_clauses(self, contract_content: str) -> List[ContractClause]:
        """
        提取合同条款
        
        Args:
            contract_content: 合同文本
            
        Returns:
            List[ContractClause]: 提取的条款列表
        """
        clauses = []
        lines = contract_content.split("\n")
        
        current_section = ""
        current_content = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if any(marker in line for marker in ["第", "条", "款", "章", "第"]):
                if current_content:
                    clause = self._classify_and_create_clause(
                        current_section,
                        "\n".join(current_content),
                        i
                    )
                    if clause:
                        clauses.append(clause)
                
                current_section = line
                current_content = [line]
            else:
                current_content.append(line)
        
        if current_content:
            clause = self._classify_and_create_clause(
                current_section,
                "\n".join(current_content),
                len(lines)
            )
            if clause:
                clauses.append(clause)
        
        return clauses

    def _classify_and_create_clause(
        self,
        title: str,
        content: str,
        line_number: int
    ) -> Optional[ContractClause]:
        """分类并创建条款"""
        content_lower = content.lower()
        
        matched_type = ClauseType.OTHER
        for clause_type, keywords in self.clause_patterns.items():
            if any(keyword in content_lower for keyword in keywords):
                matched_type = clause_type
                break
        
        risk_level = self._assess_clause_risk(content)
        
        return ContractClause(
            clause_id=str(uuid.uuid4()),
            clause_type=matched_type,
            title=title[:100] if title else "未识别条款",
            content=content[:1000],
            location=f"第{line_number}行",
            risk_level=risk_level,
            risk_description=self._get_risk_description(content, risk_level),
            is_standard_clause=self._is_standard_clause(content),
            deviations=self._find_deviations(content),
            importance=self._assess_importance(content),
            requires_attention=risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        )

    def _assess_clause_risk(self, content: str) -> RiskLevel:
        """评估条款风险"""
        risk_indicators = {
            RiskLevel.CRITICAL: ["无条件", "永久", "放弃", "免除全部", "不得异议"],
            RiskLevel.HIGH: ["30日", "违约金", "赔偿", "重大损失", "单方面"],
            RiskLevel.MEDIUM: ["应当", "如因", "超过", "变更"],
        }
        
        content_lower = content.lower()
        
        for indicator in risk_indicators[RiskLevel.CRITICAL]:
            if indicator in content_lower:
                return RiskLevel.CRITICAL
        
        for indicator in risk_indicators[RiskLevel.HIGH]:
            if indicator in content_lower:
                return RiskLevel.HIGH
        
        for indicator in risk_indicators[RiskLevel.MEDIUM]:
            if indicator in content_lower:
                return RiskLevel.MEDIUM
        
        return RiskLevel.LOW

    def _get_risk_description(self, content: str, risk_level: RiskLevel) -> str:
        """获取风险描述"""
        if risk_level == RiskLevel.CRITICAL:
            return "存在严重风险，可能导致重大损失或法律纠纷"
        elif risk_level == RiskLevel.HIGH:
            return "存在较高风险，建议谨慎处理"
        elif risk_level == RiskLevel.MEDIUM:
            return "存在一定风险，需要注意"
        return "基本无风险"

    def _is_standard_clause(self, content: str) -> bool:
        """判断是否为标准条款"""
        standard_keywords = ["按照", "根据", "依据", "符合", "遵循"]
        return any(keyword in content for keyword in standard_keywords)

    def _find_deviations(self, content: str) -> List[str]:
        """找出偏离标准的内容"""
        deviations = []
        
        if "单方面" in content:
            deviations.append("存在单方面权利/义务条款")
        if "无条件" in content:
            deviations.append("存在无条件条款")
        if any(word in content for word in ["不得", "禁止", "无权"]):
            deviations.append("存在限制性条款")
        
        return deviations

    def _assess_importance(self, content: str) -> str:
        """评估重要性"""
        if any(word in content for word in ["责任", "赔偿", "违约", "终止"]):
            return "关键"
        elif any(word in content for word in ["付款", "交付", "验收"]):
            return "重要"
        return "一般"


class ContractRiskAssessor:
    """
    合同风险评估器
    
    评估合同的整体风险和具体风险点
    """

    def assess_risks(
        self,
        clauses: List[ContractClause],
        contract_type: ContractType,
        contract_value: Optional[float] = None
    ) -> List[RiskAssessment]:
        """
        评估风险
        
        Args:
            clauses: 条款列表
            contract_type: 合同类型
            contract_value: 合同金额
            
        Returns:
            List[RiskAssessment]: 风险评估列表
        """
        risks = []
        
        high_risk_clauses = [c for c in clauses if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        
        if high_risk_clauses:
            risks.append(RiskAssessment(
                risk_id=str(uuid.uuid4()),
                risk_type="高风险条款",
                risk_level=RiskLevel.HIGH,
                description=f"合同包含 {len(high_risk_clauses)} 个高风险条款",
                affected_clauses=[c.clause_id for c in high_risk_clauses],
                potential_impact="可能导致合同纠纷或经济损失",
                likelihood=0.7,
                mitigation_suggestions=[
                    "建议聘请专业律师审核",
                    "与对方协商修改高风险条款",
                    "增加风险缓释措施"
                ],
                requires_human_review=True
            ))
        
        clause_types = set(c.clause_type for c in clauses)
        required_types = self._get_required_clauses(contract_type)
        
        missing_types = required_types - clause_types
        if missing_types:
            risks.append(RiskAssessment(
                risk_id=str(uuid.uuid4()),
                risk_type="缺失条款",
                risk_level=RiskLevel.MEDIUM,
                description=f"缺少必要的{missing_types}条款",
                affected_clauses=[],
                potential_impact="可能影响合同的完整性和可执行性",
                likelihood=0.5,
                mitigation_suggestions=[
                    "补充缺失的条款",
                    "确保合同条款完整"
                ],
                requires_human_review=False
            ))
        
        termination_clauses = [c for c in clauses if c.clause_type == ClauseType.TERMINATION]
        if not termination_clauses:
            risks.append(RiskAssessment(
                risk_id=str(uuid.uuid4()),
                risk_type="终止条款缺失",
                risk_level=RiskLevel.MEDIUM,
                description="合同中未找到终止条款",
                affected_clauses=[],
                potential_impact="合同终止时可能产生争议",
                likelihood=0.4,
                mitigation_suggestions=[
                    "添加明确的终止条件和程序",
                    "规定提前通知期限"
                ],
                requires_human_review=False
            ))
        
        liability_clauses = [c for c in clauses if c.clause_type == ClauseType.LIABILITY]
        if liability_clauses:
            risks.append(RiskAssessment(
                risk_id=str(uuid.uuid4()),
                risk_type="责任限制",
                risk_level=RiskLevel.MEDIUM,
                description="合同包含责任相关条款",
                affected_clauses=[c.clause_id for c in liability_clauses],
                potential_impact="责任范围可能过于宽泛或狭窄",
                likelihood=0.6,
                mitigation_suggestions=[
                    "明确责任上限",
                    "区分不同类型的违约责任"
                ],
                requires_human_review=True
            ))
        
        return risks

    def _get_required_clauses(self, contract_type: ContractType) -> set:
        """获取合同类型要求的必要条款"""
        base_required = {
            ClauseType.PAYMENT,
            ClauseType.LIABILITY,
            ClauseType.TERMINATION
        }
        
        type_specific = {
            ContractType.SERVICE: {ClauseType.DELIVERY, ClauseType.WARRANTY},
            ContractType.PURCHASE: {ClauseType.DELIVERY, ClauseType.WARRANTY},
            ContractType.SALES: {ClauseType.DELIVERY},
            ContractType.LABOR: {ClauseType.CONFIDENTIALITY},
            ContractType.PARTNERSHIP: {ClauseType.INTELLECTUAL_PROPERTY},
        }
        
        return base_required | type_specific.get(contract_type, set())


class ContractReviewService:
    """
    合同审核服务
    
    功能：
    1. 合同全文分析
    2. 深度条款分析
    3. 风险评估
    4. 修改建议
    5. 合同对比
    """

    def __init__(self):
        self.clause_extractor = ContractClauseExtractor()
        self.risk_assessor = ContractRiskAssessor()
        self.agent_tracer = AgentTracer()
        self.policy_retrieval = PolicyRetrievalService()
        
        self._analysis_cache = {}
        
        logger.info("✅ 合同审核服务初始化完成")

    async def analyze_contract(
        self,
        request: ContractAnalysisRequest
    ) -> Dict[str, Any]:
        """
        分析合同
        
        Args:
            request: 合同分析请求
            
        Returns:
            Dict: 分析结果
        """
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"📋 开始合同分析: {analysis_id}")
        
        trace_id = await self.agent_tracer.start_trace(
            agent_type="contract_review",
            user_query=f"合同分析: {request.contract_name}",
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            message_id=analysis_id
        )
        
        try:
            # 提取合同条款
            clauses = self.clause_extractor.extract_clauses(request.contract_content)
            logger.info(f"✅ 成功提取 {len(clauses)} 个条款")
            
            # 评估风险
            risk_assessments = []
            if request.include_risk_assessment:
                risk_assessments = self.risk_assessor.assess_risks(
                    clauses,
                    request.contract_type,
                    request.contract_value
                )
                logger.info(f"✅ 风险评估完成，发现 {len(risk_assessments)} 个风险点")
            
            # 计算风险评分
            risk_score = self._calculate_risk_score(clauses, risk_assessments)
            overall_risk_level = self._get_overall_risk_level(risk_score)
            
            # 提取关键发现
            key_findings = self._extract_key_findings(clauses, risk_assessments)
            high_risk_items = self._identify_high_risk_items(clauses, risk_assessments)
            recommended_actions = self._generate_recommendations(
                clauses,
                risk_assessments,
                overall_risk_level
            )
            
            await self.agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=f"合同分析完成，风险评分: {risk_score:.1f}",
                success=True
            )
            
            response = ContractAnalysisResponse(
                analysis_id=analysis_id,
                status=ReviewStatus.COMPLETED,
                contract_name=request.contract_name,
                contract_type=request.contract_type,
                overall_risk_level=overall_risk_level,
                risk_score=risk_score,
                clauses_extracted=clauses,
                risk_assessments=risk_assessments,
                key_findings=key_findings,
                high_risk_items=high_risk_items,
                recommended_actions=recommended_actions,
                summary=self._generate_summary(
                    request.contract_name,
                    len(clauses),
                    len(risk_assessments),
                    overall_risk_level
                ),
                generated_at=datetime.now()
            )
            
            self._analysis_cache[analysis_id] = response.model_dump()
            
            logger.info(f"✅ 合同分析成功完成，analysis_id: {analysis_id}")
            return response.model_dump()
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 合同分析数据错误: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 合同分析IO错误: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            logger.error(f"❌ 合同分析失败: {e}", exc_info=True)
            
            await self.agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=f"分析失败: {str(e)}",
                success=False,
                error_message=str(e)
            )
            
            # 返回基础结果而不是抛出异常
            return self._create_fallback_analysis(request)

    def _create_fallback_analysis(self, request: ContractAnalysisRequest) -> Dict[str, Any]:
        """
        创建降级分析结果

        当正常分析失败时，提供一个基础的分析结果
        
        Args:
            request: 合同分析请求
            
        Returns:
            Dict: 降级的分析结果
        """
        analysis_id = str(uuid.uuid4())
        
        logger.warning(f"⚠️ 使用降级分析方案，analysis_id: {analysis_id}")
        
        # 简单的文本分析
        content_length = len(request.contract_content)
        has_legal_keywords = any(
            keyword in request.contract_content.lower() 
            for keyword in ['合同', '协议', '甲方', '乙方', '条款', '违约', '责任']
        )
        
        # 基础风险评估
        if has_legal_keywords:
            risk_score = 50.0
            overall_risk_level = RiskLevel.MEDIUM
            summary = "该文本包含合同相关关键词，建议进行详细法律审核"
        else:
            risk_score = 30.0
            overall_risk_level = RiskLevel.LOW
            summary = "该文本可能不是标准合同格式，但仍建议进行人工审核"
        
        response = ContractAnalysisResponse(
            analysis_id=analysis_id,
            status=ReviewStatus.COMPLETED,
            contract_name=request.contract_name,
            contract_type=request.contract_type,
            overall_risk_level=overall_risk_level,
            risk_score=risk_score,
            clauses_extracted=[],
            risk_assessments=[],
            key_findings=[
                f"文本长度: {content_length} 字符",
                "包含合同关键词" if has_legal_keywords else "未检测到明显合同关键词",
                "建议人工审核以确保准确性"
            ],
            high_risk_items=[],
            recommended_actions=[
                "建议使用标准合同模板",
                "请人工审核文本内容",
                "如有疑问，请咨询专业律师"
            ],
            summary=summary,
            generated_at=datetime.now()
        )
        
        self._analysis_cache[analysis_id] = response.model_dump()
        
        return response.model_dump()

    async def analyze_clause_deeply(
        self,
        request: DeepClauseAnalysisRequest
    ) -> Dict[str, Any]:
        """
        深度条款分析
        
        Args:
            request: 深度分析请求
            
        Returns:
            Dict: 分析结果
        """
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"🔍 开始深度条款分析: {analysis_id}")
        
        try:
            legal_interpretation = await self._interpret_clause_legally(
                request.clause_content,
                request.clause_type
            )
            
            potential_issues = self._identify_potential_issues(
                request.clause_content,
                request.clause_type
            )
            
            industry_practices = await self._get_industry_practices(
                request.clause_type
            )
            
            risk_factors = self._analyze_risk_factors(
                request.clause_content,
                request.clause_type
            )
            
            suggestions = self._generate_clause_suggestions(
                request.clause_content,
                request.clause_type
            )
            
            references = await self._search_relevant_regulations(
                request.clause_type
            )
            
            response = DeepClauseAnalysisResponse(
                analysis_id=analysis_id,
                clause_type=request.clause_type,
                clause_summary=self._summarize_clause(request.clause_content),
                legal_interpretation=legal_interpretation,
                potential_issues=potential_issues,
                industry_practices=industry_practices,
                comparison_with_standard=self._compare_with_standard(
                    request.clause_content,
                    request.clause_type
                ),
                risk_factors=risk_factors,
                suggestions=suggestions,
                references=references,
                generated_at=datetime.now()
            )
            
            return response.model_dump()
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 深度条款分析数据错误: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=str(e))
        except (OSError, IOError) as e:
            logger.error(f"❌ 深度条款分析IO错误: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"❌ 深度条款分析失败: {e}", exc_info=True)
            raise

    async def analyze_contract_with_legal_agent(
        self,
        request: ContractAnalysisRequest,
        user_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        上传合同并调用法务智能体进行深度分析

        Args:
            request: 合同分析请求
            user_id: 用户ID
            tenant_id: 租户ID

        Returns:
            Dict: 包含分析结果的字典
        """
        logger.info(f"🕵️ 开始调用法务智能体分析合同: {request.contract_name}")

        # 1. 首先进行基础的合同分析
        try:
            basic_analysis = await self.analyze_contract(request)
            logger.info(f"✅ 基础合同分析完成")
        except Exception as e:
            logger.error(f"❌ 基础合同分析失败: {e}", exc_info=True)
            # 使用降级方案继续处理
            basic_analysis = self._create_fallback_analysis(request)
            logger.warning(f"⚠️ 使用降级分析方案继续处理")

        # 2. 尝试获取法务智能体实例
        legal_agent_available = False
        legal_result = None
        
        try:
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.agent_framework.tools.tool_manager import ToolManager
            from app.multi_agent_system.agents.legal_specialist import LegalSpecialist

            logger.info("🔧 初始化法务智能体...")

            llm_config = {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.3
            }

            llm_factory = LLMAdapterFactory()
            llm_adapter = await llm_factory.create_adapter(llm_config)
            logger.info("✅ LLM 适配器初始化成功")

            tool_manager = ToolManager()
            logger.info("✅ 工具管理器初始化成功")

            legal_specialist = LegalSpecialist(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager
            )
            logger.info("✅ 法务智能体初始化成功")

            # 3. 调用法务智能体进行深度分析
            legal_prompt = f"""请对以下合同进行深度法律分析和风险评估：

合同名称：{request.contract_name}
合同类型：{request.contract_type.value if hasattr(request.contract_type, 'value') else request.contract_type}
合同内容：
{request.contract_content[:3000]}

请从以下维度进行分析：
1. 合同的法律有效性和可执行性
2. 各方权利义务是否对等
3. 关键法律风险点识别
4. 合同条款合规性检查
5. 潜在的法律纠纷风险
6. 修改建议和风险缓解措施

请提供专业的法律意见。"""

            logger.info("📋 正在调用法务智能体...")
            legal_result = await legal_specialist.run(
                user_input=legal_prompt,
                context={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "analysis_type": "contract_review",
                    "contract_type": request.contract_type.value if hasattr(request.contract_type, 'value') else str(request.contract_type),
                    "include_deep_analysis": request.include_deep_analysis,
                    "include_risk_assessment": request.include_risk_assessment,
                    "include_suggestions": request.include_suggestions
                }
            )

            logger.info(f"✅ 法务智能体分析完成")
            legal_agent_available = True

        except ImportError as e:
            logger.warning(f"⚠️ 法务智能体模块导入失败: {e}")
            logger.info("📋 使用基础分析结果继续处理")
        except Exception as e:
            logger.error(f"❌ 调用法务智能体失败: {e}", exc_info=True)
            logger.info("📋 使用基础分析结果继续处理")

        # 4. 整合分析结果
        final_result = {
            **basic_analysis,
            "legal_agent_analysis": {
                "success": legal_agent_available,
                "available": legal_agent_available,
                "analysis": legal_result.get("analysis", {}) if legal_result else {},
                "risk_assessment": legal_result.get("risk_assessment", {}) if legal_result else {},
                "recommendations": legal_result.get("recommendations", []) if legal_result else [],
                "entities": legal_result.get("entities", {}) if legal_result else {},
                "confidence": legal_result.get("confidence", 0.0) if legal_result else 0.0,
                "domain": legal_result.get("domain") if legal_result else None
            } if legal_agent_available else {
                "success": False,
                "available": False,
                "message": "法务智能体暂时不可用，使用基础分析"
            },
            "generated_at": datetime.now().isoformat()
        }

        # 5. 保存到缓存
        analysis_id = basic_analysis.get("analysis_id")
        if analysis_id:
            self._analysis_cache[analysis_id] = final_result

        # 6. 保存到数据库
        try:
            await self._save_analysis_report(final_result, user_id, tenant_id)
        except Exception as e:
            logger.warning(f"保存分析报告失败（不影响主流程）: {e}")

        logger.info(f"✅ 合同分析完成，analysis_id: {analysis_id}")
        return final_result

    async def _save_analysis_report(
        self,
        analysis_result: Dict[str, Any],
        user_id: str,
        tenant_id: str
    ):
        """保存分析报告到数据库"""
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.contract_review import ContractReviewReport
            from datetime import datetime

            async with AsyncSessionLocal() as db:
                # 提取关键分析数据
                contract_name = analysis_result.get("contract_name", "未命名合同")
                contract_type = analysis_result.get("contract_type", "other")
                overall_risk_level = analysis_result.get("overall_risk_level", "low")
                overall_risk_score = analysis_result.get("risk_score", 0)
                
                # 处理 clauses_extracted（可能是 Pydantic 模型列表）
                clauses_extracted = analysis_result.get("clauses_extracted", [])
                if clauses_extracted and hasattr(clauses_extracted[0], 'model_dump'):
                    clauses_extracted = [c.model_dump() for c in clauses_extracted]
                
                # 处理 risk_assessments（可能是 Pydantic 模型列表）
                risk_assessments = analysis_result.get("risk_assessments", [])
                if risk_assessments and hasattr(risk_assessments[0], 'model_dump'):
                    risk_assessments = [r.model_dump() for r in risk_assessments]
                
                # 处理 legal_agent_analysis
                legal_agent_analysis = analysis_result.get("legal_agent_analysis", {})
                
                report = ContractReviewReport(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    contract_name=contract_name,
                    contract_type=contract_type,
                    overall_risk_level=overall_risk_level,
                    overall_risk_score=overall_risk_score / 100.0 if overall_risk_score else 0.0,
                    review_status=ReviewStatus.PENDING,
                    basic_analysis={
                        "clauses": clauses_extracted,
                        "risks": risk_assessments,
                        "key_findings": analysis_result.get("key_findings", []),
                        "high_risk_items": analysis_result.get("high_risk_items", []),
                        "recommended_actions": analysis_result.get("recommended_actions", [])
                    },
                    ai_analysis_summary=analysis_result.get("summary", ""),
                    clauses_analysis=clauses_extracted,
                    risk_clauses=risk_assessments,
                    suggestions=legal_agent_analysis.get("recommendations", []),
                    created_at=datetime.utcnow()
                )

                db.add(report)
                await db.commit()
                logger.info(f"✅ 分析报告已保存到数据库")

        except Exception as e:
            logger.error(f"❌ 保存分析报告失败: {e}", exc_info=True)

    async def _interpret_clause_legally(
        self,
        clause_content: str,
        clause_type: ClauseType
    ) -> str:
        """法律解释"""
        interpretations = {
            ClauseType.PAYMENT: "本条款规定了付款条件、时间和方式...",
            ClauseType.DELIVERY: "本条款规定了货物/服务交付的时间、地点和验收标准...",
            ClauseType.LIABILITY: "本条款规定了各方的责任范围和限制...",
            ClauseType.TERMINATION: "本条款规定了合同终止的条件和程序...",
            ClauseType.CONFIDENTIALITY: "本条款规定了保密义务的范围和期限...",
        }
        return interpretations.get(clause_type, "该条款需要根据具体内容进行法律解释...")

    def _identify_potential_issues(
        self,
        clause_content: str,
        clause_type: ClauseType
    ) -> List[str]:
        """识别潜在问题"""
        issues = []
        
        if "单方面" in clause_content:
            issues.append("存在单方面权利条款，可能有失公平")
        
        if "无条件" in clause_content:
            issues.append("存在无条件义务条款，需注意风险")
        
        if any(word in clause_content for word in ["不得", "禁止"]):
            count = sum(1 for word in ["不得", "禁止"] if word in clause_content)
            issues.append(f"存在{count}处限制性表述，可能对一方不利")
        
        if not issues:
            issues.append("未发现明显法律问题")
        
        return issues

    async def _get_industry_practices(
        self,
        clause_type: ClauseType
    ) -> List[str]:
        """获取行业惯例"""
        practices = {
            ClauseType.PAYMENT: [
                "行业惯例：账期通常为30-60天",
                "建议分阶段付款以降低风险",
                "银行转账是最常见的支付方式"
            ],
            ClauseType.DELIVERY: [
                "行业惯例：交付时间应有明确约定",
                "建议设置合理的验收期限",
                "货损责任通常以交货为界"
            ],
            ClauseType.LIABILITY: [
                "行业惯例：违约金不超过合同金额的20%",
                "建议明确责任上限",
                "间接损失通常不予赔偿"
            ],
        }
        return practices.get(clause_type, ["该类型条款的行业惯例需进一步调查"])

    def _analyze_risk_factors(
        self,
        clause_content: str,
        clause_type: ClauseType
    ) -> List[str]:
        """分析风险因素"""
        factors = []
        
        if len(clause_content) > 500:
            factors.append("条款内容较为复杂，需仔细阅读")
        
        if any(word in clause_content for word in ["全部", "所有", "无限"]):
            factors.append("存在宽泛的义务描述，风险较高")
        
        if not any(word in clause_content for word in ["但", "如", "若"]):
            factors.append("缺少例外条款，条款较为绝对")
        
        if not factors:
            factors.append("风险因素较少，条款相对平衡")
        
        return factors

    def _generate_clause_suggestions(
        self,
        clause_content: str,
        clause_type: ClauseType
    ) -> List[str]:
        """生成条款建议"""
        suggestions = []
        
        suggestions.append("建议增加明确的定义和解释条款")
        
        if clause_type == ClauseType.PAYMENT:
            suggestions.append("建议明确付款的具体账户信息")
            suggestions.append("建议规定逾期付款的利息计算方式")
        elif clause_type == ClauseType.DELIVERY:
            suggestions.append("建议明确验收标准和程序")
            suggestions.append("建议规定延期交付的责任")
        elif clause_type == ClauseType.LIABILITY:
            suggestions.append("建议明确责任上限")
            suggestions.append("建议区分不同类型的违约责任")
        
        return suggestions

    async def _search_relevant_regulations(
        self,
        clause_type: ClauseType
    ) -> List[Dict[str, str]]:
        """搜索相关法规"""
        try:
            search_results = await self.policy_retrieval.semantic_search(
                query=f"{clause_type.value} 合同 法规",
                top_k=3
            )
            
            references = []
            for result in search_results:
                references.append({
                    "title": result.get("title", "相关法规"),
                    "content": result.get("content", "")[:200]
                })
            
            if not references:
                references.append({
                    "title": "《中华人民共和国民法典》",
                    "content": "合同编相关规定"
                })
            
            return references
            
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ 搜索法规数据错误: {e}")
            return [{"title": "通用法规", "content": "请参考相关法律法规"}]
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ 搜索法规IO错误: {e}")
            return [{"title": "通用法规", "content": "请参考相关法律法规"}]
        except Exception as e:
            logger.warning(f"⚠️ 搜索法规失败: {e}")
            return [{"title": "通用法规", "content": "请参考相关法律法规"}]

    def _summarize_clause(self, clause_content: str) -> str:
        """总结条款"""
        summary = clause_content[:200]
        if len(clause_content) > 200:
            summary += "..."
        return summary

    def _compare_with_standard(
        self,
        clause_content: str,
        clause_type: ClauseType
    ) -> Dict[str, Any]:
        """与标准条款对比"""
        return {
            "is_standard": False,
            "deviation_count": 0,
            "comparison_notes": "需要根据具体条款内容进行对比"
        }

    def _calculate_risk_score(
        self,
        clauses: List[ContractClause],
        risks: List[RiskAssessment]
    ) -> float:
        """计算风险评分"""
        base_score = 0.0
        
        for clause in clauses:
            if clause.risk_level == RiskLevel.CRITICAL:
                base_score += 20
            elif clause.risk_level == RiskLevel.HIGH:
                base_score += 10
            elif clause.risk_level == RiskLevel.MEDIUM:
                base_score += 5
        
        for risk in risks:
            base_score += risk.likelihood * 15
        
        return min(100.0, base_score)

    def _get_overall_risk_level(self, risk_score: float) -> RiskLevel:
        """获取整体风险级别"""
        if risk_score >= 70:
            return RiskLevel.CRITICAL
        elif risk_score >= 40:
            return RiskLevel.HIGH
        elif risk_score >= 20:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _extract_key_findings(
        self,
        clauses: List[ContractClause],
        risks: List[RiskAssessment]
    ) -> List[str]:
        """提取关键发现"""
        findings = []
        
        clause_counts = {}
        for clause in clauses:
            clause_type = clause.clause_type.value
            clause_counts[clause_type] = clause_counts.get(clause_type, 0) + 1
        
        findings.append(f"合同包含 {len(clauses)} 个条款")
        
        for clause_type, count in clause_counts.items():
            if count > 0:
                findings.append(f"包含 {count} 个{clause_type}相关条款")
        
        if risks:
            findings.append(f"发现 {len(risks)} 个潜在风险点")
        
        return findings[:5]

    def _identify_high_risk_items(
        self,
        clauses: List[ContractClause],
        risks: List[RiskAssessment]
    ) -> List[str]:
        """识别高风险项目"""
        high_risk_items = []
        
        high_risk_clauses = [c for c in clauses if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        for clause in high_risk_clauses:
            high_risk_items.append(f"{clause.title}: {clause.risk_description}")
        
        critical_risks = [r for r in risks if r.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        for risk in critical_risks:
            high_risk_items.append(f"{risk.risk_type}: {risk.description}")
        
        return high_risk_items[:5]

    def _generate_recommendations(
        self,
        clauses: List[ContractClause],
        risks: List[RiskAssessment],
        overall_risk: RiskLevel
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if overall_risk in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            recommendations.append("建议聘请专业律师进行法律审核")
            recommendations.append("建议与对方协商修改不利条款")
        
        if len(clauses) < 10:
            recommendations.append("合同条款可能不够完整，建议补充")
        
        missing_types = self._find_missing_clause_types(clauses)
        if missing_types:
            recommendations.append(f"建议补充以下条款: {', '.join(missing_types)}")
        
        if not recommendations:
            recommendations.append("合同整体风险可控，但仍需注意执行细节")
        
        return recommendations

    def _find_missing_clause_types(
        self,
        clauses: List[ContractClause]
    ) -> List[str]:
        """查找缺失的条款类型"""
        all_types = set(c.clause_type for c in clauses)
        important_types = {
            ClauseType.PAYMENT,
            ClauseType.DELIVERY,
            ClauseType.LIABILITY,
            ClauseType.TERMINATION
        }
        missing = important_types - all_types
        return [t.value for t in missing]

    def _generate_summary(
        self,
        contract_name: str,
        clause_count: int,
        risk_count: int,
        risk_level: RiskLevel
    ) -> str:
        """生成摘要"""
        risk_desc = {
            RiskLevel.LOW: "低风险",
            RiskLevel.MEDIUM: "中等风险",
            RiskLevel.HIGH: "高风险",
            RiskLevel.CRITICAL: "极高风险"
        }
        
        return (
            f"合同「{contract_name}」分析完成。"
            f"共识别 {clause_count} 个条款，"
            f"发现 {risk_count} 个风险点。"
            f"整体风险评估为{risk_desc[risk_level]}，"
            f"建议关注高风险条款。"
        )

    async def compare_contracts(
        self,
        request: ContractComparisonRequest
    ) -> Dict[str, Any]:
        """
        对比合同
        
        Args:
            request: 对比请求
            
        Returns:
            Dict: 对比结果
        """
        comparison_id = str(uuid.uuid4())
        
        logger.info(f"⚖️ 开始合同对比: {comparison_id}")
        
        try:
            contract1_content = request.contract1_content or "合同1内容"
            contract2_content = request.contract2_content or "合同2内容"
            
            clauses1 = self.clause_extractor.extract_clauses(contract1_content)
            clauses2 = self.clause_extractor.extract_clauses(contract2_content)
            
            clause_comparisons = []
            
            all_types = set(c.clause_type for c in clauses1) | set(c.clause_type for c in clauses2)
            
            for clause_type in all_types:
                c1 = next((c for c in clauses1 if c.clause_type == clause_type), None)
                c2 = next((c for c in clauses2 if c.clause_type == clause_type), None)
                
                differences = []
                if c1 and c2:
                    if c1.content != c2.content:
                        differences.append("条款内容存在差异")
                    if c1.risk_level != c2.risk_level:
                        differences.append(f"风险级别不同: {c1.risk_level.value} vs {c2.risk_level.value}")
                elif c1:
                    differences.append("仅合同1包含此条款")
                elif c2:
                    differences.append("仅合同2包含此条款")
                
                comparison = ClauseComparison(
                    clause_type=clause_type,
                    your_clause=c1.content[:200] if c1 else None,
                    counterparty_clause=c2.content[:200] if c2 else None,
                    standard_clause="标准条款内容",
                    differences=differences,
                    your_position_strength="中",
                    negotiation_priority="中"
                )
                clause_comparisons.append(comparison)
            
            key_differences = self._identify_key_differences(
                clauses1,
                clauses2,
                clause_comparisons
            )
            
            response = ContractComparisonResponse(
                comparison_id=comparison_id,
                contract1_name="合同1",
                contract2_name="合同2",
                clause_comparisons=clause_comparisons,
                key_differences=key_differences,
                advantage_summary="各合同在不同方面各有优势",
                risk_summary="需根据具体情况评估",
                negotiation_points=[
                    "关注付款条件的差异",
                    "评估违约责任的平衡性",
                    "检查终止条款的公平性"
                ],
                generated_at=datetime.now()
            )
            
            return response.model_dump()
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 合同对比数据错误: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=str(e))
        except (OSError, IOError) as e:
            logger.error(f"❌ 合同对比IO错误: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"❌ 合同对比失败: {e}", exc_info=True)
            raise

    def _identify_key_differences(
        self,
        clauses1: List[ContractClause],
        clauses2: List[ContractClause],
        comparisons: List[ClauseComparison]
    ) -> List[str]:
        """识别关键差异"""
        differences = []
        
        high_risk1 = [c for c in clauses1 if c.risk_level == RiskLevel.HIGH]
        high_risk2 = [c for c in clauses2 if c.risk_level == RiskLevel.HIGH]
        
        if len(high_risk1) != len(high_risk2):
            differences.append(f"高风险条款数量不同: 合同1有{len(high_risk1)}个，合同2有{len(high_risk2)}个")
        
        payment1 = next((c for c in clauses1 if c.clause_type == ClauseType.PAYMENT), None)
        payment2 = next((c for c in clauses2 if c.clause_type == ClauseType.PAYMENT), None)
        
        if payment1 and payment2:
            differences.append("付款条款存在差异")
        
        if not differences:
            differences.append("两个合同在主要条款上差异不大")

        return differences

    async def get_analysis_history(
        self,
        user_id: str,
        tenant_id: str,
        page: int = 1,
        page_size: int = 10,
        contract_type: Optional[str] = None,
        risk_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取合同审核历史记录

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量
            contract_type: 合同类型过滤
            risk_level: 风险级别过滤

        Returns:
            包含历史记录列表和总数的字典
        """
        try:
            logger.info(f"📋 获取合同审核历史: user={user_id}, page={page}, page_size={page_size}")

            from app.db.session import AsyncSessionLocal
            from app.models.contract_review import ContractReviewReport
            from sqlalchemy import select, func, desc

            async with AsyncSessionLocal() as db:
                offset = (page - 1) * page_size

                base_query = ContractReviewReport.tenant_id == tenant_id
                if contract_type:
                    base_query = base_query & (ContractReviewReport.contract_type == contract_type)

                count_stmt = select(func.count(ContractReviewReport.id)).where(base_query)
                count_result = await db.execute(count_stmt)
                total = count_result.scalar() or 0

                stmt = (
                    select(ContractReviewReport)
                    .where(base_query)
                    .order_by(desc(ContractReviewReport.created_at))
                    .offset(offset)
                    .limit(page_size)
                )
                result = await db.execute(stmt)
                reviews = result.scalars().all()

                items = []
                for review in reviews:
                    risk_level_val = risk_level
                    if review.overall_risk_level:
                        risk_level_val = review.overall_risk_level.value
                    items.append({
                        "id": str(review.id),
                        "contract_name": review.contract_name or "未知合同",
                        "contract_type": review.contract_type.value if review.contract_type else "other",
                        "risk_level": risk_level_val or "medium",
                        "overall_risk_score": (review.overall_risk_score or 0) * 100 if review.overall_risk_score else 50,
                        "clause_count": 0,
                        "risk_count": 0,
                        "status": review.review_status.value if review.review_status else "pending",
                        "created_at": review.created_at.isoformat() if review.created_at else None
                    })

                return {
                    "analyses": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }

        except Exception as e:
            logger.error(f"❌ 获取合同审核历史失败: {e}", exc_info=True)
            return {"analyses": [], "total": 0, "page": page, "page_size": page_size}
