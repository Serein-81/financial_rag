"""
财务健康报告 MCP 工具

提供 Agent 可调用的财务健康分析工具
包含宏观体检、异常追踪、趋势阈值校验三个核心工具

工具类型：本地 STDIO（访问本地数据库）
"""

import logging
from typing import Optional, List, Dict, Any

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)


@local_tool(
    description="获取企业在特定周期的宏观财务健康快照，返回核心骨架数据（总营收、净利润、健康分等）"
)
async def get_financial_health_snapshot(
    tenant_id: str,
    period_type: str = "monthly",
    target_date: str = None,
) -> Dict[str, Any]:
    """
    获取宏观财务健康快照

    当你需要回答"公司整体经营状况如何"、"利润和营收总额是多少"时，
    必须首先调用此工具。返回值已剥离冗余噪音，仅包含关键指标。

    Args:
        tenant_id: 租户ID，必填，用于数据隔离
        period_type: 周期类型，仅允许: monthly, quarterly, yearly
        target_date: 目标日期，格式 YYYY-MM-DD，默认为当前日期

    Returns:
        包含核心财务指标的字典

    Example:
        get_financial_health_snapshot(tenant_id="xxx", period_type="monthly", target_date="2026-03-31")
    """
    if period_type not in ["monthly", "quarterly", "yearly"]:
        return {
            "status": "error",
            "error": "INVALID_PERIOD_TYPE",
            "message": "period_type 仅允许: monthly, quarterly, yearly"
        }

    try:
        from sqlalchemy import select, and_, func
        from sqlalchemy.dialects.postgresql import JSONB
        from app.db.session import get_db_context
        from app.models.financial_health import FinancialHealthReport

        async with get_db_context() as session:
            query = select(
                FinancialHealthReport.overall_health_score,
                FinancialHealthReport.health_status,
            ).where(
                and_(
                    FinancialHealthReport.tenant_id == tenant_id,
                    FinancialHealthReport.report_period == period_type,
                    FinancialHealthReport.status == "completed"
                )
            ).order_by(
                FinancialHealthReport.period_end.desc()
            ).limit(1)

            result = await session.execute(query)
            row = result.first()

            if not row:
                return {
                    "status": "error",
                    "error": "REPORT_NOT_FOUND",
                    "message": f"该租户在 {period_type} 周期未生成财务健康报告"
                }

            query2 = select(
                func.jsonb_extract_path_text(
                    FinancialHealthReport.revenue_summary, "total_revenue"
                ).label("total_revenue"),
                func.jsonb_extract_path_text(
                    FinancialHealthReport.profit_summary, "net_profit"
                ).label("net_profit"),
                func.jsonb_extract_path_text(
                    FinancialHealthReport.cash_flow_summary, "operating_cash_flow"
                ).label("operating_cash_flow"),
            ).where(
                and_(
                    FinancialHealthReport.tenant_id == tenant_id,
                    FinancialHealthReport.report_period == period_type,
                    FinancialHealthReport.status == "completed"
                )
            ).order_by(
                FinancialHealthReport.period_end.desc()
            ).limit(1)

            result2 = await session.execute(query2)
            row2 = result2.first()

            return {
                "status": "success",
                "overall_health_score": row.overall_health_score,
                "health_status": str(row.health_status.value) if row.health_status else "unknown",
                "total_revenue": float(row2.total_revenue) if row2 and row2.total_revenue else None,
                "net_profit": float(row2.net_profit) if row2 and row2.net_profit else None,
                "operating_cash_flow": float(row2.operating_cash_flow) if row2 and row2.operating_cash_flow else None,
                "period_type": period_type,
                "message": f"健康分: {row.overall_health_score}, 状态: {row.health_status.value if row.health_status else 'unknown'}"
            }

    except Exception as e:
        logger.error(f"获取财务健康快照失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "QUERY_FAILED",
            "message": f"查询失败: {str(e)}"
        }


@local_tool(
    description="追踪高危财务异常记录，当企业健康状况不佳时用于分析具体风险点"
)
async def get_critical_anomalies(
    tenant_id: str,
    severity_level: str = "high",
    limit: int = 5,
) -> Dict[str, Any]:
    """
    追踪财务异常记录

    当发现企业健康状况不佳，需要分析具体风险点时调用此工具。
    严禁自行猜测风险，必须以此工具返回的描述和偏差值(deviation)为准。

    Args:
        tenant_id: 租户ID，必填
        severity_level: 严重程度，仅允许: critical, high, medium, low
        limit: 最大返回记录数，默认5

    Returns:
        包含异常记录的字典

    Example:
        get_critical_anomalies(tenant_id="xxx", severity_level="high")
    """
    if severity_level not in ["critical", "high", "medium", "low"]:
        return {
            "status": "error",
            "error": "INVALID_SEVERITY",
            "message": "severity_level 仅允许: critical, high, medium, low"
        }

    if severity_level == "low":
        return {
            "status": "info",
            "message": "作为高管幕僚，请优先关注 critical 和 high 级别的风险"
        }

    try:
        from sqlalchemy import select, and_, desc
        from app.db.session import get_db_context
        from app.models.financial_health import FinancialAnomalyRecord

        async with get_db_context() as session:
            query = select(
                FinancialAnomalyRecord.anomaly_category,
                FinancialAnomalyRecord.title,
                FinancialAnomalyRecord.description,
                FinancialAnomalyRecord.severity,
                FinancialAnomalyRecord.detected_value,
                FinancialAnomalyRecord.expected_value,
                FinancialAnomalyRecord.deviation,
                FinancialAnomalyRecord.recommended_actions,
            ).where(
                and_(
                    FinancialAnomalyRecord.tenant_id == tenant_id,
                    FinancialAnomalyRecord.severity == severity_level,
                    FinancialAnomalyRecord.status == "detected",
                    FinancialAnomalyRecord.acknowledged == False
                )
            ).order_by(
                desc(FinancialAnomalyRecord.confidence)
            ).limit(limit)

            result = await session.execute(query)
            rows = result.all()

            if not rows:
                return {
                    "status": "success",
                    "data": [],
                    "count": 0,
                    "message": f"未检测到未处理的 {severity_level} 级别异常"
                }

            anomalies = []
            for row in rows:
                anomalies.append({
                    "anomaly_category": row.anomaly_category,
                    "title": row.title,
                    "description": row.description,
                    "severity": row.severity,
                    "detected_value": row.detected_value,
                    "expected_value": row.expected_value,
                    "deviation": row.deviation,
                    "recommended_actions": row.recommended_actions
                })

            return {
                "status": "success",
                "data": anomalies,
                "count": len(anomalies),
                "message": f"发现 {len(anomalies)} 条 {severity_level} 级别异常"
            }

    except Exception as e:
        logger.error(f"获取异常记录失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "QUERY_FAILED",
            "message": f"查询失败: {str(e)}"
        }


