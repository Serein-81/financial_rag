"""
用户财务数据管理API
提供财务数据的CRUD操作和税务查询功能
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging
import io

import pandas as pd
from fastapi.responses import StreamingResponse
from difflib import SequenceMatcher


COLUMN_MAPPING = {
    'fiscal_year': {
        'required': True,
        'synonyms': [
            '年度', '年份', '财年', '财务年度', '会计年度',
            'year', 'fy', 'fiscal_year', 'fiscalyear', 'yearly',
            'year_value', 'fiscal_year_value', 'report_year'
        ]
    },
    'period_type': {
        'required': False,
        'synonyms': [
            '周期类型', '期间类型', '报表类型', '类型',
            'period_type', 'periodtype', 'report_type', 'frequency',
            'type', 'category', 'period_category'
        ]
    },
    'period_start': {
        'required': False,
        'synonyms': [
            '开始日期', '期初日期', '周期开始', '期间开始',
            'start_date', 'period_start', 'periodstart', 'start',
            'from_date', 'begin_date', 'period_start_date'
        ]
    },
    'period_end': {
        'required': False,
        'synonyms': [
            '结束日期', '期末日期', '周期结束', '期间结束',
            'end_date', 'period_end', 'periodend', 'end',
            'to_date', 'finish_date', 'period_end_date'
        ]
    },
    'total_revenue': {
        'required': True,
        'synonyms': [
            '总收入', '营业收入', '营业额', '销售收入', '销售总额',
            'revenue', 'total_revenue', 'totalrevenue', 'sales',
            'sales_revenue', 'operating_revenue', 'income',
            'total_income', 'gross_revenue', 'total_sales'
        ]
    },
    'taxable_sales': {
        'required': True,
        'synonyms': [
            '应税销售额', '应税销售', '应税收入', '含税销售额',
            'taxable_sales', 'taxablesales', 'taxable_revenue',
            'taxed_sales', 'sales_taxable',
            'taxable_sales_amount', 'taxable_sales_amt', 'sales_taxable_amount'
        ]
    },
    'tax_free_sales': {
        'required': True,
        'synonyms': [
            '免税销售额', '免税销售', '零税率销售额', '免税收入',
            'tax_free_sales', 'taxfreesales', 'tax_free_revenue',
            'zero_tax_sales', 'exempt_sales', 'exempt_revenue'
        ]
    },
    'total_expenses': {
        'required': True,
        'synonyms': [
            '总支出', '总费用', '费用总额', '营业成本', '成本总额',
            'total_expenses', 'totalexpenses', 'expenses', 'costs',
            'total_costs', 'operating_costs', 'cost_of_sales'
        ]
    },
    'deductible_expenses': {
        'required': True,
        'synonyms': [
            '可抵扣支出', '可抵扣费用', '可抵扣成本', '允许扣除费用',
            'deductible_expenses', 'deductible', 'deductible_costs',
            'allowable_expenses', 'allowed_deductions'
        ]
    },
    'non_deductible_expenses': {
        'required': True,
        'synonyms': [
            '不可抵扣支出', '不可抵扣费用', '不可抵扣成本', '不允许扣除费用',
            'non_deductible_expenses', 'nondeductible', 'non_deductible',
            'non_deductible_costs', 'undeductible_expenses'
        ]
    },
    'input_tax': {
        'required': True,
        'synonyms': [
            '进项税额', '进项税', '可抵扣税额', '收票税额',
            'input_tax', 'inputtax', 'input_vat', 'purchase_tax',
            'vat_in', 'tax_recoverable', 'tax_paid'
        ]
    },
    'output_tax': {
        'required': True,
        'synonyms': [
            '销项税额', '销项税', '应收税额', '开票税额',
            'output_tax', 'outputtax', 'output_vat', 'sales_tax',
            'vat_out', 'tax_payable', 'tax_collected'
        ]
    },
    'vat_rate': {
        'required': True,
        'synonyms': [
            '增值税率', '税率', '增值税率率', 'VAT税率',
            'vat_rate', 'vatr', 'vat', 'tax_rate', 'rate',
            'tax_rate_value', 'vat_percentage'
        ]
    },
    'taxable_income': {
        'required': True,
        'synonyms': [
            '应纳税所得额', '应税所得', '应纳税收入',
            'taxable_income', 'taxableincome', 'tax_income',
            'tax_base', 'assessable_income', 'taxable_profit',
            'taxable_income_amount', 'taxable_income_amt', 'tax_income_amount'
        ]
    },
    'corporate_tax_rate': {
        'required': True,
        'synonyms': [
            '企业所得税率', '企业税率', '所得税率', '企业所得税率',
            'corporate_tax_rate', 'corporatetaxrate', 'corporate_rate',
            'tax_rate_corporate', 'income_tax_rate', 'cit_rate'
        ]
    },
    'is_small_enterprise': {
        'required': False,
        'synonyms': [
            '是否小微企业', '小微企业', '小微', '微型企业',
            'is_small_enterprise', 'small_enterprise', 'small_enterprise_flag',
            'small_business', 'sme', 'is_sme'
        ]
    },
    'total_payroll': {
        'required': False,
        'synonyms': [
            '工资薪金', '工资总额', '薪酬总额', '人工成本', '员工薪酬',
            'total_payroll', 'payroll', 'salaries', 'wages',
            'labor_cost', 'employee_compensation', 'staff_cost'
        ]
    },
    'special_deductions': {
        'required': False,
        'synonyms': [
            '专项附加扣除', '专项扣除', '附加扣除', '特殊扣除',
            'special_deductions', 'specialdeductions', 'additional_deductions',
            'special_deduction', 'extra_deductions'
        ]
    },
    'total_invoices': {
        'required': False,
        'synonyms': [
            '发票总数', '发票张数', '发票总张数', '总发票数',
            'total_invoices', 'totalinvoices', 'invoice_count', 'invoices',
            'invoice_total', 'number_of_invoices'
        ]
    },
    'input_invoice_count': {
        'required': False,
        'synonyms': [
            '进项发票数', '进项发票', '收票数', '进项票数',
            'input_invoice_count', 'input_invoices', 'purchase_invoices',
            'inward_invoices', 'vat_invoices_received'
        ]
    },
    'output_invoice_count': {
        'required': False,
        'synonyms': [
            '销项发票数', '销项发票', '开票数', '销项票数',
            'output_invoice_count', 'output_invoices', 'sales_invoices',
            'outward_invoices', 'vat_invoices_issued'
        ]
    }
}


def normalize_column_name(name: str) -> str:
    """规范化列名：转小写、去除空格和特殊字符"""
    if not name:
        return ''
    name = str(name).lower().strip()
    name = name.replace(' ', '').replace('_', '').replace('-', '')
    name = name.replace('（', '').replace('）', '').replace('(', '').replace(')', '')
    name = name.replace('\u00a0', '').replace('\u3000', '')
    return name


def calculate_similarity(s1: str, s2: str) -> float:
    """计算两个字符串的相似度，包含匹配时提高分数"""
    s1_norm = normalize_column_name(s1)
    s2_norm = normalize_column_name(s2)

    if s1_norm == s2_norm:
        return 1.0

    if s2_norm in s1_norm or s1_norm in s2_norm:
        base_score = SequenceMatcher(None, s1_norm, s2_norm).ratio()
        return min(0.85, base_score + 0.3)

    return SequenceMatcher(None, s1_norm, s2_norm).ratio()


def find_best_match(column: str, synonyms: list[str], threshold: float = 0.7) -> tuple[bool, str]:
    """
    在同义词列表中查找最佳匹配
    
    Returns:
        tuple: (是否匹配成功, 匹配的原始同义词)
    """
    best_match = None
    best_score = 0
    
    for synonym in synonyms:
        score = calculate_similarity(column, synonym)
        if score > best_score:
            best_score = score
            best_match = synonym
    
    if best_score >= threshold:
        return True, best_match
    return False, None


def auto_detect_columns(df_columns: list[str]) -> dict[str, str | None]:
    """
    自动检测Excel列名并映射到系统字段
    
    Returns:
        dict: {系统字段名: 检测到的Excel列名 或 None}
    """
    detected_columns = {}
    used_columns = set()
    
    for field, config in COLUMN_MAPPING.items():
        best_match = None
        best_score = 0
        best_synonym = None
        
        for excel_col in df_columns:
            if excel_col in used_columns:
                continue
                
            excel_col_normalized = normalize_column_name(excel_col)
            
            for idx, synonym in enumerate(config['synonyms']):
                score = calculate_similarity(excel_col, synonym)
                
                exact_match_bonus = 0.1 if excel_col_normalized == normalize_column_name(synonym) else 0
                priority_bonus = 0.05 if idx < 3 else 0
                
                adjusted_score = score + exact_match_bonus + priority_bonus
                
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_match = excel_col
                    best_synonym = synonym
        
        if best_score >= 0.7:
            detected_columns[field] = best_match
            if best_match:
                used_columns.add(best_match)
        else:
            detected_columns[field] = None
    
    return detected_columns


def remap_dataframe_columns(df: pd.DataFrame, column_mapping: dict[str, str | None]) -> pd.DataFrame:
    """根据映射重命名DataFrame的列"""
    rename_dict = {v: k for k, v in column_mapping.items() if v is not None}
    return df.rename(columns=rename_dict)

from app.api.deps import get_current_user, get_db, CurrentUser
from app.models.user_financial_data import UserFinancialData, FinancialDataHistory
from app.schemas.user_financial_data import (
    FinancialDataCreate,
    FinancialDataUpdate,
    FinancialDataResponse,
    FinancialDataListResponse,
    TaxQueryRequest,
    TaxQueryResponse,
    TaxCalculationResult,
    FinancialDataStatistics,
    ExcelUploadResponse,
    DataSourceEnum
)

router = APIRouter(prefix="/financial-data", tags=["财务数据管理"])
logger = logging.getLogger(__name__)


async def get_db_session(db: AsyncSession = Depends(get_db)):
    """获取数据库会话"""
    return db


@router.post("", response_model=FinancialDataResponse, status_code=201)
async def create_financial_data(
    data: FinancialDataCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建财务数据记录
    
    - 支持创建指定年度的财务数据
    - 自动进行数据验证
    - 初始化所有税务相关字段
    """
    logger.info(f"Received create request: {data.model_dump()}")
    try:
        existing = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id,
                    UserFinancialData.fiscal_year == data.fiscal_year,
                    UserFinancialData.period_type == data.period_type.value
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"该年度({data.fiscal_year})的{data.period_type.value}财务数据已存在，请使用更新接口"
            )
        
        financial_data = UserFinancialData(
            user_id=user.id,
            tenant_id=user.tenant_id,
            fiscal_year=data.fiscal_year,
            period_type=data.period_type.value,
            period_start=data.period_start,
            period_end=data.period_end,
            total_revenue=data.total_revenue,
            taxable_sales=data.taxable_sales,
            tax_free_sales=data.tax_free_sales,
            total_expenses=data.total_expenses,
            deductible_expenses=data.deductible_expenses,
            non_deductible_expenses=data.non_deductible_expenses,
            input_tax=data.input_tax,
            output_tax=data.output_tax,
            vat_rate=data.vat_rate,
            taxable_income=data.taxable_income,
            corporate_tax_rate=data.corporate_tax_rate,
            is_small_enterprise=data.is_small_enterprise,
            total_payroll=data.total_payroll,
            special_deductions=data.special_deductions,
            cost_breakdown=data.cost_breakdown,
            total_invoices=data.total_invoices,
            input_invoice_count=data.input_invoice_count,
            output_invoice_count=data.output_invoice_count,
            data_source=data.data_source.value,
            notes=data.notes
        )
        
        db.add(financial_data)
        await db.commit()
        await db.refresh(financial_data)
        
        logger.info(f"Financial data created: user={user.id}, fiscal_year={data.fiscal_year}")
        
        return FinancialDataResponse.model_validate(financial_data)
    
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create financial data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create financial data")


