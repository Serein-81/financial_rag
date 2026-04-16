# app/multi_agent_system/report_exporters.py
"""
报告导出器 - Phase 7
支持多种格式输出（JSON、Markdown、HTML）
"""
from pathlib import Path

from .agents.report_generator import AuditReport
from .report_templates import ReportTemplates, ReportType


class ReportExporter:
    """报告导出器"""
    
    def __init__(self):
        self.templates = ReportTemplates()
        print("[报告导出器] 初始化完成")
    
    def export_json(self, report: AuditReport) -> str:
        """导出为 JSON 格式"""
        return report.to_json()
    
    def export_markdown(
        self, 
        report: AuditReport,
        report_type: ReportType = ReportType.STANDARD
    ) -> str:
        """导出为 Markdown 格式"""
        data = report.to_dict()
        return self.templates.render(report_type, data)
    
    def export_html(
        self, 
        report: AuditReport,
        report_type: ReportType = ReportType.STANDARD
    ) -> str:
        """导出为 HTML 格式"""
        # 先生成 Markdown
        markdown_content = self.export_markdown(report, report_type)
        
        # 简单的 Markdown 到 HTML 转换
        html_content = self._markdown_to_html(markdown_content)
        
        # 包装在 HTML 模板中
        return self._wrap_html(html_content, report.task_id)
    
    def save_to_file(
        self, 
        content: str, 
        filepath: str
    ) -> str:
        """保存到文件"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[报告导出器] 已保存到: {filepath}")
        return str(path.absolute())
    
    def _markdown_to_html(self, markdown: str) -> str:
        """简单的 Markdown 到 HTML 转换"""
        html = markdown
        
        # 标题转换
        html = html.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)
        html = html.replace('## ', '<h2>').replace('\n', '</h2>\n')
        html = html.replace('### ', '<h3>').replace('\n', '</h3>\n')
        html = html.replace('#### ', '<h4>').replace('\n', '</h4>\n')
        
        # 列表转换
        lines = html.split('\n')
        in_list = False
        result = []
        
        for line in lines:
            if line.strip().startswith('- '):
                if not in_list:
                    result.append('<ul>')
                    in_list = True
                result.append(f'<li>{line.strip()[2:]}</li>')
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                result.append(line)
        
        if in_list:
            result.append('</ul>')
        
        html = '\n'.join(result)
        
        # 段落转换
        html = html.replace('\n\n', '</p><p>')
        
        return html
    
    def _wrap_html(self, content: str, title: str) -> str:
        """包装 HTML 内容"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>审查报告 - {title}</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        h3 {{
            color: #7f8c8d;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        li {{
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        li:before {{
            content: "▸ ";
            color: #3498db;
            font-weight: bold;
        }}
        .risk-high {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .risk-medium {{
            color: #f39c12;
            font-weight: bold;
        }}
        .risk-low {{
            color: #27ae60;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>"""


# 导出
__all__ = ['ReportExporter']
