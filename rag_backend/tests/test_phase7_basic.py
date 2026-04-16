# test_phase7_basic.py
"""
Phase 7 基础测试 - 报告生成工具
测试报告生成器、模板系统和导出器
"""
import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.multi_agent_system.report_generator import ReportGenerator, AuditReport
from app.multi_agent_system.report_templates import ReportTemplates, ReportType
from app.multi_agent_system.report_exporters import ReportExporter
from app.multi_agent_system.state import AuditState


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print(f"{'='*70}")


async def test_report_generator():
    """测试 1: 报告生成器"""
    print_section("测试 1: 报告生成器")
    
    # 创建模拟的 AuditState
    state = AuditState(
        task_id="test-task-001",
        tenant_id="test-tenant",
        audit_type="comprehensive",
        finance_findings=[
            {
                'type': 'risk',
                'message': '资产负债表不平衡，资产总额与负债+所有者权益不符',
                'severity': 'high',
                'evidence': '资产: 1000万，负债+权益: 950万',
                'legal_basis': '企业会计准则第30号',
                'confidence': 0.95
            },
            {
                'type': 'warning',
                'message': '应收账款周转率偏低，可能存在坏账风险',
                'severity': 'medium',
                'evidence': '应收账款周转率: 2.5次/年',
                'legal_basis': '',
                'confidence': 0.80
            }
        ],
        tax_findings=[
            {
                'type': 'risk',
                'message': '增值税申报金额与财务报表不一致',
                'severity': 'high',
                'evidence': '申报: 100万，报表: 120万',
                'legal_basis': '增值税暂行条例第23条',
                'confidence': 0.90
            }
        ],
        legal_findings=[
            {
                'type': 'warning',
                'message': '劳动合同缺少必备条款：工作地点',
                'severity': 'medium',
                'evidence': '合同第3条',
                'legal_basis': '劳动合同法第17条',
                'confidence': 0.85
            },
            {
                'type': 'info',
                'message': '合同签订日期早于生效日期，符合规范',
                'severity': 'low',
                'evidence': '签订: 2024-01-01, 生效: 2024-01-15',
                'legal_basis': '合同法第44条',
                'confidence': 1.0
            }
        ],
        conflicts=[
            {
                'type': 'income_vs_loan',
                'agent1': 'finance',
                'agent2': 'legal',
                'description': '财务认为是营业收入，法务认为是借款',
                'severity': 'high',
                'resolved': True
            }
        ],
        confidence_scores={
            'finance': 0.88,
            'tax': 0.90,
            'legal': 0.85,
            'overall': 0.87
        },
        reflection_summary='检测到1个跨领域冲突，已通过重做机制解决。整体置信度较高。',
        rework_count=1
    )
    
    # 创建报告生成器
    generator = ReportGenerator()
    
    # 生成报告
    report = await generator.generate(
        state=state,
        task_id="test-task-001",
        processing_time=45.2
    )
    
    # 验证报告
    assert report.task_id == "test-task-001"
    assert report.tenant_id == "test-tenant"
    assert report.total_findings == 5
    assert report.high_risk_count == 2
    assert report.medium_risk_count == 2
    assert report.low_risk_count == 1
    assert report.overall_risk_score > 0
    
    print(f"✅ 报告生成成功")
    print(f"  - 总发现数: {report.total_findings}")
    print(f"  - 风险分数: {report.overall_risk_score}")
    print(f"  - 执行摘要: {report.summary[:100]}...")
    
    return report


async def test_report_templates(report: AuditReport):
    """测试 2: 报告模板系统"""
    print_section("测试 2: 报告模板系统")
    
    templates = ReportTemplates()
    
    # 测试简版模板
    simple_report = templates.render(
        ReportType.SIMPLE,
        report.to_dict()
    )
    assert len(simple_report) > 0
    assert "审查报告（简版）" in simple_report
    print(f"✅ 简版模板渲染成功，长度: {len(simple_report)} 字符")
    
    # 测试标准模板
    standard_report = templates.render(
        ReportType.STANDARD,
        report.to_dict()
    )
    assert len(standard_report) > 0
    assert "审查报告（标准版）" in standard_report
    print(f"✅ 标准模板渲染成功，长度: {len(standard_report)} 字符")
    
    # 测试专业模板
    professional_report = templates.render(
        ReportType.PROFESSIONAL,
        report.to_dict()
    )
    assert len(professional_report) > 0
    assert "企业财税法务合规审查报告（专业版）" in professional_report
    print(f"✅ 专业模板渲染成功，长度: {len(professional_report)} 字符")
    
    return {
        'simple': simple_report,
        'standard': standard_report,
        'professional': professional_report
    }


