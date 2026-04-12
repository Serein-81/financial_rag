"""
税务智能分析 API 端点
提供税务合规智能助手的 RESTful 接口
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

from app.api.deps import get_current_user, get_db, CurrentUser
from app.schemas.tax_intelligence import (
    TaxAnalysisRequest,
    TaxAnalysisResult,
    TaxIntelligenceAnalysisResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
    PolicyQueryRequest,
    PolicyQueryResponse,
    PolicySubscriptionRequest,
    PolicySubscriptionResponse,
    TaxIntelligenceStatus,
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

        return {
            "analysis_id": analysis_result.analysis_id,
            "analysis_type": analysis_result.analysis_type,
            "fiscal_year": analysis_result.fiscal_year,
            "fiscal_period": analysis_result.fiscal_period,
            "status": analysis_result.status,
            "financial_summary": analysis_result.financial_summary,
            "tax_calculations": analysis_result.tax_calculations,
            "risk_assessment": analysis_result.risk_assessment,
            "overall_risk_score": analysis_result.overall_risk_score,
            "high_risk_count": analysis_result.high_risk_count,
            "summary": analysis_result.summary,
            "total_tax_burden": analysis_result.total_tax_burden,
            "tax_burden_rate": analysis_result.tax_burden_rate,
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


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "tax_intelligence",
        "version": "1.0.0"
    }
