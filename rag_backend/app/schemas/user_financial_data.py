"""
用户财务数据相关 Pydantic Schema 定义
"""

from typing import Optional, List, Dict, Any, Union, ClassVar
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from enum import Enum


class DataStatusEnum(str, Enum):
    """数据状态枚举"""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    FINAL = "final"


class DataSourceEnum(str, Enum):
    """数据来源枚举"""
    MANUAL = "manual"
    UPLOAD = "upload"
    AUTO = "auto"


class PeriodTypeEnum(str, Enum):
    """周期类型枚举"""
    YEARLY = "yearly"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"


class TaxCalculationResult(BaseModel):
    """税务计算结果"""
    tax_type: str = Field(..., description="税种类型")
    tax_amount: float = Field(..., description="税额")
    effective_rate: float = Field(..., description="实际税率")
    tax_benchmark: Optional[float] = Field(None, description="税负基准")
    status: str = Field(..., description="状态")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")


class FinancialDataCreate(BaseModel):
    """创建财务数据请求"""
    fiscal_year: int = Field(..., ge=2000, le=2100, description="财务年度")
    
    # 周期类型
    period_type: PeriodTypeEnum = Field(PeriodTypeEnum.YEARLY, description="周期类型: yearly/quarterly/monthly")
    
    # 周期开始和结束日期
    period_start: date = Field(..., description="周期开始日期")
    period_end: date = Field(..., description="周期结束日期")
    
    # 收入数据
    total_revenue: float = Field(0.0, ge=0, description="总收入")
    taxable_sales: float = Field(0.0, ge=0, description="应税销售额")
    tax_free_sales: float = Field(0.0, ge=0, description="免税销售额")
    
    # 支出和成本
    total_expenses: float = Field(0.0, ge=0, description="总支出")
    deductible_expenses: float = Field(0.0, ge=0, description="可抵扣支出")
    non_deductible_expenses: float = Field(0.0, ge=0, description="不可抵扣支出")
    
    # 税务数据
    input_tax: float = Field(0.0, ge=0, description="进项税额")
    output_tax: float = Field(0.0, ge=0, description="销项税额")
    vat_rate: float = Field(0.13, ge=0, le=1, description="增值税率")
    
    # 企业所得税相关
    taxable_income: float = Field(0.0, ge=0, description="应纳税所得额")
    corporate_tax_rate: float = Field(0.25, ge=0, le=1, description="企业所得税率")
    is_small_enterprise: bool = Field(False, description="是否小微企业")
    
    # 个人所得税相关
    total_payroll: float = Field(0.0, ge=0, description="工资薪金总额")
    special_deductions: float = Field(0.0, ge=0, description="专项附加扣除")
    
    # 成本结构明细
    cost_breakdown: Optional[Dict[str, float]] = Field(None, description="成本结构明细")
    
    # 发票统计
    total_invoices: int = Field(0, ge=0, description="发票总数")
    input_invoice_count: int = Field(0, ge=0, description="进项发票数")
    output_invoice_count: int = Field(0, ge=0, description="销项发票数")
    
    # 数据来源
    data_source: DataSourceEnum = Field(DataSourceEnum.MANUAL, description="数据来源")
    notes: Optional[str] = Field(None, description="备注说明")
    
    @model_validator(mode="after")
    def validate_period(self) -> "FinancialDataCreate":
        if self.period_start >= self.period_end:
            raise ValueError("周期开始日期必须早于结束日期")
        if self.period_start.year != self.fiscal_year:
            raise ValueError(f"周期开始日期年份({self.period_start.year})必须与财务年度({self.fiscal_year})一致")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fiscal_year": 2024,
                "period_type": "quarterly",
                "period_start": "2024-01-01",
                "period_end": "2024-03-31",
                "total_revenue": 1250000.0,
                "taxable_sales": 1125000.0,
                "tax_free_sales": 125000.0,
                "deductible_expenses": 750000.0,
                "input_tax": 97500.0,
                "output_tax": 146250.0,
                "vat_rate": 0.13,
                "taxable_income": 375000.0,
                "is_small_enterprise": False
            }
        }
    )


