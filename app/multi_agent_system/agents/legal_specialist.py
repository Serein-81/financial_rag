"""
法务审查智能体 (Legal Specialist Agent)
专注于合同法、公司法、劳动法审查
"""

from typing import List, Dict, Any, Optional
import uuid

from .base_specialist import BaseSpecialistAgent
from ..state import Finding, RiskLevel
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager


class LegalSpecialist(BaseSpecialistAgent):
    """
    法务审查智能体
    
    专业领域：
    1. 合同审查
    2. 公司法合规
    3. 劳动法合规
    4. 知识产权保护
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        max_iterations: int = 10,
        timeout: float = 300.0
    ):
        """初始化法务审查智能体"""
        system_prompt = self._build_system_prompt()
        
        super().__init__(
            specialty="legal",
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )
        
        print("⚖️ [法务智能体] 初始化完成")
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一位资深的法务审查专家，精通合同法、公司法、劳动法等法律法规。

你的职责是：
1. 审查合同条款的合法性和完整性
2. 检查公司运营的法律合规性
3. 审核劳动合同和用工关系
4. 识别法律风险和合规问题
5. 提供法律建议和风险防范措施

审查原则：
- 严格遵循法律法规
- 关注合同条款的完整性和明确性
- 识别潜在的法律风险
- 保护企业合法权益
- 提供可操作的法律建议

请以专业、严谨的态度进行审查。"""
    
    async def run(self, user_input: str, **kwargs) -> str:
        """实现基类的抽象方法"""
        return f"法务智能体处理: {user_input}"
    
    async def stream_run(self, user_input: str, **kwargs):
        """实现基类的抽象方法"""
        yield f"法务智能体流式处理: {user_input}"
    
    async def audit(
        self,
        state: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行法务审查
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表
        """
        print("⚖️ [法务智能体] 开始审查")
        
        self.current_state = state
        findings = []
        
        try:
            # 1. 合同审查
            contract_findings = await self._check_contract(documents)
            findings.extend(contract_findings)
            
            # 2. 公司法合规检查
            compliance_findings = await self._check_compliance(documents)
            findings.extend(compliance_findings)
            
            # 3. 劳动法审查
            labor_findings = await self._check_labor_law(documents)
            findings.extend(labor_findings)
            
            # 4. 知识产权检查
            ip_findings = await self._check_intellectual_property(documents)
            findings.extend(ip_findings)
            
            print(f"⚖️ [法务智能体] 审查完成，发现 {len(findings)} 个问题")
            
        except Exception as e:
            print(f"❌ [法务智能体] 审查失败: {e}")
            error_finding = self.create_finding(
                category="审查错误",
                description=f"法务审查过程中发生错误: {str(e)}",
                evidence=[],
                confidence=1.0
            )
            findings.append(error_finding)
        
        return findings
    
    async def _check_contract(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查合同
        
        检查项：
        1. 合同主体资格
        2. 合同必备条款
        3. 权利义务明确性
        4. 违约责任条款
        5. 争议解决条款
        """
        findings = []
        
        # 查找合同相关文档
        contract_docs = [
            doc for doc in documents
            if '合同' in doc.get('type', '') or '协议' in doc.get('type', '')
            or '合同' in doc.get('content', '')[:100] or '协议' in doc.get('content', '')[:100]
        ]
        
        if not contract_docs:
            # 如果有法务文档但没有合同，提示
            if any('法务' in doc.get('type', '') or '法律' in doc.get('type', '') for doc in documents):
                finding = self.create_finding(
                    category="合同审查",
                    description="未找到合同文档，无法进行合同审查",
                    evidence=["文档列表中缺少合同或协议"],
                    recommendations=["如需合同审查，请提供相关合同文档"],
                    confidence=0.8
                )
                findings.append(finding)
            return findings
        
        for doc in contract_docs:
            doc_content = doc.get('content', '')[:3000]  # 合同可能较长
            
            prompt = f"""请审查以下合同，重点检查：

1. 合同主体：双方主体资格是否明确、是否具备签约能力
2. 必备条款：是否包含标的、数量、质量、价款、履行期限、地点和方式、违约责任等
3. 权利义务：双方权利义务是否明确、是否公平合理
4. 违约责任：违约责任条款是否完整、是否具有可操作性
5. 争议解决：是否约定了争议解决方式（仲裁或诉讼）
6. 法律风险：是否存在违反法律法规的条款

合同内容：
{doc_content}

请指出发现的问题和法律风险。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                # 检查关键风险词
                if "主体" in response and ("不明确" in response or "缺失" in response):
                    finding = self.create_finding(
                        category="合同主体",
                        description="合同主体信息可能不完整或不明确",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核实并完善合同主体信息"],
                        legal_basis=["《中华人民共和国合同法》"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "必备条款" in response and ("缺少" in response or "不完整" in response):
                    finding = self.create_finding(
                        category="合同条款",
                        description="合同可能缺少必备条款",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请补充合同必备条款"],
                        legal_basis=["《合同法》第12条"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "违约责任" in response and ("不明确" in response or "缺失" in response):
                    finding = self.create_finding(
                        category="违约责任",
                        description="违约责任条款可能不完整或不明确",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请明确约定违约责任"],
                        legal_basis=["《合同法》第107条"],
                        confidence=0.7
                    )
                    findings.append(finding)
                
                if "不公平" in response or "显失公平" in response:
                    finding = self.create_finding(
                        category="合同公平性",
                        description="合同条款可能存在显失公平的情况",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请重新审视合同条款的公平性"],
                        legal_basis=["《合同法》第54条"],
                        confidence=0.7
                    )
                    findings.append(finding)
                
                if "违反" in response and "法律" in response:
                    finding = self.create_finding(
                        category="合同合法性",
                        description="合同可能存在违反法律法规的条款",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请修改或删除违法条款"],
                        legal_basis=["《合同法》第52条"],
                        confidence=0.8
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [法务智能体] 合同分析失败: {e}")
        
        return findings
    
    async def _check_compliance(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        公司法合规检查
        
        检查项：
        1. 公司章程合规性
        2. 股东会/董事会决议
        3. 公司治理结构
        4. 信息披露义务
        """
        findings = []
        
        # 查找公司治理相关文档
        compliance_docs = [
            doc for doc in documents
            if any(keyword in doc.get('type', '') or keyword in doc.get('content', '')[:200]
                   for keyword in ['章程', '决议', '股东', '董事', '治理'])
        ]
        
        if not compliance_docs:
            return findings
        
        for doc in compliance_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下公司治理文档，重点检查：

1. 合规性：是否符合《公司法》的规定
2. 完整性：必要的条款和程序是否完整
3. 有效性：决议程序是否合法有效
4. 风险点：是否存在法律风险

文档内容：
{doc_content}

请指出发现的问题。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                if "不符合" in response or "违反" in response:
                    finding = self.create_finding(
                        category="公司法合规",
                        description="公司治理文档可能存在合规问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核查并修正不合规内容"],
                        legal_basis=["《中华人民共和国公司法》"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [法务智能体] 公司法合规分析失败: {e}")
        
        return findings
    
    async def _check_labor_law(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        劳动法审查
        
        检查项：
        1. 劳动合同必备条款
        2. 工作时间和休息休假
        3. 劳动报酬和社会保险
        4. 劳动保护和职业危害防护
        """
        findings = []
        
        # 查找劳动合同相关文档
        labor_docs = [
            doc for doc in documents
            if any(keyword in doc.get('type', '') or keyword in doc.get('content', '')[:200]
                   for keyword in ['劳动合同', '用工', '员工', '工资', '社保'])
        ]
        
        if not labor_docs:
            return findings
        
        for doc in labor_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下劳动用工文档，重点检查：

1. 劳动合同：是否包含必备条款（工作内容、地点、时间、报酬、社保等）
2. 工作时间：是否符合法定工作时间和加班规定
3. 劳动报酬：工资支付是否符合规定
4. 社会保险：是否依法缴纳社会保险
5. 劳动保护：是否提供必要的劳动保护

文档内容：
{doc_content}

请指出发现的问题。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                if "必备条款" in response and ("缺少" in response or "不完整" in response):
                    finding = self.create_finding(
                        category="劳动合同",
                        description="劳动合同可能缺少必备条款",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请补充劳动合同必备条款"],
                        legal_basis=["《劳动合同法》第17条"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "社保" in response and ("未缴" in response or "不符合" in response):
                    finding = self.create_finding(
                        category="社会保险",
                        description="社会保险缴纳可能存在问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请依法为员工缴纳社会保险"],
                        legal_basis=["《社会保险法》"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "工作时间" in response and ("超时" in response or "违反" in response):
                    finding = self.create_finding(
                        category="工作时间",
                        description="工作时间安排可能不符合法律规定",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请调整工作时间安排，确保符合法律规定"],
                        legal_basis=["《劳动法》第36条、第41条"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [法务智能体] 劳动法分析失败: {e}")
        
        return findings
    
    async def _check_intellectual_property(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        知识产权检查
        
        检查项：
        1. 商标使用合规性
        2. 专利权保护
        3. 著作权保护
        4. 商业秘密保护
        """
        findings = []
        
        # 查找知识产权相关文档
        ip_docs = [
            doc for doc in documents
            if any(keyword in doc.get('type', '') or keyword in doc.get('content', '')[:200]
                   for keyword in ['知识产权', '商标', '专利', '著作权', '版权', '商业秘密'])
        ]
        
        if not ip_docs:
            return findings
        
        for doc in ip_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下知识产权文档，重点检查：

1. 权属：知识产权权属是否明确
2. 授权：使用他人知识产权是否获得授权
3. 保护：是否采取了必要的保护措施
4. 侵权风险：是否存在侵权风险

文档内容：
{doc_content}

请指出发现的问题。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                if "未授权" in response or "侵权" in response:
                    finding = self.create_finding(
                        category="知识产权",
                        description="可能存在知识产权侵权风险",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核实知识产权授权情况，避免侵权"],
                        legal_basis=["《商标法》、《专利法》、《著作权法》"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [法务智能体] 知识产权分析失败: {e}")
        
        return findings
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载法务专业知识库"""
        return [
            {
                "rule_id": "LEG_001",
                "category": "合同法",
                "description": "合同应包含当事人名称、标的、数量、质量、价款、履行期限地点方式、违约责任等必备条款",
                "risk_level": "high",
                "legal_basis": ["《合同法》第12条"]
            },
            {
                "rule_id": "LEG_002",
                "category": "合同法",
                "description": "违反法律、行政法规的强制性规定的合同无效",
                "risk_level": "critical",
                "legal_basis": ["《合同法》第52条"]
            },
            {
                "rule_id": "LEG_003",
                "category": "劳动法",
                "description": "劳动合同应包含工作内容、地点、时间、报酬、社会保险等必备条款",
                "risk_level": "high",
                "legal_basis": ["《劳动合同法》第17条"]
            },
            {
                "rule_id": "LEG_004",
                "category": "劳动法",
                "description": "用人单位应当依法为劳动者缴纳社会保险",
                "risk_level": "high",
                "legal_basis": ["《社会保险法》第4条"]
            },
            {
                "rule_id": "LEG_005",
                "category": "劳动法",
                "description": "国家实行劳动者每日工作时间不超过8小时、平均每周工作时间不超过44小时的工时制度",
                "risk_level": "medium",
                "legal_basis": ["《劳动法》第36条"]
            },
            {
                "rule_id": "LEG_006",
                "category": "知识产权",
                "description": "使用他人注册商标、专利、著作权需获得授权",
                "risk_level": "high",
                "legal_basis": ["《商标法》、《专利法》、《著作权法》"]
            },
            {
                "rule_id": "LEG_007",
                "category": "公司法",
                "description": "公司章程应当载明公司名称、住所、经营范围、注册资本等事项",
                "risk_level": "medium",
                "legal_basis": ["《公司法》第25条"]
            }
        ]