async def test_report_exporters(report: AuditReport):
    """测试 3: 报告导出器"""
    print_section("测试 3: 报告导出器")
    
    exporter = ReportExporter()
    
    # 测试 JSON 导出
    json_content = exporter.export_json(report)
    assert len(json_content) > 0
    assert "task_id" in json_content
    print(f"✅ JSON 导出成功，长度: {len(json_content)} 字符")
    
    # 测试 Markdown 导出
    markdown_content = exporter.export_markdown(report, ReportType.STANDARD)
    assert len(markdown_content) > 0
    assert "审查报告" in markdown_content
    print(f"✅ Markdown 导出成功，长度: {len(markdown_content)} 字符")
    
    # 测试 HTML 导出
    html_content = exporter.export_html(report, ReportType.SIMPLE)
    assert len(html_content) > 0
    assert "<!DOCTYPE html>" in html_content
    print(f"✅ HTML 导出成功，长度: {len(html_content)} 字符")
    
    # 测试文件保存
    output_dir = Path("test_reports")
    output_dir.mkdir(exist_ok=True)
    
    json_file = exporter.save_to_file(
        json_content,
        str(output_dir / "report.json")
    )
    assert Path(json_file).exists()
    print(f"✅ JSON 文件已保存: {json_file}")
    
    markdown_file = exporter.save_to_file(
        markdown_content,
        str(output_dir / "report.md")
    )
    assert Path(markdown_file).exists()
    print(f"✅ Markdown 文件已保存: {markdown_file}")
    
    html_file = exporter.save_to_file(
        html_content,
        str(output_dir / "report.html")
    )
    assert Path(html_file).exists()
    print(f"✅ HTML 文件已保存: {html_file}")
    
    return {
        'json': json_file,
        'markdown': markdown_file,
        'html': html_file
    }


async def test_complete_workflow():
    """测试 4: 完整工作流"""
    print_section("测试 4: 完整工作流")
    
    # 模拟完整的审查流程
    print("📋 模拟审查流程...")
    
    # 1. 创建审查状态
    state = AuditState(
        task_id="workflow-test-001",
        tenant_id="company-abc",
        audit_type="financial",
        finance_findings=[
            {
                'type': 'risk',
                'message': '现金流量表异常，经营活动现金流为负',
                'severity': 'high',
                'evidence': '经营活动现金流: -500万',
                'legal_basis': '企业会计准则第31号',
                'confidence': 0.92
            }
        ],
        tax_findings=[],
        legal_findings=[],
        conflicts=[],
        confidence_scores={'finance': 0.92, 'overall': 0.92},
        reflection_summary='财务审查完成，未发现跨领域冲突。',
        rework_count=0
    )
    
    # 2. 生成报告
    generator = ReportGenerator()
    report = await generator.generate(state, "workflow-test-001", 30.5)
    print(f"✅ 步骤 1: 报告生成完成")
    
    # 3. 导出多种格式
    exporter = ReportExporter()
    
    json_content = exporter.export_json(report)
    markdown_content = exporter.export_markdown(report, ReportType.PROFESSIONAL)
    html_content = exporter.export_html(report, ReportType.PROFESSIONAL)
    print(f"✅ 步骤 2: 多格式导出完成")
    
    # 4. 保存文件
    output_dir = Path("test_reports/workflow")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    exporter.save_to_file(json_content, str(output_dir / "workflow_report.json"))
    exporter.save_to_file(markdown_content, str(output_dir / "workflow_report.md"))
    exporter.save_to_file(html_content, str(output_dir / "workflow_report.html"))
    print(f"✅ 步骤 3: 文件保存完成")
    
    print(f"\n🎉 完整工作流测试成功！")
    print(f"  - 报告ID: {report.task_id}")
    print(f"  - 风险分数: {report.overall_risk_score}")
    print(f"  - 输出文件: {output_dir}")


async def main():
    """主测试函数"""
    print("\n" + "="*70)
    print("🚀 Phase 7 基础测试开始")
    print("="*70)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    try:
        # 测试 1: 报告生成器
        report = await test_report_generator()
        
        # 测试 2: 报告模板
        templates_output = await test_report_templates(report)
        
        # 测试 3: 报告导出器
        export_files = await test_report_exporters(report)
        
        # 测试 4: 完整工作流
        await test_complete_workflow()
        
        # 总结
        print("\n" + "="*70)
        print("📊 Phase 7 测试总结")
        print("="*70)
        print("✅ 测试 1: 报告生成器 - 通过")
        print("✅ 测试 2: 报告模板系统 - 通过")
        print("✅ 测试 3: 报告导出器 - 通过")
        print("✅ 测试 4: 完整工作流 - 通过")
        print("="*70)
        print("🎉 所有测试通过！Phase 7 核心功能正常！")
        print("="*70)
        
        print("\n📁 生成的报告文件:")
        print(f"  - JSON: {export_files['json']}")
        print(f"  - Markdown: {export_files['markdown']}")
        print(f"  - HTML: {export_files['html']}")
        print(f"  - 工作流报告: test_reports/workflow/")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
