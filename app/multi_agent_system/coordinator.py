"""
多智能体协调器 (Agent Coordinator)
负责编排整个审查流程，管理全局状态
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from .state import AuditState, create_initial_state, Finding, Conflict, Report
from .message_bus import MessageBus
from .rework_controller import ReworkController
from app.memory_system.memory_manager import MemoryManager
from app.memory_system.episodic_memory import EpisodicMemory
from app.memory_system.semantic_memory import SemanticMemory
from app.services.agent_service import agent_service
from app.db.session import AsyncSessionLocal
from app.models.audit_task import AuditTask
from app.models.audit_result import AuditResult


class AgentCoordinator:
    """
    多智能体协调器
    
    职责：
    1. 管理全局状态 (AuditState)
    2. 编排审查流程
    3. 协调各专业 Agent
    4. 管理企业记忆
    5. 处理重做逻辑
    """
    
    def __init__(self, tenant_id: str = None, user_id: str = None, **kwargs):
        """初始化协调器"""
        self.tenant_id = tenant_id
        self.user_id = user_id
        # 存储其他可能的参数（如db等）
        self.extra_params = kwargs
        
        self.message_bus = MessageBus()
        self.current_state: Optional[AuditState] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.rework_controller = ReworkController(max_rework_count=2)
        
        # 初始化专业智能体
        self.specialists = {}
        self._initialize_specialists()
        
        print(f"🎯 [协调器] 初始化完成 (租户: {tenant_id or 'default'}, 用户: {user_id or 'default'})")
    
    def _initialize_specialists(self):
        """初始化专业智能体"""
        try:
            # 创建LLM适配器和工具管理器
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.agent_framework.tools.tool_manager import ToolManager
            from .agents.finance_specialist import FinanceSpecialist
            from .agents.tax_specialist import TaxSpecialist
            from .agents.legal_specialist import LegalSpecialist
            from .agents.reflection_specialist import ReflectionSpecialist
            
            llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
            tool_manager = ToolManager()
            
            # 初始化三个专业智能体
            self.specialists["finance"] = FinanceSpecialist(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager
            )
            
            self.specialists["tax"] = TaxSpecialist(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager
            )
            
            self.specialists["legal"] = LegalSpecialist(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager
            )
            
            # 初始化反思智能体
            self.specialists["reflection"] = ReflectionSpecialist(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager
            )
            
            print("🤖 [协调器] 专业智能体初始化完成")
            
        except Exception as e:
            print(f"⚠️ [协调器] 专业智能体初始化失败: {e}")
            self.specialists = {}
    
    async def audit(
        self,
        task_id: str,
        tenant_id: str,
        user_id: str,
        audit_type: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行审查流程
        
        Args:
            task_id: 任务 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            audit_type: 审查类型
            documents: 文档列表
            
        Returns:
            审查结果
        """
        print(f"🚀 [协调器] 开始审查任务: {task_id}")
        
        # 1. 初始化状态和记忆
        await self._initialize_state(task_id, tenant_id, user_id, audit_type, documents)
        
        try:
            # 2. 数据摄入阶段
            await self._data_ingestion_phase()
            
            # 3. 并行审查阶段（含重做循环）
            max_iterations = 2
            for iteration in range(max_iterations):
                print(f"\n{'='*60}")
                print(f"🔄 [协调器] 审查迭代 {iteration + 1}/{max_iterations}")
                print(f"{'='*60}\n")
                
                # 3.1 并行审查
                await self._parallel_audit_phase()
                
                # 3.2 反思检查阶段
                await self._reflection_phase()
                
                # 3.3 检查是否需要重做
                if not self.rework_controller.should_rework(self.current_state):
                    print(f"✅ [协调器] 审查通过，无需重做")
                    break
                
                # 3.4 执行重做
                if iteration < max_iterations - 1:  # 不是最后一次迭代
                    print(f"⚠️ [协调器] 检测到问题，触发第 {iteration + 1} 次重做")
                    self.current_state['rework_count'] = iteration + 1
                    
                    # 只重做有问题的 Agent
                    rework_agents = self.rework_controller.identify_rework_agents(
                        self.current_state
                    )
                    await self._rework_agents(rework_agents)
                else:
                    print(f"⚠️ [协调器] 已达最大迭代次数，停止重做")
            
            # 4. 生成最终报告
            final_report = await self._generate_final_report()
            
            # 5. 归档到企业记忆
            await self._archive_to_memory()
            
            print(f"✅ [协调器] 审查任务完成: {task_id}")
            # 返回包含final_report的完整状态
            return {
                **self.current_state,
                "final_report": final_report
            }
            
        except Exception as e:
            print(f"❌ [协调器] 审查任务失败: {e}")
            self.current_state["status"] = "failed"
            self.current_state["error_message"] = str(e)
            raise
    
    async def _initialize_state(
        self,
        task_id: str,
        tenant_id: str,
        user_id: str,
        audit_type: str,
        documents: List[Dict[str, Any]]
    ):
        """初始化状态和记忆"""
        # 创建初始状态
        self.current_state = create_initial_state(
            task_id, tenant_id, user_id, audit_type, documents
        )
        
        # 初始化记忆管理器
        self.memory_manager = MemoryManager(
            session_id=task_id,
            user_id=user_id
        )
        
        # 加载企业历史记忆
        await self._load_enterprise_memory()
        
        print(f"📋 [协调器] 状态初始化完成")
    
    async def _data_ingestion_phase(self):
        """数据摄入阶段"""
        print("📥 [协调器] 开始数据摄入阶段")
        
        # TODO: 实现文档解析、实体提取、OCR 等
        # 这里先用模拟数据
        self.current_state["parsed_docs"] = []
        for i, doc in enumerate(self.current_state["documents"]):
            # 生成文档ID，如果没有的话
            doc_id = doc.get("id", f"doc_{i+1}")
            parsed_doc = {
                "doc_id": doc_id,
                "content": doc.get("content", ""),
                "type": doc.get("type", "unknown"),
                "filename": doc.get("filename", f"document_{i+1}")
            }
            self.current_state["parsed_docs"].append(parsed_doc)
        
        self.current_state["entities"] = []  # TODO: 调用实体提取服务
        self.current_state["relations"] = []  # TODO: 调用关系提取服务
        
        print("✅ [协调器] 数据摄入阶段完成")
    
    async def _parallel_audit_phase(self):
        """并行审查阶段"""
        print("🔍 [协调器] 开始并行审查阶段")
        
        audit_type = self.current_state["audit_type"]
        
        # 根据审查类型确定需要的 Agent
        agents_to_run = []
        if audit_type in ["finance", "comprehensive"]:
            agents_to_run.append("finance")
        if audit_type in ["tax", "comprehensive"]:
            agents_to_run.append("tax")
        if audit_type in ["legal", "comprehensive"]:
            agents_to_run.append("legal")
        
        # 并行执行审查
        tasks = []
        for agent_name in agents_to_run:
            task = self._run_specialist_agent(agent_name)
            tasks.append(task)
        
        # 等待所有 Agent 完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            agent_name = agents_to_run[i]
            if isinstance(result, Exception):
                print(f"❌ [协调器] {agent_name} Agent 执行失败: {result}")
            else:
                print(f"✅ [协调器] {agent_name} Agent 执行完成")
        
        print("✅ [协调器] 并行审查阶段完成")
    
    async def _run_specialist_agent(self, agent_name: str) -> List[Finding]:
        """运行专业 Agent"""
        print(f"🤖 [协调器] 启动 {agent_name} Agent")
        
        try:
            # 获取专业智能体
            specialist = self.specialists.get(agent_name)
            if not specialist:
                print(f"❌ [协调器] 未找到 {agent_name} 专业智能体")
                return []
            
            # 准备文档数据
            documents = self.current_state.get("documents", [])
            
            # 调用专业智能体进行审查
            findings = await specialist.audit(
                state=self.current_state,
                documents=documents
            )
            
            # 保存到状态
            field_name = f"{agent_name}_findings"
            self.current_state[field_name] = [f.to_dict() for f in findings]
            
            print(f"✅ [协调器] {agent_name} Agent 完成，发现 {len(findings)} 个问题")
            return findings
            
        except Exception as e:
            print(f"❌ [协调器] {agent_name} Agent 执行异常: {e}")
            
            # 创建错误发现
            error_finding = Finding(
                id=str(uuid.uuid4()),
                agent_name=agent_name,
                category="执行错误",
                description=f"{agent_name}智能体执行失败: {str(e)}",
                risk_level="medium",
                risk_score=0.5,
                confidence=1.0,
                evidence=[f"错误信息: {str(e)}"],
                recommendations=[f"请检查{agent_name}智能体配置"]
            )
            
            # 保存错误发现
            field_name = f"{agent_name}_findings"
            self.current_state[field_name] = [error_finding.to_dict()]
            
            return [error_finding]
    
    def _build_agent_input(self, agent_name: str) -> str:
        """构建 Agent 输入"""
        documents_info = "\n".join([
            f"- 文档 {doc['id']}: {doc.get('type', 'unknown')} ({len(doc.get('content', ''))} 字符)"
            for doc in self.current_state["documents"]
        ])
        
        return f"""请作为{agent_name}专家，审查以下文档：

文档列表：
{documents_info}

请重点关注{agent_name}相关的风险和问题，并提供：
1. 发现的问题
2. 风险评估
3. 改进建议
4. 法律依据（如适用）

请以结构化的方式回答。"""
    
    def _parse_agent_result(self, agent_name: str, result: str) -> List[Finding]:
        """解析 Agent 结果为 Finding 对象"""
        # TODO: 实现更智能的结果解析
        # 现在先创建一个简单的 Finding
        finding = Finding(
            id=str(uuid.uuid4()),
            agent_name=agent_name,
            category=f"{agent_name}_review",
            description=result[:200] + "..." if len(result) > 200 else result,
            risk_level="medium",  # TODO: 智能评估风险等级
            risk_score=0.6,  # TODO: 智能计算风险分数
            confidence=0.8,  # TODO: 智能计算置信度
            evidence=[],  # TODO: 提取证据
            recommendations=[]  # TODO: 提取建议
        )
        
        return [finding]
    
    async def _reflection_phase(self):
        """反思检查阶段"""
        print("🤔 [协调器] 开始反思检查阶段")
        
        # 获取反思智能体
        reflection_agent = self.specialists.get("reflection")
        if not reflection_agent:
            print("⚠️ [协调器] 反思智能体未初始化，跳过反思阶段")
            return
        
        # 执行反思检查
        try:
            await reflection_agent.audit(
                state=self.current_state,
                documents=[]
            )
            print("✅ [协调器] 反思检查阶段完成")
        except Exception as e:
            print(f"❌ [协调器] 反思检查失败: {e}")
            # 设置默认值，避免后续流程中断
            self.current_state['conflicts'] = []
            self.current_state['evidence_gaps'] = []
            self.current_state['confidence_scores'] = {'overall': 0.8}
            self.current_state['need_rework'] = False
    
    async def _rework_agents(self, agent_names: List[str]):
        """
        重做指定的 Agent
        
        Args:
            agent_names: 需要重做的 Agent 名称列表
        """
        print(f"🔄 [协调器] 开始重做 Agent: {agent_names}")
        
        tasks = []
        for agent_name in agent_names:
            # 准备重做上下文
            context = self.rework_controller.prepare_rework_context(
                self.current_state,
                agent_name
            )
            print(f"\n📝 [协调器] {agent_name} 重做上下文:\n{context}\n")
            
            # 重新执行审查
            task = self._run_specialist_agent(agent_name)
            tasks.append(task)
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            agent_name = agent_names[i]
            if isinstance(result, Exception):
                print(f"❌ [协调器] {agent_name} Agent 重做失败: {result}")
            else:
                print(f"✅ [协调器] {agent_name} Agent 重做完成")
        
        print(f"✅ [协调器] Agent 重做完成")

    
    async def _generate_final_report(self) -> Dict[str, Any]:
        """生成最终报告"""
        print("📊 [协调器] 生成最终报告")
        
        # 收集所有发现
        all_findings = []
        for field in ["finance_findings", "tax_findings", "legal_findings"]:
            findings_data = self.current_state.get(field, [])
            all_findings.extend(findings_data)
        
        # 计算综合风险分数
        overall_risk_score = self._calculate_overall_risk_score(all_findings)
        
        # 生成报告
        report = Report(
            task_id=self.current_state["task_id"],
            tenant_id=self.current_state["tenant_id"],
            audit_type=self.current_state["audit_type"],
            findings=[Finding(**f) for f in all_findings],
            conflicts=[Conflict(**c) for c in self.current_state.get("conflicts", [])],
            overall_risk_score=overall_risk_score,
            summary=self._generate_summary(all_findings),
            recommendations=self._generate_recommendations(all_findings),
            created_at=datetime.utcnow()
        )
        
        # 保存到状态
        self.current_state["final_report"] = report.to_dict()
        self.current_state["status"] = "completed"
        
        return report.to_dict()
    
    def _calculate_overall_risk_score(self, findings: List[Dict]) -> float:
        """计算综合风险分数"""
        if not findings:
            return 0.0
        
        total_score = sum(f.get("risk_score", 0) for f in findings)
        return min(total_score / len(findings), 100.0)
    
    def _generate_summary(self, findings: List[Dict]) -> str:
        """生成摘要"""
        if not findings:
            return "未发现明显风险。"
        
        high_risk_count = sum(1 for f in findings if f.get("risk_score", 0) > 0.8)
        medium_risk_count = sum(1 for f in findings if 0.5 < f.get("risk_score", 0) <= 0.8)
        
        return f"共发现 {len(findings)} 个问题，其中高风险 {high_risk_count} 个，中风险 {medium_risk_count} 个。"
    
    def _generate_recommendations(self, findings: List[Dict]) -> List[str]:
        """生成建议"""
        recommendations = []
        for finding in findings:
            if finding.get("recommendations"):
                recommendations.extend(finding["recommendations"])
        
        # 去重
        return list(set(recommendations))
    
    async def _load_enterprise_memory(self):
        """加载企业历史记忆"""
        print("🧠 [协调器] 加载企业历史记忆")
        
        if not self.memory_manager:
            print("⚠️ [协调器] 记忆管理器未初始化")
            self.current_state["historical_risks"] = []
            self.current_state["semantic_facts"] = []
            return
        
        try:
            # 1. 从情景记忆读取历史审查记录
            episodic = EpisodicMemory(
                session_id=self.current_state['task_id'],
                user_id=self.current_state['user_id']
            )
            
            # 使用retrieve方法而不是search
            historical_audits = await episodic.retrieve(
                query=f"企业 {self.current_state['tenant_id']} 历史审查风险",
                top_k=5
            )
            self.current_state['historical_risks'] = [
                {'content': m.content, 'timestamp': m.timestamp.isoformat()}
                for m in historical_audits
            ]
            
            # 2. 从语义记忆读取核心事实
            semantic = SemanticMemory(user_id=self.current_state['user_id'])
            # 使用retrieve方法而不是search
            facts = await semantic.retrieve(
                query=f"企业 {self.current_state['tenant_id']} 核心事实",
                top_k=10
            )
            self.current_state['semantic_facts'] = [
                {'content': m.content, 'importance': m.importance}
                for m in facts
            ]
            
            print(f"✅ [协调器] 加载历史记忆: {len(historical_audits)} 条历史风险, {len(facts)} 条核心事实")
            
        except Exception as e:
            print(f"⚠️ [协调器] 加载企业记忆失败: {e}")
            self.current_state["historical_risks"] = []
            self.current_state["semantic_facts"] = []
    
    async def _archive_to_memory(self):
        """归档到企业记忆"""
        print("💾 [协调器] 归档到企业记忆")
        
        if not self.memory_manager:
            print("⚠️ [协调器] 记忆管理器未初始化，跳过归档")
            return
        
        try:
            final_report = self.current_state.get("final_report")
            if not final_report:
                print("⚠️ [协调器] 无最终报告，跳过归档")
                return
            
            # 1. 归档到情景记忆
            await self.memory_manager.add_message(
                role="system",
                content=f"审查任务 {self.current_state['task_id']} 完成，"
                       f"发现 {len(final_report.get('findings', []))} 个问题，"
                       f"综合风险分数: {final_report.get('overall_risk_score', 0):.2f}",
                importance=0.9,  # 高重要性
                metadata={
                    "task_id": self.current_state["task_id"],
                    "audit_type": self.current_state["audit_type"],
                    "tenant_id": self.current_state["tenant_id"],
                    "rework_count": self.current_state.get("rework_count", 0)
                }
            )
            
            # 2. 固化高置信度事实到语义记忆
            semantic = SemanticMemory(user_id=self.current_state['user_id'])
            high_confidence_findings = [
                f for f in final_report.get('findings', [])
                if f.get('confidence', 0) > 0.9
            ]
            
            for finding in high_confidence_findings[:5]:  # 最多保存5条
                await semantic.add(
                    content=finding.get('description', ''),
                    importance=0.9,
                    metadata={
                        'tenant_id': self.current_state['tenant_id'],
                        'fact_type': finding.get('category', 'unknown'),
                        'evidence': str(finding.get('evidence', []))
                    }
                )
            
            print(f"✅ [协调器] 归档完成: 1 条审查记录, {len(high_confidence_findings)} 条核心事实")
            
        except Exception as e:
            print(f"⚠️ [协调器] 归档失败: {e}")
    
    def get_state(self) -> Optional[AuditState]:
        """获取当前状态"""
        return self.current_state
    
    def update_state(self, updates: Dict[str, Any]):
        """更新状态"""
        if self.current_state:
            self.current_state.update(updates)
    
    async def coordinate_review(self, query: str, documents: List[Dict] = None) -> Dict[str, Any]:
        """
        协调审查方法 - 为了向后兼容而添加的别名方法
        
        Args:
            query: 审查查询
            documents: 文档列表（可选）
            
        Returns:
            审查结果
        """
        # 生成任务ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # 从查询中推断审查类型
        audit_type = "comprehensive"  # 默认为综合审查
        if "财务" in query or "financial" in query.lower():
            audit_type = "finance"
        elif "税务" in query or "tax" in query.lower():
            audit_type = "tax"
        elif "法务" in query or "legal" in query.lower():
            audit_type = "legal"
        
        # 如果没有提供文档，使用空列表
        if documents is None:
            documents = []
        
        # 调用主要的audit方法
        return await self.audit(
            task_id=task_id,
            tenant_id=self.tenant_id or "default",
            user_id=self.user_id or "default",
            audit_type=audit_type,
            documents=documents
        )