@local_tool(
    description="查询财务指标历史趋势并与安全阈值红线对比，直接返回安全状态判定"
)
async def analyze_metric_safety_trend(
    tenant_id: str,
    metric_name: str,
    months_back: int = 6,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    趋势与红线校验分析

    查询单一财务指标的历史趋势，并自动与系统的安全阈值红线进行对比。
    数据库层完成 JOIN 和安全状态判定，LLM 无需自行判断指标好坏。

    Args:
        tenant_id: 租户ID，必填
        metric_name: 指标名称，如: current_ratio, monthly_revenue, gross_margin
        months_back: 向前回溯的月数，默认6
        limit: 最大返回记录数，默认20

    Returns:
        包含趋势数据和安全性判定的字典

    Example:
        analyze_metric_safety_trend(tenant_id="xxx", metric_name="current_ratio", months_back=6)
    """
    try:
        from sqlalchemy import select, and_, text
        from app.db.session import get_db_context

        async with get_db_context() as session:
            query = text("""
                SELECT 
                    t.record_date,
                    t.metric_value,
                    t.metric_unit,
                    th.warning_threshold,
                    th.critical_threshold,
                    CASE
                        WHEN th.comparison_operator = '>' AND t.metric_value < th.critical_threshold THEN 'CRITICAL_DANGER'
                        WHEN th.comparison_operator = '<' AND t.metric_value > th.critical_threshold THEN 'CRITICAL_DANGER'
                        WHEN th.comparison_operator = '>' AND t.metric_value < th.warning_threshold THEN 'WARNING'
                        WHEN th.comparison_operator = '<' AND t.metric_value > th.warning_threshold THEN 'WARNING'
                        ELSE 'SAFE'
                    END as safety_status
                FROM financial_trend_data t
                LEFT JOIN financial_thresholds th
                    ON t.tenant_id = th.tenant_id AND t.metric_name = th.metric_name
                WHERE t.tenant_id = :tenant_id
                  AND t.metric_name = :metric_name
                  AND t.record_date >= NOW() - INTERVAL '1 month' * :months_back
                ORDER BY t.record_date ASC
                LIMIT :limit
            """)

            result = await session.execute(query, {
                "tenant_id": tenant_id,
                "metric_name": metric_name,
                "months_back": months_back,
                "limit": limit
            })
            rows = result.fetchall()

            if not rows:
                return {
                    "status": "error",
                    "error": "NO_DATA",
                    "message": f"未找到指标 {metric_name} 的历史趋势数据"
                }

            trend_data = []
            safe_count = 0
            warning_count = 0
            critical_count = 0

            for row in rows:
                trend_data.append({
                    "record_date": str(row[0]) if row[0] else None,
                    "metric_value": float(row[1]) if row[1] else None,
                    "metric_unit": row[2],
                    "warning_threshold": float(row[3]) if row[3] else None,
                    "critical_threshold": float(row[4]) if row[4] else None,
                    "safety_status": row[5]
                })

                if row[5] == "SAFE":
                    safe_count += 1
                elif row[5] == "WARNING":
                    warning_count += 1
                elif row[5] == "CRITICAL_DANGER":
                    critical_count += 1

            return {
                "status": "success",
                "metric_name": metric_name,
                "trend_data": trend_data,
                "summary": {
                    "total_records": len(trend_data),
                    "safe_count": safe_count,
                    "warning_count": warning_count,
                    "critical_count": critical_count,
                    "overall_status": "CRITICAL" if critical_count > 0 else "WARNING" if warning_count > 0 else "SAFE"
                },
                "message": f"指标 {metric_name}: 安全 {safe_count} 次, 警告 {warning_count} 次, 危险 {critical_count} 次"
            }

    except Exception as e:
        logger.error(f"分析指标安全趋势失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "QUERY_FAILED",
            "message": f"查询失败: {str(e)}"
        }


def create_financial_health_tools():
    """创建财务健康工具列表"""
    return [
        get_financial_health_snapshot,
        get_critical_anomalies,
        analyze_metric_safety_trend,
    ]