@router.get("", response_model=FinancialDataListResponse)
async def list_financial_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    fiscal_year: Optional[int] = Query(None, description="财务年度"),
    period_type: Optional[str] = Query(None, description="周期类型: yearly/quarterly/monthly"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取财务数据列表
    
    - 支持按年度筛选
    - 支持按周期类型筛选
    - 支持分页
    - 按年度倒序排列
    """
    try:
        query = select(UserFinancialData).where(
            and_(
                UserFinancialData.user_id == user.id,
                UserFinancialData.tenant_id == user.tenant_id
            )
        )
        
        if fiscal_year:
            query = query.where(UserFinancialData.fiscal_year == fiscal_year)
        
        if period_type:
            query = query.where(UserFinancialData.period_type == period_type)
        
        query = query.order_by(UserFinancialData.fiscal_year.desc(), UserFinancialData.period_type.asc())
        
        total_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar()
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        records = result.scalars().all()
        
        page = (skip // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return FinancialDataListResponse(
            items=[FinancialDataResponse.model_validate(r) for r in records],
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages
        )
    
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to query financial data list: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query financial data list")


@router.get("/by-year")
async def get_financial_data_by_year(
    fiscal_year: int = Query(..., description="财务年度"),
    period_type: Optional[str] = Query("yearly", description="周期类型: yearly/quarterly/monthly"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    根据年度和周期类型获取财务数据

    - 如果存在则返回数据
    - 如果不存在则返回404
    """
    try:
        result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id,
                    UserFinancialData.fiscal_year == fiscal_year,
                    UserFinancialData.period_type == period_type
                )
            )
        )
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail=f"未找到{fiscal_year}年的{period_type}财务数据")

        return FinancialDataResponse.model_validate(record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query financial data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query financial data")


@router.get("/statistics", response_model=FinancialDataStatistics)
async def get_financial_statistics(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取财务数据统计
    
    - 返回所有记录统计
    - 返回今年和去年的对比
    - 计算同比增长
    """
    try:
        result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id
                )
            ).order_by(UserFinancialData.fiscal_year.desc())
        )
        records = result.scalars().all()
        
        current_year = datetime.now().year
        current_year_record = next((r for r in records if r.fiscal_year == current_year), None)
        previous_year_record = next((r for r in records if r.fiscal_year == current_year - 1), None)
        
        yoy_growth = {}
        tax_summary = {
            "total_vat": 0.0,
            "total_corporate_tax": 0.0,
            "total_personal_tax": 0.0
        }
        
        if current_year_record and previous_year_record:
            if previous_year_record.total_revenue > 0:
                yoy_growth["revenue"] = round(
                    (current_year_record.total_revenue - previous_year_record.total_revenue) 
                    / previous_year_record.total_revenue * 100, 2
                )
            
            yoy_growth["vat"] = round(
                current_year_record.calculated_vat - previous_year_record.calculated_vat, 2
            )
            yoy_growth["corporate_tax"] = round(
                current_year_record.calculated_corporate_tax - previous_year_record.calculated_corporate_tax, 2
            )
        
        for record in records:
            tax_summary["total_vat"] += record.calculated_vat
            tax_summary["total_corporate_tax"] += record.calculated_corporate_tax
        
        return FinancialDataStatistics(
            total_records=len(records),
            current_year_record=FinancialDataResponse.model_validate(current_year_record) if current_year_record else None,
            previous_year_record=FinancialDataResponse.model_validate(previous_year_record) if previous_year_record else None,
            year_over_year_growth=yoy_growth,
            tax_summary=tax_summary
        )
    
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to get financial statistics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get financial statistics")


@router.get("/template-description")
async def get_template_description():
    """
    获取财务数据模板说明

    返回模板的使用说明、字段解释和注意事项
    前端可以先显示此说明，引导用户正确填写数据后再下载模板
    """
    description = {
        "title": "财务数据模板使用说明",
        "sections": [
            {
                "title": "📋 模板说明",
                "content": "本模板用于批量导入企业财务数据。请按照模板格式填写您的财务数据，确保数据准确无误后上传。"
            },
            {
                "title": "📝 必填字段",
                "content": "• 会计年度 (fiscal_year): 填写年份，如 2024\n• 期间类型 (period_type): yearly/quarterly/monthly\n• 期间开始日期 (period_start): YYYY-MM-DD格式\n• 期间结束日期 (period_end): YYYY-MM-DD格式\n• 总收入 (total_revenue): 填写金额，单位：元"
            },
            {
                "title": "💰 财务指标说明",
                "content": "• 总收入 (total_revenue): 企业当期全部收入\n• 应税销售额 (taxable_sales): 需要缴纳增值税的销售额\n• 进项税额 (input_tax): 采购时收到的增值税专用发票税额\n• 销项税额 (output_tax): 销售时开具的增值税专用发票税额\n• 营业收入 (taxable_income): 应纳税所得额"
            },
            {
                "title": "⚠️ 注意事项",
                "content": "• 年份列必须填写有效年份（2000-2100）\n• 金额字段请填写数字，不要包含货币符号\n• 日期格式请使用 YYYY-MM-DD\n• 小规模纳税人请将 is_small_enterprise 设为 True\n• 建议先下载测试数据进行测试"
            },
            {
                "title": "🔧 税率说明",
                "content": "• 企业所得税税率 (corporate_tax_rate): 一般为 0.25（25%）\n• 增值税税率 (vat_rate): 一般为 0.13（13%）或 0.09（9%）\n• 小规模纳税人增值税税率为 0.01-0.03"
            },
            {
                "title": "📊 批量导入建议",
                "content": "• 建议先导入少量数据测试（如3-5条）\n• 确认数据格式正确后再批量导入\n• 可以使用「下载测试数据」功能获取1000条测试数据\n• 导入过程中请勿关闭页面"
            }
        ],
        "download_hint": "阅读完毕后，点击「下载模板」按钮获取Excel文件"
    }

    return description


@router.get("/download-template")
async def download_financial_data_template():
    """
    下载财务数据Excel模板

    返回标准中文Excel模板文件
    用户可以按照模板格式填写数据后上传
    """
    from pathlib import Path
    from urllib.parse import quote

    templates_dir = Path(__file__).parent.parent.parent.parent.parent / 'test_templates'

    if not templates_dir.exists():
        logger.error(f"Templates directory not found: {templates_dir}")
        raise HTTPException(
            status_code=404,
            detail=f"Templates directory not found: {templates_dir}"
        )

    filename = "01_标准中文模板.xlsx"
    file_path = templates_dir / filename

    if not file_path.exists():
        logger.error(f"Template file not found: {file_path}")
        raise HTTPException(
            status_code=404,
            detail=f"模板文件不存在: {filename}"
        )

    with open(file_path, 'rb') as f:
        file_content = f.read()

    logger.info(f"Serving template file: {filename}, size: {len(file_content)} bytes")

    encoded_filename = quote(filename, safe='')

    return StreamingResponse(
        iter([file_content]),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f'attachment; filename*=UTF-8\'\'{encoded_filename}'
        }
    )


@router.get("/download-test-templates")
async def download_test_templates():
    """
    下载测试数据文件

    返回包含1200条模拟财务数据的标准中文Excel模板（适用于财务数据智能上传接口）
    """
    from pathlib import Path
    from urllib.parse import quote

    templates_dir = Path(__file__).parent.parent.parent.parent.parent / 'test_templates'

    if not templates_dir.exists():
        logger.error(f"Test templates directory not found: {templates_dir}")
        raise HTTPException(
            status_code=404,
            detail=f"Test templates directory not found: {templates_dir}"
        )

    filename = "01_标准中文模板_1000条.xlsx"
    file_path = templates_dir / filename

    if not file_path.exists():
        logger.error(f"Test data file not found: {file_path}")
        raise HTTPException(
            status_code=404,
            detail=f"测试数据文件不存在: {filename}"
        )

    with open(file_path, 'rb') as f:
        file_content = f.read()

    logger.info(f"Serving test data file: {filename}, size: {len(file_content)} bytes")

    encoded_filename = quote(filename, safe='')

    return StreamingResponse(
        iter([file_content]),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f'attachment; filename*=UTF-8\'\'{encoded_filename}',
            'Content-Length': str(len(file_content)),
            'Cache-Control': 'no-cache',
        }
    )


@router.get("/{record_id}", response_model=FinancialDataResponse)
async def get_financial_data(
    record_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取财务数据详情"""
    try:
        result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.id == record_id,
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id
                )
            )
        )
        record = result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(status_code=404, detail="财务数据不存在")
        
        return FinancialDataResponse.model_validate(record)
    
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to query financial data details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query financial data details")


