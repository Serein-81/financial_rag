"""
Harness 报告生成器模块
"""

from .html_reporter import HTMLReporter, generate_html_report

__all__ = [
    "HTMLReporter",
    "generate_html_report"
]
