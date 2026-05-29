"""
HTML 报告生成器

生成可视化的评估报告。
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from tests.harness.runner import EvaluationReport

logger = logging.getLogger(__name__)


class HTMLReporter:
    """
    HTML 报告生成器

    生成美观的HTML评估报告。
    """

    def __init__(self, output_dir: str = "tests/harness/reports"):
        """
        初始化生成器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        report: EvaluationReport,
        filename: Optional[str] = None
    ) -> str:
        """
        生成 HTML 报告

        Args:
            report: 评估报告
            filename: 文件名（可选，默认自动生成）

        Returns:
            生成的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.html"

        file_path = self.output_dir / filename

        logger.info(f"[HTMLReporter] 生成 HTML 报告: {file_path}")

        html_content = self._build_html(report)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"[HTMLReporter] 报告生成完成")

        return str(file_path)

    def _build_html(self, report: EvaluationReport) -> str:
        """
        构建 HTML 内容

        Args:
            report: 评估报告

        Returns:
            HTML 字符串
        """
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG 评估报告 - {report.dataset_name}</title>
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    <div class="container">
        {self._build_header(report)}
        {self._build_summary(report)}
        {self._build_retrieval_section(report)}
        {self._build_generation_section(report)}
        {self._build_performance_section(report)}
        {self._build_difficulty_section(report)}
        {self._build_category_section(report)}
        {self._build_details_section(report)}
    </div>
</body>
</html>
"""
        return html

    def _get_css(self) -> str:
        """获取 CSS 样式"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header .meta {
            opacity: 0.9;
            font-size: 1.1em;
        }

        .section {
            background: white;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .section-title {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .stat-card {
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 8px;
            text-align: center;
        }

        .stat-card .label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 8px;
        }

        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid #eee;
        }

        .metric-row:last-child {
            border-bottom: none;
        }

        .metric-label {
            font-weight: 500;
            color: #555;
        }

        .metric-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #667eea;
        }

        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            transition: width 0.3s ease;
        }

        .result-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }

        .result-table th,
        .result-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }

        .result-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #555;
        }

        .result-table tr:hover {
            background: #f8f9fa;
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .badge-easy {
            background: #d4edda;
            color: #155724;
        }

        .badge-medium {
            background: #fff3cd;
            color: #856404;
        }

        .badge-hard {
            background: #f8d7da;
            color: #721c24;
        }

        .badge-success {
            background: #d4edda;
            color: #155724;
        }

        .badge-fail {
            background: #f8d7da;
            color: #721c24;
        }
        """

    def _build_header(self, report: EvaluationReport) -> str:
        """构建标题部分"""
        return f"""
        <div class="header">
            <h1>🎯 RAG 系统评估报告</h1>
            <div class="meta">
                <div>数据集: {report.dataset_name} v{report.dataset_version}</div>
                <div>评估时间: {report.evaluation_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
                <div>测试用例: {report.total_cases} 个 | 成功: {report.successful_cases} | 失败: {report.failed_cases}</div>
            </div>
        </div>
        """

    def _build_summary(self, report: EvaluationReport) -> str:
        """构建概览部分"""
        success_rate = (report.successful_cases / report.total_cases * 100) if report.total_cases > 0 else 0

        return f"""
        <div class="section">
            <h2 class="section-title">📊 概览</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">成功率</div>
                    <div class="value">{success_rate:.1f}%</div>
                </div>
                <div class="stat-card">
                    <div class="label">Recall@5</div>
                    <div class="value">{report.avg_retrieval_metrics.recall_at_k.get(5, 0):.3f}</div>
                </div>
                <div class="stat-card">
                    <div class="label">生成评分</div>
                    <div class="value">{report.avg_generation_metrics.overall_score:.2f}/5</div>
                </div>
                <div class="stat-card">
                    <div class="label">平均时间</div>
                    <div class="value">{report.avg_total_time_ms:.0f}ms</div>
                </div>
            </div>
        </div>
        """

    def _build_retrieval_section(self, report: EvaluationReport) -> str:
        """构建检索评估部分"""
        metrics = report.avg_retrieval_metrics

        recall_5 = metrics.recall_at_k.get(5, 0)
        precision_5 = metrics.precision_at_k.get(5, 0)
        ndcg_5 = metrics.ndcg_at_k.get(5, 0)

        return f"""
        <div class="section">
            <h2 class="section-title">🔍 检索评估</h2>

            <div class="metric-row">
                <span class="metric-label">Recall@5</span>
                <span class="metric-value">{recall_5:.4f}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {recall_5 * 100}%">{recall_5:.2%}</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">Precision@5</span>
                <span class="metric-value">{precision_5:.4f}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {precision_5 * 100}%">{precision_5:.2%}</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">NDCG@5</span>
                <span class="metric-value">{ndcg_5:.4f}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {ndcg_5 * 100}%">{ndcg_5:.2%}</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">MRR</span>
                <span class="metric-value">{metrics.mrr:.4f}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.mrr * 100}%">{metrics.mrr:.2%}</div>
            </div>
        </div>
        """

    def _build_generation_section(self, report: EvaluationReport) -> str:
        """构建生成评估部分"""
        metrics = report.avg_generation_metrics

        return f"""
        <div class="section">
            <h2 class="section-title">✨ 生成评估</h2>

            <div class="metric-row">
                <span class="metric-label">准确性 (Accuracy)</span>
                <span class="metric-value">{metrics.accuracy_score:.2f}/5</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.accuracy_score / 5 * 100}%">{metrics.accuracy_score:.2f}/5</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">完整性 (Completeness)</span>
                <span class="metric-value">{metrics.completeness_score:.2f}/5</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.completeness_score / 5 * 100}%">{metrics.completeness_score:.2f}/5</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">相关性 (Relevance)</span>
                <span class="metric-value">{metrics.relevance_score:.2f}/5</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.relevance_score / 5 * 100}%">{metrics.relevance_score:.2f}/5</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">流畅性 (Fluency)</span>
                <span class="metric-value">{metrics.fluency_score:.2f}/5</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.fluency_score / 5 * 100}%">{metrics.fluency_score:.2f}/5</div>
            </div>

            <div class="metric-row">
                <span class="metric-label">综合评分 (Overall)</span>
                <span class="metric-value">{metrics.overall_score:.2f}/5</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {metrics.overall_score / 5 * 100}%">{metrics.overall_score:.2f}/5</div>
            </div>
        </div>
        """

    def _build_performance_section(self, report: EvaluationReport) -> str:
        """构建性能统计部分"""
        return f"""
        <div class="section">
            <h2 class="section-title">⚡ 性能统计</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">平均检索时间</div>
                    <div class="value">{report.avg_retrieval_time_ms:.0f}ms</div>
                </div>
                <div class="stat-card">
                    <div class="label">平均生成时间</div>
                    <div class="value">{report.avg_generation_time_ms:.0f}ms</div>
                </div>
                <div class="stat-card">
                    <div class="label">平均总时间</div>
                    <div class="value">{report.avg_total_time_ms:.0f}ms</div>
                </div>
            </div>
        </div>
        """

    def _build_difficulty_section(self, report: EvaluationReport) -> str:
        """构建难度统计部分"""
        if not report.by_difficulty:
            return ""

        rows = ""
        for difficulty, stats in report.by_difficulty.items():
            rows += f"""
            <tr>
                <td><span class="badge badge-{difficulty}">{difficulty}</span></td>
                <td>{stats['count']}</td>
                <td>{stats['avg_recall_at_5']:.3f}</td>
                <td>{stats['avg_overall_score']:.2f}/5</td>
                <td>{stats['avg_total_time_ms']:.0f}ms</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2 class="section-title">📈 按难度统计</h2>
            <table class="result-table">
                <thead>
                    <tr>
                        <th>难度</th>
                        <th>数量</th>
                        <th>Recall@5</th>
                        <th>生成评分</th>
                        <th>平均时间</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def _build_category_section(self, report: EvaluationReport) -> str:
        """构建类别统计部分"""
        if not report.by_category:
            return ""

        rows = ""
        for category, stats in report.by_category.items():
            rows += f"""
            <tr>
                <td>{category}</td>
                <td>{stats['count']}</td>
                <td>{stats['avg_recall_at_5']:.3f}</td>
                <td>{stats['avg_overall_score']:.2f}/5</td>
                <td>{stats['avg_total_time_ms']:.0f}ms</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2 class="section-title">🏷️ 按类别统计</h2>
            <table class="result-table">
                <thead>
                    <tr>
                        <th>类别</th>
                        <th>数量</th>
                        <th>Recall@5</th>
                        <th>生成评分</th>
                        <th>平均时间</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def _build_details_section(self, report: EvaluationReport) -> str:
        """构建详细结果部分"""
        rows = ""
        for result in report.results[:20]:  # 只显示前20个
            status_badge = 'badge-success' if result.success else 'badge-fail'
            status_text = '✓' if result.success else '✗'
            difficulty_badge = f'badge-{result.difficulty}'

            rows += f"""
            <tr>
                <td>{result.test_case_id}</td>
                <td>{result.query[:50]}...</td>
                <td><span class="badge {difficulty_badge}">{result.difficulty}</span></td>
                <td><span class="badge {status_badge}">{status_text}</span></td>
                <td>{result.retrieval_metrics.recall_at_k.get(5, 0):.2f}</td>
                <td>{result.generation_metrics.overall_score:.2f}/5</td>
                <td>{result.total_time_ms:.0f}ms</td>
            </tr>
            """

        return f"""
        <div class="section">
            <h2 class="section-title">📋 详细结果 (前20个)</h2>
            <table class="result-table">
                <thead>
                    <tr>
                        <th>用例ID</th>
                        <th>查询</th>
                        <th>难度</th>
                        <th>状态</th>
                        <th>Recall@5</th>
                        <th>生成评分</th>
                        <th>时间</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """


# 辅助函数

def generate_html_report(
    report: EvaluationReport,
    output_dir: str = "tests/harness/reports",
    filename: Optional[str] = None
) -> str:
    """
    生成 HTML 报告（快捷函数）

    Args:
        report: 评估报告
        output_dir: 输出目录
        filename: 文件名

    Returns:
        生成的文件路径
    """
    reporter = HTMLReporter(output_dir=output_dir)
    return reporter.generate(report, filename=filename)
