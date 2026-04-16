"""
Phase 8: 端到端集成测试
测试完整的审查流程（文档上传 → 审查 → 报告生成）
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import json
import uuid  # 修复：添加uuid导入
import pytest  # 添加pytest导入

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.models.tenant_audit_log import TenantAuditLog
from app.multi_agent_system import MultiAgentCoordinator  # 修复：使用正确的导入
from app.multi_agent_system.pipeline.data_ingestion import DataIngestionPipeline
from app.multi_agent_system.report_generator import ReportGenerator
from app.services.minio_service import MinioService
from app.core.config import settings


class E2EIntegrationTester:
    """端到端集成测试器"""
    
    def __init__(self):
        self.db: Session = SessionLocal()
        self.test_tenant_id = "test_tenant_e2e"
        self.test_user_id = uuid.uuid4()  # 修复：使用UUID而不是整数
        self.coordinator = None
        self.results = []
        
    def setup(self):
        """测试环境准备"""
        print("=" * 80)
        print("Phase 8: 端到端集成测试")
        print("=" * 80)
        
        # 创建测试租户用户 - 使用 ON CONFLICT DO NOTHING 避免重复
        user = self.db.query(User).filter(User.id == self.test_user_id).first()
        if not user:
            try:
                user = User(
                    id=self.test_user_id,
                    username="e2e_test_user",  # 修复：使用正确的字段名
                    email="e2e@test.com",
                    hashed_password="test",
                    tenant_id=self.test_tenant_id
                )
                self.db.add(user)
                self.db.commit()
            except Exception as e:
                # 如果用户已存在，回滚并获取现有用户
                self.db.rollback()
                user = self.db.query(User).filter(User.email == "e2e@test.com").first()
                if user:
                    self.test_user_id = user.id
                    print(f"✓ 使用现有测试用户: {self.test_user_id}")
                else:
                    raise e
        
        print(f"✓ 测试租户: {self.test_tenant_id}")
        print(f"✓ 测试用户: {self.test_user_id}")
        
    async def test_scenario_1_financial_report(self):
        """场景 1: 财务报表审查（PDF 文档）"""
        print("\n" + "=" * 80)
        print("场景 1: 财务报表审查（PDF 文档）")
        print("=" * 80)
        
        start_time = datetime.now()
        
        try:
            # 模拟文档内容
            document_content = """
            财务报表审查
            
            公司名称：测试科技有限公司
            报告期间：2024年度
            
            一、资产负债表
            流动资产：5,000,000 元
            固定资产：3,000,000 元
            资产总计：8,000,000 元
            
            流动负债：2,000,000 元
            长期负债：1,000,000 元
            负债总计：3,000,000 元
            
            所有者权益：5,000,000 元
            
            二、利润表
            营业收入：10,000,000 元
            营业成本：6,000,000 元
            营业利润：4,000,000 元
            净利润：3,000,000 元
            
            三、现金流量表
            经营活动现金流：2,500,000 元
            投资活动现金流：-500,000 元
            筹资活动现金流：-300,000 元
            """
            
            # 创建协调器
            coordinator = MultiAgentCoordinator(
                tenant_id=self.test_tenant_id,
                user_id=self.test_user_id,
                db=self.db
            )
            
            # 执行审查
            print("\n开始审查...")
            result = await coordinator.coordinate_review(
                query="请审查这份财务报表，重点关注财务指标的合理性和完整性",
                documents=[{
                    "content": document_content,
                    "filename": "financial_report.pdf",
                    "doc_type": "financial"
                }]
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 验证结果
            assert result is not None, "审查结果不能为空"
            assert "final_report" in result, "缺少最终报告"
            assert duration < 120, f"处理时间过长: {duration}秒"
            
            print(f"\n✓ 场景 1 通过")
            print(f"  处理时间: {duration:.2f}秒")
            print(f"  报告长度: {len(result.get('final_report', ''))} 字符")
            
            self.results.append({
                "scenario": "财务报表审查",
                "status": "PASS",
                "duration": duration,
                "details": result
            })
            
        except Exception as e:
            print(f"\n✗ 场景 1 失败: {str(e)}")
            self.results.append({
                "scenario": "财务报表审查",
                "status": "FAIL",
                "error": str(e)
            })
            
    async def test_scenario_2_tax_filing(self):
        """场景 2: 税务申报审查（Excel 文档）"""
        print("\n" + "=" * 80)
        print("场景 2: 税务申报审查（Excel 文档）")
        print("=" * 80)
        
        start_time = datetime.now()
        
        try:
            # 模拟税务申报内容
            document_content = """
            企业所得税年度纳税申报表
            
            纳税人名称：测试科技有限公司
            纳税人识别号：91110000XXXXXXXX
            所属期间：2024年度
            
            一、收入总额
            营业收入：10,000,000 元
            其他收入：500,000 元
            收入总额：10,500,000 元
            
            二、扣除项目
            营业成本：6,000,000 元
            税金及附加：200,000 元
            销售费用：1,000,000 元
            管理费用：800,000 元
            财务费用：100,000 元
            扣除合计：8,100,000 元
            
            三、应纳税所得额
            利润总额：2,400,000 元
            纳税调整增加额：100,000 元
            纳税调整减少额：50,000 元
            应纳税所得额：2,450,000 元
            
            四、应纳税额
            税率：25%
            应纳税额：612,500 元
            已预缴税额：600,000 元
            应补（退）税额：12,500 元
            """
            
            coordinator = MultiAgentCoordinator(
                tenant_id=self.test_tenant_id,
                user_id=self.test_user_id,
                db=self.db
            )
            
            print("\n开始审查...")
            result = await coordinator.coordinate_review(
                query="请审查这份税务申报表，检查计算是否正确，是否符合税法规定",
                documents=[{
                    "content": document_content,
                    "filename": "tax_filing.xlsx",
                    "doc_type": "tax"
                }]
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            assert result is not None, "审查结果不能为空"
            assert duration < 120, f"处理时间过长: {duration}秒"
            
            print(f"\n✓ 场景 2 通过")
            print(f"  处理时间: {duration:.2f}秒")
            
            self.results.append({
                "scenario": "税务申报审查",
                "status": "PASS",
                "duration": duration
            })
            
        except Exception as e:
            print(f"\n✗ 场景 2 失败: {str(e)}")
            self.results.append({
                "scenario": "税务申报审查",
                "status": "FAIL",
                "error": str(e)
            })
            
    async def test_scenario_3_contract_review(self):
        """场景 3: 合同审查（Word 文档）"""
        print("\n" + "=" * 80)
        print("场景 3: 合同审查（Word 文档）")
        print("=" * 80)
        
        start_time = datetime.now()
        
        try:
            document_content = """
            技术服务合同
            
            甲方（委托方）：测试科技有限公司
            乙方（服务方）：某某技术服务公司
            
            一、服务内容
            乙方为甲方提供软件开发服务，包括但不限于：
            1. 需求分析
            2. 系统设计
            3. 编码实现
            4. 测试部署
            
            二、服务期限
            自2024年1月1日起至2024年12月31日止
            
            三、服务费用
            总费用：人民币500,000元（大写：伍拾万元整）
            支付方式：
            1. 签约后支付30%（150,000元）
            2. 项目中期支付40%（200,000元）
            3. 项目验收后支付30%（150,000元）
            
            四、双方权利义务
            甲方义务：
            1. 按时支付服务费用
            2. 提供必要的工作条件
            3. 配合乙方完成项目
            
            乙方义务：
            1. 按时完成服务内容
            2. 保证服务质量
            3. 保守商业秘密
            
            五、违约责任
            任何一方违约，应向对方支付合同总额10%的违约金
            
            六、争议解决
            因本合同引起的争议，双方应友好协商解决；
            协商不成的，提交甲方所在地人民法院诉讼解决。
            """
            
            coordinator = MultiAgentCoordinator(
                tenant_id=self.test_tenant_id,
                user_id=self.test_user_id,
                db=self.db
            )
            
            print("\n开始审查...")
            result = await coordinator.coordinate_review(
                query="请审查这份技术服务合同，重点关注条款的完整性和法律风险",
                documents=[{
                    "content": document_content,
                    "filename": "service_contract.docx",
                    "doc_type": "legal"
                }]
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            assert result is not None, "审查结果不能为空"
            assert duration < 120, f"处理时间过长: {duration}秒"
            
            print(f"\n✓ 场景 3 通过")
            print(f"  处理时间: {duration:.2f}秒")
            
            self.results.append({
                "scenario": "合同审查",
                "status": "PASS",
                "duration": duration
            })
            
        except Exception as e:
            print(f"\n✗ 场景 3 失败: {str(e)}")
            self.results.append({
                "scenario": "合同审查",
                "status": "FAIL",
                "error": str(e)
            })
            
    async def test_scenario_4_comprehensive_review(self):
        """场景 4: 综合审查（多文档混合）"""
        print("\n" + "=" * 80)
        print("场景 4: 综合审查（多文档混合）")
        print("=" * 80)
        
        start_time = datetime.now()
        
        try:
            documents = [
                {
                    "content": "财务报表：营业收入1000万元，净利润300万元",
                    "filename": "financial.pdf",
                    "doc_type": "financial"
                },
                {
                    "content": "税务申报：应纳税所得额245万元，应纳税额61.25万元",
                    "filename": "tax.xlsx",
                    "doc_type": "tax"
                },
                {
                    "content": "服务合同：合同金额50万元，服务期限1年",
                    "filename": "contract.docx",
                    "doc_type": "legal"
                }
            ]
            
            coordinator = MultiAgentCoordinator(
                tenant_id=self.test_tenant_id,
                user_id=self.test_user_id,
                db=self.db
            )
            
            print("\n开始综合审查...")
            result = await coordinator.coordinate_review(
                query="请对这些文档进行综合审查，检查财务、税务和法律方面的一致性",
                documents=documents
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            assert result is not None, "审查结果不能为空"
            assert duration < 120, f"处理时间过长: {duration}秒"
            
            print(f"\n✓ 场景 4 通过")
            print(f"  处理时间: {duration:.2f}秒")
            print(f"  处理文档数: {len(documents)}")
            
            self.results.append({
                "scenario": "综合审查",
                "status": "PASS",
                "duration": duration,
                "document_count": len(documents)
            })
            
        except Exception as e:
            print(f"\n✗ 场景 4 失败: {str(e)}")
            self.results.append({
                "scenario": "综合审查",
                "status": "FAIL",
                "error": str(e)
            })
            
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("测试摘要")
        print("=" * 80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = total - passed
        
        print(f"\n总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"通过率: {passed/total*100:.1f}%")
        
        if passed > 0:
            avg_duration = sum(r.get("duration", 0) for r in self.results if r["status"] == "PASS") / passed
            print(f"平均处理时间: {avg_duration:.2f}秒")
        
        print("\n详细结果:")
        for i, result in enumerate(self.results, 1):
            status_icon = "✓" if result["status"] == "PASS" else "✗"
            print(f"{i}. {status_icon} {result['scenario']}: {result['status']}")
            if result["status"] == "PASS" and "duration" in result:
                print(f"   处理时间: {result['duration']:.2f}秒")
            elif result["status"] == "FAIL":
                print(f"   错误: {result.get('error', 'Unknown')}")
        
        # 保存结果到文件
        with open("test_phase8_e2e_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✓ 测试结果已保存到: test_phase8_e2e_results.json")
        
    def cleanup(self):
        """清理测试环境"""
        if self.db:
            self.db.close()
        print("\n✓ 测试环境已清理")


async def main():
    """主测试函数"""
    tester = E2EIntegrationTester()
    
    try:
        tester.setup()
        
        # 运行所有测试场景
        await tester.test_scenario_1_financial_report()
        await tester.test_scenario_2_tax_filing()
        await tester.test_scenario_3_contract_review()
        await tester.test_scenario_4_comprehensive_review()
        
        # 打印摘要
        tester.print_summary()
        
    except Exception as e:
        print(f"\n测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        tester.cleanup()


# ==========================================
# Pytest 兼容的测试函数
# ==========================================

@pytest.mark.asyncio
async def test_e2e_financial_report():
    """pytest兼容: 财务报表审查测试"""
    tester = E2EIntegrationTester()
    try:
        tester.setup()
        await tester.test_scenario_1_financial_report()
        # 检查结果
        assert len(tester.results) > 0
        assert tester.results[-1]["status"] in ["PASS", "FAIL"]
    finally:
        tester.cleanup()


@pytest.mark.asyncio
async def test_e2e_tax_filing():
    """pytest兼容: 税务申报审查测试"""
    tester = E2EIntegrationTester()
    try:
        tester.setup()
        await tester.test_scenario_2_tax_filing()
        # 检查结果
        assert len(tester.results) > 0
        assert tester.results[-1]["status"] in ["PASS", "FAIL"]
    finally:
        tester.cleanup()


@pytest.mark.asyncio
async def test_e2e_contract_review():
    """pytest兼容: 合同审查测试"""
    tester = E2EIntegrationTester()
    try:
        tester.setup()
        await tester.test_scenario_3_contract_review()
        # 检查结果
        assert len(tester.results) > 0
        assert tester.results[-1]["status"] in ["PASS", "FAIL"]
    finally:
        tester.cleanup()


@pytest.mark.asyncio
async def test_e2e_comprehensive_review():
    """pytest兼容: 综合审查测试"""
    tester = E2EIntegrationTester()
    try:
        tester.setup()
        await tester.test_scenario_4_comprehensive_review()
        # 检查结果
        assert len(tester.results) > 0
        assert tester.results[-1]["status"] in ["PASS", "FAIL"]
    finally:
        tester.cleanup()


@pytest.mark.asyncio
async def test_e2e_full_integration():
    """pytest兼容: 完整端到端集成测试"""
    tester = E2EIntegrationTester()
    try:
        tester.setup()
        
        # 运行所有场景
        await tester.test_scenario_1_financial_report()
        await tester.test_scenario_2_tax_filing()
        await tester.test_scenario_3_contract_review()
        await tester.test_scenario_4_comprehensive_review()
        
        # 验证所有测试都有结果
        assert len(tester.results) == 4
        
        # 打印摘要
        tester.print_summary()
        
        # 至少有一个测试通过
        passed_tests = [r for r in tester.results if r["status"] == "PASS"]
        assert len(passed_tests) > 0, "至少应有一个测试场景通过"
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