@router.put("/{record_id}", response_model=FinancialDataResponse)
async def update_financial_data(
    record_id: str,
    data: FinancialDataUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新财务数据
    
    - 自动记录修改历史
    - 支持部分更新
    """
    try:
        try:
            record_uuid = UUID(record_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的财务数据ID格式")
        
        result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.id == record_uuid,
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id
                )
            )
        )
        record = result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(status_code=404, detail="财务数据不存在")
        
        history_record = FinancialDataHistory(
            financial_data_id=record.id,
            modified_by=user.id,
            previous_data={
                "total_revenue": record.total_revenue,
                "taxable_sales": record.taxable_sales,
                "input_tax": record.input_tax,
                "output_tax": record.output_tax
            },
            new_data=data.model_dump(exclude_unset=True),
            change_reason="手动更新"
        )
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(record, field):
                if field == "data_status" and value:
                    setattr(record, field, value.value if hasattr(value, 'value') else value)
                else:
                    setattr(record, field, value)
        
        db.add(history_record)
        await db.commit()
        await db.refresh(record)
        
        logger.info(f"Financial data updated: record_id={record_id}, user={user.id}")
        
        return FinancialDataResponse.model_validate(record)
    
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to update financial data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update financial data")


@router.delete("/{record_id}", status_code=204)
async def delete_financial_data(
    record_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除财务数据"""
    try:
        try:
            record_uuid = UUID(record_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的财务数据ID格式")
        
        result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.id == record_uuid,
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id
                )
            )
        )
        record = result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(status_code=404, detail="财务数据不存在")
        
        await db.delete(record)
        await db.commit()
        
        logger.info(f"Financial data deleted: record_id={record_id}, user={user.id}")
    
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to delete financial data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete financial data")


