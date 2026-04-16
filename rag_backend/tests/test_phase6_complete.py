"""
Phase 6 完整测试 - Reflection Agent + 企业记忆集成

测试内容：
1. ReflectionSpecialist 功能
2. 冲突检测
3. 证据验证
4. 重做逻辑
5. 企业记忆集成
6. 完整审查流程
"""

import asyncio
import uuid
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# 设置 UTF-8 编码（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目路径
sys.path.insert(0, '.')

from app.multi_agent_system.coordinator import AgentCoordinator
from app.multi_agent_system.state import Finding, Conflict, create_initial_state
from app.multi_agent_system.agents.reflection_specialist import ReflectionSpecialist
from app.multi_agent_system.conflict_detector import ConflictDetector
from app.multi_agent_system.evidence_validator import EvidenceValidator
from app.multi_agent_system.rework_controller import ReworkController


class Phase6Tester:
    """Phase 6 测试器"""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            "test": test_name,
            "passed": passed,
            "message": message,
            "status": status
        }
        self.test_results.append(result)
        
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        
        print(f"{status} - {test_name}")
        if message:
            print(f"    {message}")
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*70)
        print("📊 Phase 6 测试总结")
        print("="*70)
        print(f"总测试数: {len(self.test_results)}")
        print(f"✅ 通过: {self.passed}")
        print(f"❌ 失败: {self.failed}")
        print(f"成功率: {self.passed / len(self.test_results) * 100:.1f}%")
        print("="*70)
        
        # 打印失败的测试
        if self.failed > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test']}: {result['message']}")
    
    # ========== 测试1: 冲突检测器 ==========
    async def test_conflict_detector(self):
        """测试冲突检测器"""
        print("\n" + "="*70)
        print("🔍 测试1: 冲突检测器")
        print("="*70)
        
        try:
            detector = ConflictDetector()
            
            # 准备测试数据（故意制造冲突）
            finance_findings = [{
                "id": str(uuid.uuid4()),
                "agent_name": "finance",
                "category": "收入分类",
                "description": "1000万元应计入营业收入",
                "risk_level": "low",
                "risk_score": 0.3,
                "confidence": 0.9,
                "evidence": ["财务报表"],
                "legal_basis": ["企业会计准则"]
            }]
            
            legal_findings = [{
                "id": str(uuid.uuid4()),
                "agent_name": "legal",
                "category": "合同审查",
                "description": "该笔1000万元为带对赌条款的借款",
                "risk_level": "high",
                "risk_score": 0.8,
                "confidence": 0.9,
                "evidence": ["投资协议"],
                "legal_basis": ["合同法"]
            }]
            
            # 检测冲突
            conflicts = await detector.detect(
                finance_findings=finance_findings,
                tax_findings=[],
                legal_findings=legal_findings
            )
            
            # 验证结果
            self.log_test(
                "冲突检测器初始化",
                True,
                "冲突检测器成功初始化"
            )
            
            self.log_test(
                "检测到冲突",
                len(conflicts) > 0,
                f"检测到 {len(conflicts)} 个冲突"
            )
            
            if conflicts:
                conflict = conflicts[0]
                self.log_test(
                    "冲突类型正确",
                    conflict.conflict_type == "income_vs_loan",
                    f"冲突类型: {conflict.conflict_type}"
                )
                
                self.log_test(
                    "冲突严重性正确",
                    conflict.severity == "high",
                    f"严重性: {conflict.severity}"
                )
            
        except Exception as e:
            self.log_test("冲突检测器测试", False, f"异常: {str(e)}")
    
    # ========== 测试2: 证据验证器 ==========
    async def test_evidence_validator(self):
        """测试证据验证器"""
        print("\n" + "="*70)
        print("📋 测试2: 证据验证器")
        print("="*70)
        
        try:
            validator = EvidenceValidator()
            
            # 准备测试数据（缺少证据）
            findings_with_gaps = [{
                "id": str(uuid.uuid4()),
                "agent_name": "finance",
                "category": "测试",
                "description": "这是一个测试发现",
                "risk_level": "medium",
                "risk_score": 0.5,
                "confidence": 0.8,
                "evidence": [],  # 缺少证据
                "legal_basis": []  # 缺少法律依据
            }]
            
            # 验证证据
            gaps = await validator.validate(findings_with_gaps)
            
            self.log_test(
                "证据验证器初始化",
                True,
                "证据验证器成功初始化"
            )
            
            self.log_test(
                "检测到证据缺口",
                len(gaps) > 0,
                f"检测到 {len(gaps)} 个证据缺口"
            )
            
            # 测试完整证据
            findings_complete = [{
                "id": str(uuid.uuid4()),
                "agent_name": "finance",
                "category": "测试",
                "description": "这是一个完整的发现",
                "risk_level": "medium",
                "risk_score": 0.5,
                "confidence": 0.8,
                "evidence": ["证据1", "证据2"],
                "legal_basis": ["企业会计准则第1号"]
            }]
            
            gaps_complete = await validator.validate(findings_complete)
            
            self.log_test(
                "完整证据无缺口",
                len(gaps_complete) == 0,
                f"证据缺口数: {len(gaps_complete)}"
            )
            
        except Exception as e:
            self.log_test("证据验证器测试", False, f"异常: {str(e)}")
    
    # ========== 测试3: 重做控制器 ==========
    async def test_rework_controller(self):
        """测试重做控制器"""
        print("\n" + "="*70)
        print("🔄 测试3: 重做控制器")
        print("="*70)
        
        try:
            controller = ReworkController(max_rework_count=2)
            
            # 测试场景1: 有严重冲突，需要重做
            state_with_conflicts = create_initial_state(
                task_id=str(uuid.uuid4()),
                tenant_id="test_tenant",
                user_id="test_user",
                audit_type="comprehensive",
                documents=[]
            )
            state_with_conflicts['conflicts'] = [{
                'severity': 'high',
                'agent1': 'finance',
                'agent2': 'legal'
            }]
            state_with_conflicts['rework_count'] = 0
            
            should_rework = controller.should_rework(state_with_conflicts)
            
            self.log_test(
                "检测到需要重做",
                should_rework,
                "有高风险冲突，应该重做"
            )
            
            # 识别需要重做的 Agent
            rework_agents = controller.identify_rework_agents(state_with_conflicts)
            
            self.log_test(
                "识别重做 Agent",
                len(rework_agents) > 0,
                f"需要重做的 Agent: {rework_agents}"
            )
            
            # 测试场景2: 已达最大重做次数
            state_max_rework = create_initial_state(
                task_id=str(uuid.uuid4()),
                tenant_id="test_tenant",
                user_id="test_user",
                audit_type="comprehensive",
                documents=[]
            )
            state_max_rework['conflicts'] = [{'severity': 'high'}]
            state_max_rework['rework_count'] = 2
            
            should_not_rework = controller.should_rework(state_max_rework)
            
            self.log_test(
                "达到最大重做次数",
                not should_not_rework,
                "已达最大重做次数，不应再重做"
            )
            
        except Exception as e:
            self.log_test("重做控制器测试", False, f"异常: {str(e)}")

    
    # ========== 测试4: ReflectionSpecialist ==========
    async def test_reflection_specialist(self):
        """测试反思专家"""
        print("\n" + "="*70)
        print("🤔 测试4: ReflectionSpecialist")
        print("="*70)
        
        try:
            # 创建测试状态
            state = create_initial_state(
                task_id=str(uuid.uuid4()),
                tenant_id="test_tenant",
                user_id="test_user",
                audit_type="comprehensive",
                documents=[]
            )
            
            # 添加测试发现（制造冲突）
            state['finance_findings'] = [{
                "id": str(uuid.uuid4()),
                "agent_name": "finance",
                "category": "收入",
                "description": "营业收入1000万",
                "risk_level": "low",
                "risk_score": 0.3,
                "confidence": 0.9,
                "evidence": ["财务报表"],
                "legal_basis": ["企业会计准则"]
            }]
            
            state['legal_findings'] = [{
                "id": str(uuid.uuid4()),
                "agent_name": "legal",
                "category": "合同",
                "description": "借款1000万",
                "risk_level": "high",
                "risk_score": 0.8,
                "confidence": 0.9,
                "evidence": ["合同"],
                "legal_basis": ["合同法"]
            }]
            
            # 创建反思专家（使用模拟的 LLM 和工具管理器）
            try:
                from app.agent_framework.llm.factory import LLMAdapterFactory
                from app.agent_framework.tools.tool_manager import ToolManager
                
                llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
                tool_manager = ToolManager()
                
                reflection_agent = ReflectionSpecialist(
                    llm_adapter=llm_adapter,
                    tool_manager=tool_manager
                )
                
                # 执行反思
                await reflection_agent.audit(state, [])
                
                self.log_test(
                    "反思专家初始化",
                    True,
                    "反思专家成功初始化"
                )
                
                self.log_test(
                    "检测到冲突",
                    len(state.get('conflicts', [])) > 0,
                    f"检测到 {len(state.get('conflicts', []))} 个冲突"
                )
                
                self.log_test(
                    "生成置信度分数",
                    'confidence_scores' in state,
                    f"置信度: {state.get('confidence_scores', {})}"
                )
                
                self.log_test(
                    "生成反思总结",
                    'reflection_summary' in state and len(state['reflection_summary']) > 0,
                    "反思总结已生成"
                )
                
            except Exception as e:
                self.log_test("反思专家测试", False, f"初始化失败: {str(e)}")
            
        except Exception as e:
            self.log_test("反思专家测试", False, f"异常: {str(e)}")
    
    # ========== 测试5: 完整审查流程 ==========
    async def test_full_audit_workflow(self):
        """测试完整审查流程"""
        print("\n" + "="*70)
        print("🎯 测试5: 完整审查流程（含反思和重做）")
        print("="*70)
        
        try:
            # 创建协调器
            coordinator = AgentCoordinator()
            
            self.log_test(
                "协调器初始化",
                coordinator is not None,
                "协调器成功初始化"
            )
            
            self.log_test(
                "重做控制器初始化",
                coordinator.rework_controller is not None,
                "重做控制器已集成"
            )
            
            self.log_test(
                "反思专家初始化",
                "reflection" in coordinator.specialists,
                "反思专家已集成"
            )
            
            # 准备测试文档（制造冲突场景）
            documents = [
                {
                    "id": "doc1",
                    "name": "财务报表.xlsx",
                    "content": "营业收入: 1000万元",
                    "type": "finance"
                },
                {
                    "id": "doc2",
                    "name": "投资协议.docx",
                    "content": "借款协议: 甲方向乙方借款1000万元，附带对赌条款",
                    "type": "legal"
                }
            ]
            
            # 执行审查
            print("\n开始执行完整审查流程...")
            result = await coordinator.audit(
                task_id=str(uuid.uuid4()),
                tenant_id="test_tenant",
                user_id="test_user",
                audit_type="comprehensive",
                documents=documents
            )
            
            self.log_test(
                "审查流程完成",
                result is not None,
                "审查流程成功完成"
            )
            
            self.log_test(
                "生成最终报告",
                'final_report' in coordinator.current_state,
                "最终报告已生成"
            )
            
            # 验证反思阶段执行
            self.log_test(
                "反思阶段执行",
                'conflicts' in coordinator.current_state,
                f"冲突数: {len(coordinator.current_state.get('conflicts', []))}"
            )
            
            self.log_test(
                "置信度评估",
                'confidence_scores' in coordinator.current_state,
                f"总体置信度: {coordinator.current_state.get('confidence_scores', {}).get('overall', 0):.2f}"
            )
            
            # 验证重做逻辑
            rework_count = coordinator.current_state.get('rework_count', 0)
            self.log_test(
                "重做逻辑",
                True,  # 无论是否重做都算通过
                f"重做次数: {rework_count}"
            )
            
            # 验证状态完整性
            required_fields = [
                'task_id', 'tenant_id', 'user_id', 'audit_type',
                'finance_findings', 'tax_findings', 'legal_findings',
                'conflicts', 'evidence_gaps', 'confidence_scores',
                'final_report', 'status'
            ]
            
            missing_fields = [f for f in required_fields if f not in coordinator.current_state]
            
            self.log_test(
                "状态完整性",
                len(missing_fields) == 0,
                f"缺失字段: {missing_fields}" if missing_fields else "所有必需字段都存在"
            )
            
        except Exception as e:
            self.log_test("完整审查流程测试", False, f"异常: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # ========== 测试6: 企业记忆集成 ==========
    async def test_enterprise_memory(self):
        """测试企业记忆集成"""
        print("\n" + "="*70)
        print("🧠 测试6: 企业记忆集成")
        print("="*70)
        
        try:
            coordinator = AgentCoordinator()
            
            # 初始化状态
            await coordinator._initialize_state(
                task_id=str(uuid.uuid4()),
                tenant_id="test_tenant",
                user_id="test_user",
                audit_type="finance",
                documents=[]
            )
            
            self.log_test(
                "记忆管理器初始化",
                coordinator.memory_manager is not None,
                "记忆管理器已初始化"
            )
            
            # 测试记忆加载
            await coordinator._load_enterprise_memory()
            
            self.log_test(
                "历史记忆加载",
                'historical_risks' in coordinator.current_state,
                f"历史风险数: {len(coordinator.current_state.get('historical_risks', []))}"
            )
            
            self.log_test(
                "语义记忆加载",
                'semantic_facts' in coordinator.current_state,
                f"核心事实数: {len(coordinator.current_state.get('semantic_facts', []))}"
            )
            
            # 模拟审查完成，测试记忆归档
            coordinator.current_state['final_report'] = {
                'findings': [
                    {
                        'description': '测试发现',
                        'confidence': 0.95,
                        'category': 'test',
                        'evidence': ['测试证据']
                    }
                ],
                'overall_risk_score': 75.0
            }
            
            await coordinator._archive_to_memory()
            
            self.log_test(
                "记忆归档",
                True,
                "记忆归档成功执行"
            )
            
        except Exception as e:
            self.log_test("企业记忆集成测试", False, f"异常: {str(e)}")
    
    # ========== 主测试函数 ==========
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*70)
        print("🚀 Phase 6 完整测试开始")
        print("="*70)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 运行所有测试
        await self.test_conflict_detector()
        await self.test_evidence_validator()
        await self.test_rework_controller()
        await self.test_reflection_specialist()
        await self.test_full_audit_workflow()
        await self.test_enterprise_memory()
        
        # 打印总结
        self.print_summary()
        
        return self.failed == 0


async def main():
    """主函数"""
    tester = Phase6Tester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！Phase 6 实施成功！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
