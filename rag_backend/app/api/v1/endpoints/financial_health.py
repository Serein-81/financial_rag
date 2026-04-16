"""
财务健康智能监控 API 端点
提供财务异常检测和预警的 RESTful 接口
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from io import BytesIO

from app.api.deps import get_current_user, CurrentUser
from app.schemas.financial_health import (
    FinancialHealthMonitorRequest,
    AnomalyQueryResponse,
    AnomalyActionRequest,
    AnomalyActionResponse,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
    AlertSubscriptionRequest,
    AlertSubscriptionResponse,
    AnomalyType,
    SeverityLevel,
    AnomalyStatus,
)
from app.services.financial_health_service import FinancialHealthService
from app.services.pdf_export_service import pdf_export_service

router = APIRouter(prefix="/financial-health", tags=["财务健康监控"])
logger = logging.getLogger(__name__)

financial_health_service = FinancialHealthService()


@router.post("/monitor")
async def monitor_financial_health(
    request: FinancialHealthMonitorRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    手动触发财务健康检查

    功能：
    - 生成财务健康仪表盘
    - 检测财务异常
    - 提供健康评分
    - 评估各项财务指标
    """
    try:
        if not request.user_id:
            request.user_id = str(user.id)
        if not request.tenant_id:
            request.tenant_id = user.tenant_id

        result = await financial_health_service.monitor_financial_health(request)

        dashboard_obj = result.get("dashboard")
        if hasattr(dashboard_obj, 'model_dump'):
            dashboard = dashboard_obj.model_dump()
        elif isinstance(dashboard_obj, dict):
            dashboard = dashboard_obj
        else:
            dashboard = {}

        financial_data = result.get("financial_data", {})
        logger.info(f"🔍 [API] financial_data keys: {list(financial_data.keys()) if financial_data else 'empty'}")
        logger.info(f"🔍 [API] total_revenue: {financial_data.get('total_revenue', 'NOT FOUND')}")
        has_financial_data = bool(financial_data and financial_data.get("total_revenue", 0) > 0)

        flat_response = {
            "report_id": result.get("monitor_id", ""),
            "tenant_id": request.tenant_id,
            "period_start": str(request.period_start),
            "period_end": str(request.period_end),
            "overall_health_score": dashboard.get("overall_health_score", 0),
            "health_status": dashboard.get("health_status", "unknown"),
            "data_available": has_financial_data,
            "data_unavailable_message": "财务数据功能暂时不可用，请先录入财务数据" if not has_financial_data else None,
            "revenue_summary": {
                "total_revenue": financial_data.get("total_revenue", 0),
                "revenue_growth": dashboard.get("revenue_summary", {}).get("revenue_growth", 0),
                "trend": "stable"
            },
            "expense_summary": {
                "total_expenses": financial_data.get("total_expenses", 0),
                "breakdown": {}
            },
            "profit_summary": {
                "net_profit": financial_data.get("taxable_income", 0),
                "profit_margin": dashboard.get("profit_summary", {}).get("profit_margin", 0)
            },
            "cash_flow_summary": dashboard.get("cash_flow_summary", {}) or {
                "inflow": 0,
                "outflow": 0,
                "net_flow": 0
            },
            "financial_metrics": dashboard.get("key_metrics", []),
            "anomalies_detected": result.get("anomalies_detected", []),
            "trend_indicators": [],
            "recommendations": [],
            "generated_at": result.get("generated_at", datetime.now().isoformat())
        }

        return flat_response

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 财务健康监控数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"监控数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 财务健康监控IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"监控IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 财务健康监控失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"监控失败: {str(e)}")