@router.post("/query-tax", response_model=TaxQueryResponse)
async def query_tax(
    request: TaxQueryRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    税务智能查询
    
    - 根据财务数据自动计算各项税额
    - 提供风险提示和筹划建议
    - 支持指定年度查询
    """
    try:
        fiscal_year = request.fiscal_year or datetime.now().year
        
        result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id,
                    UserFinancialData.fiscal_year == fiscal_year
                )
            )
        )
        financial_data = result.scalar_one_or_none()
        
        if not financial_data:
            raise HTTPException(
                status_code=404,
                detail=f"未找到{fiscal_year}年度的财务数据，请先录入数据"
            )
        
        tax_results = []
        risk_alerts = []
        recommendations = []
        
        if request.include_vat:
            calculated_vat = financial_data.calculated_vat
            vat_rate = calculated_vat / financial_data.taxable_sales if financial_data.taxable_sales > 0 else 0
            
            tax_results.append(TaxCalculationResult(
                tax_type="增值税",
                tax_amount=calculated_vat,
                effective_rate=round(vat_rate * 100, 2),
                tax_benchmark=4.0,
                status="normal" if vat_rate <= 0.05 else "high",
                details={
                    "taxable_sales": financial_data.taxable_sales,
                    "output_tax": financial_data.output_tax,
                    "input_tax": financial_data.input_tax,
                    "vat_rate": financial_data.vat_rate
                }
            ))
            
            if calculated_vat > financial_data.taxable_sales * 0.05:
                risk_alerts.append("增值税税负率略高于行业平均水平，建议关注进项发票管理")
            
            if financial_data.input_tax < financial_data.output_tax * 0.7:
                risk_alerts.append("进项税额抵扣不足，建议核查进项发票获取情况")
                recommendations.append("建议加强供应商管理，确保取得足额增值税专用发票")
        
        if request.include_corporate_tax:
            calculated_corporate_tax = financial_data.calculated_corporate_tax
            effective_rate = calculated_corporate_tax / financial_data.taxable_income if financial_data.taxable_income > 0 else 0
            
            tax_results.append(TaxCalculationResult(
                tax_type="企业所得税",
                tax_amount=calculated_corporate_tax,
                effective_rate=round(effective_rate * 100, 2),
                tax_benchmark=2.5,
                status="normal" if effective_rate <= 0.1 else "high",
                details={
                    "taxable_income": financial_data.taxable_income,
                    "corporate_tax_rate": financial_data.corporate_tax_rate,
                    "is_small_enterprise": financial_data.is_small_enterprise
                }
            ))
            
            if financial_data.is_small_enterprise:
                recommendations.append("已享受小微企业税收优惠政策，继续关注最新政策动态")
            
            if financial_data.deductible_expenses < financial_data.total_expenses * 0.8:
                risk_alerts.append("部分支出可能无法税前抵扣，建议规范发票管理")
                recommendations.append("建议审查成本结构，确保所有合规支出取得合法凭证")
        
        if request.include_personal_tax:
            if financial_data.total_payroll > 0:
                tax_results.append(TaxCalculationResult(
                    tax_type="个人所得税（代扣代缴）",
                    tax_amount=0.0,
                    effective_rate=0.0,
                    status="info",
                    details={
                        "total_payroll": financial_data.total_payroll,
                        "special_deductions": financial_data.special_deductions
                    }
                ))
                
                recommendations.append("建议为员工办理专项附加扣除信息采集，降低员工税负")
        
        total_tax = sum(r.tax_amount for r in tax_results)
        tax_burden_rate = financial_data.tax_burden_rate
        
        tax_burden_analysis = {
            "burden_rate": tax_burden_rate,
            "benchmark": 10.0,
            "status": "normal" if tax_burden_rate <= 12.0 else "high",
            "description": f"当前税负率为{tax_burden_rate}%，{'低于' if tax_burden_rate < 12.0 else '高于'}行业平均水平的12%"
        }
        
        if not recommendations:
            recommendations.append("继续保持良好的税务合规管理，定期进行税务健康检查")
        
        data_fields = [
            financial_data.total_revenue,
            financial_data.taxable_sales,
            financial_data.input_tax,
            financial_data.output_tax,
            financial_data.taxable_income
        ]
        data_completeness = sum(1 for f in data_fields if f > 0) / len(data_fields)
        
        logger.info(f"Tax query successful: user={user.id}, fiscal_year={fiscal_year}, total_tax={total_tax}")
        
        return TaxQueryResponse(
            fiscal_year=fiscal_year,
            query_time=datetime.now(),
            financial_summary={
                "total_revenue": financial_data.total_revenue,
                "taxable_sales": financial_data.taxable_sales,
                "total_expenses": financial_data.total_expenses,
                "taxable_income": financial_data.taxable_income,
                "data_status": financial_data.data_status
            },
            tax_results=tax_results,
            total_tax_amount=total_tax,
            tax_burden_analysis=tax_burden_analysis,
            risk_alerts=risk_alerts,
            recommendations=recommendations,
            data_status=financial_data.data_status,
            data_completeness=round(data_completeness, 2)
        )
    
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Tax query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Tax query failed")


@router.get("/history/{record_id}")
async def get_financial_data_history(
    record_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取财务数据修改历史"""
    try:
        record_result = await db.execute(
            select(UserFinancialData).where(
                and_(
                    UserFinancialData.id == record_id,
                    UserFinancialData.user_id == user.id,
                    UserFinancialData.tenant_id == user.tenant_id
                )
            )
        )
        if not record_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="财务数据不存在")
        
        history_result = await db.execute(
            select(FinancialDataHistory).where(
                FinancialDataHistory.financial_data_id == record_id
            ).order_by(FinancialDataHistory.modified_at.desc())
        )
        history = history_result.scalars().all()
        
        return {
            "record_id": record_id,
            "history": [
                {
                    "id": str(h.id),
                    "modified_at": h.modified_at.isoformat(),
                    "previous_data": h.previous_data,
                    "new_data": h.new_data,
                    "change_reason": h.change_reason
                }
                for h in history
            ]
        }
    
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to query modification history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query modification history")