class FinancialDataUpdate(BaseModel):
    """更新财务数据请求"""
    total_revenue: Optional[float] = Field(None, ge=0, description="总收入")
    taxable_sales: Optional[float] = Field(None, ge=0, description="应税销售额")
    tax_free_sales: Optional[float] = Field(None, ge=0, description="免税销售额")
    total_expenses: Optional[float] = Field(None, ge=0, description="总支出")
    deductible_expenses: Optional[float] = Field(None, ge=0, description="可抵扣支出")
    non_deductible_expenses: Optional[float] = Field(None, ge=0, description="不可抵扣支出")
    input_tax: Optional[float] = Field(None, ge=0, description="进项税额")
    output_tax: Optional[float] = Field(None, ge=0, description="销项税额")
    vat_rate: Optional[float] = Field(None, ge=0, le=1, description="增值税率")
    taxable_income: Optional[float] = Field(None, ge=0, description="应纳税所得额")
    corporate_tax_rate: Optional[float] = Field(None, ge=0, le=1, description="企业所得税率")
    is_small_enterprise: Optional[bool] = Field(None, description="是否小微企业")
    total_payroll: Optional[float] = Field(None, ge=0, description="工资薪金总额")
    special_deductions: Optional[float] = Field(None, ge=0, description="专项附加扣除")
    cost_breakdown: Optional[Dict[str, float]] = Field(None, description="成本结构明细")
    total_invoices: Optional[int] = Field(None, ge=0, description="发票总数")
    input_invoice_count: Optional[int] = Field(None, ge=0, description="进项发票数")
    output_invoice_count: Optional[int] = Field(None, ge=0, description="销项发票数")
    data_status: Optional[DataStatusEnum] = Field(None, description="数据状态")
    notes: Optional[str] = Field(None, description="备注说明")


