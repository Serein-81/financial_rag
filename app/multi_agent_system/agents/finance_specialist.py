"""
财务审查智能体 (Finance Specialist Agent)
专注于财务会计、资产负债、现金流审查
"""

from typing import List, Dict, Any, Optional
import uuid

from .base_specialist import BaseSpecialistAgent
from ..state import Finding, RiskLevel
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager


class FinanceSpecialist(BaseSpecialistAgent):
    """
    财务审查智能体
    
    专业领域：
    1. 资产负债表审查
    2. 现金流量表审查
    3. 利润表审查
    4. 财务指标计算
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        max_iterations: int = 10,
        timeout: float = 300.0
    ):
        """初始化财务审查智能体"""
        system_prompt = self._build_system_prompt()
        
        super().__init__(
            specialty="finance",
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )
        
        print("💰 [财务智能体] 初始化完成")
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一位资深的财务审查专家，拥有注册会计师(CPA)资格。

你的职责是：
1. 审查资产负债表的平衡性和合理性
2. 分析现金流量表的真实性和完整性
3. 检查利润表的逻辑一致性
4. 计算关键财务指标并评估财务健康状况
5. 识别财务异常和潜在风险

审查原则：
- 严格遵循会计准则和财务报告标准
- 关注数据的一致性和逻辑性
- 识别异常数据和可疑交易
- 提供具体的证据支持
- 给出专业的改进建议

请以专业、严谨的态度进行审查。"""
    
    async def run(self, user_input: str, **kwargs) -> str:
        """实现基类的抽象方法"""
        return f"财务智能体处理: {user_input}"
    
    async def stream_run(self, user_input: str, **kwargs):
        """实现基类的抽象方法"""
        yield f"财务智能体流式处理: {user_input}"
    
    async def audit(
        self,
        state: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行财务审查
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表
        """
        print("💰 [财务智能体] 开始审查")
        
        self.current_state = state
        findings = []
        
        try:
            # 1. 资产负债表审查
            balance_findings = await self._check_balance_sheet(documents)
            findings.extend(balance_findings)
            
            # 2. 现金流量表审查
            cash_findings = await self._check_cash_flow(documents)
            findings.extend(cash_findings)
            
            # 3. 利润表审查
            profit_findings = await self._check_profit_loss(documents)
            findings.extend(profit_findings)
            
            # 4. 财务指标计算
            ratio_findings = await self._calculate_financial_ratios(documents)
            findings.extend(ratio_findings)
            
            print(f"💰 [财务智能体] 审查完成，发现 {len(findings)} 个问题")
            
        except Exception as e:
            print(f"❌ [财务智能体] 审查失败: {e}")
            # 创建错误发现
            error_finding = self.create_finding(
                category="审查错误",
                description=f"财务审查过程中发生错误: {str(e)}",
                evidence=[],
                confidence=1.0
            )
            findings.append(error_finding)
        
        return findings
    
    async def _check_balance_sheet(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查资产负债表
        
        检查项：
        1. 资产 = 负债 + 所有者权益
        2. 资产项目合理性（无负数资产）
        3. 负债结构合理性
        4. 所有者权益变动合理性
        """
        findings = []
        
        # 查找资产负债表相关文档
        balance_docs = [
            doc for doc in documents
            if '资产负债' in doc.get('type', '') or '资产负债' in doc.get('content', '')[:100]
        ]
        
        if not balance_docs:
            # 未找到资产负债表
            finding = self.create_finding(
                category="资产负债表",
                description="未找到资产负债表文档，无法进行财务审查",
                evidence=["文档列表中缺少资产负债表"],
                recommendations=["请提供完整的资产负债表"],
                confidence=1.0
            )
            findings.append(finding)
            return findings
        
        # 使用 LLM 分析资产负债表
        for doc in balance_docs:
            doc_content = doc.get('content', '')[:2000]  # 限制长度
            
            prompt = f"""请审查以下资产负债表，重点检查：

1. 资产负债平衡性：资产总额 = 负债总额 + 所有者权益总额
2. 资产项目合理性：是否存在负数资产、异常大额资产
3. 负债结构：流动负债与非流动负债比例是否合理
4. 所有者权益：是否存在异常变动

资产负债表内容：
{doc_content}

请以JSON格式返回发现的问题，格式如下：
{{
    "issues": [
        {{
            "category": "问题类别",
            "description": "问题描述",
            "evidence": ["证据1", "证据2"],
            "risk_level": "high/medium/low",
            "recommendations": ["建议1", "建议2"]
        }}
    ]
}}
"""
            
            try:
                # 调用 LLM
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1  # 低温度保证准确性
                )
                
                # 解析响应（简化处理）
                # TODO: 实现更智能的JSON解析
                if "资产负债不平衡" in response or "不平衡" in response:
                    finding = self.create_finding(
                        category="资产负债表平衡性",
                        description="资产负债表可能存在不平衡问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核对资产、负债、所有者权益的计算"],
                        confidence=0.8
                    )
                    findings.append(finding)
                
                if "负数" in response or "异常" in response:
                    finding = self.create_finding(
                        category="资产项目异常",
                        description="发现异常的资产项目数据",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请检查资产项目的数据准确性"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [财务智能体] 资产负债表分析失败: {e}")
        
        return findings
    
    async def _check_cash_flow(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查现金流量表
        
        检查项：
        1. 现金流入流出合理性
        2. 经营活动现金流与利润的匹配性
        3. 投资活动现金流合理性
        4. 筹资活动现金流合理性
        """
        findings = []
        
        # 查找现金流量表相关文档
        cash_docs = [
            doc for doc in documents
            if '现金流' in doc.get('type', '') or '现金流' in doc.get('content', '')[:100]
        ]
        
        if not cash_docs:
            return findings  # 现金流量表非必需
        
        for doc in cash_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下现金流量表，重点检查：

1. 经营活动现金流：是否与利润表匹配
2. 投资活动现金流：大额投资是否合理
3. 筹资活动现金流：融资活动是否正常
4. 现金流平衡：期初+流入-流出=期末

现金流量表内容：
{doc_content}

请指出发现的问题和风险。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                # 简化处理：检查关键词
                if "异常" in response or "不匹配" in response or "风险" in response:
                    finding = self.create_finding(
                        category="现金流量表",
                        description="现金流量表存在潜在问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核对现金流数据的准确性"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [财务智能体] 现金流量表分析失败: {e}")
        
        return findings
    
    async def _check_profit_loss(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        审查利润表
        
        检查项：
        1. 收入确认合理性
        2. 成本费用匹配性
        3. 利润计算准确性
        4. 异常损益项目
        """
        findings = []
        
        # 查找利润表相关文档
        profit_docs = [
            doc for doc in documents
            if '利润' in doc.get('type', '') or '损益' in doc.get('type', '')
            or '利润' in doc.get('content', '')[:100]
        ]
        
        if not profit_docs:
            return findings
        
        for doc in profit_docs:
            doc_content = doc.get('content', '')[:2000]
            
            prompt = f"""请审查以下利润表，重点检查：

1. 收入确认：是否符合会计准则
2. 成本费用：是否与收入匹配
3. 利润计算：营业利润、利润总额、净利润计算是否正确
4. 异常项目：是否存在异常的损益项目

利润表内容：
{doc_content}

请指出发现的问题。"""
            
            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                if "异常" in response or "错误" in response or "不合理" in response:
                    finding = self.create_finding(
                        category="利润表",
                        description="利润表存在需要关注的问题",
                        evidence=[f"文档ID: {doc.get('id')}", "LLM分析结果"],
                        recommendations=["请核对利润表的计算和数据"],
                        confidence=0.7
                    )
                    findings.append(finding)
                    
            except Exception as e:
                print(f"⚠️ [财务智能体] 利润表分析失败: {e}")
        
        return findings
    
    async def _calculate_financial_ratios(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        计算财务指标
        
        指标包括：
        1. 资产负债率 = 负债总额 / 资产总额
        2. 流动比率 = 流动资产 / 流动负债
        3. 速动比率 = (流动资产 - 存货) / 流动负债
        4. 净利润率 = 净利润 / 营业收入
        """
        findings = []
        
        # TODO: 实现财务指标提取和计算
        # 这里需要更复杂的文档解析和数据提取
        # 暂时返回空列表
        
        return findings
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载财务专业知识库"""
        return [
            {
                "rule_id": "FIN_001",
                "category": "资产负债",
                "description": "资产负债表必须平衡：资产 = 负债 + 所有者权益",
                "risk_level": "critical",
                "legal_basis": ["企业会计准则"]
            },
            {
                "rule_id": "FIN_002",
                "category": "资产项目",
                "description": "资产项目不得为负数",
                "risk_level": "high",
                "legal_basis": ["企业会计准则"]
            },
            {
                "rule_id": "FIN_003",
                "category": "现金流",
                "description": "经营活动现金流应与净利润基本匹配",
                "risk_level": "medium",
                "legal_basis": ["企业会计准则"]
            },
            {
                "rule_id": "FIN_004",
                "category": "财务指标",
                "description": "资产负债率不宜超过70%",
                "risk_level": "medium",
                "legal_basis": ["财务管理最佳实践"]
            },
            {
                "rule_id": "FIN_005",
                "category": "财务指标",
                "description": "流动比率应大于1",
                "risk_level": "medium",
                "legal_basis": ["财务管理最佳实践"]
            }
        ]