@router.post("/upload-excel-intelligent")
async def upload_financial_data_excel_intelligent(
    file: UploadFile = File(..., description="Excel文件，支持.xlsx或.xls格式"),
    fiscal_year: int = Query(None, ge=2000, le=2100, description="财务年度（可选，自动从Excel读取）"),
    period_type: str = Query("yearly", description="周期类型: yearly/quarterly/monthly"),
    overwrite_existing: bool = Query(False, description="是否覆盖已存在的数据"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    智能上传Excel文件录入财务数据

    - 自动识别Excel列名，支持各种命名格式
    - 支持中文、英文列名及变体
    - 智能提取财务数据，无需严格按模板格式
    - 如果某些必需列无法识别，会返回提示信息
    """
    logger.info(f"Received intelligent Excel upload request: user={user.id}, filename={file.filename}")
    
    import time
    start_time = time.time()

    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="只支持.xlsx或.xls格式的Excel文件"
            )

        content = await file.read()

        try:
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
        except Exception as e:
            logger.error(f"Excel file parsing failed: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Excel文件格式错误，无法解析: {str(e)}"
            )

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="Excel文件中没有数据"
            )

        original_columns = list(df.columns)
        df.columns = df.columns.str.strip()

        detected_mapping = auto_detect_columns(original_columns)

        detected_info = {
            field: {
                'detected': detected_mapping[field] is not None,
                'excel_column': detected_mapping[field],
                'required': config['required'],
                'field_name_cn': COLUMN_MAPPING[field]['synonyms'][0] if COLUMN_MAPPING[field]['synonyms'] else field
            }
            for field, config in COLUMN_MAPPING.items()
        }

        missing_required = [
            f"{info['field_name_cn']}（{info['excel_column'] or '未找到'}）"
            for field, info in detected_info.items()
            if info['required'] and not info['detected']
        ]

        if missing_required:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Excel中缺少必需列，无法自动识别",
                    "missing_columns": missing_required,
                    "detected_columns": {k: v['excel_column'] for k, v in detected_info.items()},
                    "hint": "请确保Excel包含以下列：总收入、应税销售额、免税销售额、总支出、可抵扣支出、不可抵扣支出、进项税额、销项税额、增值税率、应纳税所得额、企业所得税率、财务年度"
                }
            )

        df = remap_dataframe_columns(df, detected_mapping)

        validation_errors = []
        parsed_data = []

        for idx, row in df.iterrows():
            row_num = idx + 2

            try:
                year = row.get('fiscal_year')
                if pd.isna(year) or year is None:
                    if fiscal_year:
                        year = fiscal_year
                    else:
                        validation_errors.append({
                            "row": row_num,
                            "field": "fiscal_year",
                            "message": "财务年度未填写且未提供默认值"
                        })
                        continue
                else:
                    year = int(year)

                if not (2000 <= year <= 2100):
                    validation_errors.append({
                        "row": row_num,
                        "field": "fiscal_year",
                        "message": f"财务年度 {year} 超出有效范围(2000-2100)"
                    })
                    continue

                row_data = {
                    'fiscal_year': year,
                    'period_type': str(row.get('period_type', period_type)),
                    'period_start': str(row.get('period_start', '')),
                    'period_end': str(row.get('period_end', '')),
                    'total_revenue': float(row.get('total_revenue', 0) or 0),
                    'taxable_sales': float(row.get('taxable_sales', 0) or 0),
                    'tax_free_sales': float(row.get('tax_free_sales', 0) or 0),
                    'total_expenses': float(row.get('total_expenses', 0) or 0),
                    'deductible_expenses': float(row.get('deductible_expenses', 0) or 0),
                    'non_deductible_expenses': float(row.get('non_deductible_expenses', 0) or 0),
                    'input_tax': float(row.get('input_tax', 0) or 0),
                    'output_tax': float(row.get('output_tax', 0) or 0),
                    'vat_rate': float(row.get('vat_rate', 0.13) or 0.13),
                    'taxable_income': float(row.get('taxable_income', 0) or 0),
                    'corporate_tax_rate': float(row.get('corporate_tax_rate', 0.25) or 0.25),
                    'is_small_enterprise': bool(row.get('is_small_enterprise', False)),
                    'total_payroll': float(row.get('total_payroll', 0) or 0),
                    'special_deductions': float(row.get('special_deductions', 0) or 0),
                    'total_invoices': int(row.get('total_invoices', 0) or 0),
                    'input_invoice_count': int(row.get('input_invoice_count', 0) or 0),
                    'output_invoice_count': int(row.get('output_invoice_count', 0) or 0)
                }

                if row_data['period_type'] not in ['yearly', 'quarterly', 'monthly']:
                    row_data['period_type'] = 'yearly'

                if row_data['total_revenue'] < 0:
                    validation_errors.append({
                        "row": row_num,
                        "field": "total_revenue",
                        "message": f"总收入({row_data['total_revenue']})不能为负数"
                    })
                    continue

                if row_data['vat_rate'] < 0 or row_data['vat_rate'] > 1:
                    validation_errors.append({
                        "row": row_num,
                        "field": "vat_rate",
                        "message": f"增值税率({row_data['vat_rate']})必须在0-1之间"
                    })
                    continue

                if row_data['corporate_tax_rate'] < 0 or row_data['corporate_tax_rate'] > 1:
                    validation_errors.append({
                        "row": row_num,
                        "field": "corporate_tax_rate",
                        "message": f"企业所得税率({row_data['corporate_tax_rate']})必须在0-1之间"
                    })
                    continue

                parsed_data.append((row_num, row_data))

            except (ValueError, TypeError) as e:
                validation_errors.append({
                    "row": row_num,
                    "field": "unknown",
                    "message": f"数据类型错误: {str(e)}"
                })
                continue

        if validation_errors and not parsed_data:
            return {
                "success": False,
                "message": f"所有数据行验证失败，共{len(validation_errors)} errors",
                "detected_columns": {k: v['excel_column'] for k, v in detected_info.items()},
                "validation_errors": validation_errors
            }

        file_id = str(uuid4())
        created_records = 0
        updated_records = 0
        skipped_records = []

        for row_num, data in parsed_data:
            try:
                from dateutil.parser import parse as parse_date

                period_start_dt = None
                period_end_dt = None

                if data['period_start'] and data['period_start'] != 'nan':
                    try:
                        period_start_dt = parse_date(str(data['period_start'])).date()
                    except Exception:
                        period_start_dt = datetime.strptime(str(data['period_start']), '%Y-%m-%d').date()
                else:
                    if data['period_type'] == 'yearly':
                        period_start_dt = datetime.strptime(f"{data['fiscal_year']}-01-01", '%Y-%m-%d').date()
                        period_end_dt = datetime.strptime(f"{data['fiscal_year']}-12-31", '%Y-%m-%d').date()
                    elif data['period_type'] == 'quarterly':
                        period_start_dt = datetime.strptime(f"{data['fiscal_year']}-01-01", '%Y-%m-%d').date()
                        period_end_dt = datetime.strptime(f"{data['fiscal_year']}-03-31", '%Y-%m-%d').date()

                if data['period_end'] and data['period_end'] != 'nan':
                    try:
                        period_end_dt = parse_date(str(data['period_end'])).date()
                    except Exception:
                        period_end_dt = datetime.strptime(str(data['period_end']), '%Y-%m-%d').date()

                existing = await db.execute(
                    select(UserFinancialData).where(
                        and_(
                            UserFinancialData.user_id == user.id,
                            UserFinancialData.tenant_id == user.tenant_id,
                            UserFinancialData.fiscal_year == data['fiscal_year'],
                            UserFinancialData.period_type == data['period_type'],
                            UserFinancialData.period_start == period_start_dt
                        )
                    )
                )
                existing_record = existing.scalar_one_or_none()

                if existing_record:
                    if overwrite_existing:
                        for field, value in data.items():
                            if field not in ['fiscal_year', 'period_type']:
                                setattr(existing_record, field, value)
                        existing_record.data_source = DataSourceEnum.UPLOAD.value
                        existing_record.source_file_id = UUID(file_id)
                        existing_record.updated_at = datetime.now()
                        updated_records += 1
                    else:
                        skipped_records.append(f"{data['fiscal_year']}年的{data['period_type']}数据已存在")
                else:
                    new_record = UserFinancialData(
                        user_id=user.id,
                        tenant_id=user.tenant_id,
                        fiscal_year=data['fiscal_year'],
                        period_type=data['period_type'],
                        period_start=period_start_dt or datetime.strptime(f"{data['fiscal_year']}-01-01", '%Y-%m-%d').date(),
                        period_end=period_end_dt or datetime.strptime(f"{data['fiscal_year']}-12-31", '%Y-%m-%d').date(),
                        total_revenue=data['total_revenue'],
                        taxable_sales=data['taxable_sales'],
                        tax_free_sales=data['tax_free_sales'],
                        total_expenses=data['total_expenses'],
                        deductible_expenses=data['deductible_expenses'],
                        non_deductible_expenses=data['non_deductible_expenses'],
                        input_tax=data['input_tax'],
                        output_tax=data['output_tax'],
                        vat_rate=data['vat_rate'],
                        taxable_income=data['taxable_income'],
                        corporate_tax_rate=data['corporate_tax_rate'],
                        is_small_enterprise=data['is_small_enterprise'],
                        total_payroll=data['total_payroll'],
                        special_deductions=data['special_deductions'],
                        total_invoices=data['total_invoices'],
                        input_invoice_count=data['input_invoice_count'],
                        output_invoice_count=data['output_invoice_count'],
                        data_source=DataSourceEnum.UPLOAD.value,
                        source_file_id=UUID(file_id),
                        data_status="draft"
                    )
                    db.add(new_record)
                    created_records += 1

            except Exception as e:
                logger.error(f"Error processing data row: {str(e)}")
                validation_errors.append({
                    "row": row_num,
                    "field": "system",
                    "message": f"处理数据时出错: {str(e)}"
                })
                continue

        await db.commit()

        processing_time = time.time() - start_time

        logger.info(
            f"智能Excel数据导入成功: user={user.id}, "
            f"file_id={file_id}, "
            f"created={created_records}, "
            f"updated={updated_records}, "
            f"skipped={len(skipped_records)}, "
            f"errors={len(validation_errors)}, "
            f"processing_time={processing_time:.2f}s"
        )
        
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.FINANCIAL_DOC_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="user_financial_data",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename,
                "file_size": len(content),
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "overwrite_existing": overwrite_existing,
                "file_id": file_id,
                "records_created": created_records,
                "records_updated": updated_records,
                "records_skipped": len(skipped_records),
                "validation_errors_count": len(validation_errors),
                "result": "success",
                "processing_time": f"{processing_time:.2f}s",
                "upload_timestamp": datetime.now().isoformat()
            },
            risk_level="low"
        )

        return {
            "success": True,
            "message": f"成功导入{created_records}条记录，更新{updated_records}条记录" +
                      (f"，跳过{len(skipped_records)}条" if skipped_records else "") +
                      (f"，有{len(validation_errors)}个警告" if validation_errors else ""),
            "detected_columns": {k: v['excel_column'] for k, v in detected_info.items()},
            "records_created": created_records,
            "records_updated": updated_records,
            "records_skipped": len(skipped_records),
            "validation_errors": validation_errors
        }

    except HTTPException:
        processing_time = time.time() - start_time
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.FINANCIAL_DOC_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="user_financial_data",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename if file else "unknown",
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "result": "failed",
                "error_type": "HTTPException",
                "processing_time": f"{processing_time:.2f}s",
                "upload_timestamp": datetime.now().isoformat()
            },
            risk_level="low"
        )
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Intelligent Excel upload processing failed: {str(e)}", exc_info=True)
        
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.FINANCIAL_DOC_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="user_financial_data",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename if file else "unknown",
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "result": "failed",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "processing_time": f"{processing_time:.2f}s",
                "upload_timestamp": datetime.now().isoformat()
            },
            risk_level="medium"
        )
        raise HTTPException(status_code=500, detail=f"处理Excel文件失败: {str(e)}")


@router.post("/upload-excel", response_model=ExcelUploadResponse)
async def upload_financial_data_excel(
    file: UploadFile = File(..., description="Excel文件，仅支持.xlsx格式"),
    fiscal_year: int = Query(..., ge=2000, le=2100, description="财务年度"),
    period_type: str = Query("yearly", description="周期类型: yearly/quarterly/monthly"),
    period_start: str = Query(..., description="周期开始日期 (YYYY-MM-DD)"),
    period_end: str = Query(..., description="周期结束日期 (YYYY-MM-DD)"),
    overwrite_existing: bool = Query(False, description="是否覆盖已存在的数据"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传Excel文件录入财务数据

    - 接收.xlsx格式的Excel文件
    - 提取并验证财务数据
    - 支持批量录入多个期间的财务数据
    - 如果数据格式或内容错误，返回详细的错误信息
    """
    logger.info(f"Received Excel upload request: user={user.id}, fiscal_year={fiscal_year}, filename={file.filename}")
    
    import time
    start_time = time.time()

    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="只支持.xlsx或.xls格式的Excel文件"
            )

        content = await file.read()

        try:
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
        except Exception as e:
            logger.error(f"Excel file parsing failed: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Excel文件格式错误，无法解析: {str(e)}"
            )

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="Excel文件中没有数据"
            )

        validation_errors = []
        parsed_data = []

        required_columns = {
            'fiscal_year': '财务年度',
            'period_type': '周期类型',
            'period_start': '周期开始日期',
            'period_end': '周期结束日期',
            'total_revenue': '总收入',
            'taxable_sales': '应税销售额',
            'tax_free_sales': '免税销售额',
            'total_expenses': '总支出',
            'deductible_expenses': '可抵扣支出',
            'non_deductible_expenses': '不可抵扣支出',
            'input_tax': '进项税额',
            'output_tax': '销项税额',
            'vat_rate': '增值税率',
            'taxable_income': '应纳税所得额',
            'corporate_tax_rate': '企业所得税率',
            'is_small_enterprise': '是否小微企业',
            'total_payroll': '工资薪金总额',
            'special_deductions': '专项附加扣除',
            'total_invoices': '发票总数',
            'input_invoice_count': '进项发票数',
            'output_invoice_count': '销项发票数'
        }

        df.columns = df.columns.str.strip()

        missing_columns = [col for col in required_columns.keys() if col not in df.columns]
        if missing_columns:
            missing_names = [required_columns[col] for col in missing_columns]
            raise HTTPException(
                status_code=400,
                detail=f"Excel文件缺少必需列: {', '.join(missing_names)}"
            )

        for idx, row in df.iterrows():
            row_num = idx + 2

            try:
                row_data = {
                    'fiscal_year': int(row.get('fiscal_year', fiscal_year)),
                    'period_type': str(row.get('period_type', period_type)),
                    'period_start': str(row.get('period_start', period_start)),
                    'period_end': str(row.get('period_end', period_end)),
                    'total_revenue': float(row.get('total_revenue', 0)),
                    'taxable_sales': float(row.get('taxable_sales', 0)),
                    'tax_free_sales': float(row.get('tax_free_sales', 0)),
                    'total_expenses': float(row.get('total_expenses', 0)),
                    'deductible_expenses': float(row.get('deductible_expenses', 0)),
                    'non_deductible_expenses': float(row.get('non_deductible_expenses', 0)),
                    'input_tax': float(row.get('input_tax', 0)),
                    'output_tax': float(row.get('output_tax', 0)),
                    'vat_rate': float(row.get('vat_rate', 0.13)),
                    'taxable_income': float(row.get('taxable_income', 0)),
                    'corporate_tax_rate': float(row.get('corporate_tax_rate', 0.25)),
                    'is_small_enterprise': bool(row.get('is_small_enterprise', False)),
                    'total_payroll': float(row.get('total_payroll', 0)),
                    'special_deductions': float(row.get('special_deductions', 0)),
                    'total_invoices': int(row.get('total_invoices', 0)),
                    'input_invoice_count': int(row.get('input_invoice_count', 0)),
                    'output_invoice_count': int(row.get('output_invoice_count', 0))
                }

                if not (2000 <= row_data['fiscal_year'] <= 2100):
                    validation_errors.append(f"第{row_num}行: 财务年度必须在2000-2100之间")
                    continue

                if row_data['period_type'] not in ['yearly', 'quarterly', 'monthly']:
                    validation_errors.append(f"第{row_num}行: 周期类型必须是yearly/quarterly/monthly之一")
                    continue

                if row_data['total_revenue'] < 0:
                    validation_errors.append(f"第{row_num}行: 总收入不能为负数")
                    continue

                if row_data['taxable_sales'] < 0:
                    validation_errors.append(f"第{row_num}行: 应税销售额不能为负数")
                    continue

                if row_data['tax_free_sales'] < 0:
                    validation_errors.append(f"第{row_num}行: 免税销售额不能为负数")
                    continue

                if row_data['vat_rate'] < 0 or row_data['vat_rate'] > 1:
                    validation_errors.append(f"第{row_num}行: 增值税率必须在0-1之间")
                    continue

                if row_data['corporate_tax_rate'] < 0 or row_data['corporate_tax_rate'] > 1:
                    validation_errors.append(f"第{row_num}行: 企业所得税率必须在0-1之间")
                    continue

                if row_data['input_tax'] < 0:
                    validation_errors.append(f"第{row_num}行: 进项税额不能为负数")
                    continue

                if row_data['output_tax'] < 0:
                    validation_errors.append(f"第{row_num}行: 销项税额不能为负数")
                    continue

                if row_data['total_revenue'] < row_data['taxable_sales'] + row_data['tax_free_sales']:
                    validation_errors.append(
                        f"第{row_num}行: 总收入({row_data['total_revenue']})应大于等于应税销售额({row_data['taxable_sales']})加免税销售额({row_data['tax_free_sales']})"
                    )
                    continue

                if row_data['total_expenses'] < row_data['deductible_expenses'] + row_data['non_deductible_expenses']:
                    validation_errors.append(
                        f"第{row_num}行: 总支出({row_data['total_expenses']})应大于等于可抵扣支出({row_data['deductible_expenses']})加不可抵扣支出({row_data['non_deductible_expenses']})"
                    )
                    continue

                parsed_data.append(row_data)

            except (ValueError, TypeError) as e:
                validation_errors.append(f"第{row_num}行: 数据类型错误 - {str(e)}")
                continue

        if validation_errors:
            logger.warning(f"Excel data validation failed: {len(validation_errors)} errors")
            return ExcelUploadResponse(
                success=False,
                message=f"Excel data validation failed，发现{len(validation_errors)} errors",
                file_id=None,
                preview_data=None,
                validation_errors=validation_errors
            )

        if not parsed_data:
            raise HTTPException(
                status_code=400,
                detail="Excel文件中没有有效的财务数据"
            )

        file_id = str(uuid4())
        created_records = []
        skipped_records = []

        for data in parsed_data:
            try:
                existing = await db.execute(
                    select(UserFinancialData).where(
                        and_(
                            UserFinancialData.user_id == user.id,
                            UserFinancialData.tenant_id == user.tenant_id,
                            UserFinancialData.fiscal_year == data['fiscal_year'],
                            UserFinancialData.period_type == data['period_type']
                        )
                    )
                )
                existing_record = existing.scalar_one_or_none()

                if existing_record:
                    if overwrite_existing:
                        for field, value in data.items():
                            if field not in ['fiscal_year', 'period_type']:
                                setattr(existing_record, field, value)
                        existing_record.data_source = DataSourceEnum.UPLOAD.value
                        existing_record.source_file_id = UUID(file_id)
                        existing_record.updated_at = datetime.now()
                        created_records.append(existing_record)
                    else:
                        skipped_records.append(
                            f"{data['fiscal_year']}年的{data['period_type']}数据已存在"
                        )
                else:
                    from dateutil.parser import parse as parse_date

                    period_start_dt = parse_date(data['period_start']).date()
                    period_end_dt = parse_date(data['period_end']).date()

                    new_record = UserFinancialData(
                        user_id=user.id,
                        tenant_id=user.tenant_id,
                        fiscal_year=data['fiscal_year'],
                        period_type=data['period_type'],
                        period_start=period_start_dt,
                        period_end=period_end_dt,
                        total_revenue=data['total_revenue'],
                        taxable_sales=data['taxable_sales'],
                        tax_free_sales=data['tax_free_sales'],
                        total_expenses=data['total_expenses'],
                        deductible_expenses=data['deductible_expenses'],
                        non_deductible_expenses=data['non_deductible_expenses'],
                        input_tax=data['input_tax'],
                        output_tax=data['output_tax'],
                        vat_rate=data['vat_rate'],
                        taxable_income=data['taxable_income'],
                        corporate_tax_rate=data['corporate_tax_rate'],
                        is_small_enterprise=data['is_small_enterprise'],
                        total_payroll=data['total_payroll'],
                        special_deductions=data['special_deductions'],
                        total_invoices=data['total_invoices'],
                        input_invoice_count=data['input_invoice_count'],
                        output_invoice_count=data['output_invoice_count'],
                        data_source=DataSourceEnum.UPLOAD.value,
                        source_file_id=UUID(file_id),
                        data_status="draft"
                    )
                    db.add(new_record)
                    created_records.append(new_record)

            except Exception as e:
                logger.error(f"Error processing data row: {str(e)}")
                validation_errors.append(f"处理数据时出错: {str(e)}")
                continue

        await db.commit()

        for record in created_records:
            await db.refresh(record)

        processing_time = time.time() - start_time

        logger.info(
            f"Excel数据导入成功: user={user.id}, "
            f"file_id={file_id}, "
            f"created={len(created_records)}, "
            f"skipped={len(skipped_records)}, "
            f"processing_time={processing_time:.2f}s"
        )
        
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.FINANCIAL_DOC_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="user_financial_data",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename,
                "file_size": len(content),
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "period_start": period_start,
                "period_end": period_end,
                "overwrite_existing": overwrite_existing,
                "file_id": file_id,
                "records_created": len(created_records),
                "records_skipped": len(skipped_records),
                "validation_errors_count": len(validation_errors),
                "result": "success",
                "processing_time": f"{processing_time:.2f}s",
                "upload_timestamp": datetime.now().isoformat()
            },
            risk_level="low"
        )

        preview = parsed_data[0] if parsed_data else None

        return ExcelUploadResponse(
            success=True,
            message=f"成功导入{len(created_records)}条财务数据记录" +
                   (f"，跳过{len(skipped_records)}条已存在的数据" if skipped_records else ""),
            file_id=file_id,
            preview_data=preview,
            validation_errors=skipped_records if skipped_records else []
        )

    except HTTPException:
        processing_time = time.time() - start_time
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.FINANCIAL_DOC_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="user_financial_data",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename if file else "unknown",
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "result": "failed",
                "error_type": "HTTPException",
                "processing_time": f"{processing_time:.2f}s",
                "upload_timestamp": datetime.now().isoformat()
            },
            risk_level="low"
        )
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Excel file upload failed: {str(e)}", exc_info=True)
        
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.FINANCIAL_DOC_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="user_financial_data",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename if file else "unknown",
                "fiscal_year": fiscal_year,
                "period_type": period_type,
                "result": "failed",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "processing_time": f"{processing_time:.2f}s",
                "upload_timestamp": datetime.now().isoformat()
            },
            risk_level="medium"
        )
        raise HTTPException(status_code=500, detail=f"Excel file upload failed: {str(e)}")
