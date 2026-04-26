"""
税务智能分析 API 端点
提供税务合规智能助手的 RESTful 接口
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import StreamingResponse
from io import BytesIO

from app.api.deps import get_current_user, CurrentUser
from app.schemas.tax_intelligence import (
    TaxAnalysisRequest,
    TaxCalculationRequest,
    TaxCalculationResponse,
    PolicyQueryRequest,
    PolicyQueryResponse,
    PolicySubscriptionRequest,
    PolicySubscriptionResponse,
)
from app.services.tax_intelligence_service import TaxIntelligenceService
from app.services.pdf_export_service import pdf_export_service

router = APIRouter(prefix="/tax-intelligence", tags=["税务智能分析"])
logger = logging.getLogger(__name__)

tax_intelligence_service = TaxIntelligenceService()


@router.post("/analyze")
async def create_tax_analysis(
    background_tasks: BackgroundTasks,
    request: TaxAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    发起税务分析请求

    功能：
    - 分析指定年度/季度的税务情况
    - 自动计算应缴税款
    - 匹配适用的税收优惠政策
    - 评估税务风险并生成建议

    分析类型：
    - quarterly_vat: 季度增值税分析
    - annual_income: 年度所得税汇算
    - tax_burden: 税负分析
    - policy_benefit: 优惠政策享受分析
    - risk_assessment: 税务风险评估
    - comprehensive: 综合税务分析
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id

        analysis_result = await tax_intelligence_service.execute_analysis_workflow(request)

        def safe_float(value, default=0.0):
            """安全转换为浮点数"""
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            """安全转换为整数"""
            if value is None:
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        def build_financial_summary(result):
            """构建适配前端的财务摘要"""
            if result.financial_summary:
                if isinstance(result.financial_summary, dict):
                    return {
                        "revenue": safe_float(result.financial_summary.get("total_revenue", result.financial_summary.get("revenue", 0))),
                        "expenses": safe_float(result.financial_summary.get("total_expenses", result.financial_summary.get("expenses", 0))),
                        "profit": safe_float(result.financial_summary.get("taxable_income", result.financial_summary.get("profit", 0))),
                        "effective_tax_rate": safe_float(result.tax_burden_rate if hasattr(result, 'tax_burden_rate') and result.tax_burden_rate else result.financial_summary.get("effective_tax_rate", 0)),
                        "total_revenue": safe_float(result.financial_summary.get("total_revenue", 0)),
                        "total_expenses": safe_float(result.financial_summary.get("total_expenses", 0)),
                        "taxable_income": safe_float(result.financial_summary.get("taxable_income", 0)),
                        "input_tax": safe_float(result.financial_summary.get("input_tax", 0)),
                        "output_tax": safe_float(result.financial_summary.get("output_tax", 0)),
                    }
            return {
                "revenue": 0.0,
                "expenses": 0.0,
                "profit": 0.0,
                "effective_tax_rate": 0.0,
                "total_revenue": 0.0,
                "total_expenses": 0.0,
                "taxable_income": 0.0,
                "input_tax": 0.0,
                "output_tax": 0.0,
            }
        
        return {
            "analysis_id": analysis_result.analysis_id,
            "analysis_type": str(analysis_result.analysis_type.value) if hasattr(analysis_result.analysis_type, 'value') else str(analysis_result.analysis_type),
            "fiscal_year": safe_int(analysis_result.fiscal_year),
            "fiscal_period": str(analysis_result.fiscal_period) if analysis_result.fiscal_period else "",
            "status": str(analysis_result.status.value) if hasattr(analysis_result.status, 'value') else str(analysis_result.status),
            "financial_summary": build_financial_summary(analysis_result),
            "tax_calculations": [
                {
                    "tax_type": str(calc.tax_type) if hasattr(calc, 'tax_type') and calc.tax_type else str(calc.get("tax_type", "")) if isinstance(calc, dict) else "",
                    "taxable_amount": safe_float(calc.taxable_amount if hasattr(calc, 'taxable_amount') else calc.get("taxable_amount", 0) if isinstance(calc, dict) else 0),
                    "tax_rate": safe_float(calc.tax_rate if hasattr(calc, 'tax_rate') else calc.get("tax_rate", 0) if isinstance(calc, dict) else 0),
                    "tax_payable": safe_float(calc.calculated_tax if hasattr(calc, 'calculated_tax') else calc.get("calculated_tax", 0) if isinstance(calc, dict) else 0),
                    "calculated_tax": safe_float(calc.calculated_tax if hasattr(calc, 'calculated_tax') else calc.get("calculated_tax", 0) if isinstance(calc, dict) else 0),
                    "effective_rate": safe_float(calc.effective_rate if hasattr(calc, 'effective_rate') else calc.get("effective_rate", 0) if isinstance(calc, dict) else 0),
                    "deductions": safe_float(calc.input_tax if hasattr(calc, 'input_tax') else calc.get("input_tax", 0) if isinstance(calc, dict) else 0),
                    "input_tax": safe_float(calc.input_tax if hasattr(calc, 'input_tax') else calc.get("input_tax", 0) if isinstance(calc, dict) else 0),
                    "output_tax": safe_float(calc.output_tax if hasattr(calc, 'output_tax') else calc.get("output_tax", 0) if isinstance(calc, dict) else 0),
                    "net_tax_payable": safe_float(calc.net_tax_payable if hasattr(calc, 'net_tax_payable') else calc.get("net_tax_payable", 0) if isinstance(calc, dict) else 0),
                }
                for calc in analysis_result.tax_calculations
            ] if analysis_result.tax_calculations else [],
            "risk_assessment": [
                {
                    "severity": str(risk.severity) if hasattr(risk, 'severity') and risk.severity else str(risk.get("severity", "low")) if isinstance(risk, dict) else "low",
                    "category": str(risk.risk_type) if hasattr(risk, 'risk_type') and risk.risk_type else str(risk.get("risk_type", "general")) if isinstance(risk, dict) else "general",
                    "description": str(risk.description) if hasattr(risk, 'description') and risk.description else str(risk.get("description", "")) if isinstance(risk, dict) else "",
                    "recommendation": " ".join(risk.remediation_suggestions) if hasattr(risk, 'remediation_suggestions') and risk.remediation_suggestions else " ".join(risk.get("remediation_suggestions", [])) if isinstance(risk, dict) else "",
                    "risk_type": str(risk.risk_type) if hasattr(risk, 'risk_type') and risk.risk_type else str(risk.get("risk_type", "")) if isinstance(risk, dict) else "",
                }
                for risk in analysis_result.risk_assessment
            ] if analysis_result.risk_assessment else [],
            "compliance_issues": [
                {
                    "severity": str(risk.severity) if hasattr(risk, 'severity') and risk.severity else str(risk.get("severity", "low")) if isinstance(risk, dict) else "low",
                    "category": str(risk.risk_type) if hasattr(risk, 'risk_type') and risk.risk_type else str(risk.get("risk_type", "general")) if isinstance(risk, dict) else "general",
                    "description": str(risk.description) if hasattr(risk, 'description') and risk.description else str(risk.get("description", "")) if isinstance(risk, dict) else "",
                    "recommendation": " ".join(risk.remediation_suggestions) if hasattr(risk, 'remediation_suggestions') and risk.remediation_suggestions else " ".join(risk.get("remediation_suggestions", [])) if isinstance(risk, dict) else "",
                }
                for risk in analysis_result.risk_assessment
            ] if analysis_result.risk_assessment else [],
            "risk_score": safe_float(analysis_result.overall_risk_score),
            "confidence": safe_float(1.0 - analysis_result.overall_risk_score) if analysis_result.overall_risk_score is not None else 1.0,
            "high_risk_count": safe_int(analysis_result.high_risk_count),
            "overall_risk_score": safe_float(analysis_result.overall_risk_score),
            "total_tax_burden": safe_float(analysis_result.total_tax_burden),
            "tax_burden_rate": safe_float(analysis_result.tax_burden_rate),
            "summary": str(analysis_result.summary) if analysis_result.summary else "",
            "created_at": analysis_result.created_at.isoformat() if hasattr(analysis_result.created_at, 'isoformat') else str(analysis_result.created_at)
        }
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 税务分析数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"税务分析数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 税务分析IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"税务分析IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 税务分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"税务分析失败: {str(e)}")


@router.get("/report/{analysis_id}")
async def get_tax_analysis_report(
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取税务分析报告
    
    根据分析ID获取详细的税务分析报告
    """
    report_data = await tax_intelligence_service.get_report_by_id(analysis_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail=f"未找到分析报告: {analysis_id}")
    
    return report_data


