"""
合同审核智能助手 API 端点
提供合同深度分析和风险评估的 RESTful 接口
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime
from io import BytesIO

from app.api.deps import get_current_user, CurrentUser
from app.schemas.contract_review import (
    ContractAnalysisRequest,
    ContractAnalysisResponse,
    DeepClauseAnalysisRequest,
    DeepClauseAnalysisResponse,
    ContractComparisonRequest,
    ContractComparisonResponse,
    ContractType,
    ClauseType,
    RiskLevel,
    ReviewStatus,
    ContractClause,
    RiskAssessment,
)
from app.services.contract_review_service import ContractReviewService
from app.services.pdf_export_service import pdf_export_service

router = APIRouter(prefix="/contract-review", tags=["合同审核"])
logger = logging.getLogger(__name__)

contract_review_service = ContractReviewService()


@router.post("/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    request: ContractAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    分析合同
    
    对合同文本进行全文分析，包括：
    - 条款提取和分类
    - 风险评估
    - 关键发现
    - 修改建议
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await contract_review_service.analyze_contract(request)
        
        return ContractAnalysisResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 合同分析数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"分析数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 合同分析IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 合同分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/clause-analysis", response_model=DeepClauseAnalysisResponse)
async def analyze_clause_deeply(
    request: DeepClauseAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    深度条款分析
    
    对单个条款进行深度分析，包括：
    - 法律解释
    - 潜在问题识别
    - 行业惯例对比
    - 修改建议
    - 相关法规参考
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await contract_review_service.analyze_clause_deeply(request)
        
        return DeepClauseAnalysisResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 深度条款分析数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"分析数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 深度条款分析IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 深度条款分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/compare", response_model=ContractComparisonResponse)
async def compare_contracts(
    request: ContractComparisonRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    对比合同
    
    对比两个合同的条款差异，包括：
    - 条款对比
    - 关键差异识别
    - 优势分析
    - 风险对比
    - 谈判要点建议
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await contract_review_service.compare_contracts(request)
        
        return ContractComparisonResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 合同对比数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"对比数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 合同对比IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对比IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 合同对比失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对比失败: {str(e)}")


@router.get("/risks")
async def get_risk_assessments(
    analysis_id: str = Query(..., description="分析ID"),
    risk_level: Optional[str] = Query(None, description="风险级别筛选"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取风险评估结果
    
    获取指定合同分析的风险评估详情
    """
    try:
        if analysis_id not in contract_review_service._analysis_cache:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        
        analysis = contract_review_service._analysis_cache[analysis_id]
        
        risk_assessments = analysis.get("risk_assessments", [])
        
        if risk_level:
            try:
                risk_level_enum = RiskLevel(risk_level)
                risk_assessments = [
                    r for r in risk_assessments
                    if r.get("risk_level") == risk_level_enum.value
                ]
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的风险级别")
        
        return {
            "analysis_id": analysis_id,
            "risk_assessments": risk_assessments,
            "total_count": len(risk_assessments),
            "high_risk_count": sum(
                1 for r in risk_assessments
                if r.get("risk_level") in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
            )
        }
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取风险评估数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取风险评估IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取风险评估失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/clauses")
async def get_contract_clauses(
    analysis_id: str = Query(..., description="分析ID"),
    clause_type: Optional[str] = Query(None, description="条款类型筛选"),
    risk_level: Optional[str] = Query(None, description="风险级别筛选"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取合同条款列表
    
    获取指定合同分析的条款详情
    """
    try:
        if analysis_id not in contract_review_service._analysis_cache:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        
        analysis = contract_review_service._analysis_cache[analysis_id]
        clauses = analysis.get("clauses_extracted", [])
        
        if clause_type:
            try:
                clause_type_enum = ClauseType(clause_type)
                clauses = [
                    c for c in clauses
                    if c.get("clause_type") == clause_type_enum.value
                ]
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的条款类型")
        
        if risk_level:
            try:
                risk_level_enum = RiskLevel(risk_level)
                clauses = [
                    c for c in clauses
                    if c.get("risk_level") == risk_level_enum.value
                ]
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的风险级别")
        
        return {
            "analysis_id": analysis_id,
            "clauses": clauses,
            "total_count": len(clauses),
            "high_risk_count": sum(
                1 for c in clauses
                if c.get("risk_level") in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
            )
        }
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取条款列表数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取条款列表IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取条款列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/clause-types")
async def list_clause_types():
    """
    获取条款类型列表
    
    返回所有支持的条款类型
    """
    return {
        "clause_types": [
            {"value": ct.value, "label": _get_clause_type_label(ct)}
            for ct in ClauseType
        ]
    }


@router.get("/report/export")
async def export_contract_review_report_pdf(
    analysis_id: str = Query(..., description="分析ID"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    导出合同审核报告为 PDF
    
    根据分析ID导出合同审核报告 PDF
    
    Args:
        analysis_id: 分析ID
        
    Returns:
        PDF 文件的流式响应
    """
    try:
        if analysis_id not in contract_review_service._analysis_cache:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        
        analysis = contract_review_service._analysis_cache[analysis_id]
        
        pdf_bytes = pdf_export_service.export_contract_review_report(analysis)
        
        filename = f"contract_review_report_{analysis_id}.pdf"
        
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


def _get_clause_type_label(clause_type: ClauseType) -> str:
    """获取条款类型标签"""
    labels = {
        ClauseType.PAYMENT: "付款条款",
        ClauseType.DELIVERY: "交付条款",
        ClauseType.WARRANTY: "保修条款",
        ClauseType.LIABILITY: "责任条款",
        ClauseType.TERMINATION: "终止条款",
        ClauseType.CONFIDENTIALITY: "保密条款",
        ClauseType.INTELLECTUAL_PROPERTY: "知识产权条款",
        ClauseType.DISPUTE_RESOLUTION: "争议解决条款",
        ClauseType.FORCE_MAJEURE: "不可抗力条款",
        ClauseType.INDEMNIFICATION: "赔偿条款",
        ClauseType.ASSIGNMENT: "转让条款",
        ClauseType.GOVERNING_LAW: "适用法律条款",
        ClauseType.OTHER: "其他条款",
    }
    return labels.get(clause_type, clause_type.value)


@router.get("/contract-types")
async def list_contract_types():
    """
    获取合同类型列表
    
    返回所有支持的合同类型
    """
    return {
        "contract_types": [
            {"value": ct.value, "label": _get_contract_type_label(ct)}
            for ct in ContractType
        ]
    }


def _get_contract_type_label(contract_type: ContractType) -> str:
    """获取合同类型标签"""
    labels = {
        ContractType.SALES: "销售合同",
        ContractType.PURCHASE: "采购合同",
        ContractType.SERVICE: "服务合同",
        ContractType.LABOR: "劳动合同",
        ContractType.LEASE: "租赁合同",
        ContractType.LOAN: "借款合同",
        ContractType.PARTNERSHIP: "合作协议",
        ContractType.CONFIDENTIALITY: "保密协议",
        ContractType.OTHER: "其他合同",
    }
    return labels.get(contract_type, contract_type.value)


@router.get("/templates")
async def list_contract_templates(
    contract_type: Optional[str] = Query(None, description="合同类型过滤"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取合同审核模板列表
    
    返回预定义的合同审核模板，支持按类型过滤
    """
    templates = [
        {
            "id": "template-001",
            "name": "标准采购合同模板",
            "description": "适用于企业间标准采购业务，包含完整条款和风险提示",
            "contract_type": "purchase",
            "usage_count": 156
        },
        {
            "id": "template-002",
            "name": "销售合同标准模板",
            "description": "适用于产品销售场景，包含交付、质量保证等核心条款",
            "contract_type": "sales",
            "usage_count": 203
        },
        {
            "id": "template-003",
            "name": "服务外包合同模板",
            "description": "适用于专业服务外包，包含服务范围、验收标准等条款",
            "contract_type": "service",
            "usage_count": 178
        },
        {
            "id": "template-004",
            "name": "房屋租赁合同模板",
            "description": "适用于办公或商业租赁，包含租金、押金、装修等条款",
            "contract_type": "lease",
            "usage_count": 89
        },
        {
            "id": "template-005",
            "name": "劳动合同标准模板",
            "description": "适用于企业招聘员工，包含薪酬、福利、保密等条款",
            "contract_type": "employment",
            "usage_count": 312
        },
        {
            "id": "template-006",
            "name": "合作协议模板",
            "description": "适用于战略合作或项目合作，包含权益分配等条款",
            "contract_type": "partnership",
            "usage_count": 67
        },
        {
            "id": "template-007",
            "name": "借款合同模板",
            "description": "适用于企业或个人借贷，包含利率、还款方式等条款",
            "contract_type": "loan",
            "usage_count": 45
        },
        {
            "id": "template-008",
            "name": "保密协议模板",
            "description": "适用于商业机密保护，包含保密范围、违约责任等条款",
            "contract_type": "confidentiality",
            "usage_count": 234
        },
        {
            "id": "template-009",
            "name": "软件开发合同模板",
            "description": "适用于软件定制开发，包含需求变更、知识产权等条款",
            "contract_type": "service",
            "usage_count": 98
        },
        {
            "id": "template-010",
            "name": "供应链采购合同模板",
            "description": "适用于供应链采购，包含交货、质量控制等条款",
            "contract_type": "purchase",
            "usage_count": 76
        },
        {
            "id": "template-011",
            "name": "咨询服务合同模板",
            "description": "适用于各类咨询业务，包含服务内容、成果交付等条款",
            "contract_type": "service",
            "usage_count": 112
        },
        {
            "id": "template-012",
            "name": "设备租赁合同模板",
            "description": "适用于设备租赁业务，包含租金、维护、损坏赔偿等条款",
            "contract_type": "lease",
            "usage_count": 34
        }
    ]
    
    if contract_type:
        templates = [t for t in templates if t["contract_type"] == contract_type]
    
    return {
        "templates": templates,
        "total": len(templates)
    }


@router.get("/risk-levels")
async def list_risk_levels():
    """
    获取风险级别列表
    
    返回所有风险级别定义
    """
    return {
        "risk_levels": [
            {"value": rl.value, "label": _get_risk_level_label(rl), "description": _get_risk_level_description(rl)}
            for rl in RiskLevel
        ]
    }


def _get_risk_level_label(risk_level: RiskLevel) -> str:
    """获取风险级别标签"""
    labels = {
        RiskLevel.LOW: "低风险",
        RiskLevel.MEDIUM: "中等风险",
        RiskLevel.HIGH: "高风险",
        RiskLevel.CRITICAL: "极高风险",
    }
    return labels.get(risk_level, risk_level.value)


def _get_risk_level_description(risk_level: RiskLevel) -> str:
    """获取风险级别描述"""
    descriptions = {
        RiskLevel.LOW: "基本无风险，可正常执行",
        RiskLevel.MEDIUM: "存在一定风险，需要注意",
        RiskLevel.HIGH: "存在较高风险，建议谨慎处理",
        RiskLevel.CRITICAL: "存在严重风险，需要立即处理",
    }
    return descriptions.get(risk_level, "")


@router.get("/history")
async def get_analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    contract_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取合同审核历史记录
    """
    try:
        service = ContractReviewService()
        result = await service.get_analysis_history(
            user_id=str(user.id),
            tenant_id=user.tenant_id,
            page=page,
            page_size=page_size,
            contract_type=contract_type,
            risk_level=risk_level
        )
        return result
    except Exception as e:
        logger.error(f"❌ 获取合同审核历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取合同审核历史失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "contract_review",
        "version": "1.0.0"
    }
