"""
税务审查智能体 (Tax Specialist Agent)
专注于增值税、企业所得税、个人所得税审查
"""

from typing import List, Dict, Any, Optional
import uuid

from .base_specialist import BaseSpecialistAgent
from ..state import Finding, RiskLevel
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager


class TaxSpecialist(BaseSpecialistAgent):
    """
    税务审查智能体
    
    专业领域：
    1. 增值税审查
    2. 企业所得税审查
    3. 个人所得税审查
    4. 税务合规性检查
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        max_iterations: int = 10,
        timeout: float = 300.0
    ):
        """初始化税务审查智能体"""
        system_prompt = self._build_system_prompt()
        
        super().__init__(
            specialty="tax",
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )
        
        print("📊 [税务智能体] 初始化完成")
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一位资深的税务审查专家，精通中国税法和税务实务。

你的职责是：
1. 审查增值税计算和申报的准确性
2. 检查企业所得税的合规性
3. 审核个人所得税的代扣代缴
4. 识别税务风险和优化机会
5. 确保税务申报的完整性和及时性

审查原则：
- 严格遵循税法法规和税务政策
- 关注税率适用的准确性
- 识别税务筹划空间
- 防范税务风险
- 提供合规建议

请以专业、严谨的态度进行审查。"""
    
    async def run(self, user_input: str, **kwargs) -> str:
        """实现基类的抽象方法"""
        return f"税务智能体处理: {user_input}"
    
    async def stream_run(self, user_input: str, **kwargs):
        """实现基类的抽象方法"""
        yield f"税务智能体流式处理: {user_input}"
    
    async def audit(
        self,
        state: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行税务审查
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表
        """
        print("📊 [税务智能体] 开始审查")
        
        self.current_state = state
        findings = []
        
        try:
            # 1. 增值税审查
            vat_findings = await self._check_vat(documents)
            findings.extend(vat_findings)
            
            # 2. 企业所得税审查
            corporate_findings = await self._check_corporate_tax(documents)
            findings.extend(corporate_findings)
            
            # 3. 个人所得税审查
            individual_findings = await self._check_individual_tax(documents)
            findings.extend(individual_findings)
            
            # 4. 税务合规性检查
            compliance_findings = await self._check_tax_compliance(documents)
            findings.extend(compliance_findings)
            
            print(f"📊 [税务智能体] 审查完成，发现 {len(findings)} 个问题")
            
        except Exception as e:
            print(f"❌ [税务智能体] 审查失败: {e}")
            error_finding = self.create_finding(
                category="审查错误",
                description=f"税务审查过程中发生错误: {str(e)}",
                evidence=[],
                confidence=1.0
            )
            findings.append(error_finding)
        
        return findings
    
    async def _check_vat(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查增值税
        
        检查项：
        1. 增值税税率适用正确性
        2. 进项税额抵扣合规性
        3. 销项税额计算准确性
        4. 增值税发票管理
        """
        findings = []
        
        # 查找增值税相关文档
        vat_docs = [
            doc for doc in documents
            if '增值税' in doc.get('type', '') or '增值税' in doc.get('content', '')[:200]
            or '发票' in doc.get('type', '') or 'VAT' in doc.get('type', '').upper()
        ]
        
        if not vat_docs:
            # 如果有财务文档但没有增值税文档，提示可能缺失
            if any('财务' in doc.get('type', '') or '税务' in doc.get('type', '') for doc in documents):
                finding = self.create_finding(
                    category="增值税",
                    description="未找到增值税相关文档，可能影响税务审查完整性",
                    evidence=["文档列表中缺少增值税申报表或发票汇总"],
                    recommendations=["建议提供增值税申报表和发票明细"],
                    confidence=0.8
                )
                findings.append(finding)
            return findings
        
        for doc in vat_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下增值税相关文档，重点检查：

1. 税率适用：是否使用了正确的增值税税率（13%、9%、6%等）
2. 进项税额：进项税额抵扣是否符合规定
3. 销项税额：销项税额计算是否准确
4. 发票管理：发票开具和取得是否合规

增值税文档内容：
{doc_content}

请指出发现的问题和风险。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                # 检查关键风险词
                if "税率错误" in response or "税率不正确" in response:
                    finding = self.create_finding(
                        category="增值税税率",
                        description="增值税税率适用可能存在问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核对增值税税率的适用"],
                        legal_basis=["《中华人民共和国增值税暂行条例》"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "进项" in response and ("不合规" in response or "不符合" in response):
                    finding = self.create_finding(
                        category="增值税进项抵扣",
                        description="增值税进项税额抵扣可能存在合规问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请检查进项税额抵扣的合规性"],
                        legal_basis=["《增值税暂行条例实施细则》"],
                        confidence=0.7
                    )
                    findings.append(finding)
                
                if "发票" in response and ("异常" in response or "问题" in response):
                    finding = self.create_finding(
                        category="增值税发票",
                        description="增值税发票管理存在潜在问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核查发票的真实性和合规性"],
                        legal_basis=["《发票管理办法》"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [税务智能体] 增值税分析失败: {e}")
        
        return findings
    
    async def _check_corporate_tax(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查企业所得税
        
        检查项：
        1. 应纳税所得额计算
        2. 税率适用（25%、20%、15%等）
        3. 税前扣除项目合规性
        4. 税收优惠政策适用
        """
        findings = []
        
        # 查找企业所得税相关文档
        corporate_docs = [
            doc for doc in documents
            if '企业所得税' in doc.get('type', '') or '所得税' in doc.get('content', '')[:200]
        ]
        
        if not corporate_docs:
            return findings
        
        for doc in corporate_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下企业所得税文档，重点检查：

1. 应纳税所得额：计算是否准确
2. 税率适用：是否使用了正确的税率
3. 税前扣除：扣除项目是否符合规定
4. 税收优惠：优惠政策适用是否合规

企业所得税文档内容：
{doc_content}

请指出发现的问题。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                if "计算错误" in response or "不准确" in response:
                    finding = self.create_finding(
                        category="企业所得税计算",
                        description="企业所得税计算可能存在问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核对应纳税所得额的计算"],
                        legal_basis=["《中华人民共和国企业所得税法》"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "扣除" in response and ("不合规" in response or "超标" in response):
                    finding = self.create_finding(
                        category="企业所得税扣除",
                        description="税前扣除项目可能存在合规问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请检查税前扣除项目的合规性"],
                        legal_basis=["《企业所得税法实施条例》"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [税务智能体] 企业所得税分析失败: {e}")
        
        return findings
    
    async def _check_individual_tax(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查个人所得税
        
        检查项：
        1. 工资薪金个税代扣代缴
        2. 专项附加扣除合规性
        3. 个税申报完整性
        4. 个税缴纳及时性
        """
        findings = []
        
        # 查找个人所得税相关文档
        individual_docs = [
            doc for doc in documents
            if '个人所得税' in doc.get('type', '') or '个税' in doc.get('content', '')[:200]
            or '工资' in doc.get('type', '')
        ]
        
        if not individual_docs:
            return findings
        
        for doc in individual_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下个人所得税文档，重点检查：

1. 代扣代缴：是否正确履行代扣代缴义务
2. 专项扣除：专项附加扣除是否合规
3. 申报完整性：个税申报是否完整
4. 缴纳及时性：个税是否按时缴纳

个人所得税文档内容：
{doc_content}

请指出发现的问题。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                if "未代扣" in response or "漏缴" in response:
                    finding = self.create_finding(
                        category="个人所得税代扣代缴",
                        description="个人所得税代扣代缴可能存在问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核查个税代扣代缴情况"],
                        legal_basis=["《中华人民共和国个人所得税法》"],
                        confidence=0.8
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [税务智能体] 个人所得税分析失败: {e}")
        
        return findings
    
    async def _check_tax_compliance(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        税务合规性检查
        
        检查项：
        1. 税务申报及时性
        2. 税款缴纳完整性
        3. 税务档案管理
        4. 税务风险防范
        """
        findings = []
        
        # 综合分析所有税务文档
        tax_docs = [
            doc for doc in documents
            if any(keyword in doc.get('type', '') or keyword in doc.get('content', '')[:200]
                   for keyword in ['税', '申报', '缴纳', '发票'])
        ]
        
        if len(tax_docs) < 2:
            finding = self.create_finding(
                category="税务合规",
                description="税务文档不完整，可能影响合规性审查",
                evidence=["税务相关文档数量较少"],
                recommendations=["建议提供完整的税务申报和缴纳凭证"],
                confidence=0.6
            )
            findings.append(finding)
        
        return findings
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载税务专业知识库"""
        return [
            {
                "rule_id": "TAX_001",
                "category": "增值税",
                "description": "增值税一般纳税人适用税率：13%（货物）、9%（交通运输）、6%（现代服务）",
                "risk_level": "high",
                "legal_basis": ["《增值税暂行条例》"]
            },
            {
                "rule_id": "TAX_002",
                "category": "增值税",
                "description": "进项税额抵扣需取得合法有效的增值税专用发票",
                "risk_level": "high",
                "legal_basis": ["《增值税暂行条例》"]
            },
            {
                "rule_id": "TAX_003",
                "category": "企业所得税",
                "description": "企业所得税基本税率为25%，小型微利企业可享受优惠税率",
                "risk_level": "medium",
                "legal_basis": ["《企业所得税法》"]
            },
            {
                "rule_id": "TAX_004",
                "category": "企业所得税",
                "description": "业务招待费按发生额的60%扣除，但不得超过当年销售收入的5‰",
                "risk_level": "medium",
                "legal_basis": ["《企业所得税法实施条例》"]
            },
            {
                "rule_id": "TAX_005",
                "category": "个人所得税",
                "description": "工资薪金所得适用3%-45%的超额累进税率",
                "risk_level": "medium",
                "legal_basis": ["《个人所得税法》"]
            },
            {
                "rule_id": "TAX_006",
                "category": "税务申报",
                "description": "增值税一般纳税人应按月申报，小规模纳税人可按季申报",
                "risk_level": "medium",
                "legal_basis": ["《税收征收管理法》"]
            }
        ]
