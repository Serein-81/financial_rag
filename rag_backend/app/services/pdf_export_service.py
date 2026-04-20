"""
PDF 导出服务
提供税务报告、财务分析、合同审核等业务的 PDF 导出功能
"""

from typing import Dict, Any, List
from datetime import datetime
from fpdf import FPDF


class PDFExportService:
    """PDF 导出服务"""

    def __init__(self):
        self.title_font_size = 16
        self.heading_font_size = 14
        self.subheading_font_size = 12
        self.body_font_size = 10
        self.margin = 15

    def export_tax_analysis_report(self, report_data: Dict[str, Any]) -> bytes:
        """
        导出税务分析报告为 PDF

        Args:
            report_data: 税务分析报告数据 (TaxAnalysisResult)

        Returns:
            PDF 文件的字节数据
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        self._add_header(pdf, "税务分析报告")

        analysis_info = {
            "分析ID": report_data.get("analysis_id", "N/A"),
            "分析类型": report_data.get("analysis_type", "N/A"),
            "财务年度": str(report_data.get("fiscal_year", "N/A")),
            "财务期间": report_data.get("fiscal_period", "N/A"),
            "状态": report_data.get("status", "N/A"),
            "创建时间": self._format_datetime(report_data.get("created_at")),
            "完成时间": self._format_datetime(report_data.get("completed_at")),
            "处理耗时": f"{report_data.get('processing_time', 0):.2f} 秒" if report_data.get("processing_time") else "N/A"
        }
        self._add_info_section(pdf, "基本信息", analysis_info)

        self._add_section(pdf, "一、财务数据摘要", report_data.get("financial_summary", {}))

        self._add_section(pdf, "二、税务计算结果", self._format_tax_calculations(report_data))

        summary = {
            "总税负": f"¥{report_data.get('total_tax_burden', 0):,.2f}",
            "税负率": f"{report_data.get('tax_burden_rate', 0):.2f}%",
            "预估节省金额": f"¥{report_data.get('total_potential_savings', 0):,.2f}",
            "综合风险评分": f"{report_data.get('overall_risk_score', 0):.1f}/100",
            "高风险数量": str(report_data.get("high_risk_count", 0))
        }
        self._add_info_section(pdf, "三、核心指标汇总", summary)

        self._add_policy_benefits(pdf, report_data.get("policy_benefits", []))

        self._add_risk_assessment(pdf, report_data.get("risk_assessment", []))

        self._add_optimization_suggestions(pdf, report_data.get("optimization_suggestions", []))

        if report_data.get("summary"):
            self._add_text_section(pdf, "八、执行摘要", report_data["summary"])

        self._add_footer(pdf)

        return pdf.output()

    def export_financial_health_report(self, report_data: Dict[str, Any]) -> bytes:
        """
        导出财务健康报告为 PDF

        Args:
            report_data: 财务健康报告数据

        Returns:
            PDF 文件的字节数据
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        self._add_header(pdf, "财务健康监控报告")

        basic_info = {
            "监控ID": report_data.get("monitor_id", "N/A"),
            "企业名称": report_data.get("company_name", "N/A"),
            "监控期间": report_data.get("monitor_period", "N/A"),
            "健康评分": f"{report_data.get('health_score', 0):.1f}/100",
            "生成时间": self._format_datetime(report_data.get("created_at"))
        }
        self._add_info_section(pdf, "基本信息", basic_info)

        self._add_anomalies_section(pdf, report_data.get("anomalies", []))

        self._add_trends_section(pdf, report_data.get("trends", {}))

        self._add_recommendations(pdf, report_data.get("recommendations", []))

        self._add_footer(pdf)

        return pdf.output()

    def export_contract_review_report(self, report_data: Dict[str, Any]) -> bytes:
        """
        导出合同审核报告为 PDF

        Args:
            report_data: 合同审核报告数据

        Returns:
            PDF 文件的字节数据
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        self._add_header(pdf, "合同审核报告")

        basic_info = {
            "合同ID": report_data.get("contract_id", "N/A"),
            "合同名称": report_data.get("contract_name", "N/A"),
            "合同类型": report_data.get("contract_type", "N/A"),
            "审核时间": self._format_datetime(report_data.get("review_time")),
            "风险等级": self._get_risk_level_text(report_data.get("overall_risk_level", "low"))
        }
        self._add_info_section(pdf, "基本信息", basic_info)

        self._add_clauses_section(pdf, report_data.get("clauses", []))

        self._add_risks_section(pdf, report_data.get("risks", []))

        self._add_findings_section(pdf, report_data.get("findings", []))

        if report_data.get("summary"):
            self._add_text_section(pdf, "执行摘要", report_data["summary"])

        self._add_footer(pdf)

        return pdf.output()

    def _add_header(self, pdf: FPDF, title: str):
        """添加 PDF 头部"""
        pdf.set_font("Helvetica", "B", self.title_font_size)
        pdf.set_xy(self.margin, self.margin)
        pdf.cell(0, 10, title, ln=True, align="C")

        pdf.set_font("Helvetica", "", self.body_font_size)
        pdf.ln(5)
        pdf.set_x(self.margin)
        pdf.cell(0, 6, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.ln(10)

    def _add_footer(self, pdf: FPDF):
        """添加 PDF 尾部"""
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_x(self.margin)
        pdf.cell(0, 5, "本报告由智能税务系统自动生成，仅供参考。具体税务处理请咨询专业税务顾问。", ln=True)

    def _add_section(self, pdf: FPDF, title: str, data: Dict[str, Any]):
        """添加普通数据节"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, title, ln=True)

        pdf.set_font("Helvetica", "", self.body_font_size)
        for key, value in data.items():
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"{key}: {value}")

    def _add_info_section(self, pdf: FPDF, title: str, data: Dict[str, Any]):
        """添加信息节（表格形式）"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, title, ln=True)

        pdf.set_font("Helvetica", "", self.body_font_size)
        pdf.set_fill_color(240, 240, 240)

        for key, value in data.items():
            pdf.set_x(self.margin + 5)
            pdf.cell(50, 6, f"{key}:", border=0)
            pdf.cell(0, 6, str(value), border=0, ln=True)

    def _add_text_section(self, pdf: FPDF, title: str, text: str):
        """添加文本节"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, title, ln=True)

        pdf.set_font("Helvetica", "", self.body_font_size)
        pdf.set_x(self.margin + 5)
        pdf.multi_cell(0, 5, text)

    def _format_tax_calculations(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化税务计算结果"""
        calculations = report_data.get("tax_calculations", [])
        if not calculations:
            return {"计算结果": "暂无数据"}

        result = {}
        for calc in calculations:
            tax_type = calc.get("tax_type", "未知税种")
            result[tax_type] = f"应税金额: ¥{calc.get('taxable_amount', 0):,.2f}, 税率: {calc.get('tax_rate', 0)*100:.1f}%, 税额: ¥{calc.get('calculated_tax', 0):,.2f}"

        return result

    def _add_policy_benefits(self, pdf: FPDF, policies: List[Dict[str, Any]]):
        """添加优惠政策部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "四、可享受的优惠政策", ln=True)

        if not policies:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "暂无匹配的优惠政策", ln=True)
            return

        for i, policy in enumerate(policies[:10], 1):
            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 6, f"{i}. {policy.get('policy_title', '未知政策')}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)
            details = [
                f"   来源: {policy.get('policy_source', 'N/A')}",
                f"   匹配级别: {policy.get('match_level', 'N/A')}",
                f"   适用性: {policy.get('applicability', 0)*100:.1f}%",
                f"   预估节省: ¥{policy.get('potential_savings', 0):,.2f}"
            ]
            for detail in details:
                pdf.set_x(self.margin + 5)
                pdf.cell(0, 5, detail, ln=True)

            conditions = policy.get("conditions", [])
            if conditions:
                pdf.set_x(self.margin + 5)
                pdf.cell(0, 5, f"   适用条件: {', '.join(conditions[:3])}", ln=True)

            pdf.ln(2)

    def _add_risk_assessment(self, pdf: FPDF, risks: List[Dict[str, Any]]):
        """添加风险评估部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "五、风险评估结果", ln=True)

        if not risks:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "未发现明显风险", ln=True)
            return

        for i, risk in enumerate(risks[:10], 1):
            severity = risk.get("severity", "low")
            severity_text = self._get_severity_text(severity)

            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 6, f"{i}. [{severity_text}] {risk.get('risk_type', '未知风险')}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"   描述: {risk.get('description', 'N/A')}")

            suggestions = risk.get("remediation_suggestions", [])
            if suggestions:
                pdf.set_x(self.margin + 5)
                pdf.cell(0, 5, f"   整改建议: {', '.join(suggestions[:2])}", ln=True)

            pdf.ln(2)

    def _add_optimization_suggestions(self, pdf: FPDF, suggestions: List[Dict[str, Any]]):
        """添加优化建议部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "七、优化建议", ln=True)

        if not suggestions:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "暂无优化建议", ln=True)
            return

        for i, suggestion in enumerate(suggestions[:5], 1):
            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin + 5)
            priority = self._get_priority_text(suggestion.get("priority", "medium"))
            pdf.cell(0, 6, f"{i}. [{priority}] {suggestion.get('category', '未知类别')}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"   现状: {suggestion.get('current_situation', 'N/A')}")

            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"   方案: {suggestion.get('optimization_approach', 'N/A')}")

            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, f"   预期收益: {suggestion.get('expected_benefits', 'N/A')}", ln=True)

            pdf.ln(2)

    def _add_anomalies_section(self, pdf: FPDF, anomalies: List[Dict[str, Any]]):
        """添加财务异常部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "二、财务异常检测", ln=True)

        if not anomalies:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "未检测到财务异常", ln=True)
            return

        for i, anomaly in enumerate(anomalies[:10], 1):
            severity = self._get_severity_text(anomaly.get("severity", "low"))
            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 6, f"{i}. [{severity}] {anomaly.get('anomaly_type', '未知异常')}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"   描述: {anomaly.get('description', 'N/A')}")

            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, f"   变化幅度: {anomaly.get('change_percentage', 0):.1f}%", ln=True)

            pdf.ln(2)

    def _add_trends_section(self, pdf: FPDF, trends: Dict[str, Any]):
        """添加趋势分析部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "三、趋势分析", ln=True)

        pdf.set_font("Helvetica", "", self.body_font_size)
        for key, value in trends.items():
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, f"{key}: {value}", ln=True)

    def _add_recommendations(self, pdf: FPDF, recommendations: List[str]):
        """添加建议部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "四、改进建议", ln=True)

        if not recommendations:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "暂无建议", ln=True)
            return

        for i, rec in enumerate(recommendations[:5], 1):
            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"{i}. {rec}")

    def _add_clauses_section(self, pdf: FPDF, clauses: List[Dict[str, Any]]):
        """添加合同条款部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "二、合同条款分析", ln=True)

        if not clauses:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "未提取到条款", ln=True)
            return

        for i, clause in enumerate(clauses[:10], 1):
            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 6, f"{i}. {clause.get('clause_type', '未知条款')}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"   内容: {clause.get('content', 'N/A')[:100]}...")

            risk_level = self._get_risk_level_text(clause.get("risk_level", "low"))
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, f"   风险等级: {risk_level}", ln=True)

            pdf.ln(2)

    def _add_risks_section(self, pdf: FPDF, risks: List[Dict[str, Any]]):
        """添加风险评估部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "三、风险评估", ln=True)

        if not risks:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "未发现明显风险", ln=True)
            return

        for i, risk in enumerate(risks[:10], 1):
            severity = self._get_severity_text(risk.get("severity", "low"))
            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 6, f"{i}. [{severity}] {risk.get('risk_type', '未知风险')}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"   描述: {risk.get('description', 'N/A')}")

            if risk.get("suggestions"):
                pdf.set_x(self.margin + 5)
                pdf.cell(0, 5, f"   建议: {risk['suggestions']}", ln=True)

            pdf.ln(2)

    def _add_findings_section(self, pdf: FPDF, findings: List[Dict[str, Any]]):
        """添加关键发现部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "四、关键发现", ln=True)

        if not findings:
            pdf.set_font("Helvetica", "I", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.cell(0, 5, "未发现关键问题", ln=True)
            return

        for i, finding in enumerate(findings[:5], 1):
            pdf.set_font("Helvetica", "", self.body_font_size)
            pdf.set_x(self.margin + 5)
            pdf.multi_cell(0, 5, f"{i}. {finding.get('description', 'N/A')}")

    def _get_severity_text(self, severity: str) -> str:
        """获取严重程度文本"""
        severity_map = {
            "high": "高风险",
            "medium": "中风险",
            "low": "低风险",
            "critical": "严重"
        }
        return severity_map.get(severity.lower(), severity)

    def _get_priority_text(self, priority: str) -> str:
        """获取优先级文本"""
        priority_map = {
            "high": "高优先级",
            "medium": "中优先级",
            "low": "低优先级"
        }
        return priority_map.get(priority.lower(), priority)

    def _get_risk_level_text(self, level: str) -> str:
        """获取风险等级文本"""
        level_map = {
            "high": "高风险",
            "medium": "中风险",
            "low": "低风险",
            "critical": "严重"
        }
        return level_map.get(level.lower(), level)

    def _format_datetime(self, dt: Any) -> str:
        """格式化日期时间"""
        if dt is None:
            return "N/A"
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except Exception:
                return dt
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt)

    def export_policy_report(self, report_data: Dict[str, Any]) -> bytes:
        """
        导出政策报告为 PDF

        Args:
            report_data: 政策报告数据

        Returns:
            PDF 文件的字节数据
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        self._add_header(pdf, "政策报告")

        export_info = {
            "导出时间": report_data.get("export_time", datetime.now().isoformat()),
            "政策总数": str(report_data.get("total_count", 0)),
            "查询条件": report_data.get("query", "所有政策"),
            "企业ID": report_data.get("enterprise_id", "N/A")
        }
        self._add_info_section(pdf, "报告信息", export_info)

        policies = report_data.get("policies", [])
        if policies:
            self._add_policies_section(pdf, policies)
        else:
            self._add_empty_section(pdf, "暂无政策数据")

        self._add_footer(pdf)

        return pdf.output()

    def _add_policies_section(self, pdf: FPDF, policies: List[Dict[str, Any]]):
        """添加政策列表部分"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", self.heading_font_size)
        pdf.set_x(self.margin)
        pdf.cell(0, 8, "一、政策列表", ln=True)

        for i, policy in enumerate(policies, 1):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", self.subheading_font_size)
            pdf.set_x(self.margin)
            pdf.cell(0, 6, f"{i}. {policy.get('policy_title', policy.get('title', '未知政策'))}", ln=True)

            pdf.set_font("Helvetica", "", self.body_font_size)

            details = []
            if policy.get("policy_source"):
                details.append(f"来源: {policy['policy_source']}")
            if policy.get("department"):
                details.append(f"发布部门: {policy['department']}")
            if policy.get("publish_date"):
                details.append(f"发布日期: {policy['publish_date']}")
            if policy.get("effective_date"):
                details.append(f"生效日期: {policy['effective_date']}")

            for detail in details:
                pdf.set_x(self.margin + 5)
                pdf.cell(0, 5, detail, ln=True)

            if policy.get("summary"):
                pdf.set_x(self.margin + 5)
                pdf.multi_cell(0, 5, f"摘要: {policy['summary'][:200]}{'...' if len(str(policy.get('summary', ''))) > 200 else ''}")

            if policy.get("tags"):
                tags = policy.get("tags", [])
                if isinstance(tags, list):
                    pdf.set_x(self.margin + 5)
                    pdf.cell(0, 5, f"标签: {', '.join(tags[:5])}", ln=True)

            match_score = policy.get("match_score")
            if match_score is not None:
                pdf.set_x(self.margin + 5)
                pdf.cell(0, 5, f"匹配度: {match_score * 100:.1f}%", ln=True)

            if policy.get("conditions"):
                conditions = policy.get("conditions", [])
                if isinstance(conditions, list) and conditions:
                    pdf.set_x(self.margin + 5)
                    pdf.cell(0, 5, f"适用条件: {', '.join(conditions[:3])}", ln=True)

            if policy.get("benefits"):
                benefits = policy.get("benefits", [])
                if isinstance(benefits, list) and benefits:
                    pdf.set_x(self.margin + 5)
                    pdf.cell(0, 5, f"政策优惠: {', '.join(benefits[:3])}", ln=True)

            pdf.ln(2)

            if pdf.get_y() > 250:
                pdf.add_page()
                pdf.set_font("Helvetica", "B", self.heading_font_size)
                pdf.set_x(self.margin)
                pdf.cell(0, 8, "（续）", ln=True)
                pdf.ln(3)

    def _add_empty_section(self, pdf: FPDF, message: str):
        """添加空数据提示"""
        pdf.ln(5)
        pdf.set_font("Helvetica", "I", self.body_font_size)
        pdf.set_x(self.margin + 5)
        pdf.cell(0, 5, message, ln=True)


pdf_export_service = PDFExportService()