@router.get("/dashboard")
async def get_financial_health_dashboard(
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取财务健康仪表盘
    
    返回最新的财务健康状态概览
    """
    try:
        from datetime import datetime, timedelta
        
        request = FinancialHealthMonitorRequest(
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            period_start=datetime.now().date() - timedelta(days=90),
            period_end=datetime.now().date(),
            include_anomaly_detection=True,
            include_trend_analysis=True
        )
        
        result = await financial_health_service.monitor_financial_health(request)
        
        return result.get("dashboard", {})
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取仪表盘数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取仪表盘IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取仪表盘失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/anomalies", response_model=AnomalyQueryResponse)
async def query_anomalies(
    anomaly_types: Optional[str] = Query(None, description="异常类型，逗号分隔"),
    severity_levels: Optional[str] = Query(None, description="严重程度，逗号分隔"),
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    查询财务异常列表
    
    支持按类型、严重程度和状态筛选
    """
    try:
        types_list = None
        if anomaly_types:
            types_list = [AnomalyType(t) for t in anomaly_types.split(",")]
        
        levels_list = None
        if severity_levels:
            levels_list = [SeverityLevel(l) for l in severity_levels.split(",")]
        
        status_enum = None
        if status:
            status_enum = AnomalyStatus(status)
        
        result = await financial_health_service.query_anomalies(
            tenant_id=user.tenant_id,
            anomaly_types=types_list,
            severity_levels=levels_list,
            status=status_enum,
            limit=limit
        )
        
        return AnomalyQueryResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 查询异常数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"查询数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 查询异常IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 查询异常失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/anomalies/action", response_model=AnomalyActionResponse)
async def perform_anomaly_action(
    request: AnomalyActionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    对异常执行操作
    
    支持的操作：
    - acknowledge: 确认异常
    - resolve: 标记为已解决
    - dismiss: 驳回异常
    """
    try:
        if request.action not in ["acknowledge", "resolve", "dismiss"]:
            raise HTTPException(status_code=400, detail="不支持的操作类型")
        
        new_status_map = {
            "acknowledge": AnomalyStatus.ACKNOWLEDGED,
            "resolve": AnomalyStatus.RESOLVED,
            "dismiss": AnomalyStatus.DISMISSED
        }
        
        return AnomalyActionResponse(
            anomaly_id=request.anomaly_id,
            action=request.action,
            new_status=new_status_map[request.action],
            updated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 操作数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"操作数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 操作IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"操作IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 操作失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.post("/trend", response_model=TrendAnalysisResponse)
async def analyze_financial_trend(
    request: TrendAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    分析财务趋势
    
    支持的指标：
    - revenue: 收入
    - profit: 利润
    - cash_flow: 现金流
    - margin: 毛利率
    - cost: 成本
    
    期间类型：monthly/quarterly/annual
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await financial_health_service.perform_trend_analysis(request)
        
        return TrendAnalysisResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 趋势分析数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"分析数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 趋势分析IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 趋势分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/subscribe", response_model=AlertSubscriptionResponse)
async def subscribe_alerts(
    request: AlertSubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    订阅异常预警推送
    
    通知渠道：
    - in_app: 应用内通知
    - email: 邮件通知
    - sms: 短信通知
    - webhook: Webhook通知
    
    通知频率：
    - real_time: 实时
    - daily: 每日汇总
    - weekly: 每周汇总
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await financial_health_service.subscribe_alerts(request)
        
        return AlertSubscriptionResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 订阅数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"订阅数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 订阅IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"订阅IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"订阅失败: {str(e)}")


@router.get("/report/export")
async def export_financial_health_report_pdf(
    period_days: int = Query(90, ge=30, le=365, description="报告周期（天数）"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    导出财务健康报告为 PDF
    
    根据指定周期生成财务健康报告 PDF
    
    Args:
        period_days: 报告周期，默认90天
        
    Returns:
        PDF 文件的流式响应
    """
    try:
        from datetime import timedelta
        
        request = FinancialHealthMonitorRequest(
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            period_start=datetime.now().date() - timedelta(days=period_days),
            period_end=datetime.now().date(),
            include_anomaly_detection=True,
            include_trend_analysis=True
        )
        
        report_data = await financial_health_service.monitor_financial_health(request)
        
        pdf_bytes = pdf_export_service.export_financial_health_report(report_data)
        
        filename = f"financial_health_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ PDF导出数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"PDF导出数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ PDF导出IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF导出IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ PDF导出失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF导出失败: {str(e)}")


@router.get("/history")
async def get_analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取财务健康分析历史记录
    """
    try:
        result = await financial_health_service.get_analysis_history(
            user_id=str(user.id),
            tenant_id=user.tenant_id,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        logger.error(f"❌ 获取财务健康历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取财务健康历史失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "financial_health",
        "version": "1.0.0"
    }