class FinancialDataResponse(BaseModel):
    """财务数据响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Union[str, UUID] = Field(..., description="财务数据ID")
    user_id: Union[str, UUID] = Field(..., description="用户ID")
    tenant_id: str = Field(..., description="租户ID")
    fiscal_year: int = Field(..., description="财务年度")
    
    # 周期信息
    period_type: str = Field(..., description="周期类型: yearly/quarterly/monthly")
    period_start: date = Field(..., description="周期开始日期")
    period_end: date = Field(..., description="周期结束日期")
    
    # 收入数据
    total_revenue: float = Field(..., description="总收入")
    taxable_sales: float = Field(..., description="应税销售额")
    tax_free_sales: float = Field(..., description="免税销售额")
    
    # 支出和成本
    total_expenses: float = Field(..., description="总支出")
    deductible_expenses: float = Field(..., description="可抵扣支出")
    non_deductible_expenses: float = Field(..., description="不可抵扣支出")
    
    # 税务数据
    input_tax: float = Field(..., description="进项税额")
    output_tax: float = Field(..., description="销项税额")
    vat_rate: float = Field(..., description="增值税率")
    calculated_vat: float = Field(..., description="计算得出的增值税")
    
    # 企业所得税
    taxable_income: float = Field(..., description="应纳税所得额")
    corporate_tax_rate: float = Field(..., description="企业所得税率")
    is_small_enterprise: bool = Field(..., description="是否小微企业")
    calculated_corporate_tax: float = Field(..., description="计算得出的企业所得税")
    
    # 个人所得税
    total_payroll: float = Field(..., description="工资薪金总额")
    special_deductions: float = Field(..., description="专项附加扣除")
    
    # 发票统计
    total_invoices: int = Field(..., description="发票总数")
    input_invoice_count: int = Field(..., description="进项发票数")
    output_invoice_count: int = Field(..., description="销项发票数")
    
    # 数据状态
    data_status: str = Field(..., description="数据状态")
    data_source: str = Field(..., description="数据来源")
    
    # 税负分析
    tax_burden_rate: float = Field(..., description="整体税负率")
    
    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    @field_validator('id', 'user_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    json_schema_extra: ClassVar = {
        "example": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "user-uuid",
            "tenant_id": "tenant-uuid",
                "fiscal_year": 2024,
                "period_type": "quarterly",
                "period_start": "2024-01-01",
                "period_end": "2024-03-31",
                "total_revenue": 1250000.0,
                "calculated_vat": 48750.0,
                "calculated_corporate_tax": 9375.0,
                "tax_burden_rate": 11.4
            }
        }


class TaxQueryRequest(BaseModel):
    """税务查询请求"""
    fiscal_year: Optional[int] = Field(None, ge=2000, le=2100, description="财务年度，不填则查询今年")
    include_vat: bool = Field(True, description="是否包含增值税")
    include_corporate_tax: bool = Field(True, description="是否包含企业所得税")
    include_personal_tax: bool = Field(False, description="是否包含个人所得税")
    include_recommendations: bool = Field(True, description="是否包含筹划建议")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fiscal_year": 2024,
                "include_vat": True,
                "include_corporate_tax": True,
                "include_personal_tax": False,
                "include_recommendations": True
            }
        }
    )


class TaxQueryResponse(BaseModel):
    """税务查询响应"""
    fiscal_year: int = Field(..., description="财务年度")
    query_time: datetime = Field(..., description="查询时间")
    
    # 财务数据摘要
    financial_summary: Dict[str, Any] = Field(..., description="财务数据摘要")
    
    # 税务计算结果
    tax_results: List[TaxCalculationResult] = Field(..., description="税务计算结果")
    
    # 总税额
    total_tax_amount: float = Field(..., description="总税额")
    
    # 税负分析
    tax_burden_analysis: Dict[str, Any] = Field(..., description="税负分析")
    
    # 风险提示
    risk_alerts: List[str] = Field(default_factory=list, description="风险提示")
    
    # 筹划建议
    recommendations: List[str] = Field(default_factory=list, description="筹划建议")
    
    # 数据状态
    data_status: str = Field(..., description="数据状态")
    data_completeness: float = Field(..., ge=0, le=1, description="数据完整度")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fiscal_year": 2024,
                "query_time": "2024-03-25T10:00:00Z",
                "tax_results": [
                    {
                        "tax_type": "增值税",
                        "tax_amount": 195000.0,
                        "effective_rate": 4.34,
                        "status": "normal"
                    },
                    {
                        "tax_type": "企业所得税",
                        "tax_amount": 375000.0,
                        "effective_rate": 7.5,
                        "status": "normal"
                    }
                ],
                "total_tax_amount": 570000.0,
                "tax_burden_analysis": {
                    "burden_rate": 11.4,
                    "benchmark": 10.0,
                    "status": "higher_than_benchmark"
                },
                "data_completeness": 0.95
            }
        }
    )


class FinancialDataListResponse(BaseModel):
    """财务数据列表响应"""
    items: List[FinancialDataResponse] = Field(..., description="财务数据列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")


class FinancialDataStatistics(BaseModel):
    """财务数据统计"""
    total_records: int = Field(..., description="总记录数")
    current_year_record: Optional[FinancialDataResponse] = Field(None, description="今年记录")
    previous_year_record: Optional[FinancialDataResponse] = Field(None, description="去年记录")
    year_over_year_growth: Dict[str, float] = Field(..., description="同比增长")
    tax_summary: Dict[str, float] = Field(..., description="税务汇总")


class ExcelUploadResponse(BaseModel):
    """Excel文件上传响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    file_id: Optional[str] = Field(None, description="文件ID")
    preview_data: Optional[Dict[str, Any]] = Field(None, description="数据预览")
    validation_errors: List[str] = Field(default_factory=list, description="验证错误列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "文件上传成功",
                "file_id": "550e8400-e29b-41d4-a716-446655440000",
                "preview_data": {
                    "fiscal_year": 2024,
                    "total_revenue": 1250000.0,
                    "taxable_sales": 1125000.0
                },
                "validation_errors": []
            }
        }


class ExcelValidationResult(BaseModel):
    """Excel数据验证结果"""
    is_valid: bool = Field(..., description="数据是否有效")
    row_number: int = Field(..., description="行号")
    field_name: str = Field(..., description="字段名称")
    error_message: str = Field(..., description="错误信息")
    error_type: str = Field(..., description="错误类型")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": False,
                "row_number": 2,
                "field_name": "fiscal_year",
                "error_message": "财务年度必须在2000-2100之间",
                "error_type": "range_error"
            }
        }


class ExcelUploadRequest(BaseModel):
    """Excel文件上传请求（用于预览和验证）"""
    fiscal_year: int = Field(..., ge=2000, le=2100, description="财务年度")
    period_type: PeriodTypeEnum = Field(PeriodTypeEnum.YEARLY, description="周期类型")
    period_start: date = Field(..., description="周期开始日期")
    period_end: date = Field(..., description="周期结束日期")
    overwrite_existing: bool = Field(False, description="是否覆盖已存在的数据")
    
    @model_validator(mode="after")
    def validate_period(self) -> "ExcelUploadRequest":
        if self.period_start >= self.period_end:
            raise ValueError("周期开始日期必须早于结束日期")
        if self.period_start.year != self.fiscal_year:
            raise ValueError(f"周期开始日期年份({self.period_start.year})必须与财务年度({self.fiscal_year})一致")
        return self
