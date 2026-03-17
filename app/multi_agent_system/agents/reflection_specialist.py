"""
Reflection Specialist - 反思专家智能体
用于多智能体系统的质量检查和冲突检测
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_specialist import BaseSpecialistAgent
from ..state import AuditState, Finding, Conflict
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager


class ReflectionSpecialist(BaseSpecialistAgent):
    """
    反思专家 - 质量检查和冲突检测
    
    职责：
    1. 检测跨领域冲突
    2. 验证证据溯源
    3. 评估置信度
    4. 决定是否需要重做
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        **kwargs
    ):
        super().__init__(
            specialty="reflection",
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            **kwargs
        )
        
        # 保存LLM适配器引用用于深度分析
        self.llm_adapter = llm_adapter
        
        print("🤔 [反思专家] 初始化完成")
    
    async def audit(
        self,
        state: AuditState,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行反思检查
        
        Args:
            state: 全局状态
            documents: 文档列表（未使用，保持接口一致）
            
        Returns:
            反思发现列表
        """
        print("🤔 [反思专家] 开始反思检查")
        
        findings = []
        
        # 1. 检测跨领域冲突
        conflicts = await self.detect_cross_domain_conflicts(state)
        state['conflicts'] = [c.to_dict() for c in conflicts]
        
        # 2. 验证证据溯源
        evidence_gaps = await self.check_evidence_grounding(state)
        state['evidence_gaps'] = evidence_gaps
        
        # 3. 评估置信度
        confidence_scores = await self.evaluate_confidence(state)
        state['confidence_scores'] = confidence_scores
        
        # 4. 生成反思总结
        summary = self._generate_reflection_summary(conflicts, evidence_gaps, confidence_scores)
        state['reflection_summary'] = summary
        
        # 5. 决定是否需要重做
        state['need_rework'] = len(conflicts) > 0 or len(evidence_gaps) > 0
        if state['need_rework']:
            state['rework_agents'] = self._identify_rework_agents(conflicts, evidence_gaps)
            state['rework_reason'] = f"发现 {len(conflicts)} 个冲突，{len(evidence_gaps)} 个证据缺口"
        
        print(f"🤔 [反思专家] 检测到 {len(conflicts)} 个冲突，{len(evidence_gaps)} 个证据缺口")
        print(f"🤔 [反思专家] 需要重做: {state['need_rework']}")
        
        return findings
    
    async def run(self, task: str, context: Optional[Dict] = None) -> str:
        """
        实现 BaseAgent 的 run 方法
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            执行结果
        """
        # 反思专家主要通过 audit 方法工作
        # 这里提供一个简单的实现以满足接口要求
        return "反思检查完成"
    
    async def stream_run(self, task: str, context: Optional[Dict] = None):
        """
        实现 BaseAgent 的 stream_run 方法
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Yields:
            执行过程中的消息
        """
        # 反思专家主要通过 audit 方法工作
        # 这里提供一个简单的实现以满足接口要求
        yield "开始反思检查..."
        yield "反思检查完成"
    
    async def detect_cross_domain_conflicts(
        self,
        state: AuditState
    ) -> List[Conflict]:
        """
        检测跨领域冲突
        
        Args:
            state: 全局状态
            
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 获取各领域的发现
        finance_findings = [Finding(**f) for f in state.get('finance_findings', [])]
        tax_findings = [Finding(**f) for f in state.get('tax_findings', [])]
        legal_findings = [Finding(**f) for f in state.get('legal_findings', [])]
        
        print(f"🤔 [反思专家] 检测冲突 - 财务:{len(finance_findings)}, 税务:{len(tax_findings)}, 法务:{len(legal_findings)}")
        
        # 1. 财务 vs 法务冲突检测
        conflicts.extend(
            self._detect_finance_legal_conflicts(finance_findings, legal_findings)
        )
        
        # 2. 财务 vs 税务冲突检测
        conflicts.extend(
            self._detect_finance_tax_conflicts(finance_findings, tax_findings)
        )
        
        # 3. 法务 vs 税务冲突检测
        conflicts.extend(
            self._detect_legal_tax_conflicts(legal_findings, tax_findings)
        )
        
        # 4. 使用LLM进行深度冲突分析
        if finance_findings or tax_findings or legal_findings:
            llm_conflicts = await self._llm_conflict_detection(
                finance_findings, tax_findings, legal_findings
            )
            conflicts.extend(llm_conflicts)
        
        print(f"🤔 [反思专家] 共检测到 {len(conflicts)} 个冲突")
        return conflicts
    
    def _detect_finance_legal_conflicts(
        self,
        finance_findings: List[Finding],
        legal_findings: List[Finding]
    ) -> List[Conflict]:
        """检测财务与法务冲突"""
        conflicts = []
        
        # 冲突模式1：营业收入 vs 借款
        income_keywords = ['营业收入', '主营业务收入', '收入', '销售收入']
        loan_keywords = ['借款', '贷款', '融资', '对赌', '投资款']
        
        for f_finding in finance_findings:
            if any(kw in f_finding.description for kw in income_keywords):
                for l_finding in legal_findings:
                    if any(kw in l_finding.description for kw in loan_keywords):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[f_finding.id, l_finding.id],
                            conflict_type="classification_conflict",
                            description=f"财务认为是营业收入，法务认为是借款性质",
                            severity="high",
                            resolution_suggestion="需要重新审查资金性质和合同条款，确定正确的会计分类",
                            agent1="finance",
                            agent2="legal",
                            finding1=f_finding.to_dict(),
                            finding2=l_finding.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        # 冲突模式2：资产确认 vs 合同条款
        asset_keywords = ['固定资产', '无形资产', '资产确认', '资本化']
        contract_keywords = ['租赁', '使用权', '临时', '短期']
        
        for f_finding in finance_findings:
            if any(kw in f_finding.description for kw in asset_keywords):
                for l_finding in legal_findings:
                    if any(kw in l_finding.description for kw in contract_keywords):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[f_finding.id, l_finding.id],
                            conflict_type="asset_recognition_conflict",
                            description=f"财务确认为资产，但法务合同条款显示为临时性质",
                            severity="medium",
                            resolution_suggestion="核实合同条款，确定资产确认的正确性",
                            agent1="finance",
                            agent2="legal",
                            finding1=f_finding.to_dict(),
                            finding2=l_finding.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        return conflicts
    
    def _detect_finance_tax_conflicts(
        self,
        finance_findings: List[Finding],
        tax_findings: List[Finding]
    ) -> List[Conflict]:
        """检测财务与税务冲突"""
        conflicts = []
        
        # 冲突模式1：收入确认时点差异
        revenue_keywords = ['收入确认', '营业收入', '销售收入']
        tax_timing_keywords = ['纳税义务', '计税时点', '税务确认']
        
        for f_finding in finance_findings:
            if any(kw in f_finding.description for kw in revenue_keywords):
                for t_finding in tax_findings:
                    if any(kw in t_finding.description for kw in tax_timing_keywords):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[f_finding.id, t_finding.id],
                            conflict_type="timing_difference",
                            description=f"财务收入确认与税务计税时点存在差异",
                            severity="medium",
                            resolution_suggestion="核实收入确认政策，确定是否需要纳税调整",
                            agent1="finance",
                            agent2="tax",
                            finding1=f_finding.to_dict(),
                            finding2=t_finding.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        # 冲突模式2：费用扣除标准差异
        expense_keywords = ['费用', '成本', '扣除']
        deduction_keywords = ['税前扣除', '扣除标准', '限额']
        
        for f_finding in finance_findings:
            if any(kw in f_finding.description for kw in expense_keywords):
                for t_finding in tax_findings:
                    if any(kw in t_finding.description for kw in deduction_keywords):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[f_finding.id, t_finding.id],
                            conflict_type="deduction_conflict",
                            description=f"财务费用确认与税务扣除标准不一致",
                            severity="medium",
                            resolution_suggestion="检查费用扣除的税务合规性，必要时进行纳税调整",
                            agent1="finance",
                            agent2="tax",
                            finding1=f_finding.to_dict(),
                            finding2=t_finding.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        return conflicts
    
    def _detect_legal_tax_conflicts(
        self,
        legal_findings: List[Finding],
        tax_findings: List[Finding]
    ) -> List[Conflict]:
        """检测法务与税务冲突"""
        conflicts = []
        
        # 冲突模式1：合同性质 vs 税务处理
        contract_keywords = ['合同性质', '法律关系', '协议条款']
        tax_treatment_keywords = ['税务处理', '计税方式', '税率适用']
        
        for l_finding in legal_findings:
            if any(kw in l_finding.description for kw in contract_keywords):
                for t_finding in tax_findings:
                    if any(kw in t_finding.description for kw in tax_treatment_keywords):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[l_finding.id, t_finding.id],
                            conflict_type="legal_tax_mismatch",
                            description=f"合同法律性质与税务处理方式不匹配",
                            severity="high",
                            resolution_suggestion="重新评估合同法律性质，确定正确的税务处理方式",
                            agent1="legal",
                            agent2="tax",
                            finding1=l_finding.to_dict(),
                            finding2=t_finding.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        # 冲突模式2：合规要求 vs 税务优化
        compliance_keywords = ['合规要求', '法律风险', '监管要求']
        optimization_keywords = ['税务筹划', '节税', '优化']
        
        for l_finding in legal_findings:
            if any(kw in l_finding.description for kw in compliance_keywords):
                for t_finding in tax_findings:
                    if any(kw in t_finding.description for kw in optimization_keywords):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[l_finding.id, t_finding.id],
                            conflict_type="compliance_optimization_conflict",
                            description=f"法律合规要求与税务优化策略存在冲突",
                            severity="medium",
                            resolution_suggestion="平衡合规要求与税务优化，选择风险可控的方案",
                            agent1="legal",
                            agent2="tax",
                            finding1=l_finding.to_dict(),
                            finding2=t_finding.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        return conflicts
    
    async def check_evidence_grounding(
        self,
        state: AuditState
    ) -> List[str]:
        """
        验证证据溯源
        
        Args:
            state: 全局状态
            
        Returns:
            证据缺口列表
        """
        evidence_gaps = []
        
        # 收集所有发现
        all_findings = []
        for field in ['finance_findings', 'tax_findings', 'legal_findings']:
            findings_data = state.get(field, [])
            all_findings.extend([Finding(**f) for f in findings_data])
        
        # 检查每个发现的证据
        for finding in all_findings:
            # 检查法律依据
            if not finding.legal_basis or len(finding.legal_basis) == 0:
                evidence_gaps.append(
                    f"{finding.agent_name}: {finding.description[:50]}... 缺少法律依据"
                )
            
            # 检查具体证据
            if not finding.evidence or len(finding.evidence) == 0:
                evidence_gaps.append(
                    f"{finding.agent_name}: {finding.description[:50]}... 缺少具体证据"
                )
        
        return evidence_gaps
    
    async def evaluate_confidence(
        self,
        state: AuditState
    ) -> Dict[str, float]:
        """
        评估置信度
        
        Args:
            state: 全局状态
            
        Returns:
            置信度分数字典
        """
        confidence_scores = {}
        
        # 评估各 Agent 的置信度
        for agent_name in ['finance', 'tax', 'legal']:
            field_name = f"{agent_name}_findings"
            findings_data = state.get(field_name, [])
            
            if not findings_data:
                confidence_scores[agent_name] = 1.0
                continue
            
            findings = [Finding(**f) for f in findings_data]
            
            # 基于证据完整性计算置信度
            total_confidence = 0.0
            for finding in findings:
                # 有法律依据 +0.5
                has_legal_basis = finding.legal_basis and len(finding.legal_basis) > 0
                # 有具体证据 +0.5
                has_evidence = finding.evidence and len(finding.evidence) > 0
                
                finding_confidence = 0.0
                if has_legal_basis:
                    finding_confidence += 0.5
                if has_evidence:
                    finding_confidence += 0.5
                
                total_confidence += finding_confidence
            
            # 平均置信度
            confidence_scores[agent_name] = total_confidence / len(findings) if findings else 1.0
        
        # 计算总体置信度
        if confidence_scores:
            confidence_scores['overall'] = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            confidence_scores['overall'] = 1.0
        
        return confidence_scores
    
    def _generate_reflection_summary(
        self,
        conflicts: List[Conflict],
        evidence_gaps: List[str],
        confidence_scores: Dict[str, float]
    ) -> str:
        """生成反思总结"""
        summary_parts = []
        
        # 冲突总结
        if conflicts:
            summary_parts.append(f"发现 {len(conflicts)} 个跨领域冲突")
            for conflict in conflicts[:3]:  # 最多显示3个
                summary_parts.append(f"  - {conflict.description}")
        else:
            summary_parts.append("未发现跨领域冲突")
        
        # 证据缺口总结
        if evidence_gaps:
            summary_parts.append(f"\n发现 {len(evidence_gaps)} 个证据缺口")
            for gap in evidence_gaps[:3]:  # 最多显示3个
                summary_parts.append(f"  - {gap}")
        else:
            summary_parts.append("\n证据溯源完整")
        
        # 置信度总结
        overall_confidence = confidence_scores.get('overall', 0.0)
        summary_parts.append(f"\n总体置信度: {overall_confidence:.2f}")
        
        return "\n".join(summary_parts)
    
    def _identify_rework_agents(
        self,
        conflicts: List[Conflict],
        evidence_gaps: List[str]
    ) -> List[str]:
        """识别需要重做的 Agent"""
        rework_agents = set()
        
        # 从冲突中识别
        for conflict in conflicts:
            if hasattr(conflict, 'agent1'):
                rework_agents.add(conflict.agent1)
            if hasattr(conflict, 'agent2'):
                rework_agents.add(conflict.agent2)
        
        # 从证据缺口中识别
        for gap in evidence_gaps:
            if 'finance' in gap.lower():
                rework_agents.add('finance')
            if 'tax' in gap.lower():
                rework_agents.add('tax')
            if 'legal' in gap.lower():
                rework_agents.add('legal')
        
        return list(rework_agents)
    
    async def _llm_conflict_detection(
        self,
        finance_findings: List[Finding],
        tax_findings: List[Finding],
        legal_findings: List[Finding]
    ) -> List[Conflict]:
        """
        使用LLM进行深度冲突分析
        
        Args:
            finance_findings: 财务发现
            tax_findings: 税务发现
            legal_findings: 法务发现
            
        Returns:
            LLM检测到的冲突列表
        """
        conflicts = []
        
        try:
            # 构建分析提示词
            prompt = self._build_conflict_analysis_prompt(
                finance_findings, tax_findings, legal_findings
            )
            
            # 调用LLM进行分析
            response = await self.llm_adapter.generate(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.1
            )
            
            # 解析LLM响应，提取冲突信息
            llm_conflicts = self._parse_llm_conflicts(response)
            conflicts.extend(llm_conflicts)
            
            print(f"🤔 [反思专家] LLM检测到 {len(llm_conflicts)} 个额外冲突")
            
        except Exception as e:
            print(f"🤔 [反思专家] LLM冲突检测失败: {e}")
        
        return conflicts
    
    def _build_conflict_analysis_prompt(
        self,
        finance_findings: List[Finding],
        tax_findings: List[Finding],
        legal_findings: List[Finding]
    ) -> str:
        """构建冲突分析提示词"""
        
        prompt = """你是一个专业的财税法务审计专家，请分析以下三个领域的发现是否存在冲突：

## 财务发现：
"""
        
        for i, finding in enumerate(finance_findings[:5]):  # 限制数量避免token过多
            prompt += f"{i+1}. {finding.description}\n"
            if finding.evidence:
                prompt += f"   证据: {'; '.join(finding.evidence[:2])}\n"
        
        prompt += "\n## 税务发现：\n"
        for i, finding in enumerate(tax_findings[:5]):
            prompt += f"{i+1}. {finding.description}\n"
            if finding.evidence:
                prompt += f"   证据: {'; '.join(finding.evidence[:2])}\n"
        
        prompt += "\n## 法务发现：\n"
        for i, finding in enumerate(legal_findings[:5]):
            prompt += f"{i+1}. {finding.description}\n"
            if finding.evidence:
                prompt += f"   证据: {'; '.join(finding.evidence[:2])}\n"
        
        prompt += """
## 请分析：
1. 是否存在跨领域的逻辑冲突？
2. 不同领域的结论是否相互矛盾？
3. 证据是否支持所有结论？

## 输出格式：
如果发现冲突，请按以下格式输出：
CONFLICT: [冲突类型] | [涉及领域] | [冲突描述] | [严重程度:high/medium/low] | [解决建议]

如果没有发现冲突，请输出：
NO_CONFLICT

请开始分析：
"""
        
        return prompt
    
    def _parse_llm_conflicts(self, llm_response: str) -> List[Conflict]:
        """解析LLM响应中的冲突信息"""
        conflicts = []
        
        if not llm_response or "NO_CONFLICT" in llm_response:
            return conflicts
        
        lines = llm_response.split('\n')
        for line in lines:
            if line.startswith('CONFLICT:'):
                try:
                    # 解析格式: CONFLICT: [类型] | [领域] | [描述] | [严重程度] | [建议]
                    parts = line.replace('CONFLICT:', '').split('|')
                    if len(parts) >= 4:
                        conflict_type = parts[0].strip()
                        agents = parts[1].strip()
                        description = parts[2].strip()
                        severity = parts[3].strip().lower()
                        suggestion = parts[4].strip() if len(parts) > 4 else "需要进一步分析"
                        
                        # 确定涉及的agent
                        agent1, agent2 = "unknown", "unknown"
                        if "财务" in agents and "税务" in agents:
                            agent1, agent2 = "finance", "tax"
                        elif "财务" in agents and "法务" in agents:
                            agent1, agent2 = "finance", "legal"
                        elif "税务" in agents and "法务" in agents:
                            agent1, agent2 = "tax", "legal"
                        
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[],  # LLM检测的冲突可能没有具体的finding_id
                            conflict_type=f"llm_detected_{conflict_type}",
                            description=description,
                            severity=severity if severity in ["high", "medium", "low"] else "medium",
                            resolution_suggestion=suggestion,
                            agent1=agent1,
                            agent2=agent2,
                            finding1={},
                            finding2={},
                            resolution_needed=True,
                            resolved=False
                        ))
                        
                except Exception as e:
                    print(f"🤔 [反思专家] 解析LLM冲突失败: {e}")
                    continue
        
        return conflicts