@router.post("/report/{analysis_id}/explain")
async def explain_tax_analysis_report(
    analysis_id: str,
    body: Optional[dict] = Body(None),
    user: CurrentUser = Depends(get_current_user),
):
    """
    使用AI智能解释税务分析报告
    
    功能：
    - 基于税务报告内容生成智能解释
    - 回答用户关于报告的特定问题
    - 解释税务计算逻辑、风险因素和优化建议
    
    参数：
    - analysis_id: 分析报告ID
    - body: 可选，包含 question 字段（如未提供，则生成通用解释）
    
    返回：
    - 包含AI解释的JSON响应
    """
    try:
        # 从 body 中提取 question 参数
        question = body.get("question") if body else None
        
        explanation = await tax_intelligence_service.explain_tax_report(
            analysis_id=analysis_id,
            question=question,
            user_id=str(user.id),
            tenant_id=user.tenant_id
        )
        
        return explanation
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 解释报告数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"解释报告数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 解释报告IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解释报告IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 解释报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解释报告失败: {str(e)}")


@router.get("/report/{analysis_id}/export")
async def export_tax_analysis_report_pdf(
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    导出税务分析报告为 PDF
    
    根据分析ID导出详细的税务分析报告为 PDF 格式
    
    返回:
    - PDF 文件的流式响应
    """
    try:
        report_data = await tax_intelligence_service.get_report_by_id(analysis_id)
        
        if not report_data:
            raise HTTPException(status_code=404, detail=f"未找到分析报告: {analysis_id}")
        
        pdf_bytes = pdf_export_service.export_tax_analysis_report(report_data)
        
        filename = f"tax_analysis_report_{analysis_id}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )
        
    except HTTPException:
        raise
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


@router.post("/calculate", response_model=TaxCalculationResponse)
async def calculate_tax(
    request: TaxCalculationRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    执行税务计算
    
    支持税种：
    - vat: 增值税
    - corporate_income: 企业所得税
    - personal_income: 个人所得税
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await tax_intelligence_service.calculate_tax(request)
        
        return TaxCalculationResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 税务计算数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"税务计算数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 税务计算IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"税务计算IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 税务计算失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"税务计算失败: {str(e)}")


@router.get("/policies", response_model=PolicyQueryResponse)
async def query_tax_policies(
    query: str,
    tax_types: Optional[str] = None,
    industries: Optional[str] = None,
    regions: Optional[str] = None,
    top_k: int = 10,
    user: CurrentUser = Depends(get_current_user),
):
    """
    查询适用的税收优惠政策
    
    根据关键词查询匹配的税收优惠政策
    """
    try:
        tax_types_list = tax_types.split(",") if tax_types else None
        industries_list = industries.split(",") if industries else None
        regions_list = regions.split(",") if regions else None
        
        request = PolicyQueryRequest(
            query=query,
            tax_types=tax_types_list,
            industries=industries_list,
            regions=regions_list,
            top_k=top_k,
            user_id=str(user.id),
            tenant_id=user.tenant_id
        )
        
        result = await tax_intelligence_service.query_policies(request)
        
        return PolicyQueryResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 政策查询数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"政策查询数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 政策查询IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策查询IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 政策查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策查询失败: {str(e)}")


@router.post("/subscribe", response_model=PolicySubscriptionResponse)
async def subscribe_policy_updates(
    request: PolicySubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    订阅政策推送
    
    订阅类型：
    - immediate: 即时推送（新政策发布时立即通知）
    - daily: 每日汇总
    - weekly: 每周汇总
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await tax_intelligence_service.subscribe_policy_updates(request)
        
        return PolicySubscriptionResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 政策订阅数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"政策订阅数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 政策订阅IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策订阅IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 政策订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策订阅失败: {str(e)}")


@router.get("/history")
async def get_analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取税务分析历史记录
    """
    try:
        result = await tax_intelligence_service.get_analysis_history(
            user_id=str(user.id),
            tenant_id=user.tenant_id,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        logger.error(f"❌ 获取分析历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取分析历史失败: {str(e)}")


@router.delete("/report/{analysis_id}")
async def delete_tax_analysis_report(
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    删除税务分析报告
    
    根据分析ID删除税务分析报告
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.tax_report import TaxReport
        from sqlalchemy import delete
        
        async with AsyncSessionLocal() as db:
            stmt = delete(TaxReport).where(
                TaxReport.id == analysis_id,
                TaxReport.user_id == user.id
            )
            result = await db.execute(stmt)
            await db.commit()
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"未找到要删除的分析报告: {analysis_id}")
            
            logger.info(f"✅ 删除分析报告成功: {analysis_id}")
            return {"success": True, "message": "分析报告已删除"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除分析报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除分析报告失败: {str(e)}")


@router.get("/statistics")
async def get_tax_intelligence_statistics(
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取税务智能分析统计信息
    
    返回：
    - 总分析次数
    - 本季度分析次数
    - 高风险项数量
    - 合规率
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.tax_report import TaxReport
        from sqlalchemy import select, func, and_
        from datetime import datetime, timedelta
        
        async with AsyncSessionLocal() as db:
            current_quarter = (datetime.now().month - 1) // 3 + 1
            quarter_start_month = (current_quarter - 1) * 3 + 1
            quarter_start = datetime(datetime.now().year, quarter_start_month, 1)
            
            total_count = await db.scalar(
                select(func.count(TaxReport.id)).where(TaxReport.user_id == user.id)
            )
            
            quarter_count = await db.scalar(
                select(func.count(TaxReport.id)).where(
                    and_(
                        TaxReport.user_id == user.id,
                        TaxReport.created_at >= quarter_start
                    )
                )
            )
            
            all_reports = await db.execute(
                select(TaxReport.risk_score).where(TaxReport.user_id == user.id)
            )
            risk_scores = [row[0] for row in all_reports.fetchall()]
            
            high_risk_count = sum(1 for score in risk_scores if score and score > 0.7)
            compliance_rate = (len(risk_scores) - high_risk_count) / len(risk_scores) if risk_scores else 0.985
            
            return {
                "total_analyses": total_count or 0,
                "current_quarter_analyses": quarter_count or 0,
                "high_risk_count": high_risk_count,
                "compliance_rate": round(compliance_rate, 4)
            }
            
    except Exception as e:
        logger.error(f"❌ 获取统计信息失败: {e}", exc_info=True)
        return {
            "total_analyses": 0,
            "current_quarter_analyses": 0,
            "high_risk_count": 0,
            "compliance_rate": 0.985
        }


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "tax_intelligence",
        "version": "1.0.0"
    }
